---
id: 025
title: Wire scoring into run completion
stage: green
date: 2026-06-13
surface: agent
model: claude-opus-4-8
feature: dl-anomaly-detection
branch: feat/dl-anomaly-detection
user: dua.rizwan@jonasclub.com
command: TASK 7 — Wire scoring into run completion
labels: [anomaly, agent-runtime, tdd, scoring]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - backend/app/services/agent_runtime.py
 - backend/tests/test_complete_run_scoring.py
tests:
 - backend/tests/test_complete_run_scoring.py::test_apply_scoring_sets_fields
 - backend/tests/test_complete_run_scoring.py::test_apply_scoring_swallows_errors
---

## Prompt

TASK 7: Wire scoring into run completion. Strict TDD.

Step 1 — Create test `backend/tests/test_complete_run_scoring.py` covering `apply_anomaly_scoring(run, steps)`: one test asserting fields are set from a fake scorer, one test asserting errors are swallowed (fields unchanged).

Step 2 — Run the test (expect FAIL: module has no attribute 'apply_anomaly_scoring').

Step 3 — In `backend/app/services/agent_runtime.py`, add `from app.anomaly.scorer import AnomalyScorer`, a module-level `_scorer = AnomalyScorer()`, and `apply_anomaly_scoring(run, steps)` (best-effort, never raises). Then update `complete_agent_run` to refresh steps, build step dicts, call `apply_anomaly_scoring`, commit/refresh, rolling back on any exception. Do not duplicate existing imports (datetime/timezone/AgentRun/AgentRunStatus).

Step 4 — Run the new test (expect PASS).

Step 5 — Run the full backend suite; existing tests must still pass (scorer unavailable, no-op).

Step 6 — Commit only the two files with message "feat(anomaly): score runs on completion (best-effort)". Leave unrelated stray files alone.

Report: status, both test results, full-suite summary line, commit SHA, concerns.

## Response snapshot

Implemented via strict TDD. Confirmed `datetime`, `timezone`, `AgentRun`, `AgentRunStatus` already imported. Added `from app.anomaly.scorer import AnomalyScorer`, module-level `_scorer = AnomalyScorer()`, and `apply_anomaly_scoring(run, steps)` that no-ops when the scorer is unavailable, applies anomaly_score/step_scores/flagged from the result, and swallows all exceptions. Rewrote `complete_agent_run` to refresh `run.steps`, build lightweight step dicts, call `apply_anomaly_scoring`, then commit/refresh — wrapped in try/except with `db.rollback()` so scoring can never break run completion.

RED: 2 failed (AttributeError: module has no attribute '_scorer'). GREEN: 2 passed. Full suite: 120 passed, 1 warning (pre-existing oauth coroutine RuntimeWarning, unrelated). Committed only the two task files as ea6e07d.

## Outcome

- ✅ Impact: Completed runs are now scored for anomalies best-effort, persisting anomaly_score/step_scores/flagged without risk to run completion.
- 🧪 Tests: 2 new unit tests pass; full suite 120 passed, 1 pre-existing warning.
- 📁 Files: backend/app/services/agent_runtime.py (import + apply_anomaly_scoring + complete_agent_run), backend/tests/test_complete_run_scoring.py (new).
- 🔁 Next prompts: Commit trained ONNX artifacts so the scorer becomes available; add an integration test exercising complete_agent_run with a real DB session.
- 🧠 Reflection: Scoring is a no-op in tests since no artifacts are committed, so existing behavior is preserved.

## Evaluation notes (flywheel)

- Failure modes observed: None; RED→GREEN as expected.
- Graders run and results (PASS/FAIL): pytest PASS (122 total incl. new).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): Add a DB-backed test for complete_agent_run's step refresh path.
