"""Workflow API.

Provides a first slice of persisted workflow management for the right-panel
Workflows tab: list, create, pause/resume, manual run, and delete.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStatus

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowOut(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    trigger: dict
    actions: list
    trigger_label: str
    action_summary: str
    last_run_at: str | None
    next_run_at: str | None
    last_error: str | None
    created_at: str | None = None
    updated_at: str | None = None


class CreateWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    trigger: dict = Field(default_factory=dict)
    actions: list = Field(default_factory=list)
    status: str = "active"
    next_run_at: datetime | None = None


class UpdateWorkflowRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    trigger: dict | None = None
    actions: list | None = None
    status: str | None = None
    next_run_at: datetime | None = None


def _clean_activity_text(text: str | None) -> str | None:
    if not text:
        return text
    cleaned = " ".join(text.replace("*", " ").replace("-", " ").replace("|", " ").split())
    for mark in (".", ",", "!", "?", ";", ":"):
        cleaned = cleaned.replace(f" {mark}", mark)
    return cleaned


def _status(value: str | WorkflowStatus | None) -> WorkflowStatus:
    if isinstance(value, WorkflowStatus):
        return value
    try:
        return WorkflowStatus((value or "active").lower())
    except ValueError:
        return WorkflowStatus.ACTIVE


def _trigger_label(trigger: dict) -> str:
    label = trigger.get("label") if isinstance(trigger, dict) else None
    if isinstance(label, str) and label.strip():
        return _clean_activity_text(label) or "Manual run"
    trigger_type = trigger.get("type") if isinstance(trigger, dict) else None
    return "Manual run" if trigger_type == "manual" else "Workflow trigger"


def _action_summary(actions: list) -> str:
    if not actions:
        return "No actions configured"
    labels: list[str] = []
    for action in actions:
        if isinstance(action, dict):
            label = action.get("label") or action.get("name") or action.get("tool")
            if isinstance(label, str) and label.strip():
                labels.append(_clean_activity_text(label) or label.strip())
        elif isinstance(action, str) and action.strip():
            labels.append(_clean_activity_text(action) or action.strip())
    if not labels:
        return "No actions configured"
    summary = ", ".join(labels[:2])
    if len(labels) > 2:
        summary += f" +{len(labels) - 2} more"
    return summary


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize(workflow: Workflow) -> WorkflowOut:
    status_value = workflow.status.value if hasattr(workflow.status, "value") else str(workflow.status)
    return WorkflowOut(
        id=str(workflow.id),
        name=_clean_activity_text(workflow.name) or workflow.name,
        description=_clean_activity_text(workflow.description),
        status=status_value,
        trigger=workflow.trigger or {},
        actions=workflow.actions or [],
        trigger_label=_trigger_label(workflow.trigger or {}),
        action_summary=_action_summary(workflow.actions or []),
        last_run_at=_iso(workflow.last_run_at),
        next_run_at=_iso(workflow.next_run_at),
        last_error=_clean_activity_text(workflow.last_error),
        created_at=_iso(workflow.created_at),
        updated_at=_iso(workflow.updated_at),
    )


async def _get_user_workflow(
    workflow_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Workflow:
    workflow = await db.get(Workflow, workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    return workflow


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkflowOut]:
    result = await db.execute(
        select(Workflow)
        .where(Workflow.user_id == current_user.id)
        .order_by(Workflow.updated_at.desc(), Workflow.created_at.desc())
    )
    return [_serialize(workflow) for workflow in result.scalars().all()]


@router.post("", response_model=WorkflowOut, status_code=201)
async def create_workflow(
    body: CreateWorkflowRequest,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowOut:
    workflow = Workflow(
        user_id=current_user.id,
        name=body.name.strip(),
        description=body.description,
        trigger=body.trigger,
        actions=body.actions,
        status=_status(body.status),
        next_run_at=body.next_run_at,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return _serialize(workflow)


@router.patch("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: UUID,
    body: UpdateWorkflowRequest,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowOut:
    workflow = await _get_user_workflow(workflow_id, current_user, db)
    if body.name is not None:
        workflow.name = body.name.strip()
    if body.description is not None:
        workflow.description = body.description
    if body.trigger is not None:
        workflow.trigger = body.trigger
    if body.actions is not None:
        workflow.actions = body.actions
    if body.status is not None:
        workflow.status = _status(body.status)
    if body.next_run_at is not None:
        workflow.next_run_at = body.next_run_at
    await db.commit()
    await db.refresh(workflow)
    return _serialize(workflow)


@router.post("/{workflow_id}/pause", response_model=WorkflowOut)
async def pause_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowOut:
    workflow = await _get_user_workflow(workflow_id, current_user, db)
    workflow.status = WorkflowStatus.PAUSED
    await db.commit()
    await db.refresh(workflow)
    return _serialize(workflow)


@router.post("/{workflow_id}/resume", response_model=WorkflowOut)
async def resume_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowOut:
    workflow = await _get_user_workflow(workflow_id, current_user, db)
    workflow.status = WorkflowStatus.ACTIVE
    workflow.last_error = None
    await db.commit()
    await db.refresh(workflow)
    return _serialize(workflow)


@router.post("/{workflow_id}/run", response_model=WorkflowOut)
async def run_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowOut:
    workflow = await _get_user_workflow(workflow_id, current_user, db)
    if workflow.status == WorkflowStatus.PAUSED:
        raise HTTPException(status_code=409, detail="Paused workflows cannot run.")
    workflow.status = WorkflowStatus.ACTIVE
    workflow.last_run_at = datetime.now(timezone.utc)
    workflow.last_error = None
    await db.commit()
    await db.refresh(workflow)
    return _serialize(workflow)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    workflow = await _get_user_workflow(workflow_id, current_user, db)
    await db.delete(workflow)
    await db.commit()
