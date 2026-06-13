# ByteOps Deep Learning — Final Roadmap

**Goal:** Ship a real-data, self-supervised anomaly detector inside ByteOps (the flagship) that flags suspicious agent runs and shows the offending step in the run graph — doubling as the DL course deliverable.

**Method:** Agile, thin vertical slices. Each sprint ends with something runnable and tested. Data collection runs *in parallel* from Sprint 1 because it is the critical path.

Linked artifacts:
- Spec: `docs/superpowers/specs/2026-06-13-anomaly-detection-deep-learning-design.md`
- Plan (12 tasks, TDD): `docs/superpowers/plans/2026-06-13-anomaly-detection-deep-learning.md`

---

## Governing UX principle: non-technical-first (role-based progressive disclosure)

ByteOps unifies many platforms for BOTH technical and non-technical employees. All technical/governance features (anomaly scores, agent cards, dependency graphs, audit trails) are gated by role:
- **Non-technical employee (default):** chat + plain-language activity feed + human-worded approval prompts only. Anomaly detection surfaces ONLY as a plain-language safety prompt; never numbers/graphs/jargon.
- **Technical / power user:** + workflow builder + `/runs` trace graph.
- **Admin / governance:** + Agent Cards, dependency/blast-radius graph, audit trail, numeric suspicion scores.

Every UI task declares its target surface. Technical UI never appears on the default chat view.

## Target directory structure

```
backend/
├── app/
│   └── anomaly/                     # NEW — the DL layer (in-app, lightweight)
│       ├── __init__.py
│       ├── tokenizer.py             # step → token, vocab, encode (pure, no torch)
│       ├── scorer.py                # ONNX inference, per-step NLL, graceful fallback
│       └── artifacts/               # committed trained model
│           ├── lstm_nextaction.onnx
│           ├── vocab.json
│           ├── model_meta.json      # threshold, max_len
│           └── metrics.json         # eval results (for the report)
├── scripts/                         # NEW — offline tooling (never deployed)
│   ├── export_runs.py               # DB → JSONL token sequences
│   ├── drive_usage.py               # fire real prompts → accumulate real runs
│   └── train_anomaly.py             # train LSTM + IsolationForest → ONNX
├── alembic/versions/
│   └── 0003_anomaly_fields.py       # NEW migration
├── requirements.txt                 # + onnxruntime, numpy (runtime)
├── requirements-train.txt           # NEW — torch, sklearn, onnx (offline only)
└── tests/                           # NEW anomaly tests alongside existing

frontend/
└── src/
    ├── hooks/use-agent-runs.ts      # + anomaly fields on AgentRun
    ├── lib/graph-transformer.ts     # + per-node anomaly heat
    └── components/runs/graph-nodes/
        └── ellipse-node.tsx         # + heat marker/glow

docs/
├── ROADMAP.md                       # this file
└── superpowers/{specs,plans}/...    # design + implementation plan
```

**Boundary principle:** torch/sklearn live ONLY in `scripts/` + `requirements-train.txt` (your laptop). The backend ships only `onnxruntime` reading `artifacts/`. The Docker image stays small.

---

## Agile sprints (mapped to the 12 plan tasks)

| Sprint | Focus | Plan tasks | Exit criteria |
|---|---|---|---|
| **S1 — Foundations** | Tokenizer + DB + API surface | 1, 2, 3, 4 | Tokens computed & tested; `agent_runs` has anomaly columns; API serializes them. **Kick off data collection in parallel.** |
| **S2 — Scoring engine** | ONNX scorer + completion hook | 5, 6, 7 | A run gets scored on completion (no-op until model exists); never breaks a run; full backend suite green. |
| **S3 — Offline tooling** | Export / train / usage-driver | 8 | Scripts exist & unit-tested; usage-driver actively generating real runs. |
| **S4 — Train on real data** | Collect → red-team → train | 9 *(manual, human-in-loop)* | 400+ real runs + ~25 red-team; model trained; artifacts committed; metrics recorded. |
| **S5 — The visual** | Run-graph heat | 10, 11 | Flagged run shows red/orange marker + glow on the offending step; frontend suite green. |
| **S6 — Verify & report** | E2E + course write-up | 12 | Manual E2E passes; graceful-degradation confirmed; report metrics from S4. |

**Critical path:** S4 (real data) gates the trained model and S6. Everything else (S1–S3, S5) is pure code and can proceed without waiting. So **S1–S3 + S5 build the machinery while data accumulates**, then S4 trains, then S6 verifies.

**Parallelization for subagents:** S1 tasks 1–2 (tokenizer) and task 3 (migration) are independent; tasks 5–7 are sequential (scorer scaffold → inference → hook); 10→11 sequential (data mapping → render). I'll dispatch independent tasks concurrently where the plan allows.

---

## Skills / superpowers used during implementation

- **superpowers:subagent-driven-development** — fresh subagent per task, two-stage review between tasks (your chosen execution mode).
- **superpowers:test-driven-development** — every task is red→green→commit (already baked into the plan).
- **superpowers:verification-before-completion** — run the real test/command and confirm output before claiming a task done.
- **superpowers:requesting-code-review** — review before the final integration commit / any PR.
- **chrome-devtools-mcp / verify skill** — for the S5/S6 visual verification in a real browser.

---

## Phase 2 (added 2026-06-13): LLM-monitor track + governance features

Grounded in the two supplied papers (Storf et al. black-box monitoring; Credo AI XAI-at-scale). See the spec addendum + plan Tasks 13–16.

| Sprint | Focus | Plan tasks | Exit criteria |
|---|---|---|---|
| **S7 — LLM monitor** | Constitution + black-box monitor (no training data) | 13, 14 | Runs get a 1–10 LLM suspicion score on completion; works today without the trained model. |
| **S8 — Governance UX** | Agent Card, dependency/blast-radius graph, kill switch, audit trail | 15, 16 | Per-run Agent Card + blast-radius graph render in the existing theme; approval gates surfaced as kill switch. |
| **S9 — Comparison report** | LSTM vs Isolation Forest vs LLM-monitor | 8, 9, 13 | pAUROC@FPR<0.2 table across all three detectors for the DL course report. |

Detector lineup (course deliverable = a 3-way comparison):
- **Next-action LSTM** — trained, self-supervised, structural/ordering anomalies (your DL contribution).
- **Isolation Forest** — classical baseline.
- **LLM black-box monitor** — frontier baseline + production scorer, semantic anomalies, zero training data.

Metric: **partial AUROC at FPR < 0.2** (the paper's metric for rare-event oversight), reported alongside F1. Scoring scale standardized to **1–10** across all detectors.

## Definition of Done

- All new code TDD-covered; backend `pytest` and frontend `vitest` suites green.
- A real flagged run renders the anomaly marker on the correct step.
- Scoring degrades gracefully with no model present (run unaffected).
- `metrics.json` populated from real telemetry for the course report.
- No torch in the deployed image; secrets/data never committed.
