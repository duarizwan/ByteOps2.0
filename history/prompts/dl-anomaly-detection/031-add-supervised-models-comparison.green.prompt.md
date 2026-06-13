---
id: 031
title: Add supervised models to comparison
stage: green
date: 2026-06-13
surface: agent
model: claude-opus-4-8
feature: dl-anomaly-detection
branch: feat/dl-anomaly-detection
user: dua.rizwan@jonasclub.com
command: implement TASK 9
labels: ["anomaly", "evaluation", "deep-learning", "metrics"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - backend/scripts/evaluate_detectors.py
tests:
 - manual: python scripts/evaluate_detectors.py --data data/gen.jsonl --no-llm
---

## Prompt

TASK 9 — Add supervised models + full metrics to the comparison.

Make backend/scripts/evaluate_detectors.py: (a) tolerate missing tokens by deriving
them via run_to_tokens(steps) when absent, so it runs on data/gen.jsonl; (b) add a
supervised_scores(model_name, train, test, ...) helper that trains BiLSTM+Attention or
Transformer on rich step features and returns sigmoid anomaly scores; (c) add rows for
both supervised models to the comparison with the FULL metric set (accuracy, precision,
recall, F1, AUROC, pAUROC@FPR<0.2) for ALL detectors, using the same train/test split.
Run on the generated dataset, print the table, and commit only the script.

## Response snapshot

Implemented all three changes. Key adaptation: the original split only put 70% of
`normal` into `train` (no positives), which the supervised models need. I split BOTH
classes 70/30: held-out normal + held-out redteam form the shared `eval_items`/labels
(identical test set for every detector). Unsupervised detectors (LSTM, Isolation Forest)
still fit on the normal-train portion only; supervised models train on `sup_train =
normal-train + redteam-train`. Switched metrics to app.anomaly.metrics (accuracy/
precision/recall/F1 at the F1-optimal threshold + AUROC + pAUROC) and widened the table
+ MLflow logging to all six metrics.

Result on data/gen.jsonl (45 normal + 23 redteam test; supervised train 105 normal + 52
redteam):

| Detector | Accuracy | Precision | Recall | F1 | AUROC | pAUROC@FPR<0.2 |
|---|---|---|---|---|---|---|
| LSTM (next-action) | 0.926 | 1.000 | 0.783 | 0.878 | 0.789 | 0.783 |
| Isolation Forest | 0.559 | 0.419 | 0.783 | 0.545 | 0.504 | 0.174 |
| BiLSTM+Attention | 0.985 | 0.958 | 1.000 | 0.979 | 0.998 | 0.990 |
| Transformer | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Committed script only as fb0adb5.

## Outcome

- ✅ Impact: comparison now covers all four detectors with full metrics and runs on the synthetic dataset; supervised models are clearly strongest.
- 🧪 Tests: manual run on data/gen.jsonl produced the table above and wrote outputs/comparison.md.
- 📁 Files: backend/scripts/evaluate_detectors.py
- 🔁 Next prompts: evaluate on real exported runs once enough redteam labels exist; sanity-check transformer near-perfect scores aren't dataset-trivial.
- 🧠 Reflection: synthetic data makes anomalies very separable, so supervised perfection is partly a data-scaling artifact — report honestly.

## Evaluation notes (flywheel)

- Failure modes observed: harmless PyTorch nested-tensor prototype warning from the transformer padding-mask path; CRLF warning on commit.
- Graders run and results (PASS/FAIL): PASS (script runs, table has all 4 detectors + 6 metrics).
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): run with --no-llm on real data/runs.jsonl to compare against synthetic separability.
