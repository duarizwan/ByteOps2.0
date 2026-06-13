# ByteOps — Deep-Learning Study + Live Demo (Unified Design)

**Date:** 2026-06-13
**Status:** Design — awaiting review before implementation planning
**Supersedes:** `2026-06-13-dl-spark-package-design.md` (which had circularity + thin-data problems)

**Goal:** A project that is BOTH a credible deep-learning study (for the course) AND an
impressive, honest live demo — bridged by the fact that **interpretability (attention,
embeddings) is simultaneously a core DL concept and the visual spark.**

---

## Why this is honest (read first)

- Real agent-attack data barely exists (aligned agents refuse to misbehave). Following the
  published method (Storf et al. 2026), we **generate diverse synthetic trajectories** for both
  the normal and anomalous classes, clearly labeled, and keep the **real runs as a held-out
  realism check** (analogous to the paper's ControlArena test set).
- The demo shows **trained neural networks explaining their own decisions** (attention weights,
  embeddings) on a simulated rogue run — a genuine demonstration of the models, not scripted
  theater. We state the simulation plainly.
- Detection is evaluated for **generalization**: train on normal, test on **held-out anomaly
  types the model never saw** — so "it caught it" means it learned, not memorized.

---

## Part C — Richer data + tokenization (the foundation; build first)

The current `{step_type}|{risk}|{status}` scheme has only ~11 tokens, which caps every model and
every visual. Part C fixes the foundation.

**C1. Tokenizer v2 (`app/anomaly/tokenizer.py`, versioned).**
Richer composite token: `{step_type}|{tool}|{action_class}|{risk}|{status}`
(e.g. `tool_call|gmail|forward|external_send|completed`). This grows the vocabulary to a
meaningful size (~40–80 tokens) so sequences carry real signal. Keep v1 available for backward
compatibility; artifacts record which version they use.

**C2. Trajectory generator (`scripts/generate_dataset.py`, LLM-driven, Gloom-style).**
Uses the LLM to produce **diverse multi-step trajectories**:
- **Normal class:** varied realistic workflows across tools (triage email, prep meeting, review
  PRs, sync tickets…), with natural variation in length/order/tools.
- **Anomalous class:** varied attacks across categories (exfiltration, sabotage/destruction,
  privilege escalation, validation bypass, tool abuse) — many *implementations* per category so
  detectors can't overfit one pattern.
Output: a labeled JSONL dataset (hundreds of runs), with anomaly **type** recorded so we can do
held-out-type generalization splits. Real exported runs are merged in as a realism check.

DL concepts: data generation for self-supervision, train/test distribution design, leakage control.

---

## Part A — Multi-architecture DL study (the course substance)

Implement, train, and compare a **zoo of neural architectures** on the trajectories, in one harness.

**A1. Architectures (`app/anomaly/models.py` + `scripts/train_zoo.py`):**
- **LSTM** (have) — next-action forecasting.
- **GRU** — recurrent comparison.
- **BiLSTM** — bidirectional context.
- **Attention-LSTM** — adds an attention layer (drives the heatmap in Part B).
- **Sequence autoencoder** — encoder→decoder; reconstruction error = anomaly; bottleneck =
  behavior embedding (drives the map in Part B).
- **Small Transformer encoder** (stretch) — self-attention comparison.

**A2. Training methodology (genuine DL rigor):**
- Loss curves, **dropout + early stopping**, **overfitting** analysis (extends the capacity
  experiment), learning-rate sensitivity.
- Reproducible (seeds), multiple seeds + 95% CIs.

**A3. Evaluation:**
- pAUROC@FPR<0.2, F1, **ROC + PR curves**, per-architecture comparison table.
- **Generalization split:** train on normal + a subset of anomaly types; test on **held-out
  anomaly types** (the anti-circularity guarantee).
- Ablations (order-shuffle, sequence length, capacity, attention-vs-mean-pool, scoring rule).
- Baselines: Isolation Forest, LLM monitor. Everything logged to **MLflow**.

DL concepts covered: embeddings, RNN/LSTM/GRU, bidirectionality, attention, self-attention,
autoencoders/representation learning, regularization, model selection, evaluation, ablation.

---

## Part B — Interpretability as the live demo (the spark, in the frontend)

Surface the **trained networks' own explanations** in the app — visible, honest, DL-grounded.

**B1. Attention heatmap.** The attention-LSTM's per-step weights render as a heat strip over a
run's steps in the Execution Center — "where the model looked." (Validated on held-out data so
it's not just relearning a trivial token.)

**B2. Behavior-embedding map.** The autoencoder's embeddings of all runs, reduced to 2D
(UMAP/t-SNE), rendered as an in-app scatter (and a `behavior_map.png` for slides): normal runs
cluster, the rogue run is an outlier you can click.

**B3. Execution Center surfacing + risk curve.** Flagged runs show a badge + suspicion score +
plain-English reason; a per-step risk curve visualizes how suspicion rose across the run; a
"Flagged" filter. (This is also the run-level surfacing the audit flagged as missing.)

**B4. Demo trigger.** A demo control runs a generated rogue scenario (sandboxed, zero real
effect) so you can show, live: rogue run → attention heatmap lights the bad step → it sits as an
outlier on the behavior map → flagged with a reason. Honest simulation, real models.

---

## Demo / presentation flow

1. Hook: agent oversight risk (30s).
2. Live: trigger a rogue scenario → Execution Center flags it → **attention heatmap** pinpoints
   the step → **behavior map** shows it as an outlier (2 min).
3. The science: the **architecture comparison** (LSTM/GRU/BiLSTM/attention/autoencoder/Transformer),
   training curves, ablations, generalization-to-unseen-attack-types, MLflow (4 min).
4. Honesty: synthetic-but-diverse data, simulated adversary, limitations (1 min).

---

## Phasing (each phase ships something usable)

- **Phase C** (foundation): tokenizer v2 + dataset generator → rich labeled dataset.
- **Phase A** (substance): architecture zoo + training harness + comparison/ablations/MLflow.
- **Phase B** (spark): attention heatmap + behavior map + Execution Center surfacing + demo trigger.

## New / changed files (high level)
- Backend: `app/anomaly/tokenizer.py` (v2), `app/anomaly/models.py` (architectures),
  `app/anomaly/attention.py` (attention model + weight export), `app/api/demo.py` (rogue trigger),
  `scorer.py` (load chosen model + emit attention/risk).
- Scripts: `generate_dataset.py`, `train_zoo.py`, `train_autoencoder.py`, `make_behavior_map.py`,
  extend `run_experiments.py` / `evaluate_detectors.py`.
- Frontend: attention heat strip, behavior-map view, risk curve, flagged badge + "Flagged" filter,
  demo trigger control.

## Testing
- Tokenizer v2 (mapping, vocab growth, backward compat). Generator (determinism, class balance,
  anomaly-type coverage, no train/test leakage). Each model (forward shapes, attention weights sum
  to 1, autoencoder reconstruction ranking). Eval harness (metrics, held-out-type split). Frontend
  components (heat strip, map, risk curve, badge/filter).

## Honest limitations (in the report)
- Primary dataset is synthetic (diverse, LLM-generated, labeled); real runs are a small realism
  check. Absolute numbers depend on generation quality.
- The adversary is simulated (model organisms — standard practice).
- Transformer is stretch; on modest data it may not beat the RNNs (report honestly).

## Effort
Largest body of work in the project. Phase C and A are mostly offline DL (lower UI risk); Phase B
is frontend + a thin demo endpoint. Sequenced so the course substance (C+A) lands first, then the
demo (B).
