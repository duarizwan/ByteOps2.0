"""Backend-enforced policy for agent tool calls."""

from dataclasses import dataclass
from enum import StrEnum


class ToolRisk(StrEnum):
    READ = "read"
    WRITE = "write"
    EXTERNAL_SEND = "external_send"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ToolPolicyDecision:
    tool: str
    action: str
    risk: ToolRisk
    reason: str


DESTRUCTIVE_ACTIONS = {
    "delete_email_permanently",
    "trash_email",
    "delete_event",
    "delete_message",
    "delete_comment",
    "delete_path",
    "close_issue",
    "close_pr",
    "merge_pr",
}

EXTERNAL_SEND_ACTIONS = {
    "send_email",
    "reply_to_email",
    "forward_email",
    "send_message",
    "send_dm",
    "quick_add",
    "create_event",
}

WRITE_ACTION_PREFIXES = (
    "create_",
    "update_",
    "assign_",
    "transition_",
    "add_",
    "remove_",
    "apply_",
    "mark_as_",
    "upload_",
    "move_",
    "copy_",
)


def classify_tool_call(tool: str, action: str) -> ToolPolicyDecision:
    normalized = action.strip().lower()
    if normalized in DESTRUCTIVE_ACTIONS:
        return ToolPolicyDecision(
            tool=tool,
            action=action,
            risk=ToolRisk.DESTRUCTIVE,
            reason="This action can remove or finalize external data.",
        )
    if normalized in EXTERNAL_SEND_ACTIONS:
        return ToolPolicyDecision(
            tool=tool,
            action=action,
            risk=ToolRisk.EXTERNAL_SEND,
            reason="This action sends or creates visible external content.",
        )
    if normalized.startswith(WRITE_ACTION_PREFIXES):
        return ToolPolicyDecision(
            tool=tool,
            action=action,
            risk=ToolRisk.WRITE,
            reason="This action changes external state.",
        )
    return ToolPolicyDecision(
        tool=tool,
        action=action,
        risk=ToolRisk.READ,
        reason="This action only reads external data.",
    )


def requires_approval(decision: ToolPolicyDecision) -> bool:
    return decision.risk in {ToolRisk.WRITE, ToolRisk.EXTERNAL_SEND, ToolRisk.DESTRUCTIVE}
