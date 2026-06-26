---
id: 027
title: Persist LLM-monitor score on runs
stage: green
date: 2026-06-13
surface: agent
model: claude-opus-4-8
feature: dl-anomaly-detection
branch: feat/dl-anomaly-detection
user: dua.rizwan@jonasclub.com
command: implement TASK 14
labels: [anomaly, llm-monitor, agent-runtime, tdd, migration]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - backend/app/models/agent_run.py
 - backend/alembic/versions/0004_llm_monitor_fields.py
 - backend/app/services/agent_runtime.py
 - backend/tests/test_llm_monitor_wiring.py
tests:
 - backend/tests/test_llm_monitor_wiring.py (5 new tests)
 - backend/tests/test_serialize_anomaly.py (regression)
 - full suite: 128 passed
---

## Prompt

Implement TASK 14 (strict TDD): persist the LLM-monitor score on agent runs.
(a) add two DB columns (llm_score int, llm_reasoning text) to AgentRun;
(b) wire score_run_llm into complete_agent_run, gated so it only runs for runs
containing a risky step (write/external_send/destructive) to control LLM cost;
(c) expose the fields in serialize_agent_run. Add migration 0004_llm_monitor_fields
on top of 0003_anomaly_fields. Do not run alembic upgrade. Write the failing test
first (test_llm_monitor_wiring.py), confirm RED, implement, confirm GREEN, run the
full suite, then commit only the four named files.

## Response snapshot

- Added `llm_score` / `llm_reasoning` columns to `AgentRun` after `data_label`.
- Created alembic revision `0004_llm_monitor_fields` (down_revision `0003_anomaly_fields`).
- Added `has_risky_step(steps)` and async `apply_llm_monitoring(run, steps)` to
  `agent_runtime.py`; imported `score_run_llm` and `classify_tool_call`.
  Gating uses `classify_tool_call("", name).risk.value in {write,external_send,destructive}`.
  `apply_llm_monitoring` is best-effort (swallows all exceptions, sets `flagged` on hit).
- Wired the call into `complete_agent_run` right after `apply_anomaly_scoring`, before the commit.
- Added `llm_score` / `llm_reasoning` to `serialize_agent_run`.
- TDD: RED (5 failures: missing has_risky_step/score_run_llm) -> GREEN (7 passed incl. regression).
- Async tests collected via pytest-asyncio mode=AUTO + anyio plugin; conftest `anyio_backend` fixture already present. No collection adjustment needed.

## Outcome

- ✅ Impact: LLM black-box monitor score now persisted on risky runs and surfaced via the run serializer.
- 🧪 Tests: 5 new wiring tests + serialize regression green; full suite 128 passed, 1 pre-existing unrelated warning.
- 📁 Files: 4 changed (model, migration, runtime, test). Commit 0ea4625.
- 🔁 Next prompts: controller to apply migration 0004; frontend surfacing of llm_score/llm_reasoning.
- 🧠 Reflection: gating on risk class keeps LLM cost bounded to write/send/destructive runs.

## Evaluation notes (flywheel)

- Failure modes observed: none; classification values matched expectations (send_email/forward_email -> external_send, search_emails -> read).
- Graders run and results (PASS/FAIL): pytest PASS (128).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): consider also persisting llm flagged separately from LSTM flagged for attribution.
