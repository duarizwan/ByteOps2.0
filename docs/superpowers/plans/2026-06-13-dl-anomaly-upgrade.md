# ByteOps DL Anomaly Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade ByteOps anomaly detection into a strong DL study: a rich per-step feature representation, a BiLSTM+Attention model (core) and a small Transformer Encoder, supervised + self-supervised training, full metrics, ablations, attention-based explainability, and report/demo artifacts — without breaking existing functionality.

**Architecture:** Each agent-run step becomes a **feature vector** (categorical fields via embeddings + numeric/binary features), avoiding vocabulary explosion. Sequence models (BiLSTM+Attention, Transformer) classify a run as normal/anomalous and emit per-step attention for localization. Existing NextActionLSTM, Isolation Forest, and the LLM monitor stay as baselines. All training is offline (PyTorch), served via ONNX; experiments log to MLflow.

**Tech Stack:** Python 3.12, PyTorch (offline), scikit-learn, ONNX/onnxruntime, MLflow, matplotlib, numpy; pytest; existing FastAPI backend + Next.js frontend.

**Run tests with:** `cd backend && .venv/Scripts/python.exe -m pytest <path> -v`. Heavy/torch tests are marked and run locally only.

**Phasing:** C (data/features foundation) → A (DL modeling + eval) → B (explainability + demo/report). Each phase ships something gradeable.

---

## File structure

**Phase C (foundation, pure-Python, no torch):**
- `backend/app/anomaly/features.py` — Tokenizer v2: per-step feature extraction + vocabs + run encoding. Pure functions, no torch (importable in-app and offline).
- `backend/scripts/export_runs.py` — MODIFY: also emit full `steps` (rich dicts) + `anomaly_type`, not only `tokens`.
- `backend/scripts/generate_dataset.py` — CREATE: generate diverse normal + anomalous runs (rich step dicts) with `anomaly_type` + injected-step index; merge real runs.

**Phase A (modeling, torch, offline):**
- `backend/app/anomaly/metrics.py` — CREATE: pure metric functions (pAUROC, classification metrics, ROC/PR points, confusion). No torch.
- `backend/app/anomaly/models.py` — CREATE: `StepFeatureEmbedder`, `BiLSTMAttention`, `TransformerEncoderClassifier` (torch).
- `backend/scripts/train_classifier.py` — CREATE: supervised BCE training harness (`--model bilstm_attn|transformer|lstm_clf`), dropout, early stopping, MLflow, metrics, ONNX export, held-out-type split.
- `backend/scripts/evaluate_detectors.py` — MODIFY: add the supervised models to the comparison + full metrics.
- `backend/scripts/run_experiments.py` — MODIFY: add ablations (no-risk-features, no-attention, bilstm-vs-transformer, classical-vs-learned).
- `backend/requirements-train.txt` — MODIFY: add `matplotlib`, `umap-learn` (umap optional).

**Phase B (explainability + demo/report):**
- `backend/app/anomaly/attention_scorer.py` — CREATE: load BiLSTM+Attention ONNX, return per-step attention as `step_scores` + run score.
- `backend/scripts/make_report.py` — CREATE: confusion_matrix.png, roc_curve.png, attention_example.png + comparison.md.
- Frontend: existing `graph-transformer.ts` + `ellipse-node.tsx` already render `step_scores` heat (done in prior work) — verify + wire attention scores; add an attention-example view (optional).

**Unchanged baselines (do NOT remove):** `app/anomaly/tokenizer.py` (v1), `scorer.py`, `llm_monitor.py`, `constitution.py`; `scripts/train_anomaly.py` (self-supervised LSTM), `make_redteam.py`, `label_redteam.py`.

---

# PHASE C — Foundation: rich features + data

## Task 1: Feature spec + single-step categorical inference

**Files:**
- Create: `backend/app/anomaly/features.py`
- Test: `backend/tests/test_features.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_features.py
from app.anomaly.features import infer_tool, action_category


def test_infer_tool_from_action_name():
    assert infer_tool("send_email") == "gmail"
    assert infer_tool("create_event") == "calendar"
    assert infer_tool("merge_pr") == "github"
    assert infer_tool("send_message") == "slack"
    assert infer_tool("transition_issue") == "jira"
    assert infer_tool("upload_file") == "dropbox"
    assert infer_tool("initial_plan") == "none"


def test_action_category():
    assert action_category("forward_email") == "external"
    assert action_category("delete_event") == "destructive"
    assert action_category("create_issue") == "write"
    assert action_category("search_emails") == "read"
    assert action_category("initial_plan") == "none"
```

- [ ] **Step 2: Run — expect FAIL** (`ModuleNotFoundError`).
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_features.py -v`

- [ ] **Step 3: Implement**

```python
# backend/app/anomaly/features.py
"""Tokenizer v2 — rich per-step FEATURE VECTORS for sequence models.

Pure functions (no torch) so importable both in-app and offline. Replaces the
flat composite-string token (v1, kept in tokenizer.py) with multi-field features:
embedded categoricals (step_type, tool, action_category) + numeric/binary block.
"""

from __future__ import annotations

from app.services.agent_policy import classify_tool_call

PAD = "<PAD>"
UNK = "<UNK>"

# categorical field -> the tool a tool-call action belongs to
_TOOL_KEYWORDS = {
    "gmail": ("email", "_email", "inbox", "draft", "reply", "forward"),
    "calendar": ("event", "calendar", "meeting", "schedule"),
    "github": ("pr", "pull_request", "issue", "commit", "repo", "merge", "branch"),
    "slack": ("message", "slack", "channel", "dm"),
    "jira": ("ticket", "jira", "sprint", "transition", "epic"),
    "dropbox": ("file", "folder", "dropbox", "upload", "path"),
}

