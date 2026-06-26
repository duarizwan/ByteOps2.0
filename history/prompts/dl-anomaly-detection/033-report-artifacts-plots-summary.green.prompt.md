---
id: 033
title: Report artifacts plots and summary
stage: green
date: 2026-06-14
surface: agent
model: claude-opus-4-8
feature: dl-anomaly-detection
branch: feat/dl-anomaly-detection
user: dua.rizwan@jonasclub.com
command: implement TASK 12
labels: ["anomaly", "report", "matplotlib", "bilstm-attention", "offline"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - backend/scripts/make_report.py
tests:
 - manual run: .venv/Scripts/python.exe scripts/make_report.py --data data/gen.jsonl --epochs 50
---

## Prompt

You are implementing ONE task in repo `d:\OneDrive - Jonas Software\Dua Stuff\uni\Byteops\ByteOps-master`, branch `feat/dl-anomaly-detection`. torch/sklearn/mlflow/matplotlib installed in `backend/.venv`. Run via `cd backend && .venv/Scripts/python.exe ...`. This is offline tooling — verify with a real run that produces the output files.

CONTEXT: Create `backend/scripts/make_report.py` that trains the BiLSTM+Attention model on a dataset and writes report-ready PNGs + a markdown summary for the DL course report. Reuse existing building blocks:
- `app/anomaly/features.py`: `build_feature_vocabs([steps,...])`, `encode_run(steps, vocabs, max_len)`, `CATEGORICAL_FIELDS`, `NUMERIC_FEATURES`.
- `app/anomaly/models.py`: `BiLSTMAttention(vocab_sizes, n_numeric)` → forward returns `(logit, attn)`.
- `app/anomaly/metrics.py`: `classification_metrics`, `roc_points`, `confusion`, `partial_auroc`, `auroc`.
- Dataset `data/gen.jsonl` (rich `steps`, labels normal/redteam). Use matplotlib with `matplotlib.use("Agg")` (headless).

=== TASK 12: Report artifacts (plots + summary) ===

Step 1 — Create `backend/scripts/make_report.py` (full script provided in prompt).

Step 2 — Run (generate data if needed):
```
cd backend && .venv/Scripts/python.exe scripts/generate_dataset.py --normal 150 --per-type 15 --out data/gen.jsonl
.venv/Scripts/python.exe scripts/make_report.py --data data/gen.jsonl --epochs 50
```
Expected: prints the metrics JSON and confirms the 4 files. Verify all 4 exist.

Step 3 — Commit ONLY the script:
```
git add backend/scripts/make_report.py
git commit -m "feat(anomaly): report artifacts (confusion/ROC/attention plots + summary)"
```
CRLF warnings harmless. outputs/ is gitignored — do NOT commit the PNGs/data.

Report: status, the metrics JSON, confirmation all 4 files were written (ls output), commit SHA, any concerns.

## Response snapshot

Created `backend/scripts/make_report.py` (140 lines) exactly per the provided spec, reusing features/models/metrics modules. `data/gen.jsonl` already existed so the generation step was skipped. Ran the report with `--epochs 50`; it trained BiLSTM+Attention and wrote all 4 artifacts to `backend/outputs/`.

Metrics JSON:
```
{
  "accuracy": 0.9706, "precision": 1.0, "recall": 0.9130, "f1": 0.9545,
  "tp": 21, "fp": 0, "fn": 2, "tn": 45, "pauroc": 1.0, "auroc": 1.0
}
```

Committed only the script (SHA 0d70fa1). `backend/outputs/` left untracked.

## Outcome

- ✅ Impact: Report-ready PNGs (confusion matrix, ROC, attention) + markdown summary generated for the DL course report from a real training run.
- 🧪 Tests: Manual run produced all 4 files (confusion_matrix.png, roc_curve.png, attention_example.png, report_summary.md) and printed metrics.
- 📁 Files: backend/scripts/make_report.py (new, committed).
- 🔁 Next prompts: Optionally embed the PNGs into the final report document.
- 🧠 Reflection: AUROC=1.0/pAUROC=1.0 on this split is partly due to a small, well-separated test set; worth noting in the report.

## Evaluation notes (flywheel)

- Failure modes observed: None — script ran first try.
- Graders run and results (PASS/FAIL): PASS (4 artifacts written, metrics printed).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): Cross-validate or report mean/std over multiple seeds since perfect AUROC suggests an easy split.
