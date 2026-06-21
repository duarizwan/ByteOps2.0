"""Analytics API — aggregate metrics for the ByteOps dashboard."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.user import User
from app.models.agent_run import AgentRun
from app.models.workflow import Workflow
from app.models.hired_agent import HiredAgent

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
async def get_summary(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Total runs
    total_result = await db.execute(
        select(func.count(AgentRun.id)).where(AgentRun.user_id == current_user.id)
    )
    total_runs: int = total_result.scalar() or 0

    # Runs last 30 days
    runs_30d_result = await db.execute(
        select(func.count(AgentRun.id)).where(
            AgentRun.user_id == current_user.id,
            AgentRun.created_at >= thirty_days_ago,
        )
    )
    runs_30d: int = runs_30d_result.scalar() or 0

    # Status breakdown
    status_result = await db.execute(
        select(AgentRun.status, func.count(AgentRun.id))
        .where(AgentRun.user_id == current_user.id)
        .group_by(AgentRun.status)
    )
    status_counts: dict[str, int] = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): row[1]
        for row in status_result.all()
    }
    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0)
    success_rate = round(completed / total_runs * 100, 1) if total_runs > 0 else 0.0
    failure_rate = round(failed / total_runs * 100, 1) if total_runs > 0 else 0.0

    # Anomaly / flagged
    try:
        flagged_result = await db.execute(
            select(func.count(AgentRun.id)).where(
                AgentRun.user_id == current_user.id,
                AgentRun.flagged.is_(True),
            )
        )
        flagged_count: int = flagged_result.scalar() or 0
    except Exception:
        flagged_count = 0
    anomaly_rate = round(flagged_count / total_runs * 100, 1) if total_runs > 0 else 0.0

    # Runs per day — last 7 days
    runs_7d_result = await db.execute(
        select(AgentRun.created_at, AgentRun.status).where(
            AgentRun.user_id == current_user.id,
            AgentRun.created_at >= seven_days_ago,
        )
    )
    daily: dict[str, dict] = {}
    for i in range(7):
        day = (now - timedelta(days=6 - i)).strftime("%Y-%m-%d")
        daily[day] = {"date": day, "label": (now - timedelta(days=6 - i)).strftime("%a"), "total": 0, "completed": 0, "failed": 0}
    for created_at, status in runs_7d_result.all():
        if created_at is None:
            continue
        day = created_at.strftime("%Y-%m-%d")
        if day in daily:
            daily[day]["total"] += 1
            sv = status.value if hasattr(status, "value") else str(status)
            if sv == "completed":
                daily[day]["completed"] += 1
            elif sv == "failed":
                daily[day]["failed"] += 1
    runs_by_day = list(daily.values())

    # Tool / intent breakdown
    intent_result = await db.execute(
        select(AgentRun.intent, func.count(AgentRun.id))
        .where(
            AgentRun.user_id == current_user.id,
            AgentRun.intent.isnot(None),
        )
        .group_by(AgentRun.intent)
        .order_by(func.count(AgentRun.id).desc())
        .limit(6)
    )
    tool_breakdown = [{"tool": row[0], "count": row[1]} for row in intent_result.all()]

    # Active workflows count
    wf_result = await db.execute(
        select(func.count(Workflow.id)).where(Workflow.user_id == current_user.id)
    )
    active_workflows: int = wf_result.scalar() or 0

    # Hired agents count
    ha_result = await db.execute(
        select(func.count(HiredAgent.id)).where(HiredAgent.user_id == current_user.id)
    )
    hired_agents: int = ha_result.scalar() or 0

    # Recent flagged runs
    try:
        flagged_runs_result = await db.execute(
            select(AgentRun)
            .where(
                AgentRun.user_id == current_user.id,
                AgentRun.flagged.is_(True),
            )
            .order_by(AgentRun.created_at.desc())
            .limit(5)
        )
        flagged_runs = [
            {
                "id": str(r.id),
                "intent": r.intent,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "anomaly_score": getattr(r, "anomaly_score", None),
                "llm_score": getattr(r, "llm_score", None),
            }
            for r in flagged_runs_result.scalars().all()
        ]
    except Exception:
        flagged_runs = []

    return {
        "total_runs": total_runs,
        "runs_last_30_days": runs_30d,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "anomaly_rate": anomaly_rate,
        "flagged_count": flagged_count,
        "status_breakdown": status_counts,
        "runs_by_day": runs_by_day,
        "tool_breakdown": tool_breakdown,
        "active_workflows": active_workflows,
        "hired_agents": hired_agents,
        "flagged_runs": flagged_runs,
    }
