"""Tests for the Agent Runtime ledger helpers."""

from datetime import datetime, timezone
from uuid import uuid4

from app.models.agent_run import AgentRun, AgentRunStatus, AgentRunStep, AgentRunStepType
from app.services.agent_planner import build_agent_plan
from app.services.agent_runtime import serialize_agent_run


def test_serialize_agent_run_includes_steps_and_status():
    run = AgentRun(
        id=uuid4(),
        user_id=uuid4(),
        conversation_id=uuid4(),
        user_message_id=uuid4(),
        intent="gmail",
        status=AgentRunStatus.COMPLETED,
        plan={"summary": "Summarize unread Gmail messages", "steps": ["Read Gmail", "Summarize"]},
        final_response="You have two important emails.",
        created_at=datetime(2026, 5, 29, 10, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 29, 10, 1, tzinfo=timezone.utc),
    )
    run.steps = [
        AgentRunStep(
            id=uuid4(),
            run_id=run.id,
            step_type=AgentRunStepType.TOOL_CALL,
            name="gmail.search_emails",
            status="completed",
            input={"query": "is:unread"},
            output={"count": 2},
            created_at=datetime(2026, 5, 29, 10, 0, tzinfo=timezone.utc),
        )
    ]

    data = serialize_agent_run(run)

    assert data["status"] == "completed"
    assert data["intent"] == "gmail"
    assert data["plan"]["summary"] == "Summarize unread Gmail messages"
    assert data["steps"][0]["name"] == "gmail.search_emails"
    assert data["steps"][0]["output"] == {"count": 2}


def test_build_agent_plan_for_gmail_task():
    plan = build_agent_plan(
        user_message="Summarize my unread emails",
        intent="gmail",
        connected_tools=["gmail"],
    )

    assert plan["intent"] == "gmail"
    assert plan["requires_tools"] == ["gmail"]
    assert plan["steps"] == [
        "Route to gmail specialist",
        "Execute requested gmail work",
        "Verify answer addresses the request",
    ]


def test_plan_marks_missing_tool():
    plan = build_agent_plan(
        user_message="Summarize my unread emails",
        intent="gmail",
        connected_tools=[],
    )

    assert plan["blocked"] is True
    assert plan["block_reason"] == "gmail is not connected"


def test_serialized_failed_run_exposes_clean_error():
    run = AgentRun(
        id=uuid4(),
        user_id=uuid4(),
        intent="slack",
        status=AgentRunStatus.FAILED,
        error="Slack token expired",
    )

    data = serialize_agent_run(run)

    assert data["status"] == "failed"
    assert data["error"] == "Slack token expired"