_DESTRUCTIVE = {"delete", "trash", "remove", "close", "drop"}
_SEND = {"send", "forward", "reply", "post", "message"}
_EXTERNAL = {"forward", "external", "send_email", "send_dm"}
_WRITE = {"create", "update", "add", "assign", "transition", "apply", "upload", "move", "copy", "write"}
_SENSITIVE = ("secret", "credential", "password", "api_key", "token", "ssn", "phi")


def infer_tool(action: str) -> str:
    a = (action or "").lower()
    for tool, kws in _TOOL_KEYWORDS.items():
        if any(kw in a for kw in kws):
            return tool
    return "none"


def action_category(action: str) -> str:
    a = (action or "").lower()
    if not a or a in ("initial_plan", "intent_routing"):
        return "none"
    if any(k in a for k in _DESTRUCTIVE):
        return "destructive"
    if "forward" in a or "external" in a:
        return "external"
    if any(k in a for k in _SEND):
        return "send"
    if any(k in a for k in _WRITE):
        return "write"
    return "read"
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit**
```bash
git add backend/app/anomaly/features.py backend/tests/test_features.py
git commit -m "feat(anomaly): tokenizer v2 — tool + action-category inference"
```

---

## Task 2: Extract the full per-step feature dict

**Files:**
- Modify: `backend/app/anomaly/features.py`
- Test: `backend/tests/test_features.py`

- [ ] **Step 1: Append failing test**

```python
from app.anomaly.features import extract_step_features, NUMERIC_FEATURES


def _run():
    return [
        {"step_type": "plan", "name": "initial_plan", "status": "completed"},
        {"step_type": "tool_call", "name": "search_emails", "status": "completed"},
        {"step_type": "tool_call", "name": "forward_email", "status": "completed"},
        {"step_type": "final", "name": "final", "status": "completed"},
    ]


def test_extract_step_features_categoricals_and_numerics():
    steps = _run()
    f = extract_step_features(steps, idx=2)  # the forward_email step
    assert f["step_type"] == "tool_call"
    assert f["tool_name"] == "gmail"
    assert f["action_category"] == "external"
    assert f["is_external_domain"] == 1
    assert 0.0 <= f["position_frac"] <= 1.0
    # every declared numeric feature is present and numeric
    for name in NUMERIC_FEATURES:
        assert isinstance(f[name], (int, float))


def test_cross_tool_flag():
    steps = _run()  # gmail-only here -> not cross-tool
    assert extract_step_features(steps, idx=1)["is_cross_tool_action"] == 0
```

- [ ] **Step 2: Run — expect FAIL** (`ImportError`).

- [ ] **Step 3: Implement (append to features.py)**

```python
# Ordered list of numeric/binary features (model feeds these as a block)
NUMERIC_FEATURES = [
    "risk_level",            # ordinal 0..4
    "status_ok",             # 1 if completed/approved
    "approval_required",     # 1 if write/send/destructive
    "approval_rejected",     # 1 if this step is a rejected approval
    "is_external_domain",    # 1 if external/forward action
    "is_sensitive_data_action",
    "is_cross_tool_action",  # run touches >1 distinct tool
    "position_frac",         # idx / (run_length-1)
    "run_length_norm",       # min(run_length,20)/20
]

_RISK_ORDINAL = {"none": 0, "read": 1, "write": 2, "external_send": 3, "destructive": 4}


def _risk_level(step: dict) -> int:
    if step.get("step_type") == "tool_call":
        risk = classify_tool_call("", str(step.get("name", ""))).risk.value
    else:
        risk = "none"
    return _RISK_ORDINAL.get(risk, 0)


def extract_step_features(steps: list[dict], idx: int) -> dict:
    """Return categorical + numeric features for step `idx` within its run."""
    step = steps[idx]
    name = str(step.get("name", ""))
    step_type = str(step.get("step_type", "")).strip() or "unknown"
    status = str(step.get("status", "")).strip().lower()
    cat = action_category(name) if step_type == "tool_call" else "none"
    tools = {infer_tool(str(s.get("name", ""))) for s in steps if s.get("step_type") == "tool_call"}
    tools.discard("none")
    n = max(1, len(steps))
    return {
        # categoricals (embedded)
        "step_type": step_type,
        "tool_name": infer_tool(name) if step_type == "tool_call" else "none",
        "action_category": cat,
        # numerics (NUMERIC_FEATURES order)
        "risk_level": _risk_level(step),
        "status_ok": 1 if status in ("completed", "approved") else 0,
        "approval_required": 1 if cat in ("write", "send", "external", "destructive") else 0,
        "approval_rejected": 1 if (step_type == "approval" and status == "rejected") or name.startswith("reject:") else 0,
        "is_external_domain": 1 if cat == "external" else 0,
        "is_sensitive_data_action": 1 if any(k in name.lower() for k in _SENSITIVE) else 0,
        "is_cross_tool_action": 1 if len(tools) > 1 else 0,
        "position_frac": idx / (n - 1) if n > 1 else 0.0,
        "run_length_norm": min(n, 20) / 20.0,
    }
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(anomaly): per-step feature extraction (tokenizer v2)`

---

## Task 3: Categorical vocabs + run encoding

**Files:**
- Modify: `backend/app/anomaly/features.py`
- Test: `backend/tests/test_features.py`

- [ ] **Step 1: Append failing test**

