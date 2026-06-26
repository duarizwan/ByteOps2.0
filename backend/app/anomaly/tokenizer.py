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
