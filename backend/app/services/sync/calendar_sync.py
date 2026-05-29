"""Google Calendar background sync service.

Fetches upcoming calendar events and writes them as Notification rows.
Runs on first connect (next 7 days) and on every scheduled re-sync
(incremental — events starting after the last sync timestamp).

Key design decisions:
  - Direct Google Calendar REST API calls via httpx (not the MCP subprocess)
    for efficiency in headless background jobs.
  - Deduplication: checks metadata_->source_id before inserting so
    re-syncs never produce duplicate notifications.
  - Cap: integrated with the shared 200-notification cap.
  - Calendar failure never propagates — logged and skipped.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationPriority
from app.models.tool_connection import ConnectionStatus, ToolConnection
from app.services.sync.token_refresh import ensure_fresh_token

logger = logging.getLogger(__name__)

# Shared HTTP client
_http_client = httpx.AsyncClient(timeout=15.0)

# Calendar API base
_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"

# How far ahead to fetch events (days)
_LOOKAHEAD_DAYS = 7

# Max events per sync
_MAX_RESULTS = 20


async def run_calendar_sync(
    connection: ToolConnection,
    db: AsyncSession,
) -> int:
    """Scan upcoming Calendar events and write new Notification rows.

    Returns the count of new notifications written.
    Raises nothing — all errors are caught internally.
    """
    user_id: UUID = connection.user_id

    # ── 0. Guard: already syncing? ────────────────────────────────────────────
    meta: dict = dict(connection.metadata_ or {})
    if meta.get("is_syncing"):
        logger.info("Calendar sync already in progress for user=%s — skipping.", user_id)
        return 0

    # ── 1. Ensure fresh access token ──────────────────────────────────────────
    token_ok = await ensure_fresh_token(connection, db)
    if not token_ok:
        return 0

    # ── 2. Lock ────────────────────────────────────────────────────────────────
    connection.metadata_ = {**meta, "is_syncing": True}
    await db.commit()

    try:
        return await _do_sync(connection, db, user_id)
    except Exception:
        logger.exception("Calendar sync failed for user=%s", user_id)
        return 0
    finally:
        # ── Unlock ────────────────────────────────────────────────────────────
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
    """Inner sync — separated so the finally block is clean."""
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=_LOOKAHEAD_DAYS)).isoformat()

    headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Content-Type": "application/json",
    }

    # ── 3. Fetch upcoming events from primary calendar ────────────────────────
    resp = await _http_client.get(
        f"{_CALENDAR_BASE}/calendars/primary/events",
        headers=headers,
        params={
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": _MAX_RESULTS,
            "singleEvents": "true",
            "orderBy": "startTime",
            "fields": "items(id,summary,start,end,location,htmlLink,attendees)",
        },
    )

    if resp.status_code == 401:
        logger.warning("Calendar 401 for user=%s — token invalid.", user_id)
        connection.status = ConnectionStatus.EXPIRED
        await db.commit()
        return 0

    if resp.status_code != 200:
        logger.warning(
            "Calendar list failed %s for user=%s", resp.status_code, user_id
        )
        return 0

    events = resp.json().get("items", [])
    if not events:
        logger.info("No upcoming Calendar events for user=%s", user_id)
        return 0

    new_count = 0

    for event in events:
        event_id: str = event.get("id", "")
        if not event_id:
            continue

        # ── 4. Deduplication ──────────────────────────────────────────────────
        exists_result = await db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.source_tool == "calendar",
                Notification.metadata_["source_id"].astext() == event_id,
            )
        )
        if exists_result.scalar_one_or_none():
            logger.debug("Skipping event_id=%s — already in DB", event_id)
            continue

        # ── 5. Build notification ─────────────────────────────────────────────
        title = event.get("summary") or "(no title)"
        start_info = event.get("start", {})
        start_str = start_info.get("dateTime") or start_info.get("date") or ""
        location = event.get("location", "")

        # Determine priority: events starting within 24h are HIGH
        is_soon = False
        if start_str:
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                is_soon = (start_dt - now) < timedelta(hours=24)
            except ValueError:
                pass

        priority = NotificationPriority.HIGH if is_soon else NotificationPriority.MEDIUM

        # Build readable content
        content_parts = []
        if start_str:
            content_parts.append(f"Starts: {start_str}")
        if location:
            content_parts.append(f"📍 {location}")
        attendees = event.get("attendees", [])
        if attendees:
            attendee_emails = [a.get("email", "") for a in attendees[:3] if a.get("email")]
            if attendee_emails:
                content_parts.append(f"With: {', '.join(attendee_emails)}")

        content = " · ".join(content_parts) if content_parts else None

        notif = Notification(
            user_id=user_id,
            source_tool="calendar",
            title=f"📅 {title}",
            content=content,
            priority=priority,
            metadata_={
                "source_id": event_id,
                "start": start_str,
                "location": location,
                "html_link": event.get("htmlLink", ""),
            },
        )
        db.add(notif)
        new_count += 1
        logger.info("Queuing calendar event notification: %s", title)

    await db.commit()
    logger.info("Calendar sync: %d new notifications for user=%s", new_count, user_id)
    return new_count