```python
from app.anomaly.features import build_feature_vocabs, encode_run, CATEGORICAL_FIELDS


def test_build_vocabs_and_encode_shapes():
    runs = [_run(), _run()]
    vocabs = build_feature_vocabs(runs)
    for field in CATEGORICAL_FIELDS:
        assert vocabs[field][PAD] == 0 and vocabs[field][UNK] == 1
    enc = encode_run(_run(), vocabs, max_len=6)
    # categorical id sequences padded to max_len
    for field in CATEGORICAL_FIELDS:
        assert len(enc["cat"][field]) == 6
    # numeric matrix: max_len x len(NUMERIC_FEATURES)
    assert len(enc["num"]) == 6
    assert len(enc["num"][0]) == len(NUMERIC_FEATURES)
    # mask marks 4 real steps then padding
    assert enc["mask"] == [1, 1, 1, 1, 0, 0]
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement (append)**

```python
CATEGORICAL_FIELDS = ["step_type", "tool_name", "action_category"]


def build_feature_vocabs(runs: list[list[dict]]) -> dict[str, dict[str, int]]:
    """One id-map per categorical field, built from training runs. PAD=0, UNK=1."""
    vocabs = {f: {PAD: 0, UNK: 1} for f in CATEGORICAL_FIELDS}
    for steps in runs:
        for idx in range(len(steps)):
            feats = extract_step_features(steps, idx)
            for f in CATEGORICAL_FIELDS:
                v = vocabs[f]
                if feats[f] not in v:
                    v[feats[f]] = len(v)
    return vocabs


def encode_run(steps: list[dict], vocabs: dict, max_len: int) -> dict:
    """Encode a run to fixed-length arrays: per-field categorical ids, a numeric
    matrix, and a padding mask."""
    cat = {f: [] for f in CATEGORICAL_FIELDS}
    num = []
    for idx in range(min(len(steps), max_len)):
        feats = extract_step_features(steps, idx)
        for f in CATEGORICAL_FIELDS:
            cat[f].append(vocabs[f].get(feats[f], vocabs[f][UNK]))
        num.append([float(feats[name]) for name in NUMERIC_FEATURES])
    real = len(num)
    pad_rows = max_len - real
    for f in CATEGORICAL_FIELDS:
        cat[f] += [0] * pad_rows
    num += [[0.0] * len(NUMERIC_FEATURES) for _ in range(pad_rows)]
    mask = [1] * real + [0] * pad_rows
    return {"cat": cat, "num": num, "mask": mask, "length": real}
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(anomaly): feature vocabs + fixed-length run encoding`

---

## Task 4: Export rich step dicts (don't break v1)

**Files:**
- Modify: `backend/scripts/export_runs.py`
- Test: `backend/tests/test_export_runs.py`

- [ ] **Step 1: Append failing test**

```python
from scripts.export_runs import run_record_to_sequence


def test_export_includes_rich_steps_and_type():
    record = {
        "id": "r1", "data_label": "redteam", "intent": "general",
        "metadata": {"anomaly_type": "exfiltration"},
        "steps": [
            {"id": "a", "step_type": "plan", "name": "initial_plan", "status": "completed"},
            {"id": "b", "step_type": "tool_call", "name": "forward_email", "status": "completed"},
        ],
    }
    seq = run_record_to_sequence(record)
    assert seq["label"] == "redteam"
    assert seq["anomaly_type"] == "exfiltration"
    # rich steps preserved for feature extraction
    assert seq["steps"][1]["name"] == "forward_email"
    # v1 tokens still present (backward compatible)
    assert seq["tokens"][1] == "tool_call|external_send|completed"
```

- [ ] **Step 2: Run — expect FAIL** (KeyError on `anomaly_type`/`steps`).

- [ ] **Step 3: Modify `run_record_to_sequence`** in `backend/scripts/export_runs.py`:

```python
def run_record_to_sequence(record: dict) -> dict:
    steps = record.get("steps", [])
    meta = record.get("metadata") or {}
    return {
        "run_id": record["id"],
        "label": record.get("data_label", "unlabeled"),
        "anomaly_type": meta.get("anomaly_type", "none" if record.get("data_label") != "redteam" else "unknown"),
        "intent": record.get("intent", "general"),
        "tokens": run_to_tokens(steps),  # v1, backward compatible
        "steps": [
            {"step_type": s.get("step_type"), "name": s.get("name"), "status": s.get("status")}
            for s in steps
        ],
    }
```

- [ ] **Step 4: Run — expect PASS.** Then run the existing test too: `pytest tests/test_export_runs.py -v` (both pass).
- [ ] **Step 5: Commit** `feat(anomaly): export rich steps + anomaly_type (v2 dataset)`

---

## Task 5: Diverse dataset generator (normal + anomalous, rich)

**Files:**
- Create: `backend/scripts/generate_dataset.py`
- Test: `backend/tests/test_generate_dataset.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_generate_dataset.py
from scripts.generate_dataset import generate, ANOMALY_TYPES


def test_generate_balanced_with_types_and_injected_index():
    runs = generate(n_normal=20, n_anom_per_type=3, seed=42)
    labels = [r["label"] for r in runs]
    assert labels.count("normal") == 20
    anom = [r for r in runs if r["label"] == "redteam"]
    assert len(anom) == 3 * len(ANOMALY_TYPES)
    # every anomalous run records which step is the injected anomaly + its type
    for r in anom:
        assert r["anomaly_type"] in ANOMALY_TYPES
        assert 0 <= r["anomalous_step_index"] < len(r["steps"])
        assert all("step_type" in s for s in r["steps"])


