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
import uuid
from datetime import datetime, timezone
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
    _scheduler.add_job(
        _periodic_hired_agents_all,
        trigger="interval",
        minutes=1,
        id="periodic_hired_agents",
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


async def _periodic_hired_agents_all() -> None:
    """Find hired agents whose next_run_at is due and execute them."""
    from app.models.hired_agent import HiredAgent, HiredAgentStatus

    now = datetime.now(timezone.utc)

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(HiredAgent).where(
                    HiredAgent.status == HiredAgentStatus.ACTIVE,
                    HiredAgent.next_run_at <= now,
                    HiredAgent.next_run_at.isnot(None),
                )
            )
            due_agents = result.scalars().all()
            due = [(a.id, a.user_id) for a in due_agents]
    except Exception as exc:
        logger.warning("Hired agent scheduler skipped — DB not ready: %s", exc)
        return

    if not due:
        return

    logger.info("Hired agent scheduler: %d agent(s) due.", len(due))
    tasks = [
        asyncio.create_task(
            _run_hired_agent(agent_id=agent_id, user_id=user_id),
            name=f"hired_agent_{agent_id}",
        )
        for agent_id, user_id in due
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _run_hired_agent(agent_id: UUID, user_id: UUID) -> None:
    """Execute a single hired agent and update its state."""
    from app.api.agents import AGENT_TEMPLATES, _schedule_to_next_run
    from app.models.hired_agent import HiredAgent, HiredAgentStatus
    from app.models.notification import Notification, NotificationPriority
    from app.models.tool_connection import ToolConnection, ToolType, ConnectionStatus
    from app.services.sync.token_refresh import ensure_fresh_token
    from app.services.workflow_runner import execute_workflow_run

    async with AsyncSessionLocal() as db:
        agent = await db.get(HiredAgent, agent_id)
        if not agent or agent.status != HiredAgentStatus.ACTIVE:
            return

        template = AGENT_TEMPLATES.get(agent.template_key)
        if not template:
            logger.warning("Hired agent %s has unknown template '%s'", agent_id, agent.template_key)
            return

        # ── OAuth token check — auto-pause if any required tool is expired ────
        expired_tools = []
        for tool_name in template["required_tools"]:
            try:
                tool_type = ToolType(tool_name)
            except ValueError:
                continue
            result = await db.execute(
                select(ToolConnection).where(
                    ToolConnection.user_id == user_id,
                    ToolConnection.tool_type == tool_type,
                    ToolConnection.status == ConnectionStatus.CONNECTED,
                )
            )
            connection = result.scalar_one_or_none()
            if not connection:
                expired_tools.append(tool_name)
                continue
            fresh = await ensure_fresh_token(connection, db)
            if not fresh:
                expired_tools.append(tool_name)

        if expired_tools:
            tools_str = ", ".join(expired_tools)
            agent.status = HiredAgentStatus.PAUSED
            agent.last_error = (
                f"Token expired for: {tools_str}. "
                f"Reconnect in Settings → Connections to resume."
            )
            db.add(Notification(
                user_id=user_id,
                source_tool=agent.template_key,
                title=f"{agent.name} paused — reconnect {tools_str}",
                content=agent.last_error,
                priority=NotificationPriority.HIGH,
            ))
            await db.commit()
            logger.warning("Hired agent %s paused — expired tokens: %s", agent_id, tools_str)
            return

        now = datetime.now(timezone.utc)
        agent.status = HiredAgentStatus.RUNNING
        agent.last_run_at = now
        agent.last_error = None
        await db.commit()

        success = False
        try:
            run_data = await execute_workflow_run(
                workflow_name=agent.name,
                workflow_id=str(agent.id),
                trigger={"type": "agent_scheduled", "template": agent.template_key},
                actions=[
                    {"tool": t, "operation": "auto", "prompt": template["prompt_template"]}
                    for t in template["required_tools"]
                ],
                user_id=user_id,
                db=db,
            )
            # Tag the AgentRun with this hired agent's id so the detail view can filter by it
            if run_data.get("id"):
                from app.models.agent_run import AgentRun as AgentRunModel
                agent_run_row = await db.get(AgentRunModel, uuid.UUID(run_data["id"]))
                if agent_run_row:
                    agent_run_row.hired_agent_id = agent_id
                    await db.flush()
            agent.total_runs = (agent.total_runs or 0) + 1
            agent.status = HiredAgentStatus.ACTIVE
            agent.metadata_ = {**(agent.metadata_ or {}), "last_agent_run_id": run_data.get("id")}
            if run_data.get("status") == "failed":
                agent.status = HiredAgentStatus.FAILED
                agent.last_error = str(run_data.get("final_response", "Run failed"))[:500]
            else:
                success = True
        except Exception as exc:
            agent.status = HiredAgentStatus.FAILED
            agent.last_error = str(exc)[:500]
            logger.error("Hired agent %s failed: %s", agent_id, exc)

        # ── Notify user of run outcome ─────────────────────────────────────────
        if success:
            db.add(Notification(
                user_id=user_id,
                source_tool=agent.template_key,
                title=f"{agent.name} completed",
                content=f"Run #{agent.total_runs} finished successfully.",
                priority=NotificationPriority.LOW,
            ))
        else:
            db.add(Notification(
                user_id=user_id,
                source_tool=agent.template_key,
                title=f"{agent.name} failed",
                content=agent.last_error or "Unknown error.",
                priority=NotificationPriority.HIGH,
            ))

        schedule = (agent.config or {}).get("schedule", "every_2_hours")
        agent.next_run_at = _schedule_to_next_run(schedule)
        await db.commit()
        logger.info("Hired agent %s completed (success=%s) — next run: %s", agent_id, success, agent.next_run_at)
