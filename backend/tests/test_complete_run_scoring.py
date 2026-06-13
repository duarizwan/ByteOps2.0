"""complete_agent_run applies anomaly scoring without breaking on failure."""

import app.services.agent_runtime as rt


class _FakeScorer:
    available = True

    def score_run(self, steps):
        return {"anomaly_score": 1.23, "step_scores": {"x": 1.23}, "flagged": True}


def test_apply_scoring_sets_fields(monkeypatch):
    monkeypatch.setattr(rt, "_scorer", _FakeScorer())

    class Run:
        anomaly_score = None
        step_scores = None
        flagged = False

    run = Run()
    steps = [{"id": "x", "step_type": "final", "name": "final", "status": "completed"}]
    rt.apply_anomaly_scoring(run, steps)
    assert run.anomaly_score == 1.23
    assert run.flagged is True
    assert run.step_scores == {"x": 1.23}


def test_apply_scoring_swallows_errors(monkeypatch):
    class Boom:
        available = True

        def score_run(self, steps):
            raise RuntimeError("model exploded")

    monkeypatch.setattr(rt, "_scorer", Boom())

    class Run:
        anomaly_score = None
        step_scores = None
        flagged = False

    run = Run()
    rt.apply_anomaly_scoring(run, [{"id": "x", "step_type": "final", "name": "f", "status": "completed"}])
    assert run.anomaly_score is None  # unchanged; no exception raised
