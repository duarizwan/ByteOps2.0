"""Tests for the anomaly tokenizer."""

from app.anomaly.tokenizer import PAD, UNK, step_to_token


def test_tool_call_step_uses_risk_class():
    step = {"step_type": "tool_call", "name": "send_email", "status": "completed"}
    assert step_to_token(step) == "tool_call|external_send|completed"


def test_read_tool_call_token():
    step = {"step_type": "tool_call", "name": "search_emails", "status": "completed"}
    assert step_to_token(step) == "tool_call|read|completed"


def test_non_tool_step_has_none_risk():
    step = {"step_type": "plan", "name": "initial_plan", "status": "completed"}
    assert step_to_token(step) == "plan|none|completed"


def test_special_tokens_are_distinct():
    assert PAD == "<PAD>"
    assert UNK == "<UNK>"
    assert PAD != UNK
