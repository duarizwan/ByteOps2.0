---
id: 034
title: Prefer attention scores for run-graph heat
stage: green
date: 2026-06-14
surface: agent
model: claude-opus-4-8
feature: dl-anomaly-detection
branch: feat/dl-anomaly-detection
user: dua.rizwan@jonasclub.com
command: TASK 13
labels: [anomaly, attention, scoring, run-graph]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - backend/app/services/agent_runtime.py
 - backend/tests/test_complete_run_scoring.py
tests:
 - tests/test_complete_run_scoring.py::test_apply_scoring_sets_fields
 - tests/test_complete_run_scoring.py::test_apply_scoring_swallows_errors
---

## Prompt

TASK 13: Prefer attention scores for the run-graph heat. Add an AttentionScorer singleton (`_attn_scorer`) to agent_runtime.py and modify `apply_anomaly_scoring(run, steps)` to try the supervised attention model first (better per-step localization), falling back to the LSTM NLL scorer (`_scorer`) otherwise. Keep best-effort (never raises). Also set `run.llm_reasoning` from the attention scorer's reasoning when present and not already set. Update test_complete_run_scoring.py to monkeypatch `rt._attn_scorer` to a fake-unavailable object so the LSTM fallback path is still exercised (a real clf_bilstm_attn.onnx exists in artifacts). Run targeted test + full suite, then commit only the two files.

## Response snapshot

Added `from app.anomaly.attention_scorer import AttentionScorer` and `_attn_scorer = AttentionScorer()` next to the existing `_scorer = AnomalyScorer()`. Rewrote `apply_anomaly_scoring` to try `_attn_scorer` first (when `.available`), fall back to `_scorer`, set anomaly_score/step_scores/flagged, and populate `run.llm_reasoning` from the attention reasoning when present and not already set. Updated both tests to monkeypatch `rt._attn_scorer` to an `_OffAttention` fake (`available = False`) so the LSTM fallback path is exercised despite a real attention model being present in artifacts. Targeted test: 2 passed. Full suite: 164 passed, 1 pre-existing unrelated warning. Committed as 05384b4.

## Outcome

- ✅ Impact: Run-graph heat now uses the supervised attention model's per-step weights when available, with graceful LSTM fallback.
- 🧪 Tests: tests/test_complete_run_scoring.py 2 passed; full suite 164 passed.
- 📁 Files: agent_runtime.py (scorer singleton + scoring logic), test_complete_run_scoring.py (attention-off monkeypatch).
- 🔁 Next prompts: Verify frontend run-graph renders attention-derived step_scores as expected.
- 🧠 Reflection: A real attention model in artifacts would have shadowed the fake `_scorer`; disabling `_attn_scorer` in tests keeps the LSTM-path assertions meaningful.

## Evaluation notes (flywheel)

- Failure modes observed: None; anticipated test-shadowing by real model handled via `_OffAttention` monkeypatch.
- Graders run and results (PASS/FAIL): PASS (targeted 2/2, suite 164/164).
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Confirm `llm_reasoning` population does not conflict with the LLM monitor's later write.