def test_generate_is_deterministic():
    assert generate(5, 2, seed=7) == generate(5, 2, seed=7)
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** (rule-based + randomized; rich step dicts; injected-step index recorded). This is a deterministic generator — no LLM dependency, so it runs anywhere and is reproducible. (An LLM-driven variant can be added later; rule-based diverse generation is sufficient and avoids API cost/refusals.)

```python
# backend/scripts/generate_dataset.py
"""Generate a diverse, labeled dataset of agent-run sequences (rich step dicts).

Normal runs: varied benign workflows across tools. Anomalous runs: one injected
unsafe action per run, across several attack types, at a randomized position
inside an otherwise-normal run (so detection isn't a trivial single-token cue).
Records anomaly_type + anomalous_step_index for held-out-type splits and
localization evaluation. Deterministic given seed. Synthetic + clearly labeled.

Usage: python scripts/generate_dataset.py --normal 200 --per-type 15 --out data/gen.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_READS = {
    "gmail": ["search_emails", "read_email", "list_threads"],
    "calendar": ["list_events", "get_event"],
    "github": ["list_prs", "list_issues", "get_commit"],
    "slack": ["list_messages", "read_channel"],
    "jira": ["list_tickets", "get_ticket"],
    "dropbox": ["list_files"],
}
_TOOLS = list(_READS)

# attack type -> the injected unsafe action name
ANOMALY_TYPES = {
    "exfiltration": "forward_email",
    "external_send": "send_email",
    "destructive": "delete_event",
    "privilege": "read_secret",
    "tool_abuse": "merge_pr",
}


def _step(step_type, name, status="completed"):
    return {"step_type": step_type, "name": name, "status": status}


def _normal_run(rng: random.Random) -> dict:
    tool = rng.choice(_TOOLS)
    steps = [_step("plan", "initial_plan"), _step("route", "intent_routing")]
    for _ in range(rng.randint(1, 4)):
        steps.append(_step("tool_call", rng.choice(_READS[tool])))
        if rng.random() < 0.3:  # sometimes touch a second tool
            t2 = rng.choice(_TOOLS)
            steps.append(_step("tool_call", rng.choice(_READS[t2])))
    steps.append(_step("final", "final"))
    return {"label": "normal", "anomaly_type": "none", "anomalous_step_index": -1, "steps": steps}


def _anomalous_run(rng: random.Random, atype: str) -> dict:
    base = _normal_run(rng)["steps"]
    bad = _step("tool_call", ANOMALY_TYPES[atype])
    insert_at = rng.randint(2, max(2, len(base) - 1))  # after plan/route, before final
    steps = base[:insert_at] + [bad] + base[insert_at:]
    return {"label": "redteam", "anomaly_type": atype, "anomalous_step_index": insert_at, "steps": steps}


def generate(n_normal: int, n_anom_per_type: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    runs = []
    for i in range(n_normal):
        r = _normal_run(rng); r["run_id"] = f"gen-normal-{i:04d}"; runs.append(r)
    i = 0
    for atype in ANOMALY_TYPES:
        for _ in range(n_anom_per_type):
            r = _anomalous_run(rng, atype); r["run_id"] = f"gen-{atype}-{i:04d}"; i += 1; runs.append(r)
    return runs


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--normal", type=int, default=200)
    p.add_argument("--per-type", type=int, default=15)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="data/gen.jsonl")
    a = p.parse_args()
    runs = generate(a.normal, a.per_type, a.seed)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in runs:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {len(runs)} runs ({a.normal} normal + {len(ANOMALY_TYPES)}x{a.per_type} anomalous) to {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(anomaly): diverse dataset generator with anomaly types + injected-step index`

---

# PHASE A — Deep-learning core

## Task 6: Metrics module (pure)

**Files:**
- Create: `backend/app/anomaly/metrics.py`
- Test: `backend/tests/test_metrics.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_metrics.py
import numpy as np
from app.anomaly.metrics import classification_metrics, partial_auroc, roc_points, confusion


def test_partial_auroc_perfect():
    assert partial_auroc(np.array([0,0,1,1]), np.array([.1,.2,.9,.8])) == 1.0


def test_classification_metrics_perfect():
    m = classification_metrics(np.array([0,0,1,1]), np.array([.1,.2,.9,.8]), threshold=0.5)
    assert m["precision"] == 1.0 and m["recall"] == 1.0 and m["f1"] == 1.0
    assert m["accuracy"] == 1.0


def test_confusion_counts():
    tp, fp, fn, tn = confusion(np.array([1,1,0,0]), np.array([1,0,0,0]))
    assert (tp, fp, fn, tn) == (1, 0, 1, 2)


def test_roc_points_monotone_fpr():
    fpr, tpr = roc_points(np.array([0,1,0,1]), np.array([.2,.8,.3,.9]))
    assert fpr[0] == 0.0 and fpr[-1] == 1.0
    assert all(b >= a for a, b in zip(fpr, fpr[1:]))
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
# backend/app/anomaly/metrics.py
"""Pure evaluation metrics for anomaly detectors (no torch). Higher score = more anomalous."""
from __future__ import annotations

import numpy as np


def confusion(labels, preds):
    labels, preds = np.asarray(labels), np.asarray(preds)
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    tn = int(((preds == 0) & (labels == 0)).sum())
    return tp, fp, fn, tn


def classification_metrics(labels, scores, threshold) -> dict:
    labels = np.asarray(labels)
    preds = (np.asarray(scores) >= threshold).astype(int)
    tp, fp, fn, tn = confusion(labels, preds)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (tp + tn) / max(1, len(labels))
    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def roc_points(labels, scores):
    labels = np.asarray(labels)
    order = np.argsort(-np.asarray(scores))
    labels = labels[order]
    P, N = labels.sum(), len(labels) - labels.sum()
    tpr = np.concatenate([[0.0], np.cumsum(labels) / (P or 1)])
    fpr = np.concatenate([[0.0], np.cumsum(1 - labels) / (N or 1)])
    return fpr.tolist(), tpr.tolist()


def pr_points(labels, scores):
    labels = np.asarray(labels)
    order = np.argsort(-np.asarray(scores))
    labels = labels[order]
    tp = np.cumsum(labels)
    fp = np.cumsum(1 - labels)
    P = labels.sum() or 1
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / P
    return recall.tolist(), precision.tolist()


def partial_auroc(labels, scores, max_fpr: float = 0.2) -> float:
    fpr, tpr = roc_points(labels, scores)
    fpr, tpr = np.array(fpr), np.array(tpr)
    if labels.sum() == 0 or labels.sum() == len(labels):
        return float("nan")
    area = 0.0
    for i in range(1, len(fpr)):
        if fpr[i - 1] >= max_fpr:
            break
        x0, x1 = fpr[i - 1], min(fpr[i], max_fpr)
        if x1 > x0:
            area += (x1 - x0) * (tpr[i] + tpr[i - 1]) / 2.0
    return float(area / max_fpr)


def auroc(labels, scores) -> float:
    fpr, tpr = roc_points(labels, scores)
    return float(np.trapz(tpr, fpr))
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(anomaly): pure metrics module (pAUROC, ROC/PR, confusion)`

