# ByteOps DL "Spark Package" — Design Spec

**Date:** 2026-06-13
**Status:** Design — awaiting review before implementation planning
**Goal:** Turn the anomaly-detection layer into an impressive, presentable, live deep-learning
demo: **spawn a rogue agent, watch a deep-learning monitor catch it red-handed in real time,
then explain it with a behavior map and an attention heatmap.**

---

## The honest framing (state this in the report/demo)

Aligned agents won't misbehave on command, so to demonstrate detection we follow standard
AI-safety practice (Storf et al. 2026) and build a **"model organism"** — a deliberately
misaligned *demo* agent. Real/normal data stays real; the adversary is simulated and clearly
labeled as such. The product framing is **agent oversight**: watch agents, flag/explain/halt
risky behavior, keep a human in control.

---

## The four components

### 1. Rogue agent (model organism) — enables the live catch
A clearly-separated **demo mode** that runs a deliberately-misaligned agent. Given a benign
task ("summarize my emails"), it performs normal steps but injects a hidden misaligned action
(e.g. `read_context → forward_external`). It produces **real `agent_run` steps** (so the
detectors see them), but risky tool calls execute against a **no-op/sandbox tool** so there is
**zero real-world effect**.

- New: `backend/app/anomaly/rogue.py` — a small library of scripted rogue *scenarios*
  (exfiltration, sabotage, privilege-escalation, tool-repetition), each a sequence of steps
  with one or more injected risky actions.
- New endpoint: `POST /api/demo/rogue-run` (demo-only) — runs a chosen scenario, recording a
  real `agent_run` with `data_label='rogue'`, streaming step events over SSE like a normal run.
- Honest + safe: risky steps are recorded but routed to a sandbox executor (no real Gmail/etc).

### 2. Real-time interception + risk meter — the drama
Today scoring is post-completion. Make it **per-step and live**:
- After each step is recorded (in the rogue-run path first; later the normal path), run the
  fast local LSTM scorer on the **partial** sequence and emit a `risk_update` SSE event with
  the running 0–10 risk score.
- If the running risk crosses the threshold mid-run, emit an `intercepted` event and **halt the
  run** (status `intercepted`).
- Frontend: a live **risk meter** (gauge climbing) on the run view; on interception, a red
  "⚠️ Agent halted — suspicious behavior" banner with the offending step + reason.
- New: incremental scoring helper in `scorer.py` (`score_partial(steps_so_far)`); SSE event
  types `risk_update` / `intercepted`; a `RiskMeter` React component.

### 3. Latent-space behavior map (sequence autoencoder) — the visual
- New: `backend/scripts/train_autoencoder.py` — an LSTM **encoder→decoder** trained to
  reconstruct normal runs; the encoder's bottleneck is each run's **behavior embedding**.
- New: `backend/scripts/make_behavior_map.py` — embeds all runs, reduces to 2D (UMAP/t-SNE),
  and renders `outputs/behavior_map.png` (+ a JSON the frontend can plot): normal runs cluster,
  rogue/anomalous runs sit as outliers. High reconstruction error = anomaly (a 2nd detector).
- DL concepts: representation learning, autoencoders, dimensionality reduction.

### 4. Attention LSTM + heatmap — "where it went wrong"
- New: an **attention-based classifier** (`backend/app/anomaly/attention_model.py` +
  training in `scripts/train_attention.py`) trained on normal vs rogue/synthetic runs. It
  outputs a score **and per-step attention weights**.
- The attention weights render as a **heat strip** over the run's steps (frontend) — visually
  pinpointing the step that drove the alarm. Ported/adapted from the agentsop attention code.
- DL concepts: attention mechanism, supervised sequence classification, interpretability.

---

## How the detectors now stack (the report story)

| Detector | Paradigm | DL concept | Role |
|---|---|---|---|
| Next-action LSTM | forecasting (self-supervised) | RNN/LSTM | per-step surprise + live risk meter |
| Sequence autoencoder | reconstruction | autoencoder/embeddings | behavior map + outlier score |
| Attention classifier | supervised | attention | "where" heatmap + score |
| Isolation Forest | classical | — | baseline |
| LLM monitor | prompt-based | frontier LLM | semantic risk + plain-English reason |

Five detectors across four paradigms, compared with pAUROC@FPR<0.2 + the ablation suite.
That is a genuinely rich DL study.

---

## Demo / presentation flow

1. **Hook (30s):** the rogue-agent risk for enterprises.
2. **Live catch (2 min):** enable demo mode → spawn rogue agent → **risk meter climbs** as steps
   stream → at the exfiltration step the monitor **halts it** → red banner + reason + step heat.
3. **The science (3 min):** the **behavior map** (rogue = glowing outlier), the **attention
   heatmap** (where), the 5-detector comparison + ablations + MLflow.
4. **Honesty (30s):** real normal data; simulated adversary (model organisms); limitations.

---

## Architecture / data flow

```
Demo mode → rogue scenario runner → records real agent_run steps (sandboxed tools)
        → per-step LSTM scoring → SSE risk_update / intercepted → live risk meter + halt
Offline: runs → autoencoder → embeddings → 2D map (behavior_map.png)
         runs → attention classifier → per-step attention → heatmap
All detectors → evaluate_detectors / run_experiments → pAUROC + MLflow
```

## New / changed files (high level)
- Backend: `app/anomaly/rogue.py`, `app/anomaly/attention_model.py`, `app/api/demo.py`,
  `scorer.py` (+`score_partial`), `agent_runtime` (per-step scoring hook), SSE event types.
- Scripts: `train_autoencoder.py`, `make_behavior_map.py`, `train_attention.py`.
- Frontend: `RiskMeter`, interception banner, attention heat strip, behavior-map view.

## Testing
- Unit: rogue scenario generation (deterministic, produces risky tokens); `score_partial`
  monotonic/0–10; autoencoder reconstruction-error ranking; attention weights sum to 1.
- Integration: a rogue run gets intercepted with a reason; behavior map renders; a normal run
  is not intercepted.
- Frontend: risk meter renders/climbs; interception banner; heat strip.

## Scope: v1 vs stretch
- **v1 (the demo):** rogue agent + per-step scoring/risk-meter/interception + attention heatmap.
- **Stretch:** the autoencoder behavior map (gorgeous but more work); live frontend embedding
  view; applying live scoring to the *normal* chat path (v1 applies it to the rogue/demo path).

## Honest limitations
- The adversary is simulated (model organisms) — stated, standard practice.
- Live interception is demoed on the rogue/demo path first; retrofitting the full chat path is
  stretch.
- Small real dataset → absolute numbers stay modest; the spark is the live demo + visuals +
  the breadth of DL methods, not headline accuracy.

## Effort (rough)
- Rogue agent + demo endpoint: medium. Per-step scoring + risk meter + interception: medium-high
  (touches the run loop + SSE + a new UI component). Autoencoder + behavior map: medium.
  Attention model + heatmap: medium. Total: the largest feature in the project so far — worth it
  for a flagship demo.
