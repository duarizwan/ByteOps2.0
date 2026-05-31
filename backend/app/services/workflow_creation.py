"""Create persisted workflow definitions from natural-language chat requests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow, WorkflowStatus

SUPPORTED_TOOLS = ("gmail", "slack", "jira", "github", "calendar", "dropbox")
INTERNAL_WORKFLOW_TOOLS = ("byteops",)
SUPPORTED_WORKFLOW_ACTION_TOOLS = (*SUPPORTED_TOOLS, *INTERNAL_WORKFLOW_TOOLS)
WRITE_ACTION_CUES = (
    "post",
    "send",
    "reply",
    "respond",
    "create ticket",
    "create issue",
    "update",
    "delete",
    "assign",
    "move",
    "upload",
)


def initial_next_run_at(trigger: dict, *, enabled: bool = True) -> datetime | None:
    if not enabled or not isinstance(trigger, dict) or trigger.get("type") != "schedule":
        return None
    label = str(trigger.get("label") or "").lower()
    now = datetime.now(timezone.utc)
    next_run = now + timedelta(days=1)
    if "weekday" in label:
        while next_run.weekday() >= 5:
            next_run += timedelta(days=1)
    return next_run


def is_workflow_creation_request(message: str) -> bool:
    text = message.lower()
    return "workflow" in text and any(
        phrase in text for phrase in ("create", "make", "set up", "setup", "automate")
    )


def _trigger_from_prompt(text: str) -> dict:
    if "every weekday" in text:
        return {"type": "schedule", "label": "Every weekday"}
    if "every morning" in text:
        return {"type": "schedule", "label": "Every morning"}
    if "daily" in text or "every day" in text:
        return {"type": "schedule", "label": "Daily"}
    if "when " in text:
        return {"type": "event", "label": "When matching activity appears"}
    return {"type": "manual", "label": "Manual run"}


def _tools_from_prompt(text: str) -> list[str]:
    return [tool for tool in SUPPORTED_TOOLS if tool in text]


def _label_for_tool(tool: str, text: str) -> str:
    if "summarize" in text or "summary" in text:
        return f"Summarize {tool.title()}"
    if "post" in text:
        return f"Post {tool.title()} update"
    if "send" in text:
        return f"Send {tool.title()} update"
    if tool == "jira":
        return "Review Jira items"
    if tool == "github":
        return "Review GitHub activity"
    if tool == "calendar":
        return "Review Calendar events"
    return f"Check {tool.title()}"


def _name_from_prompt(tools: list[str], trigger: dict, text: str) -> str:
    if trigger.get("label") == "Every morning" and tools:
        tool_names = " and ".join(tool.title() for tool in tools[:2])
        return f"Morning {tool_names} brief"
    if tools:
        tool_names = " and ".join(tool.title() for tool in tools[:2])
        return f"{tool_names} workflow"
    if "urgent" in text:
        return "Urgent task workflow"
    return "AI workflow"


def build_workflow_draft(message: str, connected_tools: list[str]) -> dict:
    text = message.lower()
    trigger = _trigger_from_prompt(text)
    tools = _tools_from_prompt(text)
    connected = {tool.lower() for tool in connected_tools}
    missing_tools = [tool for tool in tools if tool not in connected]
    actions = [{"tool": tool, "label": _label_for_tool(tool, text)} for tool in tools]
    review_reasons = [
        f"Connect {tool.title()} before this workflow can run."
        for tool in missing_tools
    ]

    if any(cue in text for cue in WRITE_ACTION_CUES):
        review_reasons.append("Review and approve write actions before saving.")

    if "urgent task" in text or "urgent tasks" in text or "anything urgent" in text:
        actions.append({"tool": "byteops", "label": "List urgent tasks"})

    return {
        "name": _name_from_prompt(tools, trigger, text),
        "description": "Created from AI chat.",
        "trigger": trigger,
        "actions": actions,
        "missing_tools": missing_tools,
        "requires_review": bool(review_reasons),
        "review_reasons": review_reasons,
    }


def validate_workflow_draft(draft: dict) -> None:
    if not isinstance(draft.get("name"), str) or not draft["name"].strip():
        raise ValueError("Workflow draft name is required.")
    if not isinstance(draft.get("trigger"), dict):
        raise ValueError("Workflow draft trigger is required.")
    actions = draft.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("Workflow draft must include at least one action.")
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("Workflow draft actions must be objects.")
        tool = action.get("tool")
        if tool not in SUPPORTED_WORKFLOW_ACTION_TOOLS:
            raise ValueError(f"Unsupported workflow action tool: {tool}.")
        label = action.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Workflow draft action labels are required.")


async def create_workflow_from_prompt(
    db: AsyncSession,
    *,
    user_id: UUID,
    message: str,
    connected_tools: list[str],
) -> tuple[Workflow, dict]:
    draft = build_workflow_draft(message, connected_tools)
    if draft["requires_review"]:
        raise ValueError("Workflow draft requires review before saving.")
    validate_workflow_draft(draft)
    workflow = Workflow(
        user_id=user_id,
        name=draft["name"],
        description=draft["description"],
        trigger=draft["trigger"],
        actions=draft["actions"],
        status=WorkflowStatus.ACTIVE,
        next_run_at=initial_next_run_at(draft["trigger"]),
        metadata_={
            "created_from_chat": True,
            "missing_tools": draft["missing_tools"],
        },
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow, draft


async def create_workflow_from_draft(
    db: AsyncSession,
    *,
    user_id: UUID,
    draft: dict,
) -> Workflow:
    validate_workflow_draft(draft)
    missing_tools = draft.get("missing_tools") or []
    status = WorkflowStatus.PAUSED if missing_tools else WorkflowStatus.ACTIVE
    workflow = Workflow(
        user_id=user_id,
        name=draft["name"],
        description=draft.get("description") or "Created from reviewed AI draft.",
        trigger=draft["trigger"],
        actions=draft["actions"],
        status=status,
        next_run_at=initial_next_run_at(draft["trigger"], enabled=status == WorkflowStatus.ACTIVE),
        metadata_={
            "created_from_reviewed_draft": True,
            "missing_tools": missing_tools,
            "review_reasons": draft.get("review_reasons") or [],
        },
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


def workflow_draft_response(draft: dict) -> str:
    action_labels = ", ".join(action["label"] for action in draft["actions"]) or "No actions extracted"
    reason_text = " ".join(draft["review_reasons"]) or "Review the workflow details before saving."
    return (
        f"Draft workflow ready for review. Name: {draft['name']}. "
        f"Trigger: {draft['trigger']['label']}. Actions: {action_labels}. "
        f"{reason_text}"
    )


def workflow_creation_response(workflow: Workflow, draft: dict) -> str:
    action_count = len(draft["actions"])
    text = f"Created workflow {workflow.name} with {action_count} action"
    if action_count != 1:
        text += "s"
    text += ". You can review, run, pause, or resume it from the Workflows tab."
    if draft["missing_tools"]:
        missing = ", ".join(tool.title() for tool in draft["missing_tools"])
        text += f" Connect {missing} for every action to run."
    return text
