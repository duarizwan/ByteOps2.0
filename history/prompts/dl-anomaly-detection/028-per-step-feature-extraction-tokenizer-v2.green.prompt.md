---
id: 028
title: Per-Step Feature Extraction Tokenizer v2
stage: green
date: 2026-06-13
surface: agent
model: claude-sonnet-4-6
feature: dl-anomaly-detection
branch: feat/dl-anomaly-detection
user: Dua Rizwan
command: implement task 2 — extract_step_features + NUMERIC_FEATURES
labels: ["anomaly-detection","feature-extraction","tdd","tokenizer-v2","onnx"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/anomaly/features.py
  - backend/tests/test_features.py
tests:
  - tests/test_features.py::test_infer_tool_from_action_name
  - tests/test_features.py::test_action_category
  - tests/test_features.py::test_extract_step_features_categoricals_and_numerics
  - tests/test_features.py::test_cross_tool_flag
---

## Prompt

Implement Task 2 in strict TDD: append tests for `extract_step_features` and `NUMERIC_FEATURES` to `backend/tests/test_features.py`, confirm red phase (ImportError), then append the implementation to `backend/app/anomaly/features.py` (NUMERIC_FEATURES list + `_risk_level` helper + `extract_step_features` function), confirm all 4 tests pass, then commit only the two files with message "feat(anomaly): per-step feature extraction (tokenizer v2)".

## Response snapshot

- Appended 2 new tests (`test_extract_step_features_categoricals_and_numerics`, `test_cross_tool_flag`) to `backend/tests/test_features.py`.
- Confirmed red phase: `ImportError: cannot import name 'extract_step_features'` (exit code 2), 2 existing tests blocked from collection.
- Appended `NUMERIC_FEATURES`, `_RISK_ORDINAL`, `_risk_level()`, and `extract_step_features()` to `backend/app/anomaly/features.py` without touching existing code.
- Confirmed green phase: all 4 tests pass in 0.03s.
- Committed as `d3e0502` with CRLF warnings (harmless on Windows).

## Outcome

- Impact: `extract_step_features` now produces a complete per-step feature dict (3 categoricals + 9 numerics) usable by the LSTM/sequence model pipeline.
- Tests: 4/4 PASS — `test_infer_tool_from_action_name`, `test_action_category`, `test_extract_step_features_categoricals_and_numerics`, `test_cross_tool_flag`.
- Files: `backend/app/anomaly/features.py` (+47 lines), `backend/tests/test_features.py` (+29 lines).
- Next prompts: Task 3 — `build_feature_vocabs` and `encode_run` for vocab building and sequence encoding.
- Reflection: Strict TDD maintained; red phase verified via ImportError before implementation was written. No existing code modified.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): pytest tests/test_features.py — 4 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): add vocab-builder + encoder (separate task)
