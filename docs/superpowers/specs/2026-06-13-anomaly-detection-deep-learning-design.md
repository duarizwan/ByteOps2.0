# ByteOps Deep Learning Anomaly Detection — Design Spec

**Date:** 2026-06-13
**Status:** Approved for planning
**Origin:** Blending the `agentsop` DL course project into ByteOps using real data only.

## Decisions (locked)

| Decision | Choice |
|---|---|
| Priority | ByteOps is the main project; agentsop standalone is retired/archived after the port |
| Data policy | **Real data only.** No synthetic generation, no injected fake rows |
| Data gap (63 real runs today) | Drive real usage via a local usage-driver script to 500+ runs over ~2 weeks, in parallel with building the pipeline |
| Anomaly labels | None used for training. ~25–30 **real red-team runs** (deliberately out-of-policy sessions, hand-labeled in DB) used for **evaluation only** |
| Model | **Self-supervised next-action prediction LSTM** (DeepLog-style): trained on normal real runs to predict each next action token; improbable steps (high NLL / top-k miss) indicate anomalies |
| Baseline | Isolation Forest on handcrafted session features (ported from agentsop `baseline.py`) |
| Deployment | Train offline with PyTorch (local scripts, never deployed); serve inference via **ONNX Runtime** in the FastAPI backend (no torch in the Docker image) |
| Course story | "Self-supervised sequence modeling of real multi-agent telemetry, evaluated against real adversarial sessions" |

## Academic grounding (DeepLog)

The self-supervised next-action model implements the **DeepLog** approach (Du, Li, Zheng & Srikumar, *"DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning,"* ACM CCS 2017): an LSTM learns normal log-key sequences and flags entries the model finds improbable (not in the top-k / high NLL predictions). ByteOps adapts it from system logs to agent-run telemetry, with agent-policy risk classes as the token alphabet. Experiment tracking uses **MLflow** to log the LSTM-vs-Isolation-Forest comparison for the report.

## 1. Concept

ByteOps's agent runtime logs every step of every agent run (`agent_runs` / `agent_run_steps`). A deep learning layer learns from real runs what normal agent behavior looks like and flags deviating runs. Training is label-free; real red-team sessions are the evaluation set. Anomaly scores surface in the Action Center and as per-step heat coloring in the run graph.

## 2. What is removed from agentsop

| Component | Fate | Reason |
|---|---|---|
| `data.py` synthetic generator + anomaly injection | Deleted | Replaced by real telemetry export |
| `app.py` (Streamlit) | Deleted | ByteOps UI replaces it |
| Notebook 01 (dataset generation) | Deleted | No generated data |
| Supervised BiLSTM+attention classifier + BCE objective | Replaced | No labels for supervised training; becomes a causal next-action LSTM with cross-entropy objective |
| `preprocessing.py` | Ported & adapted | Keep hygiene rules: train-only vocab, `<PAD>`=0, `<UNK>`=1, padding mask; new token scheme over real fields |
| `baseline.py` (Isolation Forest, classification metrics, rank-based ROC-AUC) | Ported nearly unchanged | Features computed from real runs |
| `train.py` loop, `experiments.py`, `reporting.py` | Ported & adapted | Objective and ablations change; markdown report tables reused for the course report |

## 3. New components in ByteOps

### Backend package `backend/app/anomaly/`
- **`tokenizer.py`** — converts `agent_run_steps` rows to token sequences: `{tool}|{action_class}|{outcome}`, where `action_class` comes from the existing `agent_policy` risk classes (read/write/external/destructive). Coarse tokens by design — small vocabulary suits small data. Unknown tools map to `<UNK>`.
- **`scorer.py`** — loads ONNX model + `vocab.json`; computes per-step NLL and a session-level score; applies the validation-tuned threshold; never raises into the run path (failures log and leave score null).

### Database (one Alembic migration)
New columns on `agent_runs`: `anomaly_score (float, nullable)`, `step_scores (JSONB, nullable)`, `flagged (bool, default false)`, `data_label (enum: normal | redteam | unlabeled, default unlabeled)`.

### Runtime hook
On run completion in `agent_runtime`, score asynchronously; if score exceeds threshold → set `flagged` and create a notification. Scoring is fire-and-forget relative to the run lifecycle.

### Offline scripts (local only, not deployed)
- `backend/scripts/export_runs.py` — DB → JSONL token sequences with run metadata and labels.
- `backend/scripts/train_anomaly.py` — PyTorch training: next-action LSTM on normal runs; threshold tuned on validation NLL; evaluation vs red-team set (precision/recall/F1/ROC-AUC) and vs Isolation Forest; exports ONNX + vocab.json + model_meta.json (tuned threshold, max_len, training stats) — small artifacts, committed.
- `backend/scripts/drive_usage.py` — usage driver: sends varied real prompts through `/api/chat` on a schedule to accumulate genuine runs (use test accounts for Gmail/Slack where possible).

### Frontend
- Action Center: anomaly badge + "Flagged" filter on run cards.
- Run graph (`graph-canvas`): per-step heat coloring from step NLL scores — highlights which step looked anomalous.
- API: anomaly fields included in existing `/api/agent-runs` responses (no new endpoints).

## 4. End-to-end workflow

1. **Collect (weeks 1–2, parallel with build):** usage driver + organic use until 500+ real runs. Existing 63 runs count.
2. **Red-team protocol:** ~25–30 real out-of-policy sessions (external forwarding, tool repetition, order violations), hand-labeled `redteam`.
3. **Train offline:** split 80/10/10 by run ID; vocab from train only; tune threshold on validation; evaluate on held-out normal + red-team runs; compare against Isolation Forest.
4. **Ship:** commit ONNX + vocab; backend scores every completed run thereafter.
5. **Course experiments:** top-k vs NLL scoring, sequence-length sensitivity, hidden-size ablation, LSTM vs Isolation Forest — all on real data, reported via ported `reporting.py`.

## 5. Model sizing (small-data regime, intentional)

Single-layer causal LSTM, hidden 32–64, embedding 32, `max_len` ≈ 12, dropout, early stopping on validation NLL. Real runs currently average ~3 steps and few distinct tools; the model and vocab are sized to match, not to impress.

## 6. Honest limitations (must appear in the course report)

- First model trained on few hundred runs is statistically weak; quality grows with data. Isolation Forest is competitive early.
- Red-team evaluation measures detection of *enacted* anomaly patterns, not all real-world anomalies.
- Low workflow diversity today; vocabulary shifts when new tools are added → periodic retraining is part of the design.

## 7. Error handling

- Missing/corrupt model artifacts → scoring disabled gracefully, runs unaffected, warning logged once.
- Unknown tokens at inference → `<UNK>`; logged for retraining triage.
- Score write failures → logged, never propagate to the run or the user response.

## 8. Testing

- Unit: tokenizer mapping (incl. unknown tools), exporter output shapes, threshold/flag logic with a tiny fixture ONNX model.
- Integration: completed run → scored → flagged → notification, with a stub scorer.
- Frontend: badge rendering + graph heat overlay, following existing vitest patterns.
- Training script: deterministic smoke run on a tiny real-data fixture (seeded).

## 9. Out of scope

Synthetic data of any kind, attention-based supervised classifier, transformer comparison, SHAP, real-time per-step streaming scores (post-completion scoring only for v1), auto-retraining pipelines, multi-tenant model isolation.