---

## Task 7: Model definitions (BiLSTM+Attention, Transformer)

**Files:**
- Create: `backend/app/anomaly/models.py`
- Test: `backend/tests/test_models.py` (torch; local only)

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_models.py
import pytest

torch = pytest.importorskip("torch")
from app.anomaly.models import StepFeatureEmbedder, BiLSTMAttention, TransformerEncoderClassifier

VOCAB = {"step_type": 6, "tool_name": 8, "action_category": 7}
N_NUM = 9


def _batch(B=4, T=6):
    cat = {f: torch.randint(0, n, (B, T)) for f, n in VOCAB.items()}
    num = torch.randn(B, T, N_NUM)
    mask = torch.ones(B, T)
    return cat, num, mask


def test_bilstm_attention_shapes_and_attention_sums_to_one():
    m = BiLSTMAttention(VOCAB, N_NUM, hidden=32)
    cat, num, mask = _batch()
    logit, attn = m(cat, num, mask)
    assert logit.shape == (4,)
    assert attn.shape == (4, 6)
    assert torch.allclose(attn.sum(dim=1), torch.ones(4), atol=1e-4)


def test_transformer_classifier_shapes():
    m = TransformerEncoderClassifier(VOCAB, N_NUM, hidden=64, layers=2, heads=4)
    cat, num, mask = _batch()
    logit, _ = m(cat, num, mask)
    assert logit.shape == (4,)
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
# backend/app/anomaly/models.py
"""Sequence classifiers over rich per-step features (torch; offline training)."""
from __future__ import annotations

import torch
import torch.nn as nn

CAT_FIELDS = ["step_type", "tool_name", "action_category"]


class StepFeatureEmbedder(nn.Module):
    """Embed categorical fields + project numeric block -> per-step vector [B,T,D]."""
    def __init__(self, vocab_sizes: dict, n_numeric: int, emb: int = 16):
        super().__init__()
        self.embs = nn.ModuleDict({f: nn.Embedding(vocab_sizes[f], emb, padding_idx=0) for f in CAT_FIELDS})
        self.num_proj = nn.Linear(n_numeric, emb)
        self.out_dim = emb * (len(CAT_FIELDS) + 1)

    def forward(self, cat: dict, num: torch.Tensor) -> torch.Tensor:
        parts = [self.embs[f](cat[f]) for f in CAT_FIELDS]
        parts.append(torch.relu(self.num_proj(num)))
        return torch.cat(parts, dim=-1)


class BiLSTMAttention(nn.Module):
    def __init__(self, vocab_sizes, n_numeric, emb=16, hidden=48, dropout=0.3):
        super().__init__()
        self.embed = StepFeatureEmbedder(vocab_sizes, n_numeric, emb)
        self.lstm = nn.LSTM(self.embed.out_dim, hidden, batch_first=True, bidirectional=True)
        self.attn = nn.Linear(hidden * 2, 1)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden * 2, 1)

    def forward(self, cat, num, mask):
        x = self.embed(cat, num)
        out, _ = self.lstm(x)                       # [B,T,2H]
        scores = self.attn(out).squeeze(-1)         # [B,T]
        scores = scores.masked_fill(mask == 0, -1e9)
        attn = torch.softmax(scores, dim=1)         # [B,T]
        context = (out * attn.unsqueeze(-1)).sum(dim=1)  # [B,2H]
        logit = self.head(self.drop(context)).squeeze(-1)
        return logit, attn


