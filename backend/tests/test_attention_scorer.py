from app.anomaly.attention_scorer import AttentionScorer


def test_unavailable_returns_none(tmp_path):
    s = AttentionScorer(artifacts_dir=tmp_path)  # empty dir, no model
    assert s.available is False
    assert s.score_run([{"step_type": "plan", "name": "initial_plan", "status": "completed"}]) is None
