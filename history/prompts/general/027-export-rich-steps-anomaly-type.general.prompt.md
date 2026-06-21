---
id: 027
title: Export Rich Steps and Anomaly Type (v2 Dataset)
stage: green
date: 2026-06-13
surface: agent
model: claude-sonnet-4-6
feature: dl-anomaly-detection
branch: feat/dl-anomaly-detection
user: Dua Rizwan
command: Task 4 — export rich step dicts (don't break v1)
labels: ["anomaly-detection","tdd","export","tokenizer","dataset"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/scripts/export_runs.py
  - backend/tests/test_export_runs.py
tests:
  - backend/tests/test_export_runs.py::test_run_record_to_sequence_shape
  - backend/tests/test_export_runs.py::test_export_includes_rich_steps_and_type
---

## Prompt

Implement Task 4 (TDD): Export rich step dicts (don't break v1) in `backend/scripts/export_runs.py`.

Steps:
1. Append `test_export_includes_rich_steps_and_type` to `backend/tests/test_export_runs.py`
2. Run tests → new test must FAIL (KeyError 'anomaly_type')
3. Replace `run_record_to_sequence` with enriched version emitting `steps`, `anomaly_type`, `intent` while keeping `tokens` for backward compat
4. Run both tests → all PASS
5. Commit only the two files with message: `feat(anomaly): export rich steps + anomaly_type (v2 dataset)`

## Response snapshot

- Appended `test_export_includes_rich_steps_and_type` to the test file.
- Confirmed new test failed with `KeyError: 'anomaly_type'` (existing test passed).
- Replaced `run_record_to_sequence` in `export_runs.py` with version that extracts `steps`, `anomaly_type` from `metadata`, and `intent`; `tokens` retained via `run_to_tokens(steps)`.
- Both tests passed: 2 passed in 0.02s.
- Committed as `ddc095d`: `feat(anomaly): export rich steps + anomaly_type (v2 dataset)`.

## Outcome

- Impact: `run_record_to_sequence` now emits `anomaly_type`, `intent`, and rich `steps` list alongside backward-compatible `tokens`; v2 dataset export is ready.
- Tests: 2 passed, 0 failed.
- Files: backend/scripts/export_runs.py, backend/tests/test_export_runs.py
- Next prompts: wire rich steps into Tokenizer v2 feature extraction; train/eval v2 model on exported dataset.
- Reflection: TDD cycle clean — red/green confirmed before implementing. No other files touched.

## Evaluation notes (flywheel)

- Failure modes observed: none — CRLF warnings from git on Windows are harmless.
- Graders run and results (PASS/FAIL): pytest tests/test_export_runs.py — PASS (2/2)
- Prompt variant (if applicable): none
- Next experiment: add `test_anomaly_type_default_for_normal_label` to cover the `"none"` default branch.
