# ByteOps Deep Learning Anomaly Detection — Implementation Plan (Lean v1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-supervised deep-learning layer to ByteOps that learns normal agent-run behavior from real telemetry and flags anomalous runs, surfacing the suspicious step visually in the run graph.

**Architecture:** Real `agent_run_steps` are tokenized into coarse `{step_type}|{risk}|{status}` tokens. A next-action LSTM is trained offline (PyTorch) on normal runs to predict each next token; the per-step negative log-likelihood (NLL) is the anomaly signal. The model is exported to ONNX and served in FastAPI via onnxruntime, scoring each run on completion. Scores persist on `agent_runs` and drive per-step heat coloring in the existing run graph. An Isolation Forest baseline (offline) provides the academic comparison.

**Tech Stack:** Python/FastAPI, SQLAlchemy async + Alembic, PyTorch (offline only), scikit-learn (offline), ONNX Runtime (in-backend), Next.js/React/TypeScript + @xyflow/react, vitest, pytest.

**Scope note (under-1-week lean v1):** Ships data collection + training + backend scoring + ONE visual (run-graph heat). Deferred: ablation experiments, report polish, retraining automation, Action Center badge/filter (can fast-follow).

---

## File Structure

**Backend — new package `backend/app/anomaly/`:**
- `__init__.py` — package marker.
- `tokenizer.py` — pure functions: step → token, run → token list, build vocab, encode. No torch/onnx import (so it's testable everywhere and importable offline + in-backend).
- `scorer.py` — `AnomalyScorer` singleton: loads ONNX + vocab + meta, scores a run's steps, degrades gracefully when artifacts are absent.
- `artifacts/` — committed model files: `lstm_nextaction.onnx`, `vocab.json`, `model_meta.json`. (Created by training in Task 8; empty until then.)

**Backend — offline scripts (never imported by the app):**
- `backend/scripts/export_runs.py` — DB → JSONL of token sequences + labels.
- `backend/scripts/train_anomaly.py` — train LSTM + Isolation Forest, tune threshold, export ONNX/vocab/meta + metrics.
- `backend/scripts/drive_usage.py` — fire varied real prompts through `/api/chat` to accumulate real runs.
- `backend/requirements-train.txt` — offline-only deps (torch, scikit-learn, onnx).

**Backend — modified:**
- `backend/app/models/agent_run.py` — 4 new columns on `AgentRun`.
- `backend/alembic/versions/0003_anomaly_fields.py` — migration (new).
- `backend/app/services/agent_runtime.py` — call scorer in `complete_agent_run`; add fields to `serialize_agent_run`.
- `backend/requirements.txt` — add `onnxruntime`, `numpy`.

**Frontend — modified:**
- `frontend/src/hooks/use-agent-runs.ts` — add anomaly fields to `AgentRun`.
- `frontend/src/lib/graph-transformer.ts` — map step scores → per-node `anomalyScore`.
- `frontend/src/components/runs/graph-nodes/ellipse-node.tsx` — render heat ring.

---

## Token scheme (the single most important design decision)

Each step becomes `"{step_type}|{risk}|{status}"`:
- `step_type` ∈ {route, plan, tool_call, approval, verify, final} (from `AgentRunStepType`).
- `risk` for `tool_call` steps = `classify_tool_call("", step.name).risk.value` (read/write/external_send/destructive); for all other step types = `"none"`.
- `status` = step.status (completed/failed/approved/rejected/…).

Example run: `route|none|completed`, `plan|none|completed`, `tool_call|read|completed`, `tool_call|external_send|completed`, `final|none|completed`.

This keeps the vocabulary to ~15–25 real tokens — correct for the small-data regime. `<PAD>`=0, `<UNK>`=1.

---

## Task 1: Tokenizer — step → token

**Files:**
- Create: `backend/app/anomaly/__init__.py` (empty)
- Create: `backend/app/anomaly/tokenizer.py`
- Test: `backend/tests/test_anomaly_tokenizer.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_anomaly_tokenizer.py
"""Tests for the anomaly tokenizer."""

from app.anomaly.tokenizer import PAD, UNK, step_to_token


def test_tool_call_step_uses_risk_class():
    step = {"step_type": "tool_call", "name": "send_email", "status": "completed"}
    assert step_to_token(step) == "tool_call|external_send|completed"


def test_read_tool_call_token():
    step = {"step_type": "tool_call", "name": "search_emails", "status": "completed"}
    assert step_to_token(step) == "tool_call|read|completed"


def test_non_tool_step_has_none_risk():
    step = {"step_type": "plan", "name": "initial_plan", "status": "completed"}
    assert step_to_token(step) == "plan|none|completed"


def test_special_tokens_are_distinct():
    assert PAD == "<PAD>"
    assert UNK == "<UNK>"
    assert PAD != UNK
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_anomaly_tokenizer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.anomaly.tokenizer'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/anomaly/__init__.py
```
(create the file empty)

```python
# backend/app/anomaly/tokenizer.py
"""Convert agent-run steps into coarse tokens for sequence modeling.

Pure functions only — no torch/onnx imports — so this module is importable
both inside the FastAPI app and from offline training scripts.
"""

from __future__ import annotations

from app.services.agent_policy import classify_tool_call

PAD = "<PAD>"
UNK = "<UNK>"


def step_to_token(step: dict) -> str:
    """Map one step dict ({step_type, name, status}) to a composite token."""
    step_type = str(step.get("step_type", "")).strip() or "unknown"
    status = str(step.get("status", "")).strip() or "unknown"
    if step_type == "tool_call":
        risk = classify_tool_call("", str(step.get("name", ""))).risk.value
    else:
        risk = "none"
    return f"{step_type}|{risk}|{status}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_anomaly_tokenizer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/anomaly/__init__.py backend/app/anomaly/tokenizer.py backend/tests/test_anomaly_tokenizer.py
git commit -m "feat(anomaly): add step tokenizer"
```

---

## Task 2: Tokenizer — run → tokens, vocab, encode

**Files:**
- Modify: `backend/app/anomaly/tokenizer.py`
- Test: `backend/tests/test_anomaly_tokenizer.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# append to backend/tests/test_anomaly_tokenizer.py
from app.anomaly.tokenizer import build_vocab, encode_tokens, run_to_tokens


def test_run_to_tokens_preserves_order():
    steps = [
        {"step_type": "plan", "name": "initial_plan", "status": "completed"},
        {"step_type": "tool_call", "name": "search_emails", "status": "completed"},
    ]
    assert run_to_tokens(steps) == ["plan|none|completed", "tool_call|read|completed"]


def test_build_vocab_reserves_special_tokens():
    vocab = build_vocab([["a|b|c"], ["a|b|c", "d|e|f"]])
    assert vocab[PAD] == 0
    assert vocab[UNK] == 1
    assert vocab["a|b|c"] >= 2
    assert vocab["d|e|f"] >= 2


def test_encode_pads_to_max_len():
    vocab = {PAD: 0, UNK: 1, "a|b|c": 2}
    encoded = encode_tokens(["a|b|c"], vocab, max_len=4)
    assert encoded == [2, 0, 0, 0]


def test_encode_truncates_and_maps_unknown():
    vocab = {PAD: 0, UNK: 1, "a|b|c": 2}
    encoded = encode_tokens(["a|b|c", "z|z|z", "a|b|c"], vocab, max_len=2)
    assert encoded == [2, 1]  # truncated to 2; unknown -> UNK(1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_anomaly_tokenizer.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_vocab'`

- [ ] **Step 3: Write minimal implementation (append to tokenizer.py)**

```python
# append to backend/app/anomaly/tokenizer.py


def run_to_tokens(steps: list[dict]) -> list[str]:
    """Map an ordered list of step dicts to a token sequence."""
    return [step_to_token(s) for s in steps]


def build_vocab(sequences: list[list[str]]) -> dict[str, int]:
    """Build a token→id vocab from training sequences. PAD=0, UNK=1."""
    vocab: dict[str, int] = {PAD: 0, UNK: 1}
    for seq in sequences:
        for token in seq:
            if token not in vocab:
                vocab[token] = len(vocab)
    return vocab


def encode_tokens(tokens: list[str], vocab: dict[str, int], max_len: int) -> list[int]:
    """Encode a token list to fixed-length ids: truncate to max_len, pad with 0."""
    unk = vocab[UNK]
    ids = [vocab.get(t, unk) for t in tokens[:max_len]]
    if len(ids) < max_len:
        ids += [vocab[PAD]] * (max_len - len(ids))
    return ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_anomaly_tokenizer.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/anomaly/tokenizer.py backend/tests/test_anomaly_tokenizer.py
git commit -m "feat(anomaly): add run tokenization, vocab, encoding"
```

---

## Task 3: Database migration + model columns

**Files:**
- Modify: `backend/app/models/agent_run.py:32-61` (AgentRun columns)
- Create: `backend/alembic/versions/0003_anomaly_fields.py`

- [ ] **Step 1: Add columns to the AgentRun model**

In `backend/app/models/agent_run.py`, inside class `AgentRun`, immediately after the `metadata_` column (line 56), add:

```python
    anomaly_score: Mapped[float | None] = mapped_column(nullable=True)
    step_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    flagged: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    data_label: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unlabeled", server_default="unlabeled"
    )
```

(`Float` is inferred from `float`; `JSONB` and `String` are already imported at the top of the file.)

- [ ] **Step 2: Create the Alembic migration**

```python
# backend/alembic/versions/0003_anomaly_fields.py
"""add anomaly detection fields to agent_runs

Revision ID: 0003_anomaly_fields
Revises: 0002_workflow_metadata
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_anomaly_fields"
down_revision = "0002_workflow_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("anomaly_score", sa.Float(), nullable=True))
    op.add_column("agent_runs", sa.Column("step_scores", JSONB(), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "agent_runs",
        sa.Column("data_label", sa.String(length=20), nullable=False, server_default="unlabeled"),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "data_label")
    op.drop_column("agent_runs", "flagged")
    op.drop_column("agent_runs", "step_scores")
    op.drop_column("agent_runs", "anomaly_score")
```

> Confirm `down_revision` matches the actual latest revision id in `backend/alembic/versions/0002_workflow_metadata.py` (open it and read its `revision = ...`). Adjust the string if it differs.

- [ ] **Step 3: Apply the migration**

Run: `cd backend && .venv/Scripts/python.exe -m alembic upgrade head`
Expected: `Running upgrade 0002_workflow_metadata -> 0003_anomaly_fields`

- [ ] **Step 4: Verify columns exist**

Run:
```bash
cd backend && .venv/Scripts/python.exe -c "import asyncio; from sqlalchemy import text; from app.core.database import async_session_factory
async def m():
    async with async_session_factory() as s:
        r = await s.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='agent_runs' AND column_name IN ('anomaly_score','step_scores','flagged','data_label')\"))
        print(sorted(c[0] for c in r))
asyncio.run(m())"
```
Expected: `['anomaly_score', 'data_label', 'flagged', 'step_scores']`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/agent_run.py backend/alembic/versions/0003_anomaly_fields.py
git commit -m "feat(anomaly): add anomaly fields to agent_runs"
```

---

## Task 4: Serialize anomaly fields in the API response

**Files:**
- Modify: `backend/app/services/agent_runtime.py:21-48` (serialize_agent_run)
- Test: `backend/tests/test_serialize_anomaly.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_serialize_anomaly.py
"""serialize_agent_run exposes anomaly fields."""

from types import SimpleNamespace

from app.services.agent_runtime import serialize_agent_run


def _run(**overrides):
    base = dict(
        id="11111111-1111-1111-1111-111111111111",
        user_id="22222222-2222-2222-2222-222222222222",
        conversation_id=None,
        intent="general",
        status="completed",
        plan=None,
        final_response="done",
        error=None,
        metadata_=None,
        created_at=None,
        updated_at=None,
        completed_at=None,
        steps=[],
        anomaly_score=0.42,
        step_scores={"step-1": 0.9},
        flagged=True,
        data_label="redteam",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_serialize_includes_anomaly_fields():
    data = serialize_agent_run(_run())
    assert data["anomaly_score"] == 0.42
    assert data["step_scores"] == {"step-1": 0.9}
    assert data["flagged"] is True
    assert data["data_label"] == "redteam"


def test_serialize_defaults_when_unscored():
    data = serialize_agent_run(_run(anomaly_score=None, step_scores=None, flagged=False, data_label="unlabeled"))
    assert data["anomaly_score"] is None
    assert data["flagged"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_serialize_anomaly.py -v`
Expected: FAIL with `KeyError: 'anomaly_score'`

- [ ] **Step 3: Add fields to serialize_agent_run**

In `backend/app/services/agent_runtime.py`, inside `serialize_agent_run`, add these keys to the returned dict immediately after the `"metadata": run.metadata_,` line:

```python
        "anomaly_score": getattr(run, "anomaly_score", None),
        "step_scores": getattr(run, "step_scores", None),
        "flagged": bool(getattr(run, "flagged", False)),
        "data_label": getattr(run, "data_label", "unlabeled"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_serialize_anomaly.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_runtime.py backend/tests/test_serialize_anomaly.py
git commit -m "feat(anomaly): serialize anomaly fields in agent-run API"
```

---

## Task 5: Scorer — graceful no-artifact behavior

**Files:**
- Create: `backend/app/anomaly/scorer.py`
- Create: `backend/app/anomaly/artifacts/.gitkeep` (empty placeholder)
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_anomaly_scorer.py`

- [ ] **Step 1: Add runtime deps**

Append to `backend/requirements.txt`:
```
onnxruntime>=1.17
numpy>=1.26
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_anomaly_scorer.py
"""AnomalyScorer degrades gracefully when artifacts are missing."""

from app.anomaly.scorer import AnomalyScorer


def test_scorer_unavailable_returns_none(tmp_path):
    scorer = AnomalyScorer(artifacts_dir=tmp_path)  # empty dir, no model
    assert scorer.available is False
    steps = [{"step_type": "plan", "name": "initial_plan", "status": "completed"}]
    assert scorer.score_run(steps) is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_anomaly_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.anomaly.scorer'`

- [ ] **Step 4: Write minimal implementation**

Create `backend/app/anomaly/artifacts/.gitkeep` (empty file).

```python
# backend/app/anomaly/scorer.py
"""Score agent runs for anomalies using an offline-trained ONNX model.

Designed to never raise into the request path: if artifacts are missing or
inference fails, scoring returns None and the run proceeds unaffected.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.anomaly.tokenizer import encode_tokens, run_to_tokens

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(__file__).resolve().parent / "artifacts"


class AnomalyScorer:
    def __init__(self, artifacts_dir: Path | None = None) -> None:
        self._dir = Path(artifacts_dir) if artifacts_dir else _DEFAULT_DIR
        self._session = None
        self._vocab: dict[str, int] = {}
        self._meta: dict = {}
        self._load()

    @property
    def available(self) -> bool:
        return self._session is not None

    def _load(self) -> None:
        onnx_path = self._dir / "lstm_nextaction.onnx"
        vocab_path = self._dir / "vocab.json"
        meta_path = self._dir / "model_meta.json"
        if not (onnx_path.exists() and vocab_path.exists() and meta_path.exists()):
            logger.info("Anomaly artifacts not found in %s; scoring disabled.", self._dir)
            return
        try:
            import onnxruntime as ort

            self._vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
            self._meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self._session = ort.InferenceSession(
                str(onnx_path), providers=["CPUExecutionProvider"]
            )
        except Exception as exc:  # noqa: BLE001 - never break startup
            logger.warning("Failed to load anomaly model: %s", exc)
            self._session = None

    def score_run(self, steps: list[dict]) -> dict | None:
        """Return {anomaly_score, step_scores, flagged} or None if unavailable."""
        if not self.available:
            return None
        return None  # real inference added in Task 6
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_anomaly_scorer.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/anomaly/scorer.py backend/app/anomaly/artifacts/.gitkeep backend/requirements.txt backend/tests/test_anomaly_scorer.py
git commit -m "feat(anomaly): add scorer scaffold with graceful fallback"
```

---

## Task 6: Scorer — real NLL inference

**Files:**
- Modify: `backend/app/anomaly/scorer.py`
- Test: `backend/tests/test_anomaly_scorer.py`

This task computes per-step anomaly scores from model logits. The ONNX model takes int64 input `[1, max_len]` named `"tokens"` and returns float logits `[1, max_len, vocab_size]` named `"logits"`. For position i (predicting token i+1), the NLL of the actual next token is `-log_softmax(logits[i])[token[i+1]]`. Each real step (index ≥ 1) gets the NLL that predicted it; step 0 gets the run's mean NLL (no predecessor). The session score is the max step NLL (a single bad step should flag the run). `flagged = session_score >= meta["threshold"]`.

- [ ] **Step 1: Write the failing test (append)**

```python
# append to backend/tests/test_anomaly_scorer.py
import json

import numpy as np


def _write_fake_artifacts(tmp_path):
    """Create a tiny ONNX identity-ish model + vocab + meta for testing."""
    import onnx
    from onnx import TensorProto, helper

    vocab = {"<PAD>": 0, "<UNK>": 1, "plan|none|completed": 2, "tool_call|read|completed": 3,
             "tool_call|external_send|completed": 4}
    max_len = 6
    vocab_size = len(vocab)

    # Model: embed tokens via Gather into a fixed [vocab_size, vocab_size] identity*5
    # weight, producing logits that strongly predict "repeat the same token".
    weight = (np.eye(vocab_size, dtype=np.float32) * 5.0)
    w_init = helper.make_tensor("W", TensorProto.FLOAT, weight.shape, weight.flatten().tolist())
    tokens_in = helper.make_tensor_value_info("tokens", TensorProto.INT64, [1, max_len])
    logits_out = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, max_len, vocab_size])
    gather = helper.make_node("Gather", ["W", "tokens"], ["logits"], axis=0)
    graph = helper.make_graph([gather], "tiny", [tokens_in], [logits_out], [w_init])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 9
    onnx.save(model, str(tmp_path / "lstm_nextaction.onnx"))
    (tmp_path / "vocab.json").write_text(json.dumps(vocab), encoding="utf-8")
    (tmp_path / "model_meta.json").write_text(
        json.dumps({"max_len": max_len, "threshold": 2.0}), encoding="utf-8"
    )


def test_scorer_produces_step_scores(tmp_path):
    _write_fake_artifacts(tmp_path)
    scorer = AnomalyScorer(artifacts_dir=tmp_path)
    assert scorer.available is True
    steps = [
        {"id": "s0", "step_type": "plan", "name": "initial_plan", "status": "completed"},
        {"id": "s1", "step_type": "tool_call", "name": "search_emails", "status": "completed"},
        {"id": "s2", "step_type": "tool_call", "name": "send_email", "status": "completed"},
    ]
    result = scorer.score_run(steps)
    assert set(result) == {"anomaly_score", "step_scores", "flagged"}
    assert set(result["step_scores"]) == {"s0", "s1", "s2"}
    assert isinstance(result["anomaly_score"], float)
    assert isinstance(result["flagged"], bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_anomaly_scorer.py::test_scorer_produces_step_scores -v`
Expected: FAIL (result is None → `TypeError` on `set(result)`). If `onnx` import fails, run `.venv/Scripts/python.exe -m pip install onnx` first (test-only dep).

- [ ] **Step 3: Implement real inference**

Replace the body of `score_run` in `backend/app/anomaly/scorer.py` with:

```python
    def score_run(self, steps: list[dict]) -> dict | None:
        """Return {anomaly_score, step_scores, flagged} or None if unavailable."""
        if not self.available or not steps:
            return None
        try:
            import numpy as np

            max_len = int(self._meta.get("max_len", 12))
            threshold = float(self._meta.get("threshold", 0.0))
            tokens = run_to_tokens(steps)
            ids = encode_tokens(tokens, self._vocab, max_len)
            arr = np.asarray([ids], dtype=np.int64)
            (logits,) = self._session.run(["logits"], {"tokens": arr})
            logits = logits[0]  # [max_len, vocab_size]

            # log-softmax along vocab axis
            m = logits.max(axis=-1, keepdims=True)
            log_probs = logits - m - np.log(np.exp(logits - m).sum(axis=-1, keepdims=True))

            n = min(len(steps), max_len)
            nlls: list[float] = []
            for i in range(1, n):
                nlls.append(float(-log_probs[i - 1, ids[i]]))
            mean_nll = float(np.mean(nlls)) if nlls else 0.0

            step_scores: dict[str, float] = {}
            for idx, step in enumerate(steps):
                sid = str(step.get("id", idx))
                if idx == 0 or idx >= max_len:
                    step_scores[sid] = round(mean_nll, 4)
                else:
                    step_scores[sid] = round(float(-log_probs[idx - 1, ids[idx]]), 4)

            session_score = max(step_scores.values()) if step_scores else 0.0
            return {
                "anomaly_score": round(float(session_score), 4),
                "step_scores": step_scores,
                "flagged": bool(session_score >= threshold),
            }
        except Exception as exc:  # noqa: BLE001 - never break the run
            logger.warning("Anomaly scoring failed: %s", exc)
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_anomaly_scorer.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/anomaly/scorer.py backend/tests/test_anomaly_scorer.py
git commit -m "feat(anomaly): compute per-step NLL anomaly scores"
```

---

## Task 7: Wire scoring into run completion

**Files:**
- Modify: `backend/app/services/agent_runtime.py` (add module singleton + score in `complete_agent_run`)
- Test: `backend/tests/test_complete_run_scoring.py`

The scorer is loaded once as a module-level singleton. `complete_agent_run` already has the run and db. After marking completed, we load the run's steps, score them, and persist — all inside try/except so scoring can never fail a run.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_complete_run_scoring.py
"""complete_agent_run applies anomaly scoring without breaking on failure."""

import app.services.agent_runtime as rt


class _FakeScorer:
    available = True

    def score_run(self, steps):
        return {"anomaly_score": 1.23, "step_scores": {"x": 1.23}, "flagged": True}


def test_apply_scoring_sets_fields(monkeypatch):
    monkeypatch.setattr(rt, "_scorer", _FakeScorer())

    class Run:
        anomaly_score = None
        step_scores = None
        flagged = False

    run = Run()
    steps = [{"id": "x", "step_type": "final", "name": "final", "status": "completed"}]
    rt.apply_anomaly_scoring(run, steps)
    assert run.anomaly_score == 1.23
    assert run.flagged is True
    assert run.step_scores == {"x": 1.23}


def test_apply_scoring_swallows_errors(monkeypatch):
    class Boom:
        available = True

        def score_run(self, steps):
            raise RuntimeError("model exploded")

    monkeypatch.setattr(rt, "_scorer", Boom())

    class Run:
        anomaly_score = None
        step_scores = None
        flagged = False

    run = Run()
    rt.apply_anomaly_scoring(run, [{"id": "x", "step_type": "final", "name": "f", "status": "completed"}])
    assert run.anomaly_score is None  # unchanged; no exception raised
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_complete_run_scoring.py -v`
Expected: FAIL with `AttributeError: module 'app.services.agent_runtime' has no attribute 'apply_anomaly_scoring'`

- [ ] **Step 3: Implement the singleton + helper, call it in complete_agent_run**

At the top of `backend/app/services/agent_runtime.py`, after the existing imports, add:

```python
from app.anomaly.scorer import AnomalyScorer

_scorer = AnomalyScorer()


def apply_anomaly_scoring(run, steps: list[dict]) -> None:
    """Best-effort: write anomaly fields onto `run`. Never raises."""
    try:
        if not _scorer.available:
            return
        result = _scorer.score_run(steps)
        if not result:
            return
        run.anomaly_score = result["anomaly_score"]
        run.step_scores = result["step_scores"]
        run.flagged = result["flagged"]
    except Exception:  # noqa: BLE001 - scoring must never break a run
        return
```

Then change `complete_agent_run` so it scores before the final commit. Replace the existing function body with:

```python
async def complete_agent_run(db: AsyncSession, run: AgentRun, final_response: str) -> AgentRun:
    run.status = AgentRunStatus.COMPLETED
    run.final_response = final_response
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    try:
        await db.refresh(run, ["steps"])
        steps = [
            {"id": str(s.id), "step_type": s.step_type.value if hasattr(s.step_type, "value") else str(s.step_type),
             "name": s.name, "status": s.status}
            for s in run.steps
        ]
        apply_anomaly_scoring(run, steps)
        await db.commit()
        await db.refresh(run)
    except Exception:  # noqa: BLE001 - scoring is best-effort
        await db.rollback()
    return run
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_complete_run_scoring.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full backend suite (no regressions)**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass (existing + new). The scorer is unavailable in CI (no artifacts), so `apply_anomaly_scoring` is a no-op there.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/agent_runtime.py backend/tests/test_complete_run_scoring.py
git commit -m "feat(anomaly): score runs on completion (best-effort)"
```

---

## Task 8: Offline data + training tooling

**Files:**
- Create: `backend/requirements-train.txt`
- Create: `backend/scripts/export_runs.py`
- Create: `backend/scripts/drive_usage.py`
- Create: `backend/scripts/train_anomaly.py`
- Test: `backend/tests/test_export_runs.py`

These run on your laptop, never in production. Only `export_runs`' pure helper is unit-tested; the training script is validated by a real smoke run in Task 9.

- [ ] **Step 1: Offline training deps**

```
# backend/requirements-train.txt
torch>=2.2
scikit-learn>=1.4
onnx>=1.15
numpy>=1.26
mlflow>=2.10
```

> **MLflow integration (chosen enhancement):** `train_anomaly.py` wraps training in an MLflow run that logs params (epochs, max_len, hidden, embed, vocab_size), metrics (lstm precision/recall/f1, isolation_forest recall), and the exported ONNX as an artifact. This produces the comparison evidence for the course report. See the `mlflow` calls embedded in the script in Step 4. MLflow stores to a local `./mlruns` dir (gitignored) — view with `mlflow ui`.

- [ ] **Step 2: Write the failing test for the export helper**

```python
# backend/tests/test_export_runs.py
from scripts.export_runs import run_record_to_sequence


def test_run_record_to_sequence_shape():
    record = {
        "id": "r1",
        "data_label": "normal",
        "steps": [
            {"id": "a", "step_type": "plan", "name": "initial_plan", "status": "completed"},
            {"id": "b", "step_type": "tool_call", "name": "send_email", "status": "completed"},
        ],
    }
    seq = run_record_to_sequence(record)
    assert seq["run_id"] == "r1"
    assert seq["label"] == "normal"
    assert seq["tokens"] == ["plan|none|completed", "tool_call|external_send|completed"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_export_runs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.export_runs'`

> If collection errors on missing `scripts/__init__.py`, create an empty `backend/scripts/__init__.py`.

- [ ] **Step 4: Implement the scripts**

```python
# backend/scripts/export_runs.py
"""Export real agent runs from the DB into JSONL token sequences for training.

Usage: python scripts/export_runs.py --out data/runs.jsonl
Run sequences are labeled by agent_runs.data_label (normal/redteam/unlabeled).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.anomaly.tokenizer import run_to_tokens


def run_record_to_sequence(record: dict) -> dict:
    return {
        "run_id": record["id"],
        "label": record.get("data_label", "unlabeled"),
        "tokens": run_to_tokens(record.get("steps", [])),
    }


async def _export(out_path: Path) -> int:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.database import async_session_factory
    from app.models.agent_run import AgentRun
    from app.services.agent_runtime import serialize_agent_run

    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentRun).options(selectinload(AgentRun.steps)).order_by(AgentRun.created_at)
        )
        runs = result.scalars().all()

    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for run in runs:
            seq = run_record_to_sequence(serialize_agent_run(run))
            if not seq["tokens"]:
                continue
            f.write(json.dumps(seq) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/runs.jsonl")
    args = parser.parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = asyncio.run(_export(out_path))
    print(f"Exported {n} run sequences to {out_path}")


if __name__ == "__main__":
    main()
```

```python
# backend/scripts/drive_usage.py
"""Drive REAL agent runs by sending varied prompts through /api/chat.

This accumulates genuine telemetry (real tools, real model). Nothing synthetic
is written to the DB — only the choice of prompts is scripted.

Usage:
  python scripts/drive_usage.py --token "<clerk_jwt>" --rounds 10 --base http://localhost:8000

Get a Clerk JWT from your browser devtools (Authorization header on any API call)
while signed in to the running frontend.
"""

from __future__ import annotations

import argparse
import time

import httpx

PROMPTS = [
    "Summarize my latest 5 emails.",
    "Do I have any unread important emails?",
    "What's on my calendar this week?",
    "Any meetings tomorrow morning?",
    "Find emails from my manager about the project.",
    "List my open GitHub pull requests.",
    "Any failing CI checks on my repos?",
    "Show recent commits on my main project.",
    "What Jira tickets are assigned to me?",
    "Any blocked tickets in the current sprint?",
    "Catch me up on my unread Slack messages.",
    "Any direct messages I missed today?",
    "Draft a reply to my most recent email.",
    "What files were shared with me in Dropbox recently?",
    "Summarize today's activity across my tools.",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Clerk JWT")
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--rounds", type=int, default=5, help="passes over the prompt list")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between calls")
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}", "Content-Type": "application/json"}
    sent = 0
    for r in range(args.rounds):
        for prompt in PROMPTS:
            body = {"message": f"{prompt} (run {r + 1})"}
            try:
                with httpx.stream(
                    "POST", f"{args.base}/api/chat", headers=headers, json=body, timeout=120
                ) as resp:
                    for _ in resp.iter_lines():
                        pass  # drain the SSE stream so the run completes
                sent += 1
                print(f"[{sent}] ok: {prompt[:48]}")
            except Exception as exc:  # noqa: BLE001
                print(f"  failed: {prompt[:40]} -> {exc}")
            time.sleep(args.delay)
    print(f"Done. Triggered {sent} real runs.")


if __name__ == "__main__":
    main()
```

```python
# backend/scripts/train_anomaly.py
"""Train a next-action LSTM (self-supervised) + Isolation Forest baseline on
REAL exported run sequences, then export ONNX + vocab + meta + metrics.

Usage:
  python scripts/train_anomaly.py --data data/runs.jsonl --epochs 30 --max-len 12

Trains ONLY on label=='normal' (or 'unlabeled') sequences. Sequences labeled
'redteam' are held out for evaluation. Picks the flag threshold as a high
percentile of validation NLL.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from app.anomaly.tokenizer import PAD, build_vocab, encode_tokens

ARTIFACTS = Path(__file__).resolve().parent.parent / "app" / "anomaly" / "artifacts"


def load_sequences(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    import torch
    import torch.nn as nn
    from sklearn.ensemble import IsolationForest

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/runs.jsonl")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--max-len", type=int, default=12)
    parser.add_argument("--hidden", type=int, default=48)
    parser.add_argument("--embed", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    import mlflow

    mlflow.set_experiment("byteops-anomaly")

    seqs = load_sequences(Path(args.data))
    normal = [s for s in seqs if s["label"] in ("normal", "unlabeled")]
    redteam = [s for s in seqs if s["label"] == "redteam"]
    if len(normal) < 20:
        print(f"WARNING: only {len(normal)} normal runs — metrics will be weak.")

    mlflow.start_run()
    mlflow.log_params({
        "epochs": args.epochs, "max_len": args.max_len, "hidden": args.hidden,
        "embed": args.embed, "n_normal": len(normal), "n_redteam": len(redteam),
    })

    # split normal 80/20
    rng = np.random.default_rng(args.seed)
    idx = rng.permutation(len(normal))
    cut = max(1, int(0.8 * len(normal)))
    train = [normal[i] for i in idx[:cut]]
    val = [normal[i] for i in idx[cut:]] or train[:1]

    vocab = build_vocab([s["tokens"] for s in train])
    vocab_size = len(vocab)
    max_len = args.max_len

    def encode_batch(items):
        return torch.tensor([encode_tokens(s["tokens"], vocab, max_len) for s in items], dtype=torch.long)

    class NextActionLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Embedding(vocab_size, args.embed, padding_idx=vocab[PAD])
            self.lstm = nn.LSTM(args.embed, args.hidden, batch_first=True)
            self.head = nn.Linear(args.hidden, vocab_size)

        def forward(self, x):
            emb = self.embed(x)
            out, _ = self.lstm(emb)
            return self.head(out)  # [B, T, V]

    model = NextActionLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss(ignore_index=vocab[PAD])
    xb = encode_batch(train)

    model.train()
    for ep in range(args.epochs):
        opt.zero_grad()
        logits = model(xb[:, :-1])
        loss = loss_fn(logits.reshape(-1, vocab_size), xb[:, 1:].reshape(-1))
        loss.backward()
        opt.step()
        if (ep + 1) % 5 == 0:
            print(f"epoch {ep + 1}: loss={loss.item():.4f}")

    model.eval()

    def session_nll(items):
        scores = []
        with torch.no_grad():
            x = encode_batch(items)
            logits = model(x)
            logp = torch.log_softmax(logits, dim=-1)
            for b in range(x.shape[0]):
                nlls = []
                for t in range(1, max_len):
                    tok = x[b, t].item()
                    if tok == vocab[PAD]:
                        break
                    nlls.append(-logp[b, t - 1, tok].item())
                scores.append(max(nlls) if nlls else 0.0)
        return np.array(scores)

    val_scores = session_nll(val)
    threshold = float(np.percentile(val_scores, 90)) if len(val_scores) else 1.0

    # Evaluation vs red-team (if any)
    metrics = {"n_train": len(train), "n_val": len(val), "n_redteam": len(redteam),
               "threshold": threshold, "vocab_size": vocab_size}
    if redteam:
        rt_scores = session_nll(redteam)
        tp = int((rt_scores >= threshold).sum())
        fn = int((rt_scores < threshold).sum())
        fp = int((val_scores >= threshold).sum())
        tn = int((val_scores < threshold).sum())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        metrics["lstm"] = {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn}

    # Isolation Forest baseline on simple length/risk features
    def features(items):
        rows = []
        for s in items:
            toks = s["tokens"]
            n = len(toks) or 1
            ext = sum(1 for t in toks if "external_send" in t or "destructive" in t)
            uniq = len(set(toks))
            rows.append([n, ext / n, uniq / n])
        return np.array(rows) if items else np.zeros((0, 3))

    if len(train) >= 5:
        iso = IsolationForest(n_estimators=200, contamination=0.2, random_state=args.seed)
        iso.fit(features(train))
        if redteam:
            pred = iso.predict(features(redteam))  # -1 = anomaly
            metrics["isolation_forest"] = {"recall_on_redteam": float((pred == -1).mean())}

    # Export ONNX
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    dummy = torch.zeros(1, max_len, dtype=torch.long)
    torch.onnx.export(
        model, dummy, str(ARTIFACTS / "lstm_nextaction.onnx"),
        input_names=["tokens"], output_names=["logits"],
        dynamic_axes=None, opset_version=13,
    )
    (ARTIFACTS / "vocab.json").write_text(json.dumps(vocab), encoding="utf-8")
    (ARTIFACTS / "model_meta.json").write_text(
        json.dumps({"max_len": max_len, "threshold": threshold}), encoding="utf-8"
    )
    (ARTIFACTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    # MLflow: log flat metrics + the ONNX artifact for the course report
    flat = {"threshold": threshold, "vocab_size": vocab_size}
    if "lstm" in metrics:
        flat.update({f"lstm_{k}": v for k, v in metrics["lstm"].items()})
    if "isolation_forest" in metrics:
        flat.update({f"iso_{k}": v for k, v in metrics["isolation_forest"].items()})
    mlflow.log_metrics({k: float(v) for k, v in flat.items()})
    mlflow.log_artifact(str(ARTIFACTS / "lstm_nextaction.onnx"))
    mlflow.log_artifact(str(ARTIFACTS / "metrics.json"))
    mlflow.end_run()

    print("Saved artifacts to", ARTIFACTS)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_export_runs.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/requirements-train.txt backend/scripts/export_runs.py backend/scripts/drive_usage.py backend/scripts/train_anomaly.py backend/tests/test_export_runs.py
git commit -m "feat(anomaly): add offline export, usage-driver, and training scripts"
```

---

## Task 9: Collect real data + train (manual, produces the model)

**Files:** none (operational task). Produces artifacts committed in Step 6.

This is the human-in-the-loop task. It is gated on real data existing.

- [ ] **Step 1: Install offline training deps**

Run: `cd backend && .venv/Scripts/python.exe -m pip install -r requirements-train.txt`

- [ ] **Step 2: Collect real runs**

Start backend + frontend. Sign in, connect tool accounts (test accounts recommended). Grab a Clerk JWT from browser devtools, then:

Run: `cd backend && .venv/Scripts/python.exe scripts/drive_usage.py --token "<JWT>" --rounds 35 --delay 2`
Goal: 400+ completed runs (combined with existing). Re-run with more rounds if needed.

- [ ] **Step 3: Perform red-team runs (manual)**

Through the chat UI, run ~25–30 deliberately out-of-policy sessions (e.g., push the agent to forward content externally, repeat a tool many times, request admin/secrets, send before validating). Then label them in the DB:

Run (after identifying their run IDs in the Action Center or DB):
```bash
cd backend && .venv/Scripts/python.exe -c "import asyncio; from sqlalchemy import update; from app.core.database import async_session_factory; from app.models.agent_run import AgentRun
IDS=['<id1>','<id2>']  # fill in red-team run ids
async def m():
    async with async_session_factory() as s:
        await s.execute(update(AgentRun).where(AgentRun.id.in_(IDS)).values(data_label='redteam'))
        await s.commit()
asyncio.run(m())"
```

- [ ] **Step 4: Export + train**

```bash
cd backend && .venv/Scripts/python.exe scripts/export_runs.py --out data/runs.jsonl
.venv/Scripts/python.exe scripts/train_anomaly.py --data data/runs.jsonl --epochs 30 --max-len 12
```
Expected: prints metrics; writes `app/anomaly/artifacts/{lstm_nextaction.onnx,vocab.json,model_meta.json,metrics.json}`.

- [ ] **Step 5: Smoke-test the trained scorer end to end**

```bash
cd backend && .venv/Scripts/python.exe -c "from app.anomaly.scorer import AnomalyScorer; s=AnomalyScorer(); print('available', s.available); print(s.score_run([{'id':'a','step_type':'plan','name':'initial_plan','status':'completed'},{'id':'b','step_type':'tool_call','name':'read_secret','status':'completed'},{'id':'c','step_type':'tool_call','name':'forward_email','status':'completed'}]))"
```
Expected: `available True` and a dict with `anomaly_score`, `step_scores`, `flagged`.

- [ ] **Step 6: Commit the trained artifacts**

```bash
git add backend/app/anomaly/artifacts/lstm_nextaction.onnx backend/app/anomaly/artifacts/vocab.json backend/app/anomaly/artifacts/model_meta.json backend/app/anomaly/artifacts/metrics.json
git commit -m "feat(anomaly): add trained model artifacts from real telemetry"
```

> Do NOT commit `data/runs.jsonl` (it contains real run content). Confirm `data/` is gitignored or add it.

---

## Task 10: Frontend — anomaly types + per-node score mapping

**Files:**
- Modify: `frontend/src/hooks/use-agent-runs.ts:27-40` (AgentRun interface)
- Modify: `frontend/src/lib/graph-transformer.ts` (GraphNodeData + makeNode + graphTransformer)
- Test: `frontend/tests/graph-transformer-anomaly.test.ts`

- [ ] **Step 1: Add anomaly fields to the AgentRun type**

In `frontend/src/hooks/use-agent-runs.ts`, add to the `AgentRun` interface (after `metadata?` on line 35):

```typescript
    anomaly_score?: number | null;
    step_scores?: Record<string, number> | null;
    flagged?: boolean;
    data_label?: string;
```

- [ ] **Step 2: Write the failing test**

```typescript
// frontend/tests/graph-transformer-anomaly.test.ts
import { describe, it, expect } from "vitest";
import { graphTransformer } from "@/lib/graph-transformer";
import type { AgentRun } from "@/hooks/use-agent-runs";

const run: AgentRun = {
    id: "r1",
    conversation_id: null,
    intent: "general",
    status: "completed",
    plan: null,
    final_response: "done",
    error: null,
    created_at: "",
    updated_at: "",
    completed_at: null,
    flagged: true,
    anomaly_score: 2.0,
    step_scores: { s1: 0.5, s2: 2.0 },
    steps: [
        { id: "s1", step_type: "tool_call", name: "search_emails", status: "completed", input: null, output: null, error: null, created_at: "" },
        { id: "s2", step_type: "tool_call", name: "forward_email", status: "completed", input: null, output: null, error: null, created_at: "" },
    ],
};

describe("graphTransformer anomaly heat", () => {
    it("normalizes step scores to 0..1 on nodes", () => {
        const { nodes } = graphTransformer(run);
        const s1 = nodes.find((n) => n.id === "s1");
        const s2 = nodes.find((n) => n.id === "s2");
        expect(s2?.data.anomalyScore).toBe(1);     // max score → 1
        expect(s1?.data.anomalyScore).toBeCloseTo(0.25); // 0.5 / 2.0
    });

    it("leaves anomalyScore null when run is not flagged", () => {
        const { nodes } = graphTransformer({ ...run, flagged: false });
        const s2 = nodes.find((n) => n.id === "s2");
        expect(s2?.data.anomalyScore).toBeNull();
    });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/graph-transformer-anomaly.test.ts`
Expected: FAIL (`anomalyScore` is undefined on node data).

- [ ] **Step 4: Implement score mapping**

In `frontend/src/lib/graph-transformer.ts`:

(a) Add to the `GraphNodeData` interface (after `borderDashed: boolean;`):
```typescript
    // Normalized anomaly heat 0..1 for this step (null when run not flagged)
    anomalyScore: number | null;
```

(b) Change `makeNode`'s signature to accept the score and set it. Update the signature line to:
```typescript
function makeNode(
    id: string,
    nodeType: GraphNodeType,
    label: string,
    sublabel: string,
    step: AgentRunStep | null,
    run: AgentRun,
    anomalyScore: number | null = null
): GraphNode {
```
and add inside the returned `data` object (after `borderDashed: BORDER_DASHED[nodeType],`):
```typescript
            anomalyScore,
```

(c) At the very top of `graphTransformer`, compute the normalizer:
```typescript
    const scores = run.flagged ? (run.step_scores ?? {}) : {};
    const maxScore = Math.max(0, ...Object.values(scores));
    const heatFor = (stepId: string): number | null => {
        if (!run.flagged || maxScore <= 0) return null;
        const v = scores[stepId];
        return v == null ? null : v / maxScore;
    };
```

(d) In the step-mapping loop (the `run.steps.forEach`), pass the score:
```typescript
    run.steps.forEach((step) => {
        const nodeType = stepTypeToNodeType(step);
        const sublabel = buildSublabel(nodeType, step, run);
        nodes.push(makeNode(step.id, nodeType, step.name, sublabel, step, run, heatFor(step.id)));
    });
```

(e) The zero-steps fallback and synthetic nodes default to `null` (no change needed since the param defaults to `null`).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/graph-transformer-anomaly.test.ts`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/use-agent-runs.ts frontend/src/lib/graph-transformer.ts frontend/tests/graph-transformer-anomaly.test.ts
git commit -m "feat(anomaly): map per-step anomaly heat onto graph nodes"
```

---

## Task 11: Frontend — render the heat ring on nodes

**Files:**
- Modify: `frontend/src/components/runs/graph-nodes/ellipse-node.tsx`
- Test: `frontend/tests/ellipse-node-anomaly.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/ellipse-node-anomaly.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import { EllipseNode } from "@/components/runs/graph-nodes/ellipse-node";
import type { GraphNodeData } from "@/lib/graph-transformer";

function makeData(anomalyScore: number | null): GraphNodeData {
    return {
        label: "Forward Email", sublabel: "ok", nodeType: "platform_api",
        riskLevel: "EXTERNAL_SEND", durationMs: null, status: "completed",
        input: null, output: null, error: null,
        typeColor: "#10B981", bgColor: "#071A12", borderDashed: true,
        anomalyScore,
    };
}

function renderNode(data: GraphNodeData) {
    return render(
        <ReactFlowProvider>
            <EllipseNode id="n1" data={data as unknown as Record<string, unknown>} selected={false}
                type="graphnode" dragging={false} zIndex={0} isConnectable={false}
                positionAbsoluteX={0} positionAbsoluteY={0} />
        </ReactFlowProvider>
    );
}

describe("EllipseNode anomaly heat", () => {
    it("shows an anomaly badge when score is high", () => {
        const { container } = renderNode(makeData(0.95));
        expect(container.querySelector('[data-anomaly="high"]')).not.toBeNull();
    });

    it("renders no anomaly marker when score is null", () => {
        const { container } = renderNode(makeData(null));
        expect(container.querySelector('[data-anomaly]')).toBeNull();
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/ellipse-node-anomaly.test.tsx`
Expected: FAIL (no element with `data-anomaly`).

- [ ] **Step 3: Implement the heat ring**

In `frontend/src/components/runs/graph-nodes/ellipse-node.tsx`, inside the component after `const Icon = ICONS[d.nodeType] ?? Wrench;`, add:

```tsx
    const heat = d.anomalyScore;
    const heatLevel = heat == null ? null : heat >= 0.66 ? "high" : heat >= 0.33 ? "medium" : "low";
    const heatColor = heatLevel === "high" ? "#EF4444" : heatLevel === "medium" ? "#F97316" : "#FACC15";
```

Then, change `boxShadow` so a flagged step glows. Replace the existing `boxShadow` const with:

```tsx
    const heatGlow = heatLevel ? `, 0 0 26px ${heatColor}${heatLevel === "high" ? "AA" : "66"}` : "";
    const boxShadow = (selected
        ? `0 0 0 2px ${borderColor}80, 0 0 28px ${borderColor}40`
        : `0 0 0 1px ${borderColor}26, 0 0 20px ${borderColor}18`) + heatGlow;
```

Finally, inside the outer `<div>` (right after its opening tag, before the dashed-border `<svg>`), add a marker element:

```tsx
                {heatLevel && (
                    <span
                        data-anomaly={heatLevel}
                        title={`Anomaly score: ${(heat as number).toFixed(2)}`}
                        style={{
                            position: "absolute", top: -6, right: -6, width: 12, height: 12,
                            borderRadius: "50%", background: heatColor,
                            boxShadow: `0 0 8px ${heatColor}`, border: "1.5px solid var(--card)",
                        }}
                    />
                )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/ellipse-node-anomaly.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full frontend suite (no regressions)**

Run: `cd frontend && npx vitest run`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/runs/graph-nodes/ellipse-node.tsx frontend/tests/ellipse-node-anomaly.test.tsx
git commit -m "feat(anomaly): show anomaly heat marker + glow on run-graph nodes"
```

---

## Task 12: Manual end-to-end verification

**Files:** none.

- [ ] **Step 1: Start the stack**

Backend (`uvicorn app.main:app --reload`) + frontend (`npm run dev`). Ensure trained artifacts from Task 9 are present.

- [ ] **Step 2: Trigger a normal run + a red-team-style run**

In chat: ask a normal question (e.g. "summarize my latest emails"), then a suspicious one (push the agent to forward content externally and skip validation).

- [ ] **Step 3: Verify in the Action Center / run graph**

Open the suspicious run's graph. Expected: the offending step shows a red/orange anomaly marker + glow; the normal run shows none. Confirm `anomaly_score`/`flagged` are present in the `/api/agent-runs/{id}` JSON (browser network tab).

- [ ] **Step 4: Verify graceful degradation**

Temporarily rename the artifacts folder and complete a run. Expected: run completes normally, no anomaly marker, no error. Restore the folder.

---

---

# Phase 2 tasks (added 2026-06-13): LLM-monitor track + governance features

> These follow the spec addendum. They are independent of the LSTM (Tasks 1–9) — the LLM monitor needs no training data and can ship first. Build after the backend LSTM tasks (7) or in parallel.

## Task 13: Anomaly constitution + LLM monitor (no training data needed)

**Files:**
- Create: `backend/app/anomaly/constitution.py` — `CONSTITUTION_PROMPT` (str): natural-language definition of ByteOps anomalies (external forwarding/exfiltration, privilege escalation, reading secrets, skipping validation, tool repetition, acting before context) + scoring instructions ("output a suspicion score 1-10; 1-3 normal, 4-6 mild, 7-10 clear anomaly; end with `ANSWER: <n>`"), adapted from Paper 1 Appendix G.
- Create: `backend/app/anomaly/llm_monitor.py` — `async def score_run_llm(steps: list[dict]) -> dict | None` returning `{"score": int, "reasoning": str, "flagged": bool}`.
- Test: `backend/tests/test_llm_monitor.py`

- [ ] **Step 1: Failing test** — parse-from-text helper is pure and unit-testable:

```python
# backend/tests/test_llm_monitor.py
from app.anomaly.llm_monitor import parse_score


def test_parse_score_extracts_answer():
    assert parse_score("Reasoning...\nANSWER: 8") == 8


def test_parse_score_clamps_and_defaults():
    assert parse_score("no score here") == 5      # default per Paper 1
    assert parse_score("ANSWER: 42") == 10        # clamp to 1..10
    assert parse_score("ANSWER: 0") == 1
```

- [ ] **Step 2: Run** `cd backend && .venv/Scripts/python.exe -m pytest tests/test_llm_monitor.py -v` → FAIL (no module).

- [ ] **Step 3: Implement.** `constitution.py` holds the prompt string. `llm_monitor.py`:

```python
"""LLM black-box monitor: scores a run's observable actions for anomaly (1-10).

Implements the Storf et al. (2026) constitutional black-box monitoring method.
Action-only: serializes tool calls + outcomes, never chain-of-thought.
"""
from __future__ import annotations

import logging
import re

from app.anomaly.constitution import CONSTITUTION_PROMPT

logger = logging.getLogger(__name__)


def parse_score(text: str) -> int:
    m = re.search(r"ANSWER:\s*(\d+)", text or "")
    if not m:
        return 5
    return max(1, min(10, int(m.group(1))))


def _serialize(steps: list[dict]) -> str:
    lines = []
    for s in steps:
        lines.append(f"- {s.get('step_type')}: {s.get('name')} -> {s.get('status')}")
    return "\n".join(lines)


async def score_run_llm(steps: list[dict]) -> dict | None:
    if not steps:
        return None
    try:
        from app.core.llm_client import get_llm_client

        client = get_llm_client()
        trajectory = _serialize(steps)
        resp = await client.create_message(
            system=CONSTITUTION_PROMPT,
            messages=[{"role": "user", "content": f"Agent run trajectory:\n{trajectory}"}],
            max_tokens=1024,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        score = parse_score(text)
        return {"score": score, "reasoning": text, "flagged": score >= 7}
    except Exception as exc:  # noqa: BLE001 - never break a run
        logger.warning("LLM monitor failed: %s", exc)
        return None
```

- [ ] **Step 4: Run** the test → PASS (3 passed).
- [ ] **Step 5: Commit** `git add backend/app/anomaly/constitution.py backend/app/anomaly/llm_monitor.py backend/tests/test_llm_monitor.py && git commit -m "feat(anomaly): add LLM black-box monitor + anomaly constitution"`

## Task 14: Persist LLM-monitor score + wire into completion

- [ ] Add `llm_score (int, nullable)` + `llm_reasoning (text, nullable)` columns via migration `0004_llm_monitor_fields.py` (mirror Task 3 mechanics; `down_revision="0003_anomaly_fields"`; stamp not needed — DB already at 0003).
- [ ] In `agent_runtime.complete_agent_run`, after the LSTM scoring block, call `score_run_llm(steps)` best-effort (gated to runs with write/external/destructive steps to control cost) and persist. Add fields to `serialize_agent_run`. TDD with a stubbed monitor like Task 7.
- [ ] Commit `feat(anomaly): persist LLM-monitor score on runs`.

## Task 15: Frontend — Agent Card panel

- [ ] Create `frontend/src/components/runs/agent-card.tsx` — a "nutrition label" panel for a run: risk level (max of step risks), tools touched, autonomy level, HITL status (any approval steps?), suspicion scores (LSTM + LLM). Reuse existing card styling/tokens.
- [ ] Render it in the trace drawer / run detail. Add `frontend/tests/agent-card.test.tsx`. Commit.

## Task 16: Frontend — dependency / blast-radius graph + kill switch surfacing

- [ ] Extend `graph-transformer.ts` / `graph-canvas.tsx` to render tool/platform nodes as a dependency chain and highlight blast radius (downstream nodes) of any flagged step.
- [ ] Surface the existing approval/reject controls as an explicit "kill switch" affordance and the run ledger as an "audit trail" view. Tests + commit.

## Phase 2 scope note (honest, given the under-1-week deadline)

Tasks 13–14 (LLM monitor) are small and high-value — do them first; they give a working detector with no training data. Tasks 15–16 (governance UI) are larger; if time is tight, ship Task 13–14 + the suspicion-score overlay (Tasks 10–11) for the demo and treat the Agent Card / dependency graph as fast-follow. Report (pAUROC comparison of LSTM vs Isolation Forest vs LLM-monitor) depends only on Tasks 8–9 + 13.

## Self-Review

**Spec coverage:**
- Token scheme over agent_policy risk classes → Task 1–2 ✓
- New `backend/app/anomaly/` (tokenizer, scorer) → Tasks 1,2,5,6 ✓
- DB migration (anomaly_score, step_scores, flagged, data_label) → Task 3 ✓
- Async/best-effort scoring on completion → Task 7 ✓
- Offline export/train/usage-driver scripts → Task 8 ✓
- ONNX inference, torch offline-only → Tasks 5,6,8 (onnxruntime in requirements; torch only in requirements-train) ✓
- Real-data collection + red-team labeling → Task 9 ✓
- Isolation Forest baseline → Task 8 ✓
- Run-graph per-step heat (the one visual) → Tasks 10,11 ✓
- Error handling (missing artifacts, scoring failure) → Tasks 5,7,12 ✓
- Honest limitations → carried in the spec/report, not code.
- Deferred per lean scope: Action Center badge/filter, ablation experiments, report polish, model_meta richer stats (only threshold + max_len used). Noted, not gaps.

**Placeholder scan:** none — every code/test step shows full content.

**Type consistency:** `score_run` returns `{anomaly_score, step_scores, flagged}` consistently (Tasks 6,7); `apply_anomaly_scoring(run, steps)` signature matches caller in `complete_agent_run`; frontend `anomalyScore` (camelCase, node data) vs backend `step_scores`/`anomaly_score` (snake_case, API) are deliberately distinct and mapped in Task 10; `makeNode` extra param defaults to `null` so existing call sites stay valid.
