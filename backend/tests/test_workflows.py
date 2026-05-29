"""Tests for workflow model helpers and API payloads."""

from datetime import datetime, timezone
from uuid import uuid4

from app.api.workflows import _serialize
from app.models.workflow import Workflow, WorkflowStatus


def test_serialize_workflow_includes_status_and_run_timestamps():
    workflow = Workflow(
        id=uuid4(),
        user_id=uuid4(),
        name="Daily inbox triage",
        description="Summarize priority messages each morning.",
        trigger={"type": "schedule", "label": "Every weekday at 9:00 AM"},
        actions=[{"tool": "gmail", "label": "Summarize unread important emails"}],
        status=WorkflowStatus.ACTIVE,
        last_run_at=datetime(2026, 5, 29, 9, 0, tzinfo=timezone.utc),
        next_run_at=datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc),
        last_error=None,
    )

    payload = _serialize(workflow)

    assert payload.id == str(workflow.id)
    assert payload.name == "Daily inbox triage"
    assert payload.status == "active"
    assert payload.trigger_label == "Every weekday at 9:00 AM"
    assert payload.action_summary == "Summarize unread important emails"
    assert payload.last_run_at == "2026-05-29T09:00:00+00:00"
    assert payload.next_run_at == "2026-05-30T09:00:00+00:00"


def test_serialize_failed_workflow_exposes_clean_error():
    workflow = Workflow(
        id=uuid4(),
        user_id=uuid4(),
        name="Slack follow-up monitor",
        trigger={"type": "manual", "label": "Manual run"},
        actions=[],
        status=WorkflowStatus.FAILED,
        last_error="*Slack* | token - expired",
    )

    payload = _serialize(workflow)

    assert payload.status == "failed"
    assert payload.last_error == "Slack token expired"
