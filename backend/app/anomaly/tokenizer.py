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
