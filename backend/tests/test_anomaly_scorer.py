"""AnomalyScorer degrades gracefully when artifacts are missing."""

from app.anomaly.scorer import AnomalyScorer


def test_scorer_unavailable_returns_none(tmp_path):
    scorer = AnomalyScorer(artifacts_dir=tmp_path)  # empty dir, no model
    assert scorer.available is False
    steps = [{"step_type": "plan", "name": "initial_plan", "status": "completed"}]
    assert scorer.score_run(steps) is None
