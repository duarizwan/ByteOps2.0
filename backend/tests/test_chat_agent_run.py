"""Tests for chat-to-Agent Runtime planning hooks."""

from pathlib import Path

from app.agents.orchestrator import detect_intent
from app.services.agent_planner import build_agent_plan
from app.services.workflow_creation import is_workflow_creation_request


def test_chat_runtime_plan_for_connected_gmail():
    intent = detect_intent("Summarize my unread emails", [])
    plan = build_agent_plan("Summarize my unread emails", intent, ["gmail"])

    assert intent == "gmail"
    assert plan["blocked"] is False
    assert plan["requires_tools"] == ["gmail"]


def test_chat_runtime_plan_blocks_missing_gmail():
    intent = detect_intent("Summarize my unread emails", [])
    plan = build_agent_plan("Summarize my unread emails", intent, [])

    assert intent == "gmail"
    assert plan["blocked"] is True
    assert plan["block_reason"] == "gmail is not connected"


def test_workflow_creation_requests_use_workflow_runtime_intent():
    message = "Create a workflow that summarizes Gmail and Slack every morning and lists urgent tasks."
    intent = "workflow" if is_workflow_creation_request(message) else detect_intent(message, [])
    plan = build_agent_plan(message, intent, ["gmail", "slack"])

    assert intent == "workflow"
    assert plan["blocked"] is False
    assert plan["requires_tools"] == []


def test_chat_sse_stream_has_watchdog_for_silent_queue():
    source = Path("app/api/chat.py").read_text(encoding="utf-8")

    assert "CHAT_STREAM_IDLE_TIMEOUT_SECONDS" in source
    assert "timeout=CHAT_STREAM_IDLE_TIMEOUT_SECONDS" in source
    assert 'yield _sse("error", "Chat request timed out before ByteOps could respond.")' in source


def test_chat_sse_stream_surfaces_task_crashes_before_timeout():
    source = Path("app/api/chat.py").read_text(encoding="utf-8")

    assert "asyncio.wait(" in source
    assert "queue_task = asyncio.create_task(queue.get())" in source
    assert "chat_task = asyncio.create_task(_run_chat(request, current_user, db, queue))" in source
    assert 'yield _sse("error", "Chat request failed before ByteOps could respond.")' in source


def test_chat_workflow_requests_always_emit_reviewable_drafts():
    source = Path("app/api/chat.py").read_text(encoding="utf-8")
    workflow_branch = source[source.index('if intent == "workflow":'):source.index('elif intent == "gmail":')]

    assert "workflow_draft_response(draft)" in workflow_branch
    assert 'await queue.put(("workflow_draft"' in workflow_branch
    assert "create_workflow_from_prompt" not in workflow_branch
