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
