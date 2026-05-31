"""Tests for backend-enforced agent tool policy."""

from app.services.agent_policy import ToolRisk, classify_tool_call, requires_approval


def test_read_tools_do_not_require_approval():
    decision = classify_tool_call("gmail", "search_emails")

    assert decision.risk == ToolRisk.READ
    assert requires_approval(decision) is False


def test_send_and_delete_tools_require_approval():
    send_decision = classify_tool_call("slack", "send_message")
    delete_decision = classify_tool_call("calendar", "delete_event")

    assert send_decision.risk == ToolRisk.EXTERNAL_SEND
    assert delete_decision.risk == ToolRisk.DESTRUCTIVE
    assert requires_approval(send_decision) is True
    assert requires_approval(delete_decision) is True