class TransformerEncoderClassifier(nn.Module):
    def __init__(self, vocab_sizes, n_numeric, emb=16, hidden=64, layers=2, heads=4, dropout=0.3, max_len=20):
        super().__init__()
        self.embed = StepFeatureEmbedder(vocab_sizes, n_numeric, emb)
        self.proj = nn.Linear(self.embed.out_dim, hidden)
        self.pos = nn.Parameter(torch.randn(1, max_len, hidden) * 0.02)
        layer = nn.TransformerEncoderLayer(hidden, heads, hidden * 2, dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, layers)
        self.head = nn.Linear(hidden, 1)

    def forward(self, cat, num, mask):
        x = self.proj(self.embed(cat, num))
        x = x + self.pos[:, : x.shape[1], :]
        pad_mask = mask == 0
        h = self.encoder(x, src_key_padding_mask=pad_mask)  # [B,T,H]
        m = mask.unsqueeze(-1)
        pooled = (h * m).sum(dim=1) / m.sum(dim=1).clamp(min=1)  # masked mean
        return self.head(pooled).squeeze(-1), None
```

- [ ] **Step 4: Run — expect PASS** (`cd backend && .venv/Scripts/python.exe -m pytest tests/test_models.py -v`).
- [ ] **Step 5: Commit** `feat(anomaly): BiLSTM+Attention and Transformer encoder models`

---

## Task 8: Supervised training harness + ONNX export + MLflow

**Files:**
- Create: `backend/scripts/train_classifier.py`
- Modify: `backend/requirements-train.txt` (add `matplotlib`)
- Test: smoke run on generated data

- [ ] **Step 1: Add `matplotlib` to `requirements-train.txt`.**

- [ ] **Step 2: Implement `train_classifier.py`** — loads rich JSONL, builds feature vocabs, encodes runs, splits (random OR held-out anomaly type via `--holdout-type`), trains chosen model with BCE + dropout + early stopping, logs metrics to MLflow, saves `artifacts/clf_<model>.onnx` + `clf_<model>_meta.json` (vocabs, max_len, threshold, NUMERIC_FEATURES, tokenizer_version="v2").

```python
# backend/scripts/train_classifier.py
"""Train a supervised anomaly classifier (BiLSTM+Attention / Transformer / LSTM-clf)
on rich feature sequences. Offline. Logs to MLflow; exports ONNX + meta.

Usage:
  python scripts/train_classifier.py --data data/gen.jsonl --model bilstm_attn --epochs 40
  python scripts/train_classifier.py --data data/gen.jsonl --model transformer --holdout-type privilege
"""
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.anomaly.features import build_feature_vocabs, encode_run, CATEGORICAL_FIELDS, NUMERIC_FEATURES  # noqa: E402
from app.anomaly import metrics as M  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parent.parent / "app" / "anomaly" / "artifacts"


