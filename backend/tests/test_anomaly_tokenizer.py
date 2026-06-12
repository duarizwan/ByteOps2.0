"""Tests for the anomaly tokenizer."""

from app.anomaly.tokenizer import PAD, UNK, step_to_token
from app.anomaly.tokenizer import build_vocab, encode_tokens, run_to_tokens


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


def test_run_to_tokens_preserves_order():
    steps = [
        {"step_type": "plan", "name": "initial_plan", "status": "completed"},
        {"step_type": "tool_call", "name": "search_emails", "status": "completed"},
    ]
    assert run_to_tokens(steps) == ["plan|none|completed", "tool_call|read|completed"]


def test_build_vocab_reserves_special_tokens():
    vocab = build_vocab([["a|b|c"], ["a|b|c", "d|e|f"]])
    assert vocab[PAD] == 0
    assert vocab[UNK] == 1
    assert vocab["a|b|c"] >= 2
    assert vocab["d|e|f"] >= 2


def test_encode_pads_to_max_len():
    vocab = {PAD: 0, UNK: 1, "a|b|c": 2}
    encoded = encode_tokens(["a|b|c"], vocab, max_len=4)
    assert encoded == [2, 0, 0, 0]


def test_encode_truncates_and_maps_unknown():
    vocab = {PAD: 0, UNK: 1, "a|b|c": 2}
    encoded = encode_tokens(["a|b|c", "z|z|z", "a|b|c"], vocab, max_len=2)
    assert encoded == [2, 1]  # truncated to 2; unknown -> UNK(1)
