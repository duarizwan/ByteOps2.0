"""APScheduler-based sync scheduler.

Manages the lifecycle of periodic sync jobs and provides a function to
trigger an immediate sync (called from the OAuth callback on connect).

Uses AsyncIOScheduler so jobs run within the same event loop as FastAPI
without threading complexity.

Each job creates its own DB session (does NOT reuse request-scoped sessions)
so there are no session leaks between the request lifecycle and the background
scheduler lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.database import async_session_factory as AsyncSessionLocal
from app.models.tool_connection import ConnectionStatus, ToolConnection, ToolType

logger = logging.getLogger(__name__)

# Singleton scheduler — created once at startup
_scheduler: AsyncIOScheduler | None = None

# Sync interval — change to 1 or 2 minutes during dev testing
SYNC_INTERVAL_MINUTES = 60
_SYNC_INTERVAL_MINUTES = SYNC_INTERVAL_MINUTES  # backward compat alias


# ── Lifecycle ──────────────────────────────────────────────────────────────────

async def start_scheduler() -> None:
    """Start the scheduler. Called from FastAPI lifespan startup."""
    global _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Periodic job — runs every N minutes for ALL connected users
    _scheduler.add_job(
        _periodic_sync_all,
        trigger="interval",
        minutes=_SYNC_INTERVAL_MINUTES,
        id="periodic_sync",
        replace_existing=True,
    )
    _scheduler.add_job(
        _periodic_workflows_all,
        trigger="interval",
        minutes=_SYNC_INTERVAL_MINUTES,
        id="periodic_workflows",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Sync scheduler started — periodic sync every %d minutes.",
        _SYNC_INTERVAL_MINUTES,
    )


async def stop_scheduler() -> None:
    """Stop the scheduler gracefully. Called from FastAPI lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Sync scheduler stopped.")


# ── Public trigger ─────────────────────────────────────────────────────────────

async def trigger_immediate_sync(user_id: UUID, tool_type: ToolType) -> None:
    """Trigger an immediate sync for one user+tool pair.

    Fire-and-forget — creates a background asyncio task so the OAuth
    callback can return the redirect without waiting.
    """
    asyncio.create_task(
        _run_single_sync(user_id=user_id, tool_type=tool_type),
        name=f"sync_{tool_type}_{user_id}",
    )
    logger.info("Immediate sync queued for %s user=%s", tool_type, user_id)


# ── Internal runners ──────────────────────────────────────────────────────────

async def _periodic_sync_all() -> None:
    """Scan all CONNECTED tool connections and sync each one."""
    logger.info("Periodic sync: scanning all connected tools…")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ToolConnection).where(
                ToolConnection.status == ConnectionStatus.CONNECTED
            )
        )
        connections = result.scalars().all()

    # Run each sync in a separate task so one failure doesn't block others
    tasks = [
        asyncio.create_task(
            _run_single_sync(
                user_id=conn.user_id,
                tool_type=conn.tool_type,
            ),
            name=f"sync_{conn.tool_type}_{conn.user_id}",
        )
        for conn in connections
    ]

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Periodic sync complete — %d connections processed.", len(tasks))


async def _periodic_workflows_all() -> None:
    """Run due active workflows on the scheduler interval."""
    from app.services.workflow_runner import execute_due_workflows

    async with AsyncSessionLocal() as db:
        result = await execute_due_workflows(db)
    logger.info(
        "Periodic workflows complete: %d of %d workflows ran.",
        result["ran"],
        result["scanned"],
    )


async def _run_single_sync(user_id: UUID, tool_type: ToolType) -> None:
    """Run the appropriate sync for a single user + tool combination."""
    from app.services.sync.gmail_sync import run_gmail_sync
    from app.services.sync.calendar_sync import run_calendar_sync

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ToolConnection).where(
                ToolConnection.user_id == user_id,
                ToolConnection.tool_type == tool_type,
                ToolConnection.status == ConnectionStatus.CONNECTED,
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            logger.warning(
                "Sync skipped — no CONNECTED %s for user=%s", tool_type, user_id
            )
            return

        if tool_type == ToolType.GMAIL:
            count = await run_gmail_sync(connection=connection, db=db)
            logger.info(
                "Gmail sync done: %d new notifications for user=%s", count, user_id
            )
        elif tool_type == ToolType.CALENDAR:
            count = await run_calendar_sync(connection=connection, db=db)
            logger.info(
                "Calendar sync done: %d new notifications for user=%s", count, user_id
            )
        else:
            # Placeholder — add per-tool sync functions here as tools are added
            logger.debug("No sync implemented for %s — skipping.", tool_type)
