"""apply_llm_monitoring gates on risky steps and persists best-effort."""

import pytest

import app.services.agent_runtime as rt


def _run():
    class Run:
        llm_score = None
        llm_reasoning = None
        flagged = False
    return Run()


def test_has_risky_step_detects_external_send():
    steps = [{"step_type": "tool_call", "name": "send_email", "status": "completed"}]
    assert rt.has_risky_step(steps) is True


def test_has_risky_step_false_for_read_only():
    steps = [{"step_type": "tool_call", "name": "search_emails", "status": "completed"},
             {"step_type": "plan", "name": "initial_plan", "status": "completed"}]
    assert rt.has_risky_step(steps) is False


@pytest.mark.anyio
async def test_apply_llm_monitoring_persists(monkeypatch):
    async def fake_score(steps):
        return {"score": 9, "reasoning": "looks bad", "flagged": True}
    monkeypatch.setattr(rt, "score_run_llm", fake_score)
    run = _run()
    steps = [{"step_type": "tool_call", "name": "forward_email", "status": "completed"}]
    await rt.apply_llm_monitoring(run, steps)
    assert run.llm_score == 9
    assert run.llm_reasoning == "looks bad"
    assert run.flagged is True


@pytest.mark.anyio
async def test_apply_llm_monitoring_skips_read_only(monkeypatch):
    called = {"v": False}
    async def fake_score(steps):
        called["v"] = True
        return {"score": 9, "reasoning": "x", "flagged": True}
    monkeypatch.setattr(rt, "score_run_llm", fake_score)
    run = _run()
    steps = [{"step_type": "tool_call", "name": "search_emails", "status": "completed"}]
    await rt.apply_llm_monitoring(run, steps)
    assert called["v"] is False        # gated: read-only run never calls the LLM
    assert run.llm_score is None


@pytest.mark.anyio
async def test_apply_llm_monitoring_swallows_errors(monkeypatch):
    async def boom(steps):
        raise RuntimeError("llm down")
    monkeypatch.setattr(rt, "score_run_llm", boom)
    run = _run()
    steps = [{"step_type": "tool_call", "name": "send_email", "status": "completed"}]
    await rt.apply_llm_monitoring(run, steps)   # must not raise
    assert run.llm_score is None
