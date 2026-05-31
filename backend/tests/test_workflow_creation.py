"""Tests for creating workflow drafts from natural-language chat prompts."""

from app.services.workflow_creation import (
    create_workflow_from_prompt,
    create_workflow_from_draft,
    build_workflow_draft,
    is_workflow_creation_request,
    workflow_draft_response,
)


class FakeWorkflowDb:
    def __init__(self):
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.committed = True

    async def refresh(self, value):
        self.refreshed.append(value)


def test_detects_workflow_creation_request():
    assert is_workflow_creation_request(
        "Create a workflow that summarizes Gmail and Slack every morning and lists urgent tasks."
    ) is True
    assert is_workflow_creation_request("Summarize my unread Gmail emails") is False


def test_build_workflow_draft_from_morning_gmail_slack_prompt():
    draft = build_workflow_draft(
        "Create a workflow that summarizes Gmail and Slack every morning and lists urgent tasks.",
        connected_tools=["gmail", "slack"],
    )

    assert draft["name"] == "Morning Gmail and Slack brief"
    assert draft["trigger"] == {"type": "schedule", "label": "Every morning"}
    assert draft["actions"] == [
        {"tool": "gmail", "label": "Summarize Gmail"},
        {"tool": "slack", "label": "Summarize Slack"},
        {"tool": "byteops", "label": "List urgent tasks"},
    ]
    assert draft["missing_tools"] == []


def test_build_workflow_draft_reports_missing_connected_tools():
    draft = build_workflow_draft(
        "Create a workflow that summarizes Gmail and Slack every morning.",
        connected_tools=["gmail"],
    )

    assert draft["missing_tools"] == ["slack"]
    assert draft["requires_review"] is True
    assert draft["review_reasons"] == ["Connect Slack before this workflow can run."]


def test_build_workflow_draft_requires_review_for_write_actions():
    draft = build_workflow_draft(
        "Create a workflow that posts a Slack update every morning.",
        connected_tools=["slack"],
    )

    assert draft["requires_review"] is True
    assert draft["review_reasons"] == ["Review and approve write actions before saving."]


def test_workflow_draft_response_uses_plain_text_without_markdown_markers():
    draft = build_workflow_draft(
        "Create a workflow that summarizes Gmail and Slack every morning.",
        connected_tools=["gmail"],
    )

    response = workflow_draft_response(draft)

    assert "Draft workflow ready for review." in response
    assert "Connect Slack before this workflow can run." in response
    assert "*" not in response
    assert "|" not in response
    assert "-" not in response


async def test_create_workflow_from_draft_pauses_when_tools_are_missing():
    db = FakeWorkflowDb()
    draft = build_workflow_draft(
        "Create a workflow that summarizes Gmail and Slack every morning.",
        connected_tools=["gmail"],
    )

    workflow = await create_workflow_from_draft(db, user_id="user-123", draft=draft)

    assert workflow.name == "Morning Gmail and Slack brief"
    assert workflow.status == "paused"
    assert workflow.metadata_["created_from_reviewed_draft"] is True
    assert workflow.metadata_["missing_tools"] == ["slack"]
    assert db.added == [workflow]
    assert db.committed is True
    assert db.refreshed == [workflow]


async def test_create_scheduled_workflow_from_draft_sets_next_run_time():
    db = FakeWorkflowDb()
    draft = build_workflow_draft(
        "Create a workflow that summarizes Gmail every morning.",
        connected_tools=["gmail"],
    )

    workflow = await create_workflow_from_draft(db, user_id="user-123", draft=draft)

    assert workflow.status == "active"
    assert workflow.trigger["type"] == "schedule"
    assert workflow.next_run_at is not None


async def test_create_scheduled_workflow_from_prompt_sets_next_run_time():
    db = FakeWorkflowDb()

    workflow, draft = await create_workflow_from_prompt(
        db,
        user_id="user-123",
        message="Create a workflow that summarizes Gmail every morning.",
        connected_tools=["gmail"],
    )

    assert draft["trigger"]["type"] == "schedule"
    assert workflow.status == "active"
    assert workflow.next_run_at is not None
