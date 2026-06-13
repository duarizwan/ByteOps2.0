"""AnomalyScorer degrades gracefully when artifacts are missing."""

from app.anomaly.scorer import AnomalyScorer


def test_scorer_unavailable_returns_none(tmp_path):
    scorer = AnomalyScorer(artifacts_dir=tmp_path)  # empty dir, no model
    assert scorer.available is False
    steps = [{"step_type": "plan", "name": "initial_plan", "status": "completed"}]
    assert scorer.score_run(steps) is None


import json

import numpy as np


def _write_fake_artifacts(tmp_path):
    """Create a tiny ONNX model + vocab + meta for testing."""
    import onnx
    from onnx import TensorProto, helper

    vocab = {"<PAD>": 0, "<UNK>": 1, "plan|none|completed": 2, "tool_call|read|completed": 3,
             "tool_call|external_send|completed": 4}
    max_len = 6
    vocab_size = len(vocab)

    weight = (np.eye(vocab_size, dtype=np.float32) * 5.0)
    w_init = helper.make_tensor("W", TensorProto.FLOAT, weight.shape, weight.flatten().tolist())
    tokens_in = helper.make_tensor_value_info("tokens", TensorProto.INT64, [1, max_len])
    logits_out = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, max_len, vocab_size])
    gather = helper.make_node("Gather", ["W", "tokens"], ["logits"], axis=0)
    graph = helper.make_graph([gather], "tiny", [tokens_in], [logits_out], [w_init])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 9
    onnx.save(model, str(tmp_path / "lstm_nextaction.onnx"))
    (tmp_path / "vocab.json").write_text(json.dumps(vocab), encoding="utf-8")
    (tmp_path / "model_meta.json").write_text(
        json.dumps({"max_len": max_len, "threshold": 2.0}), encoding="utf-8"
    )


def test_scorer_produces_step_scores(tmp_path):
    _write_fake_artifacts(tmp_path)
    scorer = AnomalyScorer(artifacts_dir=tmp_path)
    assert scorer.available is True
    steps = [
        {"id": "s0", "step_type": "plan", "name": "initial_plan", "status": "completed"},
        {"id": "s1", "step_type": "tool_call", "name": "search_emails", "status": "completed"},
        {"id": "s2", "step_type": "tool_call", "name": "send_email", "status": "completed"},
    ]
    result = scorer.score_run(steps)
    assert set(result) == {"anomaly_score", "step_scores", "flagged"}
    assert set(result["step_scores"]) == {"s0", "s1", "s2"}
    assert isinstance(result["anomaly_score"], float)
    assert isinstance(result["flagged"], bool)
