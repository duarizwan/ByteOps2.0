"""Gmail background sync service.

Fetches unread emails from Gmail and writes them as Notification rows.
Runs on first connect (full scan, last 7 days) and on every scheduled
re-sync (incremental — only items newer than last_synced_at).

Key design decisions:
  - Direct Gmail API calls via httpx (not the MCP subprocess) for efficiency
    in headless background jobs.
  - Deduplication: checks metadata_->source_id before inserting so
    re-syncs never produce duplicate notifications.
  - Cap: hard limit of 200 notifications per user; oldest read ones are
    pruned when exceeded.
  - Notification failure never propagates — logged and skipped.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationPriority
from app.models.tool_connection import ConnectionStatus, ToolConnection
from app.services.sync.token_refresh import ensure_fresh_token

logger = logging.getLogger(__name__)

# Shared HTTP client — reused across all Gmail sync calls
_http_client = httpx.AsyncClient(timeout=15.0)

# Gmail API base
_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# Max notifications per user before pruning
_NOTIFICATION_CAP = 200

# Headers pulled from each message (avoids fetching full body)
_META_HEADERS = ["Subject", "From", "Date"]

# Labels that imply high priority
_HIGH_PRIORITY_LABELS = {"IMPORTANT", "STARRED"}


async def run_gmail_sync(
    connection: ToolConnection,
    db: AsyncSession,
) -> int:
    """Scan Gmail and write new Notification rows.

    Returns the count of new notifications written.

    Raises nothing — all errors are caught internally so the scheduler
    loop is never interrupted.
    """
    user_id: UUID = connection.user_id

    # ── 0. Guard: already syncing this connection? ────────────────────────────
    meta: dict = dict(connection.metadata_ or {})  # copy — never mutate in place
    if meta.get("is_syncing"):
        logger.info("Sync already in progress for gmail user=%s — skipping.", user_id)
        return 0

    # ── 1. Ensure fresh access token ──────────────────────────────────────────
    token_ok = await ensure_fresh_token(connection, db)
    if not token_ok:
        return 0

    # ── 2. Lock (prevent concurrent runs) ─────────────────────────────────────
    # Assign a NEW dict so SQLAlchemy detects the JSONB mutation
    connection.metadata_ = {**meta, "is_syncing": True}
    await db.commit()

    try:
        return await _do_sync(connection, db, user_id)
    except Exception:
        logger.exception("Gmail sync failed for user=%s", user_id)
        return 0
    finally:
        # ── Unlock ───────────────────────────────────────────────────────────
        # Re-read from DB first, then assign a fresh dict — same rule as above
        await db.refresh(connection)
        current_meta = dict(connection.metadata_ or {})
        connection.metadata_ = {
            **current_meta,
            "is_syncing": False,
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.commit()


async def _do_sync(
    connection: ToolConnection,
    db: AsyncSession,
    user_id: UUID,
) -> int:
    """Inner sync — separated so the finally block in run_gmail_sync is clean."""
    meta = connection.metadata_ or {}
    is_first_connect = "last_synced_at" not in meta

    # Build query string for Gmail
    if is_first_connect:
        query = "is:unread newer_than:7d"
    else:
        # Incremental: only unread emails since last sync
        last = meta["last_synced_at"]  # ISO string
        # Google accepts "after:YYYY/MM/DD"
        dt = datetime.fromisoformat(last)
        date_str = dt.strftime("%Y/%m/%d")
        query = f"is:unread after:{date_str}"

    headers = {"Authorization": f"Bearer {connection.access_token}"}

    # ── 3. List message IDs ───────────────────────────────────────────────
    list_resp = await _http_client.get(
        f"{_GMAIL_BASE}/messages",
        headers=headers,
        params={"q": query, "maxResults": 30},
    )
    if list_resp.status_code == 401:
        logger.warning("Gmail 401 for user=%s — token invalid.", user_id)
        connection.status = ConnectionStatus.EXPIRED
        await db.commit()
        return 0
    if list_resp.status_code != 200:
        logger.warning(
            "Gmail list failed %s for user=%s", list_resp.status_code, user_id
        )
        return 0

    messages = list_resp.json().get("messages", [])
    if not messages:
        logger.info("No new Gmail messages for user=%s", user_id)
        return 0

    new_count = 0

    for msg_stub in messages:
        msg_id: str = msg_stub["id"]

        # ── 4. Deduplication check ────────────────────────────────────────
        exists = await db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.source_tool == "gmail",
                Notification.metadata_["source_id"].astext() == msg_id,
            )
        )
        if exists.scalar_one_or_none():
            logger.info("Skipping msg_id=%s — already in DB", msg_id)
            continue  # Already surfaced this email

        logger.info("Found new msg_id=%s — fetching details...", msg_id)
        # ── 5. Fetch metadata headers ─────────────────────────────────────
        # metadataHeaders must be repeated params — httpx handles lists correctly
        detail_resp = await _http_client.get(
            f"{_GMAIL_BASE}/messages/{msg_id}",
            headers=headers,
            params=[
                ("format", "metadata"),
                ("metadataHeaders", "Subject"),
                ("metadataHeaders", "From"),
                ("metadataHeaders", "Date"),
            ],
        )
        if detail_resp.status_code != 200:
            logger.warning("Failed to fetch details for msg_id=%s: %s", msg_id, detail_resp.status_code)
            continue

        detail = detail_resp.json()
        label_ids: list[str] = detail.get("labelIds", [])
        payload_headers: list[dict] = detail.get("payload", {}).get("headers", [])
        snippet: str = detail.get("snippet", "")

        # Extract headers
        hmap = {h["name"]: h["value"] for h in payload_headers}
        subject = hmap.get("Subject", "(no subject)")[:500]
        sender = hmap.get("From", "Unknown")[:200]
        date_str = hmap.get("Date", "")

        is_important = bool(_HIGH_PRIORITY_LABELS & set(label_ids))
        priority = (
            NotificationPriority.HIGH if is_important else NotificationPriority.MEDIUM
        )

        # ── 6. Write notification ─────────────────────────────────────────
        notif = Notification(
            user_id=user_id,
            source_tool="gmail",
            title=subject,
            content=snippet[:500] if snippet else sender,
            priority=priority,
            metadata_={
                "source_id": msg_id,
                "sender": sender,
                "date": date_str,
                "label_ids": label_ids,
            },
        )
        db.add(notif)
        new_count += 1
        logger.info("Queueing insert for msg_id=%s: %s", msg_id, subject)

    await db.commit()
    logger.info("Gmail sync: %d new notifications for user=%s", new_count, user_id)

    # ── 7. Enforce notification cap ───────────────────────────────────────────
    await _enforce_cap(db, user_id)

    return new_count


async def _enforce_cap(db: AsyncSession, user_id: UUID) -> None:
    """Delete oldest read notifications if user is over the cap."""
    total_result = await db.execute(
        select(func.count()).where(Notification.user_id == user_id)
    )
    total = total_result.scalar_one()

    if total <= _NOTIFICATION_CAP:
        return

    overflow = total - _NOTIFICATION_CAP

    # Find IDs of the oldest read notifications
    oldest = await db.execute(
        select(Notification.id)
        .where(Notification.user_id == user_id, Notification.is_read == True)  # noqa: E712
        .order_by(Notification.created_at.asc())
        .limit(overflow)
    )
    ids_to_delete = [row[0] for row in oldest.all()]

    if ids_to_delete:
        await db.execute(
            delete(Notification).where(Notification.id.in_(ids_to_delete))
        )
        await db.commit()
        logger.info("Pruned %d old notifications for user=%s", len(ids_to_delete), user_id)
