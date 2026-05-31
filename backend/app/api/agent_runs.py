"""Agent run history API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.user import User
from app.models.workflow import WorkflowStatus
from app.services.agent_runtime import record_agent_step, resolve_approval, serialize_agent_run
from app.models.agent_run import AgentRunStepType
from app.services.workflow_creation import create_workflow_from_draft, validate_workflow_draft

router = APIRouter(prefix="/api/agent-runs", tags=["agent-runs"])


class ApproveWorkflowDraftRequest(BaseModel):
    draft: dict | None = None


def _latest_workflow_draft(run: AgentRun) -> dict | None:
    for step in reversed(getattr(run, "steps", []) or []):
        if step.name == "workflow_draft_needs_review" and isinstance(step.output, dict):
            return step.output
    return None


@router.get("")
async def list_agent_runs(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    result = await db.execute(
        select(AgentRun)
        .options(selectinload(AgentRun.steps))
        .where(AgentRun.user_id == current_user.id)
        .order_by(AgentRun.created_at.desc())
        .limit(50)
    )
    return [serialize_agent_run(run) for run in result.scalars().all()]


@router.get("/{run_id}")
async def get_agent_run(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(
        select(AgentRun)
        .options(selectinload(AgentRun.steps))
        .where(AgentRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run or run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found.")
    return serialize_agent_run(run)


@router.post("/{run_id}/approve")
async def approve_agent_run(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run or run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found.")
    if run.status != AgentRunStatus.WAITING_APPROVAL:
        signalled = resolve_approval(str(run_id), approved=True)
        if signalled:
            return {"status": "approved", "run_id": str(run_id)}
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run is not waiting for approval.")
    signalled = resolve_approval(str(run_id), approved=True)
    if not signalled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No approval gate active.")
    return {"status": "approved", "run_id": str(run_id)}


@router.post("/{run_id}/approve-workflow-draft")
async def approve_workflow_draft(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ApproveWorkflowDraftRequest | None = None,
) -> dict:
    result = await db.execute(
        select(AgentRun)
        .options(selectinload(AgentRun.steps))
        .where(AgentRun.id == run_id)
        .with_for_update()
    )
    run = result.scalar_one_or_none()
    if not run or run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found.")

    metadata = run.metadata_ or {}
    approved_workflow_id = metadata.get("approved_workflow_id")
    if approved_workflow_id:
        return {
            "status": "already_approved",
            "run_id": str(run_id),
            "workflow_id": approved_workflow_id,
            "workflow_status": metadata.get("approved_workflow_status") or WorkflowStatus.ACTIVE.value,
        }

    draft = body.draft if body and body.draft else _latest_workflow_draft(run)
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run does not contain a workflow draft to approve.",
        )
    try:
        validate_workflow_draft(draft)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    workflow = await create_workflow_from_draft(
        db,
        user_id=current_user.id,
        draft=draft,
    )
    run.metadata_ = {
        **metadata,
        "approved_workflow_id": str(workflow.id),
        "approved_workflow_status": workflow.status.value if hasattr(workflow.status, "value") else str(workflow.status),
    }
    await db.commit()
    await record_agent_step(
        db,
        run_id=run.id,
        step_type=AgentRunStepType.APPROVAL,
        name="workflow_draft_approved",
        input={"draft_name": draft.get("name")},
        output={
            "workflow_id": str(workflow.id),
            "workflow_status": workflow.status.value if hasattr(workflow.status, "value") else str(workflow.status),
        },
    )
    return {
        "status": "created",
        "run_id": str(run_id),
        "workflow_id": str(workflow.id),
        "workflow_status": workflow.status.value if hasattr(workflow.status, "value") else str(workflow.status),
    }


@router.post("/{run_id}/reject")
async def reject_agent_run(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run or run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found.")
    if run.status != AgentRunStatus.WAITING_APPROVAL:
        signalled = resolve_approval(str(run_id), approved=False)
        if signalled:
            run.status = AgentRunStatus.CANCELLED
            await db.commit()
            return {"status": "rejected", "run_id": str(run_id)}
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run is not waiting for approval.")
    signalled = resolve_approval(str(run_id), approved=False)
    if not signalled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No approval gate active.")
    run.status = AgentRunStatus.CANCELLED
    await db.commit()
    return {"status": "rejected", "run_id": str(run_id)}