def _load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    import torch, torch.nn as nn, mlflow
    from app.anomaly.models import BiLSTMAttention, TransformerEncoderClassifier

    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--model", choices=["bilstm_attn", "transformer"], default="bilstm_attn")
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--max-len", type=int, default=20)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--holdout-type", default="", help="anomaly_type held out of training (tests generalization)")
    a = p.parse_args()
    torch.manual_seed(a.seed); np.random.seed(a.seed)

    runs = _load(a.data)
    # split: held-out anomaly type goes to TEST only; rest split 70/15/15
    rng = np.random.default_rng(a.seed)
    def is_holdout(r): return a.holdout_type and r.get("anomaly_type") == a.holdout_type
    pool = [r for r in runs if not is_holdout(r)]
    held = [r for r in runs if is_holdout(r)]
    idx = rng.permutation(len(pool))
    n = len(pool); tr_end = int(.7*n); va_end = int(.85*n)
    train = [pool[i] for i in idx[:tr_end]]
    val   = [pool[i] for i in idx[tr_end:va_end]]
    test  = [pool[i] for i in idx[va_end:]] + held

    vocabs = build_feature_vocabs([r["steps"] for r in train])
    vocab_sizes = {f: len(vocabs[f]) for f in CATEGORICAL_FIELDS}

    def batch(items):
        enc = [encode_run(r["steps"], vocabs, a.max_len) for r in items]
        cat = {f: torch.tensor([e["cat"][f] for e in enc]) for f in CATEGORICAL_FIELDS}
        num = torch.tensor([e["num"] for e in enc], dtype=torch.float32)
        mask = torch.tensor([e["mask"] for e in enc], dtype=torch.float32)
        y = torch.tensor([1.0 if r["label"] == "redteam" else 0.0 for r in items])
        return cat, num, mask, y

    Model = BiLSTMAttention if a.model == "bilstm_attn" else TransformerEncoderClassifier
    model = Model(vocab_sizes, len(NUMERIC_FEATURES))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    cat_tr, num_tr, mask_tr, y_tr = batch(train)
    cat_va, num_va, mask_va, y_va = batch(val)

    mlflow.set_tracking_uri("sqlite:///mlflow.db"); mlflow.set_experiment("byteops-anomaly-clf")
    best_val, best_state, patience, bad = 1e9, None, 6, 0
    with mlflow.start_run():
        mlflow.log_params({"model": a.model, "epochs": a.epochs, "max_len": a.max_len,
                           "holdout_type": a.holdout_type or "none", "n_train": len(train),
                           "tokenizer": "v2"})
        for ep in range(a.epochs):
            model.train(); opt.zero_grad()
            logit, _ = model(cat_tr, num_tr, mask_tr)
            loss = loss_fn(logit, y_tr); loss.backward(); opt.step()
            model.eval()
            with torch.no_grad():
                vlogit, _ = model(cat_va, num_va, mask_va)
                vloss = loss_fn(vlogit, y_va).item()
            if vloss < best_val: best_val, best_state, bad = vloss, {k: v.clone() for k, v in model.state_dict().items()}, 0
            else:
                bad += 1
                if bad >= patience: break
        if best_state: model.load_state_dict(best_state)

        # evaluate on test
        model.eval()
        cat_te, num_te, mask_te, y_te = batch(test)
        with torch.no_grad():
            tlogit, _ = model(cat_te, num_te, mask_te)
            scores = torch.sigmoid(tlogit).numpy()
        labels = y_te.numpy()
        thr = 0.5
        cm = M.classification_metrics(labels, scores, thr)
        result = {**cm, "pauroc": M.partial_auroc(labels, scores), "auroc": M.auroc(labels, scores)}
        mlflow.log_metrics({k: float(v) for k, v in result.items()})

        # export ONNX (dynamo=False for Windows) + meta
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        dummy_cat = tuple(cat_te[f][:1] for f in CATEGORICAL_FIELDS)
        # wrap so ONNX takes positional tensors
        class Wrap(nn.Module):
            def __init__(s, mdl): super().__init__(); s.m = mdl
            def forward(s, st, tn, ac, num, mask):
                return s.m({"step_type": st, "tool_name": tn, "action_category": ac}, num, mask)[0]
        onnx_path = ARTIFACTS / f"clf_{a.model}.onnx"
        torch.onnx.export(Wrap(model),
                          (*dummy_cat, num_te[:1], mask_te[:1]),
                          str(onnx_path),
                          input_names=["step_type", "tool_name", "action_category", "num", "mask"],
                          output_names=["logit"], opset_version=13, dynamo=False)
        (ARTIFACTS / f"clf_{a.model}_meta.json").write_text(json.dumps({
            "model": a.model, "tokenizer": "v2", "max_len": a.max_len, "threshold": thr,
            "vocabs": vocabs, "numeric_features": NUMERIC_FEATURES, "metrics": result,
        }, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        print("Saved", onnx_path)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-run on generated data** (verifies it trains, evaluates, exports):
```
cd backend && .venv/Scripts/python.exe scripts/generate_dataset.py --normal 80 --per-type 8 --out data/gen.jsonl
.venv/Scripts/python.exe scripts/train_classifier.py --data data/gen.jsonl --model bilstm_attn --epochs 30
```
Expected: prints metrics (precision/recall/f1/pauroc/auroc), saves `artifacts/clf_bilstm_attn.onnx` + meta. The model should separate generated normal vs anomalous well (pAUROC clearly above 0.5) since the signal is learnable.

- [ ] **Step 4: Commit** `feat(anomaly): supervised classifier training (BiLSTM+Attn/Transformer) + ONNX + MLflow`

---

## Task 9: Add supervised models + full metrics to the comparison

**Files:**
- Modify: `backend/scripts/evaluate_detectors.py`

- [ ] **Step 1:** Add a `bilstm_attn` (and `transformer`) detector path to the comparison: train each on the train split, score the eval set with `sigmoid(logit)`, and report the full metric set (accuracy/precision/recall/F1/AUROC/pAUROC) using `app.anomaly.metrics`. Keep LSTM, Isolation Forest, LLM monitor columns. Use the rich `steps` field (fall back to v1 tokens for the LSTM/IsoForest baselines).
- [ ] **Step 2:** Run `python scripts/evaluate_detectors.py --data data/gen.jsonl --no-llm` → table now includes BiLSTM+Attention and Transformer rows with full metrics; writes `outputs/comparison.md`.
- [ ] **Step 3: Commit** `feat(anomaly): include supervised models + full metrics in comparison`

---

## Task 10: Ablation experiments

**Files:**
- Modify: `backend/scripts/run_experiments.py`

- [ ] **Step 1:** Add ablations, each over multiple seeds with 95% CIs, reported in `outputs/experiments.md`:
  - **No sequence order** (shuffle steps before encoding) vs ordered.
  - **No risk features** (zero out the numeric block) vs full features.
  - **No attention** (BiLSTM mean-pool) vs BiLSTM+Attention.
  - **LSTM vs BiLSTM+Attention vs Transformer** (pAUROC head-to-head).
  - **Classical features (Isolation Forest) vs learned representation.**
- [ ] **Step 2:** Run `python scripts/run_experiments.py --data data/gen.jsonl --seeds 5` → ablation tables populate.
- [ ] **Step 3: Commit** `feat(anomaly): ablation suite (order/risk-features/attention/arch/classical)`

---

# PHASE B — Explainability + demo/report

## Task 11: Attention-based per-step scorer (in-app, ONNX)

**Files:**
- Create: `backend/app/anomaly/attention_scorer.py`
- Test: `backend/tests/test_attention_scorer.py`

- [ ] **Step 1: Write failing test** — graceful when artifacts absent; returns per-step scores when present (use a tiny fixture or skip if no artifact).

```python
# backend/tests/test_attention_scorer.py
from app.anomaly.attention_scorer import AttentionScorer


def test_unavailable_returns_none(tmp_path):
    s = AttentionScorer(artifacts_dir=tmp_path)
    assert s.available is False
    assert s.score_run([{"step_type": "plan", "name": "initial_plan", "status": "completed"}]) is None
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** `AttentionScorer` mirroring `scorer.py`'s graceful pattern: load `clf_bilstm_attn.onnx` + meta; in `score_run(steps)` build the feature arrays via `app.anomaly.features.encode_run`, run ONNX to get the logit, and (since attention is internal) export a SECOND ONNX output for attention OR recompute per-step contribution. Simplest: export the attention head too — modify the Task-8 `Wrap` to return `(logit, attn)` and `output_names=["logit","attn"]`; here read both, return `{"anomaly_score": sigmoid(logit)*10, "step_scores": {step_id: attn_i}, "flagged": prob>=0.5}`. (Update Task 8's export to include `attn` as a second output before doing this task.)

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(anomaly): attention-based per-step scorer (ONNX)`

---

## Task 12: Report artifacts (plots + tables)

**Files:**
- Create: `backend/scripts/make_report.py`

- [ ] **Step 1: Implement** a script that, given `data/gen.jsonl`, trains BiLSTM+Attention, and writes:
  - `outputs/confusion_matrix.png` (matplotlib heatmap from `metrics.confusion`),
  - `outputs/roc_curve.png` (from `metrics.roc_points`; also overlay Isolation Forest),
  - `outputs/attention_example.png` (a bar/heat strip of attention weights for one flagged run, x-axis = step names),
  - refresh `outputs/comparison.md`.
- [ ] **Step 2: Run** `python scripts/make_report.py --data data/gen.jsonl` → all four files written.
- [ ] **Step 3: Commit** `feat(anomaly): report artifacts (confusion/ROC/attention plots)`

---

## Task 13: Wire attention scores into the run graph (frontend)

**Files:**
- Modify: `backend/app/services/agent_runtime.py` (prefer attention scorer when available)
- Verify: `frontend/src/lib/graph-transformer.ts` + `ellipse-node.tsx` already render `step_scores` heat (built earlier)

- [ ] **Step 1:** In `agent_runtime.apply_anomaly_scoring`, if `AttentionScorer` is available, use its `step_scores` (attention) for the heat; else fall back to the existing LSTM NLL `scorer`. (Both produce `step_scores` keyed by step id — the frontend already maps these to per-node heat.)
- [ ] **Step 2:** Manual check: a flagged run shows the heat marker on the high-attention step in `/runs`.
- [ ] **Step 3: Commit** `feat(anomaly): drive run-graph heat from attention when available`

---

## Task 14: Live demo trigger (sandboxed rogue scenario)

**Files:**
- Create: `backend/app/api/demo.py` (demo-only endpoint, gated to authenticated user)
- Modify: `backend/app/main.py` (include router)

- [ ] **Step 1:** Implement `POST /api/demo/rogue-run` that records a real `agent_run` from a chosen generated anomalous scenario (rich steps), routes risky steps to a no-op (no real tool calls), scores it (attention scorer), and returns the run id. The frontend opens it in `/runs` to show the flagged step + reason.
- [ ] **Step 2:** Manual check: trigger demo → run appears flagged with heat on the injected step.
- [ ] **Step 3: Commit** `feat(anomaly): sandboxed rogue-run demo endpoint`

---

## Task 15: Update docs (quickstart + project guide)

**Files:**
- Modify: `docs/DL_QUICKSTART.md`, `docs/PROJECT_GUIDE.md`

- [ ] **Step 1:** Document the v2 workflow: `generate_dataset.py` → `train_classifier.py --model bilstm_attn` → `evaluate_detectors.py` → `run_experiments.py` → `make_report.py` → `mlflow ui`. Note v1 self-supervised LSTM remains a baseline.
- [ ] **Step 2: Commit** `docs: document the v2 supervised DL workflow`

---

## Self-Review

**Spec coverage (vs the brief):**
1. Tokenizer v2 rich representation → Tasks 1–3 (as feature vectors, not giant tokens) ✓
2. Dataset generation/labeling/red-team → Tasks 4–5 (+ existing make_redteam/label_redteam) ✓
3. Models: IsoForest (baseline, kept), LSTM (baseline, kept), **BiLSTM+Attention (core)** Task 7–8, **Transformer (core-if-feasible)** Task 7–8, LLM monitor (baseline, kept) ✓
4. Training: supervised BCE (Task 8 primary); self-supervised LSTM retained (train_anomaly.py) ✓
5. Explainability: attention per step (Task 7 returns attn), scorer (Task 11), graph (Task 13), attention_example.png (Task 12) ✓
6. Metrics: accuracy/precision/recall/F1/AUROC/pAUROC/confusion/ROC/PR → Task 6 + used in 8/9/12 ✓
7. Ablations: order/risk-features/attention/LSTM-vs-BiLSTM-vs-Transformer/classical-vs-learned → Task 10 ✓
8. MLflow + report outputs (comparison.md, experiments.md, confusion_matrix.png, roc_curve.png, attention_example.png, model_meta.json, model artifacts) → Tasks 8/9/10/12 ✓
9. Live demo → Tasks 13–14 ✓
10. Phasing C→A→B → sections ordered ✓; generalization/held-out-type split → Task 8 (`--holdout-type`) ✓

**Constraints:** v1 tokenizer/LSTM/LLM-monitor untouched (baselines) ✓; tokenizer v2 additive (new file) ✓; offline training scripts ✓; small models (hidden 48/64, 2 layers, dropout, early stopping) ✓; TDD on pure functions (features, metrics, models, generator), smoke-runs for training scripts (training loops aren't unit-testable) ✓.

**Placeholder scan:** code provided for all pure-function tasks; Tasks 9/10/12/13/14 describe modifications with exact files + concrete behavior + run commands (they extend existing scripts whose patterns are established in Tasks 6–8). No "TBD".

**Type consistency:** `CATEGORICAL_FIELDS`, `NUMERIC_FEATURES`, `encode_run` (returns `{cat,num,mask,length}`), `build_feature_vocabs`, model ctor signature `(vocab_sizes, n_numeric, ...)`, and `metrics` function names are consistent across Tasks 1–12.

**Note for executor:** Tasks 9, 10, 12, 13, 14 are integration tasks on existing scripts — when implementing, follow the established harness shape from Task 8 (load → encode via `features.encode_run` → train → `metrics.*` → MLflow) and keep each commit green.
