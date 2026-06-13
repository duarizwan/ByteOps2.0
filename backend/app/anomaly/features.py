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
# NOTE: order matters — more specific keyword sets must appear before broader ones
# (e.g. jira before github so "transition_issue" matches jira via "transition" not github via "issue")
_TOOL_KEYWORDS = {
    "gmail": ("email", "_email", "inbox", "draft", "reply", "forward"),
    "calendar": ("event", "calendar", "meeting", "schedule"),
    "jira": ("ticket", "jira", "sprint", "transition", "epic"),
    "github": ("pr", "pull_request", "issue", "commit", "repo", "merge", "branch"),
    "slack": ("message", "slack", "channel", "dm"),
    "dropbox": ("file", "folder", "dropbox", "upload", "path"),
}

_DESTRUCTIVE = {"delete", "trash", "remove", "close", "drop"}
_SEND = {"send", "forward", "reply", "post", "message"}
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
