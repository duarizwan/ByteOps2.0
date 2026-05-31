"""Tests for approving workflow drafts stored on agent runs."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.agent_runs import ApproveWorkflowDraftRequest, approve_workflow_draft
from app.models.agent_run import AgentRun, AgentRunStatus, AgentRunStep, AgentRunStepType
from app.models.workflow import WorkflowStatus
from app.services.workflow_creation import build_workflow_draft


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDb:
    def __init__(self, run):
        self.run = run
        self.added = []
        self.commits = 0
        self.refreshed = []

    async def execute(self, _statement):
        return ScalarResult(self.run)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        self.refreshed.append(value)


@pytest.mark.anyio
async def test_approve_workflow_draft_creates_paused_workflow_and_marks_run():
    user_id = uuid4()
    run_id = uuid4()
    draft = build_workflow_draft(
        "Create a workflow that summarizes Gmail and Slack every morning.",
        connected_tools=["gmail"],
    )
    run = AgentRun(
        id=run_id,
        user_id=user_id,
        intent="workflow",
        status=AgentRunStatus.COMPLETED,
        plan={"summary": "Create workflow"},
        metadata_={},
    )
    run.steps = [
        AgentRunStep(
            run_id=run_id,
            step_type=AgentRunStepType.FINAL,
            name="workflow_draft_needs_review",
            output=draft,
        )
    ]
    db = FakeDb(run)

    result = await approve_workflow_draft(run_id, SimpleNamespace(id=user_id), db)

    workflow = db.added[0]
    assert result["status"] == "created"
    assert result["workflow_id"] == str(workflow.id)
    assert result["workflow_status"] == WorkflowStatus.PAUSED.value
    assert workflow.name == "Morning Gmail and Slack brief"
    assert run.metadata_["approved_workflow_id"] == str(workflow.id)
    assert run.metadata_["approved_workflow_status"] == WorkflowStatus.PAUSED.value
    assert any(step.name == "workflow_draft_approved" for step in db.added)


@pytest.mark.anyio
async def test_approve_workflow_draft_is_idempotent_after_first_approval():
    user_id = uuid4()
    run_id = uuid4()
    run = AgentRun(
        id=run_id,
        user_id=user_id,
        intent="workflow",
        status=AgentRunStatus.COMPLETED,
        plan={"summary": "Create workflow"},
        metadata_={
            "approved_workflow_id": "workflow-123",
            "approved_workflow_status": "paused",
        },
    )
    db = FakeDb(run)

    result = await approve_workflow_draft(run_id, SimpleNamespace(id=user_id), db)

    assert result == {
        "status": "already_approved",
        "run_id": str(run_id),
        "workflow_id": "workflow-123",
        "workflow_status": "paused",
    }
    assert db.added == []


@pytest.mark.anyio
async def test_approve_workflow_draft_uses_edited_draft_payload():
    user_id = uuid4()
    run_id = uuid4()
    original_draft = build_workflow_draft(
        "Create a workflow that summarizes Gmail and Slack every morning.",
        connected_tools=["gmail"],
    )
    edited_draft = {
        **original_draft,
        "name": "Edited inbox workflow",
        "trigger": {"type": "schedule", "label": "Daily at 8 AM"},
        "actions": [original_draft["actions"][0]],
    }
    run = AgentRun(
        id=run_id,
        user_id=user_id,
        intent="workflow",
        status=AgentRunStatus.COMPLETED,
        plan={"summary": "Create workflow"},
        metadata_={},
    )
    run.steps = [
        AgentRunStep(
            run_id=run_id,
            step_type=AgentRunStepType.FINAL,
            name="workflow_draft_needs_review",
            output=original_draft,
        )
    ]
    db = FakeDb(run)

    result = await approve_workflow_draft(
        run_id,
        SimpleNamespace(id=user_id),
        db,
        body=ApproveWorkflowDraftRequest(draft=edited_draft),
    )

    workflow = db.added[0]
    assert result["status"] == "created"
    assert workflow.name == "Edited inbox workflow"
    assert workflow.trigger == {"type": "schedule", "label": "Daily at 8 AM"}
    assert workflow.actions == [original_draft["actions"][0]]


@pytest.mark.anyio
async def test_approve_workflow_draft_rejects_unknown_action_tool():
    user_id = uuid4()
    run_id = uuid4()
    draft = build_workflow_draft(
        "Create a workflow that summarizes Gmail every morning.",
        connected_tools=["gmail"],
    )
    draft = {
        **draft,
        "actions": [{"tool": "unknown", "label": "Run unknown action"}],
    }
    run = AgentRun(
        id=run_id,
        user_id=user_id,
        intent="workflow",
        status=AgentRunStatus.COMPLETED,
        plan={"summary": "Create workflow"},
        metadata_={},
    )
    run.steps = [
        AgentRunStep(
            run_id=run_id,
            step_type=AgentRunStepType.FINAL,
            name="workflow_draft_needs_review",
            output=draft,
        )
    ]
    db = FakeDb(run)

    with pytest.raises(HTTPException) as exc:
        await approve_workflow_draft(
            run_id,
            SimpleNamespace(id=user_id),
            db,
            body=ApproveWorkflowDraftRequest(draft=draft),
        )

    assert exc.value.status_code == 422
    assert "Unsupported workflow action tool" in exc.value.detail
    assert db.added == []


@pytest.mark.anyio
async def test_approve_workflow_draft_rejects_empty_action_list():
    user_id = uuid4()
    run_id = uuid4()
    draft = build_workflow_draft(
        "Create a workflow that summarizes Gmail every morning.",
        connected_tools=["gmail"],
    )
    draft = {**draft, "actions": []}
    run = AgentRun(
        id=run_id,
        user_id=user_id,
        intent="workflow",
        status=AgentRunStatus.COMPLETED,
        plan={"summary": "Create workflow"},
        metadata_={},
    )
    run.steps = [
        AgentRunStep(
            run_id=run_id,
            step_type=AgentRunStepType.FINAL,
            name="workflow_draft_needs_review",
            output=draft,
        )
    ]
    db = FakeDb(run)

    with pytest.raises(HTTPException) as exc:
        await approve_workflow_draft(
            run_id,
            SimpleNamespace(id=user_id),
            db,
            body=ApproveWorkflowDraftRequest(draft=draft),
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "Workflow draft must include at least one action."
    assert db.added == []
