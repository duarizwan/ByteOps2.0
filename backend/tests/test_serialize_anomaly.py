"""serialize_agent_run exposes anomaly fields."""

from types import SimpleNamespace

from app.services.agent_runtime import serialize_agent_run


def _run(**overrides):
    base = dict(
        id="11111111-1111-1111-1111-111111111111",
        user_id="22222222-2222-2222-2222-222222222222",
        conversation_id=None,
        intent="general",
        status="completed",
        plan=None,
        final_response="done",
        error=None,
        metadata_=None,
        created_at=None,
        updated_at=None,
        completed_at=None,
        steps=[],
        anomaly_score=0.42,
        step_scores={"step-1": 0.9},
        flagged=True,
        data_label="redteam",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_serialize_includes_anomaly_fields():
    data = serialize_agent_run(_run())
    assert data["anomaly_score"] == 0.42
    assert data["step_scores"] == {"step-1": 0.9}
    assert data["flagged"] is True
    assert data["data_label"] == "redteam"


def test_serialize_defaults_when_unscored():
    data = serialize_agent_run(_run(anomaly_score=None, step_scores=None, flagged=False, data_label="unlabeled"))
    assert data["anomaly_score"] is None
    assert data["flagged"] is False
