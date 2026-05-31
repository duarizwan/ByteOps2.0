"""Agent Runtime service helpers."""

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, AgentRunStatus, AgentRunStep, AgentRunStepType


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


_approval_events: dict = {}
_approval_decisions: dict = {}


def serialize_agent_run(run: AgentRun) -> dict:
    return {
        "id": str(run.id),
        "user_id": str(run.user_id),
        "conversation_id": str(run.conversation_id) if run.conversation_id else None,
        "intent": run.intent,
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "plan": run.plan,
        "final_response": run.final_response,
        "error": run.error,
        "metadata": run.metadata_,
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
        "completed_at": _iso(run.completed_at),
        "steps": [
            {
                "id": str(step.id),
                "step_type": step.step_type.value if hasattr(step.step_type, "value") else str(step.step_type),
                "name": step.name,
                "status": step.status,
                "input": step.input,
                "output": step.output,
                "error": step.error,
                "created_at": _iso(step.created_at),
            }
            for step in getattr(run, "steps", [])
        ],
    }


async def create_agent_run(
    db: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID | None,
    user_message_id: UUID | None,
    intent: str,
    plan: dict,
) -> AgentRun:
    run = AgentRun(
        user_id=user_id,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        intent=intent,
        status=AgentRunStatus.PLANNING if not plan.get("blocked") else AgentRunStatus.FAILED,
        plan=plan,
        error=plan.get("block_reason"),
    )
    db.add(run)
    await db.flush()
    db.add(
        AgentRunStep(
            run_id=run.id,
            step_type=AgentRunStepType.PLAN,
            name="initial_plan",
            input={"intent": intent},
            output=plan,
        )
    )
    await db.commit()
    await db.refresh(run)
    return run


async def record_agent_step(
    db: AsyncSession,
    *,
    run_id: UUID,
    step_type: AgentRunStepType,
    name: str,
    input: dict | None = None,
    output: dict | None = None,
    status: str = "completed",
    error: str | None = None,
) -> AgentRunStep:
    step = AgentRunStep(
        run_id=run_id,
        step_type=step_type,
        name=name,
        status=status,
        input=input,
        output=output,
        error=error,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def complete_agent_run(db: AsyncSession, run: AgentRun, final_response: str) -> AgentRun:
    run.status = AgentRunStatus.COMPLETED
    run.final_response = final_response
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


async def fail_agent_run(db: AsyncSession, run: AgentRun, error: str) -> AgentRun:
    run.status = AgentRunStatus.FAILED
    run.error = error
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


async def pause_for_approval(run_id, db, tool, action, input_data, reason):
    """Pause execution and wait for user approval. Returns True if approved."""
    from sqlalchemy import update as _update
    await db.execute(
        _update(AgentRun).where(AgentRun.id == run_id).values(
            status=AgentRunStatus.WAITING_APPROVAL,
        )
    )
    await db.commit()
    key = str(run_id)
    event = asyncio.Event()
    _approval_events[key] = event
    try:
        await asyncio.wait_for(event.wait(), timeout=300.0)
    except asyncio.TimeoutError:
        _approval_decisions.pop(key, None)
        _approval_events.pop(key, None)
        return False
    finally:
        _approval_events.pop(key, None)
    decision = _approval_decisions.pop(key, False)
    if decision:
        await db.execute(
            _update(AgentRun).where(AgentRun.id == run_id).values(status=AgentRunStatus.RUNNING)
        )
        await db.commit()
    return decision


def resolve_approval(run_id, approved):
    """Signal waiting run. Returns False if no gate active."""
    event = _approval_events.get(str(run_id))
    if not event:
        return False
    _approval_decisions[str(run_id)] = approved
    event.set()
    return True


async def policy_aware_call_tool(session, block, agent_name, run_id, db, queue):
    """Execute one MCP tool call through the policy gate.
    - READ actions: execute immediately, record step
    - WRITE/SEND/DESTRUCTIVE with run_id+db: pause for approval first
    - WRITE/SEND/DESTRUCTIVE without run_id: execute immediately (no DB context)
    """
    from app.services.agent_policy import classify_tool_call, requires_approval as _req
    decision = classify_tool_call(agent_name, block.name)
    if _req(decision) and run_id is not None and db is not None:
        await queue.put(("approval_required", {
            "run_id": str(run_id),
            "tool": agent_name,
            "action": block.name,
            "input": block.input,
            "risk": decision.risk.value,
            "reason": decision.reason,
            "summary": agent_name + ": " + block.name,
        }))
        approved = await pause_for_approval(run_id, db, agent_name, block.name, block.input, decision.reason)
        if run_id and db:
            await record_agent_step(
                db, run_id=run_id,
                step_type=AgentRunStepType.APPROVAL,
                name=("approve:" if approved else "reject:") + block.name,
                input={"tool": agent_name, "action": block.name, "risk": decision.risk.value},
                status="approved" if approved else "rejected",
            )
        if not approved:
            raise RuntimeError("Action " + repr(block.name) + " was rejected by the user.")
    await queue.put(("tool_call_start", block.name, json.dumps(block.input, default=str)))
    tool_result = await session.call_tool(block.name, arguments=block.input)
    result_text = "\n".join(c.text for c in tool_result.content if c.type == "text")
    await queue.put(("tool_call_result", block.name, result_text))
    if run_id and db:
        await record_agent_step(
            db, run_id=run_id,
            step_type=AgentRunStepType.TOOL_CALL,
            name=block.name,
            input=block.input,
            output={"result": result_text[:2000]},
            status="completed",
        )
    return result_text
