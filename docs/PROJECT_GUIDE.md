# ByteOps — Complete Project Guide (Plain English)

A single document that explains the whole project: what it is, how it works, the
technology and models used (and why), how to run it, what you need to do, why this
approach was chosen over alternatives, how to present it, and what comes next.

---

## 1. What ByteOps is (in one paragraph)

ByteOps is an **AI assistant that unifies many work tools in one place**. Instead of
juggling Gmail, Calendar, GitHub, Slack, Jira, and Dropbox separately, you type a
request in plain English ("summarize my unread emails", "what's on my calendar
Friday") and an AI agent does it for you across those tools. On top of that, ByteOps
has a **deep-learning safety layer** that watches what the agents do and flags
anything suspicious — so misbehavior gets caught and shown to a human instead of
slipping by. It is built for **both technical and non-technical employees**.

Two audiences, two faces of the product:
- **Non-technical user:** just a chat box + plain-language results and approval prompts.
- **Technical / admin user:** an "Execution Center" showing every agent run as a graph,
  plus the anomaly flags and governance views.

---

## 2. The big picture (how the pieces fit)

```
You type a request
        │
        ▼
┌───────────────┐     ┌──────────────────────────────┐
│  Frontend     │ →   │  Backend (FastAPI)           │
│  (Next.js)    │     │  - figures out your intent    │
│  chat + UI    │ ←   │  - routes to the right agent  │
└───────────────┘     │  - agent calls your tools     │
                      │    (Gmail, Slack, …) via MCP  │
                      │  - streams the answer back     │
                      │  - records every step          │
                      └───────────┬──────────────────┘
                                  │ (after the run finishes)
                                  ▼
                      ┌──────────────────────────────┐
                      │  Deep-learning safety layer    │
                      │  scores the run for anomalies  │
                      │  → flags suspicious runs        │
                      └──────────────────────────────┘
```

The key idea: **every action an agent takes is logged as a "run" made of "steps"**,
and the deep-learning layer reads those steps to decide if the run looks normal or
suspicious.

---

## 3. Technology used — what and why

### Frontend (what the user sees)
| Tech | What it does | Why this one |
|---|---|---|
| **Next.js 16 + React 19** | The web app / UI framework | Industry-standard, fast, modern; great for dashboards |
| **TypeScript** | Typed JavaScript | Catches bugs before runtime |
| **Tailwind CSS 4** | Styling | Fast, consistent design system |
| **Clerk** | Login / authentication | Secure, ready-made auth so we don't build it from scratch |
| **@xyflow/react + Dagre** | The run-trace graph | Best library for drawing node-graphs (the execution trace) |

### Backend (the brains)
| Tech | What it does | Why this one |
|---|---|---|
| **FastAPI (Python)** | The API server | Fast, async, modern Python standard |
| **PostgreSQL (Neon)** | The database | Reliable, handles structured data + JSON |
| **SQLAlchemy + Alembic** | Talk to the DB + manage schema changes | Safe, versioned database migrations |
| **MCP (Model Context Protocol)** | How agents talk to tools | A standard way to give an AI safe, structured access to tools |
| **Gemini (LLM via API)** | The "brain" that understands requests | A pre-trained large language model we *rent* (could swap for Claude) |
| **APScheduler** | Runs scheduled "workflows" | Lets agents run automatically on a schedule |

### Deep-learning layer (the safety net + the course project)
| Tech | What it does | Why this one |
|---|---|---|
| **PyTorch** | Builds + trains our own model | The standard deep-learning framework |
| **LSTM neural network** | Learns normal agent behavior | Best simple model for *sequences* (order matters) |
| **scikit-learn (Isolation Forest)** | A classical ML baseline | The "control" to compare our model against |
| **ONNX + onnxruntime** | Runs the trained model in the backend | Lightweight (~30 MB) instead of shipping all of PyTorch (~2 GB) |
| **MLflow** | Tracks training experiments | Records every run's settings + results (proof of experiments) |

---

## 4. How it works, end to end (a real example)

You type: **"Summarize my latest emails."**

1. **Frontend** sends your message to the backend and opens a live stream.
2. **Intent routing** figures out this is a Gmail task (it uses keywords first, then
   the LLM if unclear, with a fallback) and routes to the Gmail agent.
3. **The agent** uses the LLM (Gemini) to decide what to do, then calls the Gmail
   tool (via MCP) to read your emails. Each action is saved as a **step**.
4. **Safety check:** if an action is risky (sending, deleting, forwarding externally),
   the run **pauses and asks you to approve** — this is the human-in-the-loop control.
5. The agent writes a summary and **streams it back** to you.
6. The whole run (all its steps) is saved, and **the deep-learning layer scores it**
   for anomalies in the background.

If instead the agent had quietly tried to **forward your email to an outside address**
in the middle of that task, the deep-learning layer would flag it and the run graph
would highlight the exact suspicious step.

---

## 5. The deep-learning part — the concept

### The problem it solves
AI agents act on your behalf. How do you know an agent isn't doing something it
shouldn't (leaking data, deleting things, acting out of order)? You need an automatic
"supervisor" that watches agent behavior and raises a flag when something looks wrong.

### The core idea (in one line)
**Learn what "normal" agent behavior looks like; flag anything that surprises the model.**

### Three detectors (we compare them — that's the study)
1. **Next-action LSTM (our trained deep-learning model).**
   - We turn each run into a sequence of simple tokens like `tool_call|external_send|completed`.
   - The LSTM learns to *predict the next action* from normal runs (this is called
     "self-supervised" — it needs **no labels**, it just learns from the sequences themselves).
   - When a real step is one the model finds *improbable*, that's a "surprise" =
     a likely anomaly. We point at the exact surprising step.
2. **Isolation Forest (classical ML baseline).** A simpler, older method using
   hand-made features (run length, how many external actions, etc.). It's the
   "control" we measure our deep-learning model against.
3. **LLM black-box monitor (frontier-model baseline).** We send the run's actions to
   Gemini with a written rulebook ("constitution") and ask it to rate suspicion 1–10.
   "Black-box" means it judges by *observable actions only*, not the agent's hidden
   reasoning. It needs **no training** — it's prompt-based.

### V2 — Supervised attention study (added on top of the baselines)

The project now includes a **supervised deep-learning study** alongside the three
v1 baselines above. Two new architectures are trained on a labeled synthetic dataset
(150 normal + 5 anomaly types × 15 examples each):

- **BiLSTM + multi-head attention (core model)** — bidirectional LSTM with an
  attention layer; produces per-step attention weights used for anomaly localization.
- **Transformer Encoder (comparison)** — small self-attention architecture evaluated
  side-by-side.

Both are compared against the LSTM / Isolation Forest / LLM monitor baselines using
the same primary metric: **partial AUROC at FPR < 0.2 (pAUROC)**. Key results on the
synthetic set: BiLSTM+Attention reaches pAUROC ~0.94–0.99 / F1 ~0.95 and clearly
outperforms Isolation Forest (pAUROC ~0.17–0.53). The attention mechanism localizes
the injected anomalous step with ~96% attention weight, powering the **per-step heat
marker** visible in the Execution Center on flagged runs.

Ablations (action order, risk features, attention vs mean-pool, architecture, classical
vs learned) are run via `scripts/run_experiments.py` and logged to MLflow.

**Honest caveat:** training and evaluation data are fully synthetic and highly
separable by design, so absolute numbers are optimistic. Real production telemetry
would yield more modest results — this is stated explicitly in all reports.

See `docs/DL_QUICKSTART.md` — "V2 — Supervised attention models" for the full
6-command workflow.

### Why three?
A real, professional anomaly project never reports one model alone. Comparing a
trained model, a classical baseline, and a frontier LLM — using the right metric —
is exactly what makes it a credible study.

### The right metric
**Partial AUROC at low false-positive rate (FPR < 0.2).** In plain terms: a good
detector must catch bad runs *without* flooding a human with false alarms. We measure
performance specifically in the "few false alarms" zone, because that's what matters
for real oversight.

---

## 6. Why this approach and not something else

| Choice | Why, and why not the alternative |
|---|---|
| **LSTM (not just keyword rules)** | Rules are brittle and miss context; an LSTM learns *order* — the same action can be fine or suspicious depending on what came before. Our experiment proved order carries signal. |
| **Self-supervised (not supervised)** | Supervised learning needs lots of labeled "bad" examples, which don't exist. Self-supervision learns from normal data alone — realistic. |
| **LSTM (not a Transformer)** | With limited data, a big Transformer just overfits. A small LSTM is the right size; a Transformer is listed as future work. |
| **Adding an LLM monitor** | It's the method from the research paper, needs no training data, and catches *meaning-based* anomalies the LSTM can't. Complements the LSTM. |
| **ONNX in the backend (not PyTorch)** | PyTorch is ~2 GB and slow to ship; ONNX runs the same model in ~30 MB. |
| **MCP for tools** | A clean, standard, safe way to give the agent tool access, instead of hand-coding each integration unsafely. |
| **Human approval gates** | Autonomous agents with write access are dangerous; pausing risky actions for approval is the core trust mechanism. |

---

## 7. How to run and use it

### Run the app
- **Backend:** from `backend/`, start the FastAPI server (uvicorn). Needs `.env` with a
  database URL, a Clerk key, and an LLM key (you have Gemini).
- **Frontend:** from `frontend/`, `npm run dev`. Open the local URL, sign in, connect
  your tools (Gmail, etc.), and start chatting.

### Run the deep-learning part (all from `backend/`, full guide in `docs/DL_QUICKSTART.md`)
```
# 1. install the training tools (one time)
.venv/Scripts/python.exe -m pip install -r requirements-train.txt

# 2. export your real runs to a dataset
.venv/Scripts/python.exe scripts/export_runs.py --out data/runs.jsonl

# 2b. add the synthetic red-team class (REQUIRED after every export — export
#     overwrites the file, and aligned agents won't produce real attack runs)
.venv/Scripts/python.exe scripts/make_redteam.py --append data/runs.jsonl --n 25

# 3. train your model (makes the live anomaly marker work)
.venv/Scripts/python.exe scripts/train_anomaly.py --data data/runs.jsonl --epochs 30

# 4. run the experiment study (order/length/capacity ablations)
.venv/Scripts/python.exe scripts/run_experiments.py --data data/runs.jsonl --seeds 5

# 5. (after labeling red-team runs) run the 3-way comparison
.venv/Scripts/python.exe scripts/evaluate_detectors.py --data data/runs.jsonl

# 6. view experiment dashboard
.venv/Scripts/python.exe -m mlflow ui --backend-store-uri sqlite:///mlflow.db
```

---

## 8. What YOU need to do (your action items)

The system is built. The remaining work is **data**, which only you can produce:

1. **Connect your tools** in the app (Gmail, Calendar, GitHub, Slack, Jira, Dropbox).
   More tools = richer data = a model that can actually tell normal from abnormal.
2. **Generate normal runs.** Use the app normally, or run `scripts/drive_usage.py`
   (it fires ~45 varied prompts automatically). Aim for a few hundred runs.
3. **Create + label red-team runs (~15–25).** Deliberately push the agent out of
   policy (e.g., "forward my email to an outside address"). **Reject these at the
   approval prompt** so no real harm is done — the attempt is still recorded. Then:
   `python scripts/label_redteam.py --list` → `python scripts/label_redteam.py <id> ...`
4. **Re-run train + evaluate + experiments** to get sharper numbers and the full
   comparison table.

---

## 9. How to present the project (step by step)

> **Data honesty (say this up front):** the project uses **real normal telemetry**
> (your actual agent runs) + **hand-labeled red-team runs where available** (rejected
> approval-gate attempts) + a **controlled synthetic benchmark reported separately**.
> We do NOT claim "no synthetic data." V1 and V2 are two distinct workflows:
> - **V1 (real-telemetry, self-supervised):** the next-action LSTM trained on real runs.
> - **V2 (synthetic, supervised):** BiLSTM+Attention and Transformer trained/evaluated on
>   the controlled synthetic benchmark. **Its metrics are optimistic** (data is separable
>   by design) and are reported separately from real-data results.

A 5–10 minute presentation / demo flow:

1. **The problem (30s).** "Companies run many AI agents; how do we know they behave?
   ByteOps unifies tools AND watches the agents for misbehavior."
2. **Live demo — normal (1 min).** Type "summarize my emails"; open the Execution Center
   and show the run as a graph of steps.
3. **Safe sandbox demo — caught misbehavior (1 min).** Trigger `/api/demo/rogue-run`
   (a **sandboxed simulation** — it injects a known unsafe step with no real effect; it is
   a controlled demo, **not proof of real-world attack detection**). Show the run flagged
   with the **heat marker on the exact bad step** + the reason.
4. **V1 deep learning (1.5 min).** `train_anomaly.py`'s `NextActionLSTM` — self-supervised
   next-action prediction on **real** runs (DeepLog lineage; Storf et al. 2026 in `docs/papers/`).
5. **V2 supervised study (2.5 min).** The **BiLSTM+Attention (core)** and **Transformer**,
   the **5-detector comparison** — Isolation Forest, Next-action LSTM, BiLSTM+Attention,
   Transformer Encoder, LLM monitor — using **pAUROC@FPR<0.2** (`outputs/comparison.md` +
   MLflow). Show the **ablations** (order, risk features, **intent/context features**,
   attention vs mean-pool, architecture, classical vs learned) in `outputs/experiments.md`.
   **State clearly these V2 numbers are on the synthetic benchmark and are optimistic.**
6. **Honest limitations (30s).** Real-data results are modest and data-limited; the
   synthetic-benchmark results are strong but optimistic by design; the two are reported
   separately. Future work: richer real data + hand-labeled red-team at scale.
7. **Why it matters (30s).** "Same anomaly layer is both a real product safety feature
   and a complete applied deep-learning study."

**What to have ready:** the running app, the trained artifacts
(`lstm_nextaction_v1.onnx`, `bilstm_attention_classifier_v2.onnx`,
`transformer_encoder_classifier_v2.onnx`), `outputs/comparison.md`,
`outputs/experiments.md`, the MLflow UI, and the two papers.

---

## 10. Future steps (roadmap)

**Immediate (you):** collect more runs + label red-team → real metrics.

**Deep-learning depth (great for the report):**
- Add an **attention mechanism** + attention heatmaps (more explainability).
- Compare **LSTM vs BiLSTM vs GRU vs a small Transformer**.
- A **sequence autoencoder** (a different anomaly paradigm) for comparison.
- More ablations + ROC/PR curves once red-team data exists (scaffolding is built).

**Product depth (from the governance paper):**
- Surface anomaly flags in the Execution Center (badge + "Flagged" filter + reasons).
- A **kill-switch** to stop a running agent.
- An **Agent Card** (per-run "nutrition label": tools, risk, suspicion).
- Role-based views so non-technical users only ever see the simple chat surface.

**Hardening (partly done):** token encryption (done), CORS + input limits (done),
move secrets to a manager, replace 30s polling with live updates.

---

## 11. Honest limitations (state these — they're a strength, not a weakness)

**Two workflows, reported separately:**
- **V1 (real telemetry, self-supervised LSTM):** trained on your real agent runs. Data is
  small and low-diversity, so absolute numbers are modest. Red-team positives are limited
  to hand-labeled rejected approval-gate attempts. This is the *real-world* result.
- **V2 (synthetic benchmark, supervised BiLSTM+Attention / Transformer):** trained and
  evaluated on a **controlled synthetic dataset**. Numbers are strong but **optimistic by
  design** — the synthetic data is more separable than reality. These are reported as a
  *benchmark*, never conflated with the real-data results.

**General:**
- We use **real normal telemetry + hand-labeled red-team where available + a controlled
  synthetic benchmark** — we do not claim "no synthetic data."
- The models are small and modest — a solid applied project, not a novel research model.
- The `/api/demo/rogue-run` demo is a **safe sandbox simulation** (injected unsafe step,
  no real effect); it illustrates the detector, it is not evidence of real-world attack
  detection.
- Real-world detection quality scales with more real data + more hand-labeled red-team runs.

A professor respects an honest limitations section far more than inflated numbers. The
strength here is a **correctly-built, end-to-end, well-evaluated system** — that's
professional methodology, which is what gets graded.

---

## 12. Where everything lives (quick map)

- **Frontend app:** `frontend/src/`
- **Backend API + agents:** `backend/app/`
- **Deep-learning code:** `backend/app/anomaly/` (tokenizer, scorer, LLM monitor, constitution)
- **Offline DL scripts:** `backend/scripts/` (export, train, evaluate, experiments, drive_usage, label_redteam)
- **DL how-to:** `docs/DL_QUICKSTART.md`
- **Design + research:** `docs/superpowers/specs/`, `docs/papers/`, `docs/ROADMAP.md`
- **This guide:** `docs/PROJECT_GUIDE.md`
