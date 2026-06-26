---
id: "029"
title: Pure metrics module TDD
stage: green
date: 2026-06-13
surface: agent
model: claude-sonnet-4-6
feature: dl-anomaly-detection
branch: feat/dl-anomaly-detection
user: Dua Rizwan
command: implement task 6 - metrics module (pure)
labels: ["anomaly-detection","metrics","tdd","numpy","auroc"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/anomaly/metrics.py
  - backend/tests/test_metrics.py
tests:
  - tests/test_metrics.py::test_partial_auroc_perfect
  - tests/test_metrics.py::test_classification_metrics_perfect
  - tests/test_metrics.py::test_confusion_counts
  - tests/test_metrics.py::test_roc_points_monotone_fpr
---

## Prompt

Create a NEW pure metrics module `backend/app/anomaly/metrics.py` (numpy only, no torch) with evaluation functions used across training/eval scripts. Higher score = more anomalous (positive class = anomalous = label 1).

Task 6: Metrics module (pure) — TDD workflow:
1. Write test file backend/tests/test_metrics.py
2. Run tests (expect FAIL - ModuleNotFoundError)
3. Create backend/app/anomaly/metrics.py with confusion, classification_metrics, roc_points, pr_points, partial_auroc, auroc
4. Run tests (expect 4 PASS)
5. Commit only those two files

## Response snapshot

- Created `backend/tests/test_metrics.py` with 4 tests covering pAUROC, classification metrics, confusion matrix, and ROC monotonicity.
- RED phase confirmed: ModuleNotFoundError on `app.anomaly.metrics`.
- Created `backend/app/anomaly/metrics.py` with pure numpy implementations of confusion, classification_metrics, roc_points, pr_points, partial_auroc, and auroc.
- GREEN phase: all 4 tests passed in 0.09s.
- Committed as `2aef428` with message `feat(anomaly): pure metrics module (pAUROC, ROC/PR, confusion)`.

## Outcome

- Impact: Standalone, torch-free metrics module available for training and evaluation pipelines in the anomaly detection feature.
- Tests: 4/4 passed (test_partial_auroc_perfect, test_classification_metrics_perfect, test_confusion_counts, test_roc_points_monotone_fpr).
- Files: backend/app/anomaly/metrics.py (new), backend/tests/test_metrics.py (new).
- Next prompts: Wire metrics into training loop; add eval script calling partial_auroc on held-out set.
- Reflection: Strict TDD flow executed cleanly. CRLF warnings from git are harmless on Windows.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): pytest tests/test_metrics.py — 4 PASS
- Prompt variant (if applicable): none
- Next experiment: Add parametrized edge-case tests (all-negative, all-positive, ties in scores)
