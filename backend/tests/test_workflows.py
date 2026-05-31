"""Tests for workflow model helpers and API payloads."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.api.workflows import _serialize, resume_workflow, run_workflow
from app.models.tool_connection import ConnectionStatus, ToolType
from app.models.workflow import Workflow, WorkflowStatus
from app.services.workflow_runner import (
    build_workflow_run_plan,
    execute_due_workflows,
    execute_workflow_action,
)


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
    assert payload.condition_summary == "Run when schedule is due."
    assert payload.action_summary == "Summarize unread important emails"
    assert payload.approval_required is False
    assert payload.approval_summary == "No approval needed for read only actions."
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


def test_build_workflow_run_plan_uses_trigger_and_actions():
    plan = build_workflow_run_plan(
        workflow_name="Daily email brief",
        trigger={"type": "schedule", "label": "Every weekday at 9:00 AM"},
        actions=[{"tool": "gmail", "label": "Summarize unread important emails"}],
    )

    assert plan["summary"] == "Run workflow: Daily email brief"
    assert plan["trigger"] == "Every weekday at 9:00 AM"
    assert plan["actions"] == ["Summarize unread important emails"]


def test_serialize_workflow_includes_runtime_metadata():
    workflow = Workflow(
        id=uuid4(),
        user_id=uuid4(),
        name="Daily inbox triage",
        trigger={"type": "schedule", "label": "Every weekday at 9:00 AM"},
        actions=[
            {"tool": "gmail", "label": "Summarize unread important emails"},
            {"tool": "slack", "label": "Draft team update"},
        ],
        status=WorkflowStatus.ACTIVE,
        metadata_={
            "last_agent_run_id": "run-123",
            "last_plan": {
                "summary": "Run workflow: Daily inbox triage",
                "actions": ["Summarize unread important emails", "Draft team update"],
            },
            "last_run_status": "completed",
            "last_run_summary": "Workflow completed 2 actions.",
        },
    )

    payload = _serialize(workflow)

    assert payload.last_agent_run_id == "run-123"
    assert payload.last_run_status == "completed"
    assert payload.last_run_summary == "Workflow completed 2 actions."
    assert payload.action_count == 2
    assert payload.needs_attention is False


def test_serialize_workflow_includes_clean_condition_summary():
    workflow = Workflow(
        id=uuid4(),
        user_id=uuid4(),
        name="Urgent Gmail triage",
        trigger={"type": "event", "label": "When matching activity appears"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.ACTIVE,
        metadata_={
            "condition_summary": "*Unread* | urgent - Gmail message exists",
        },
    )

    payload = _serialize(workflow)

    assert payload.condition_summary == "Unread urgent Gmail message exists"


def test_serialize_workflow_marks_write_actions_for_approval():
    workflow = Workflow(
        id=uuid4(),
        user_id=uuid4(),
        name="Slack publisher",
        trigger={"type": "manual", "label": "Manual run"},
        actions=[{"tool": "slack", "label": "*Post* | Slack - update"}],
        status=WorkflowStatus.ACTIVE,
    )

    payload = _serialize(workflow)

    assert payload.approval_required is True
    assert payload.approval_summary == "Approval required before external changes."


def test_serialize_workflow_includes_retry_metadata():
    workflow = Workflow(
        id=uuid4(),
        user_id=uuid4(),
        name="Daily inbox triage",
        trigger={"type": "schedule", "label": "Daily"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.ACTIVE,
        metadata_={
            "last_run_status": "failed",
            "last_run_summary": "Workflow completed 0 of 1 action(s).",
            "consecutive_failure_count": 2,
            "last_failure_at": "2026-05-31T09:00:00+00:00",
        },
    )

    payload = _serialize(workflow)

    assert payload.last_run_status == "failed"
    assert payload.consecutive_failure_count == 2
    assert payload.last_failure_at == "2026-05-31T09:00:00+00:00"
    assert payload.needs_attention is True


def test_build_workflow_run_plan_includes_workflow_id():
    plan = build_workflow_run_plan(
        workflow_name="Daily email brief",
        trigger={"type": "manual", "label": "Manual run"},
        actions=[{"tool": "gmail", "label": "Summarize unread important emails"}],
        workflow_id="workflow-123",
    )

    assert plan["workflow_id"] == "workflow-123"
    assert plan["summary"] == "Run workflow: Daily email brief"


async def test_execute_workflow_action_runs_internal_byteops_task():
    result = await execute_workflow_action(
        {"tool": "byteops", "label": "List urgent tasks"},
        user_id=uuid4(),
        db=None,
        run_id=uuid4(),
    )

    assert result["tool"] == "byteops"
    assert result["status"] == "completed"
    assert result["summary"] == "Listed urgent tasks."


async def test_execute_workflow_action_fails_when_gmail_is_not_connected():
    class EmptyScalarResult:
        def first(self):
            return None

    class EmptyDb:
        async def execute(self, statement):
            return EmptyScalarResult()

    result = await execute_workflow_action(
        {"tool": "gmail", "label": "Summarize Gmail"},
        user_id=uuid4(),
        db=EmptyDb(),
        run_id=uuid4(),
    )

    assert result["tool"] == "gmail"
    assert result["status"] == "failed"
    assert result["summary"] == "Gmail is not connected."


async def test_execute_workflow_action_runs_gmail_specialist(monkeypatch):
    user_id = uuid4()
    run_id = uuid4()
    connection = SimpleNamespace(
        user_id=user_id,
        tool_type=ToolType.GMAIL,
        status=ConnectionStatus.CONNECTED,
        access_token="token",
        refresh_token="refresh",
        token_expires_at=None,
    )
    calls = {}

    class ConnectedScalarResult:
        def first(self):
            return connection

    class ConnectedDb:
        async def execute(self, statement):
            calls["queried_connection"] = True
            return ConnectedScalarResult()

    async def fake_ensure_fresh_token(tool_connection, db):
        calls["refreshed"] = tool_connection
        return True

    async def fake_run_gmail_agent(user_message, history, tool_connection, queue, run_id=None, db=None):
        calls["user_message"] = user_message
        calls["history"] = history
        calls["tool_connection"] = tool_connection
        calls["run_id"] = run_id
        calls["db"] = db
        return "Two important Gmail messages need attention."

    monkeypatch.setattr("app.services.workflow_runner.ensure_fresh_token", fake_ensure_fresh_token)
    monkeypatch.setattr("app.services.workflow_runner.run_gmail_agent", fake_run_gmail_agent)

    result = await execute_workflow_action(
        {"tool": "gmail", "label": "Summarize unread important emails"},
        user_id=user_id,
        db=ConnectedDb(),
        run_id=run_id,
    )

    assert result["tool"] == "gmail"
    assert result["status"] == "completed"
    assert result["summary"] == "Two important Gmail messages need attention."
    assert calls["queried_connection"] is True
    assert calls["refreshed"] is connection
    assert calls["user_message"] == "Summarize unread important emails"
    assert calls["tool_connection"] is connection
    assert calls["run_id"] == run_id


async def test_execute_workflow_action_fails_when_slack_is_not_connected():
    class EmptyScalarResult:
        def first(self):
            return None

    class EmptyDb:
        async def execute(self, statement):
            return EmptyScalarResult()

    result = await execute_workflow_action(
        {"tool": "slack", "label": "Review Slack activity"},
        user_id=uuid4(),
        db=EmptyDb(),
        run_id=uuid4(),
    )

    assert result["tool"] == "slack"
    assert result["status"] == "failed"
    assert result["summary"] == "Slack is not connected."


async def test_execute_workflow_action_runs_slack_specialist(monkeypatch):
    user_id = uuid4()
    run_id = uuid4()
    connection = SimpleNamespace(
        user_id=user_id,
        tool_type=ToolType.SLACK,
        status=ConnectionStatus.CONNECTED,
        access_token="xoxb-token",
        refresh_token=None,
        token_expires_at=None,
    )
    calls = {}

    class ConnectedScalarResult:
        def first(self):
            return connection

    class ConnectedDb:
        async def execute(self, statement):
            calls["queried_connection"] = True
            return ConnectedScalarResult()

    async def fake_run_slack_agent(user_message, history, tool_connection, queue, run_id=None, db=None):
        calls["user_message"] = user_message
        calls["history"] = history
        calls["tool_connection"] = tool_connection
        calls["run_id"] = run_id
        calls["db"] = db
        return "One Slack thread needs a follow up."

    monkeypatch.setattr("app.services.workflow_runner.run_slack_agent", fake_run_slack_agent)

    result = await execute_workflow_action(
        {"tool": "slack", "label": "Review Slack activity"},
        user_id=user_id,
        db=ConnectedDb(),
        run_id=run_id,
    )

    assert result["tool"] == "slack"
    assert result["status"] == "completed"
    assert result["summary"] == "One Slack thread needs a follow up."
    assert calls["queried_connection"] is True
    assert calls["user_message"] == "Review Slack activity"
    assert calls["history"] == []
    assert calls["tool_connection"] is connection
    assert calls["run_id"] == run_id


async def test_execute_workflow_action_times_out_slow_specialist(monkeypatch):
    user_id = uuid4()
    run_id = uuid4()
    connection = SimpleNamespace(
        user_id=user_id,
        tool_type=ToolType.SLACK,
        status=ConnectionStatus.CONNECTED,
        access_token="xoxb-token",
        refresh_token=None,
        token_expires_at=None,
    )

    class ConnectedScalarResult:
        def first(self):
            return connection

    class ConnectedDb:
        async def execute(self, statement):
            return ConnectedScalarResult()

    async def slow_run_slack_agent(user_message, history, tool_connection, queue, run_id=None, db=None):
        import asyncio
        await asyncio.sleep(1)
        return "too late"

    monkeypatch.setattr("app.services.workflow_runner.WORKFLOW_ACTION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr("app.services.workflow_runner.run_slack_agent", slow_run_slack_agent)

    result = await execute_workflow_action(
        {"tool": "slack", "label": "Review Slack activity"},
        user_id=user_id,
        db=ConnectedDb(),
        run_id=run_id,
    )

    assert result["tool"] == "slack"
    assert result["status"] == "failed"
    assert result["summary"] == "Slack action timed out."


async def test_execute_workflow_action_fails_when_calendar_is_not_connected():
    class EmptyScalarResult:
        def first(self):
            return None

    class EmptyDb:
        async def execute(self, statement):
            return EmptyScalarResult()

    result = await execute_workflow_action(
        {"tool": "calendar", "label": "Find overdue calendar follow ups"},
        user_id=uuid4(),
        db=EmptyDb(),
        run_id=uuid4(),
    )

    assert result["tool"] == "calendar"
    assert result["status"] == "failed"
    assert result["summary"] == "Calendar is not connected."


async def test_execute_workflow_action_runs_calendar_specialist(monkeypatch):
    user_id = uuid4()
    run_id = uuid4()
    connection = SimpleNamespace(
        user_id=user_id,
        tool_type=ToolType.CALENDAR,
        status=ConnectionStatus.CONNECTED,
        access_token="calendar-token",
        refresh_token="refresh",
        token_expires_at=None,
    )
    calls = {}

    class ConnectedScalarResult:
        def first(self):
            return connection

    class ConnectedDb:
        async def execute(self, statement):
            calls["queried_connection"] = True
            return ConnectedScalarResult()

    async def fake_ensure_fresh_token(tool_connection, db):
        calls["refreshed"] = tool_connection
        return True

    async def fake_run_calendar_agent(
        user_message, history, tool_connection, queue, run_id=None, db=None
    ):
        calls["user_message"] = user_message
        calls["history"] = history
        calls["tool_connection"] = tool_connection
        calls["run_id"] = run_id
        calls["db"] = db
        return "Two calendar items need attention."

    monkeypatch.setattr("app.services.workflow_runner.ensure_fresh_token", fake_ensure_fresh_token)
    monkeypatch.setattr("app.services.workflow_runner.run_calendar_agent", fake_run_calendar_agent)

    result = await execute_workflow_action(
        {"tool": "calendar", "label": "Find overdue calendar follow ups"},
        user_id=user_id,
        db=ConnectedDb(),
        run_id=run_id,
    )

    assert result["tool"] == "calendar"
    assert result["status"] == "completed"
    assert result["summary"] == "Two calendar items need attention."
    assert calls["queried_connection"] is True
    assert calls["refreshed"] is connection
    assert calls["user_message"] == "Find overdue calendar follow ups"
    assert calls["history"] == []
    assert calls["tool_connection"] is connection
    assert calls["run_id"] == run_id


async def test_execute_workflow_action_fails_when_github_is_not_connected():
    class EmptyScalarResult:
        def first(self):
            return None

    class EmptyDb:
        async def execute(self, statement):
            return EmptyScalarResult()

    result = await execute_workflow_action(
        {"tool": "github", "label": "Review open pull requests"},
        user_id=uuid4(),
        db=EmptyDb(),
        run_id=uuid4(),
    )

    assert result["tool"] == "github"
    assert result["status"] == "failed"
    assert result["summary"] == "GitHub is not connected."


async def test_execute_workflow_action_runs_github_specialist(monkeypatch):
    user_id = uuid4()
    run_id = uuid4()
    connection = SimpleNamespace(
        user_id=user_id,
        tool_type=ToolType.GITHUB,
        status=ConnectionStatus.CONNECTED,
        access_token="github-token",
        refresh_token=None,
        token_expires_at=None,
    )
    calls = {}

    class ConnectedScalarResult:
        def first(self):
            return connection

    class ConnectedDb:
        async def execute(self, statement):
            calls["queried_connection"] = True
            return ConnectedScalarResult()

    async def fake_run_github_agent(
        user_message, history, tool_connection, queue, run_id=None, db=None
    ):
        calls["user_message"] = user_message
        calls["history"] = history
        calls["tool_connection"] = tool_connection
        calls["run_id"] = run_id
        calls["db"] = db
        return "Three pull requests need review."

    monkeypatch.setattr("app.services.workflow_runner.run_github_agent", fake_run_github_agent)

    result = await execute_workflow_action(
        {"tool": "github", "label": "Review open pull requests"},
        user_id=user_id,
        db=ConnectedDb(),
        run_id=run_id,
    )

    assert result["tool"] == "github"
    assert result["status"] == "completed"
    assert result["summary"] == "Three pull requests need review."
    assert calls["queried_connection"] is True
    assert calls["user_message"] == "Review open pull requests"
    assert calls["history"] == []
    assert calls["tool_connection"] is connection
    assert calls["run_id"] == run_id


async def test_execute_workflow_action_fails_when_jira_is_not_connected():
    class EmptyScalarResult:
        def first(self):
            return None

    class EmptyDb:
        async def execute(self, statement):
            return EmptyScalarResult()

    result = await execute_workflow_action(
        {"tool": "jira", "label": "List assigned Jira issues"},
        user_id=uuid4(),
        db=EmptyDb(),
        run_id=uuid4(),
    )

    assert result["tool"] == "jira"
    assert result["status"] == "failed"
    assert result["summary"] == "Jira is not connected."


async def test_execute_workflow_action_runs_jira_specialist(monkeypatch):
    user_id = uuid4()
    run_id = uuid4()
    connection = SimpleNamespace(
        user_id=user_id,
        tool_type=ToolType.JIRA,
        status=ConnectionStatus.CONNECTED,
        access_token="jira-token",
        refresh_token="refresh",
        token_expires_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        metadata_={"cloud_id": "cloud-123", "cloud_url": "https://jira.example"},
    )
    calls = {}

    class ConnectedScalarResult:
        def first(self):
            return connection

    class ConnectedDb:
        async def execute(self, statement):
            calls["queried_connection"] = True
            return ConnectedScalarResult()

    async def fake_ensure_fresh_token(tool_connection, db):
        calls["refreshed"] = tool_connection
        return True

    async def fake_run_jira_agent(user_message, history, tool_connection, queue, run_id=None, db=None):
        calls["user_message"] = user_message
        calls["history"] = history
        calls["tool_connection"] = tool_connection
        calls["run_id"] = run_id
        calls["db"] = db
        return "One Jira issue is blocked."

    monkeypatch.setattr("app.services.workflow_runner.ensure_fresh_token", fake_ensure_fresh_token)
    monkeypatch.setattr("app.services.workflow_runner.run_jira_agent", fake_run_jira_agent)

    result = await execute_workflow_action(
        {"tool": "jira", "label": "List assigned Jira issues"},
        user_id=user_id,
        db=ConnectedDb(),
        run_id=run_id,
    )

    assert result["tool"] == "jira"
    assert result["status"] == "completed"
    assert result["summary"] == "One Jira issue is blocked."
    assert calls["queried_connection"] is True
    assert calls["refreshed"] is connection
    assert calls["user_message"] == "List assigned Jira issues"
    assert calls["history"] == []
    assert calls["tool_connection"] is connection
    assert calls["run_id"] == run_id


async def test_execute_workflow_action_fails_when_dropbox_is_not_connected():
    class EmptyScalarResult:
        def first(self):
            return None

    class EmptyDb:
        async def execute(self, statement):
            return EmptyScalarResult()

    result = await execute_workflow_action(
        {"tool": "dropbox", "label": "Check shared Dropbox files"},
        user_id=uuid4(),
        db=EmptyDb(),
        run_id=uuid4(),
    )

    assert result["tool"] == "dropbox"
    assert result["status"] == "failed"
    assert result["summary"] == "Dropbox is not connected."


async def test_execute_workflow_action_runs_dropbox_specialist(monkeypatch):
    user_id = uuid4()
    run_id = uuid4()
    connection = SimpleNamespace(
        user_id=user_id,
        tool_type=ToolType.DROPBOX,
        status=ConnectionStatus.CONNECTED,
        access_token="dropbox-token",
        refresh_token=None,
        token_expires_at=None,
    )
    calls = {}

    class ConnectedScalarResult:
        def first(self):
            return connection

    class ConnectedDb:
        async def execute(self, statement):
            calls["queried_connection"] = True
            return ConnectedScalarResult()

    async def fake_run_dropbox_agent(
        user_message, history, tool_connection, queue, run_id=None, db=None
    ):
        calls["user_message"] = user_message
        calls["history"] = history
        calls["tool_connection"] = tool_connection
        calls["run_id"] = run_id
        calls["db"] = db
        return "One shared Dropbox file needs review."

    monkeypatch.setattr("app.services.workflow_runner.run_dropbox_agent", fake_run_dropbox_agent)

    result = await execute_workflow_action(
        {"tool": "dropbox", "label": "Check shared Dropbox files"},
        user_id=user_id,
        db=ConnectedDb(),
        run_id=run_id,
    )

    assert result["tool"] == "dropbox"
    assert result["status"] == "completed"
    assert result["summary"] == "One shared Dropbox file needs review."
    assert calls["queried_connection"] is True
    assert calls["user_message"] == "Check shared Dropbox files"
    assert calls["history"] == []
    assert calls["tool_connection"] is connection
    assert calls["run_id"] == run_id


async def test_execute_workflow_action_fails_unknown_tool():
    result = await execute_workflow_action(
        {"tool": "unknown", "label": "Do something"},
        user_id=uuid4(),
        db=None,
        run_id=uuid4(),
    )

    assert result["tool"] == "unknown"
    assert result["status"] == "failed"
    assert result["summary"] == "Unsupported workflow action tool: unknown."


async def test_execute_due_workflows_runs_only_due_active_scheduled_workflows(monkeypatch):
    now = datetime(2026, 5, 31, 9, 0, tzinfo=timezone.utc)
    user_id = uuid4()
    due_workflow = Workflow(
        id=uuid4(),
        user_id=user_id,
        name="Morning Gmail brief",
        trigger={"type": "schedule", "label": "Daily"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.ACTIVE,
        next_run_at=datetime(2026, 5, 31, 8, 55, tzinfo=timezone.utc),
    )
    future_workflow = Workflow(
        id=uuid4(),
        user_id=user_id,
        name="Future brief",
        trigger={"type": "schedule", "label": "Daily"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.ACTIVE,
        next_run_at=datetime(2026, 5, 31, 10, 0, tzinfo=timezone.utc),
    )
    paused_workflow = Workflow(
        id=uuid4(),
        user_id=user_id,
        name="Paused brief",
        trigger={"type": "schedule", "label": "Daily"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.PAUSED,
        next_run_at=datetime(2026, 5, 31, 8, 55, tzinfo=timezone.utc),
    )
    manual_workflow = Workflow(
        id=uuid4(),
        user_id=user_id,
        name="Manual brief",
        trigger={"type": "manual", "label": "Manual run"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.ACTIVE,
        next_run_at=datetime(2026, 5, 31, 8, 55, tzinfo=timezone.utc),
    )
    calls = []

    class WorkflowScalarResult:
        def all(self):
            return [due_workflow, future_workflow, paused_workflow, manual_workflow]

    class WorkflowResult:
        def scalars(self):
            return WorkflowScalarResult()

    class WorkflowDb:
        def __init__(self):
            self.commits = 0

        async def execute(self, statement):
            return WorkflowResult()

        async def commit(self):
            self.commits += 1

    async def fake_execute_workflow_run(workflow_name, workflow_id, trigger, actions, user_id, db):
        calls.append(
            {
                "workflow_name": workflow_name,
                "workflow_id": workflow_id,
                "trigger": trigger,
                "actions": actions,
                "user_id": user_id,
            }
        )
        return {
            "id": "run-123",
            "plan": {"summary": "Run workflow: Morning Gmail brief"},
            "status": "completed",
            "final_response": "Workflow completed 1 of 1 action(s).",
        }

    monkeypatch.setattr(
        "app.services.workflow_runner.execute_workflow_run", fake_execute_workflow_run
    )

    db = WorkflowDb()
    result = await execute_due_workflows(db, now=now)

    assert result == {"scanned": 4, "ran": 1}
    assert len(calls) == 1
    assert calls[0]["workflow_name"] == "Morning Gmail brief"
    assert due_workflow.last_run_at == now
    assert due_workflow.next_run_at == datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    assert due_workflow.metadata_["last_agent_run_id"] == "run-123"
    assert due_workflow.metadata_["last_run_status"] == "completed"
    assert due_workflow.metadata_["consecutive_failure_count"] == 0
    assert db.commits == 1


async def test_execute_due_workflows_retries_failed_scheduled_workflow(monkeypatch):
    now = datetime(2026, 5, 31, 9, 0, tzinfo=timezone.utc)
    workflow = Workflow(
        id=uuid4(),
        user_id=uuid4(),
        name="Morning Gmail brief",
        trigger={"type": "schedule", "label": "Daily"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.ACTIVE,
        next_run_at=datetime(2026, 5, 31, 8, 55, tzinfo=timezone.utc),
        metadata_={"consecutive_failure_count": 0},
    )

    class WorkflowScalarResult:
        def all(self):
            return [workflow]

    class WorkflowResult:
        def scalars(self):
            return WorkflowScalarResult()

    class WorkflowDb:
        def __init__(self):
            self.commits = 0

        async def execute(self, statement):
            return WorkflowResult()

        async def commit(self):
            self.commits += 1

    async def fake_execute_workflow_run(**kwargs):
        return {
            "id": "run-failed",
            "plan": {"summary": "Run workflow: Morning Gmail brief"},
            "status": "failed",
            "final_response": "Workflow completed 0 of 1 action(s).",
        }

    monkeypatch.setattr(
        "app.services.workflow_runner.execute_workflow_run", fake_execute_workflow_run
    )

    db = WorkflowDb()
    result = await execute_due_workflows(db, now=now)

    assert result == {"scanned": 1, "ran": 1}
    assert workflow.status == WorkflowStatus.ACTIVE
    assert workflow.last_error == "Workflow completed 0 of 1 action(s)."
    assert workflow.next_run_at == now + timedelta(minutes=15)
    assert workflow.metadata_["consecutive_failure_count"] == 1
    assert workflow.metadata_["last_run_status"] == "failed"
    assert workflow.metadata_["last_failure_at"] == now.isoformat()
    assert db.commits == 1


async def test_execute_due_workflows_marks_failed_after_retry_limit(monkeypatch):
    now = datetime(2026, 5, 31, 9, 0, tzinfo=timezone.utc)
    workflow = Workflow(
        id=uuid4(),
        user_id=uuid4(),
        name="Morning Gmail brief",
        trigger={"type": "schedule", "label": "Daily"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.ACTIVE,
        next_run_at=datetime(2026, 5, 31, 8, 55, tzinfo=timezone.utc),
        metadata_={"consecutive_failure_count": 2},
    )

    class WorkflowScalarResult:
        def all(self):
            return [workflow]

    class WorkflowResult:
        def scalars(self):
            return WorkflowScalarResult()

    class WorkflowDb:
        def __init__(self):
            self.commits = 0

        async def execute(self, statement):
            return WorkflowResult()

        async def commit(self):
            self.commits += 1

    async def fake_execute_workflow_run(**kwargs):
        return {
            "id": "run-failed",
            "plan": {"summary": "Run workflow: Morning Gmail brief"},
            "status": "failed",
            "final_response": "Workflow completed 0 of 1 action(s).",
        }

    monkeypatch.setattr(
        "app.services.workflow_runner.execute_workflow_run", fake_execute_workflow_run
    )

    db = WorkflowDb()
    result = await execute_due_workflows(db, now=now)

    assert result == {"scanned": 1, "ran": 1}
    assert workflow.status == WorkflowStatus.FAILED
    assert workflow.last_error == "Workflow completed 0 of 1 action(s)."
    assert workflow.next_run_at is None
    assert workflow.metadata_["consecutive_failure_count"] == 3
    assert workflow.metadata_["last_run_status"] == "failed"
    assert db.commits == 1


async def test_run_workflow_marks_manual_failure_for_attention(monkeypatch):
    user_id = uuid4()
    workflow = Workflow(
        id=uuid4(),
        user_id=user_id,
        name="Manual inbox triage",
        trigger={"type": "manual", "label": "Manual run"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.ACTIVE,
        metadata_={"consecutive_failure_count": 1},
    )

    class WorkflowDb:
        def __init__(self):
            self.commits = 0
            self.refreshed = []

        async def get(self, model, workflow_id):
            return workflow if workflow_id == workflow.id else None

        async def commit(self):
            self.commits += 1

        async def refresh(self, entity):
            self.refreshed.append(entity)

    async def fake_execute_workflow_run(**kwargs):
        return {
            "id": "run-failed",
            "plan": {"summary": "Run workflow: Manual inbox triage"},
            "status": "failed",
            "final_response": "Workflow completed 0 of 1 action(s).",
        }

    monkeypatch.setattr("app.api.workflows.execute_workflow_run", fake_execute_workflow_run)

    db = WorkflowDb()
    payload = await run_workflow(workflow.id, SimpleNamespace(id=user_id), db)

    assert payload.status == "failed"
    assert payload.last_error == "Workflow completed 0 of 1 action(s)."
    assert payload.last_run_status == "failed"
    assert payload.consecutive_failure_count == 2
    assert payload.needs_attention is True
    assert workflow.metadata_["last_agent_run_id"] == "run-failed"
    assert db.commits == 1
    assert db.refreshed == [workflow]


async def test_resume_scheduled_workflow_without_next_run_sets_next_run_time():
    user_id = uuid4()
    workflow = Workflow(
        id=uuid4(),
        user_id=user_id,
        name="Morning Gmail brief",
        trigger={"type": "schedule", "label": "Every morning"},
        actions=[{"tool": "gmail", "label": "Summarize Gmail"}],
        status=WorkflowStatus.PAUSED,
        next_run_at=None,
    )

    class WorkflowDb:
        def __init__(self):
            self.commits = 0
            self.refreshed = []

        async def get(self, model, workflow_id):
            return workflow if workflow_id == workflow.id else None

        async def commit(self):
            self.commits += 1

        async def refresh(self, entity):
            self.refreshed.append(entity)

    db = WorkflowDb()
    payload = await resume_workflow(workflow.id, SimpleNamespace(id=user_id), db)

    assert payload.status == "active"
    assert workflow.next_run_at is not None
    assert payload.next_run_at is not None
    assert db.commits == 1
    assert db.refreshed == [workflow]
