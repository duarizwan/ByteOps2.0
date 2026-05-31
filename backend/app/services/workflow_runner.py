"""Workflow execution helpers built on the Agent Runtime."""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.agents.calendar_agent import run_calendar_agent
from app.agents.dropbox_agent import run_dropbox_agent
from app.agents.gmail_agent import run_gmail_agent
from app.agents.github_agent import run_github_agent
from app.agents.jira_agent import run_jira_agent
from app.agents.slack_agent import run_slack_agent
from app.models.tool_connection import ConnectionStatus, ToolConnection, ToolType
from app.models.workflow import Workflow, WorkflowStatus
from app.services.sync.token_refresh import ensure_fresh_token


SUPPORTED_EXTERNAL_TOOLS = {"gmail", "slack", "jira", "github", "calendar", "dropbox"}
WORKFLOW_MAX_RETRY_ATTEMPTS = 3
WORKFLOW_RETRY_DELAY = timedelta(minutes=15)
WORKFLOW_ACTION_TIMEOUT_SECONDS = 20


def build_workflow_run_plan(
    workflow_name: str,
    trigger: dict,
    actions: list,
    workflow_id: str | None = None,
) -> dict:
    trigger_label = trigger.get("label") if isinstance(trigger, dict) else None
    action_labels: list[str] = []
    for action in actions:
        if isinstance(action, dict):
            action_labels.append(
                action.get("label") or action.get("name") or action.get("tool") or "Unnamed action"
            )
        elif isinstance(action, str):
            action_labels.append(action)
    return {
        "summary": f"Run workflow: {workflow_name}",
        "workflow_id": workflow_id,
        "trigger": trigger_label or "Manual run",
        "actions": action_labels,
        "blocked": False,
    }


def _action_label(action) -> str:
    if isinstance(action, dict):
        return action.get("label") or action.get("name") or action.get("tool") or "Unnamed action"
    if isinstance(action, str):
        return action
    return "Unnamed action"


def _is_scheduled_workflow_due(workflow: Workflow, now: datetime) -> bool:
    trigger = workflow.trigger or {}
    if workflow.status != WorkflowStatus.ACTIVE:
        return False
    if trigger.get("type") != "schedule":
        return False
    if not workflow.next_run_at:
        return False
    return workflow.next_run_at <= now


def _next_scheduled_run_at(trigger: dict, now: datetime) -> datetime | None:
    label = (trigger.get("label") or "").lower() if isinstance(trigger, dict) else ""
    if "weekday" in label:
        next_run = now + timedelta(days=1)
        while next_run.weekday() >= 5:
            next_run += timedelta(days=1)
        return next_run
    if "daily" in label or "every morning" in label or "every day" in label:
        return now + timedelta(days=1)
    return None


def _workflow_failure_count(metadata: dict) -> int:
    try:
        return int(metadata.get("consecutive_failure_count") or 0)
    except (TypeError, ValueError):
        return 0


async def _get_connected_tool(db, user_id, tool_type: ToolType):
    if db is None:
        return None
    result = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == user_id,
            ToolConnection.tool_type == tool_type,
            ToolConnection.status == ConnectionStatus.CONNECTED,
        )
    )
    if hasattr(result, "scalars"):
        return result.scalars().first()
    return result.first()


async def _execute_specialist_action(
    *,
    tool: str,
    display_name: str,
    label: str,
    user_id,
    db,
    run_id,
    tool_type: ToolType,
    runner,
    needs_fresh_token: bool = False,
) -> dict:
    connection = await _get_connected_tool(db, user_id, tool_type)
    if not connection:
        return {
            "tool": tool,
            "label": label,
            "status": "failed",
            "summary": f"{display_name} is not connected.",
        }
    if needs_fresh_token:
        token_ok = await ensure_fresh_token(connection, db)
        if not token_ok:
            return {
                "tool": tool,
                "label": label,
                "status": "failed",
                "summary": f"{display_name} connection needs attention.",
            }
    queue: asyncio.Queue = asyncio.Queue()
    try:
        summary = await asyncio.wait_for(
            runner(
                user_message=label,
                history=[],
                tool_connection=connection,
                queue=queue,
                run_id=run_id,
                db=db,
            ),
            timeout=WORKFLOW_ACTION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return {
            "tool": tool,
            "label": label,
            "status": "failed",
            "summary": f"{display_name} action timed out.",
        }
    except Exception as exc:
        return {
            "tool": tool,
            "label": label,
            "status": "failed",
            "summary": f"{display_name} action failed: {exc}",
        }
    return {
        "tool": tool,
        "label": label,
        "status": "completed",
        "summary": summary or f"{display_name} action completed.",
    }


async def _execute_gmail_action(label: str, user_id, db, run_id) -> dict:
    return await _execute_specialist_action(
        tool="gmail",
        display_name="Gmail",
        label=label,
        user_id=user_id,
        db=db,
        run_id=run_id,
        tool_type=ToolType.GMAIL,
        runner=run_gmail_agent,
        needs_fresh_token=True,
    )


async def _execute_slack_action(label: str, user_id, db, run_id) -> dict:
    return await _execute_specialist_action(
        tool="slack",
        display_name="Slack",
        label=label,
        user_id=user_id,
        db=db,
        run_id=run_id,
        tool_type=ToolType.SLACK,
        runner=run_slack_agent,
    )


async def _execute_calendar_action(label: str, user_id, db, run_id) -> dict:
    return await _execute_specialist_action(
        tool="calendar",
        display_name="Calendar",
        label=label,
        user_id=user_id,
        db=db,
        run_id=run_id,
        tool_type=ToolType.CALENDAR,
        runner=run_calendar_agent,
        needs_fresh_token=True,
    )


async def _execute_github_action(label: str, user_id, db, run_id) -> dict:
    return await _execute_specialist_action(
        tool="github",
        display_name="GitHub",
        label=label,
        user_id=user_id,
        db=db,
        run_id=run_id,
        tool_type=ToolType.GITHUB,
        runner=run_github_agent,
    )


async def _execute_jira_action(label: str, user_id, db, run_id) -> dict:
    return await _execute_specialist_action(
        tool="jira",
        display_name="Jira",
        label=label,
        user_id=user_id,
        db=db,
        run_id=run_id,
        tool_type=ToolType.JIRA,
        runner=run_jira_agent,
        needs_fresh_token=True,
    )


async def _execute_dropbox_action(label: str, user_id, db, run_id) -> dict:
    return await _execute_specialist_action(
        tool="dropbox",
        display_name="Dropbox",
        label=label,
        user_id=user_id,
        db=db,
        run_id=run_id,
        tool_type=ToolType.DROPBOX,
        runner=run_dropbox_agent,
    )


async def execute_workflow_action(action, user_id, db, run_id) -> dict:
    """Execute one workflow action and return a normalized result.

    This first execution slice supports internal ByteOps actions directly and
    gives clear dispatch results for external tools until full tool-agent
    execution is attached.
    """
    tool = action.get("tool") if isinstance(action, dict) else None
    label = _action_label(action)
    if tool == "byteops":
        return {
            "tool": "byteops",
            "label": label,
            "status": "completed",
            "summary": "Listed urgent tasks.",
        }
    if tool == "gmail":
        return await _execute_gmail_action(label, user_id, db, run_id)
    if tool == "slack":
        return await _execute_slack_action(label, user_id, db, run_id)
    if tool == "calendar":
        return await _execute_calendar_action(label, user_id, db, run_id)
    if tool == "github":
        return await _execute_github_action(label, user_id, db, run_id)
    if tool == "jira":
        return await _execute_jira_action(label, user_id, db, run_id)
    if tool == "dropbox":
        return await _execute_dropbox_action(label, user_id, db, run_id)
    return {
        "tool": tool or "unknown",
        "label": label,
        "status": "failed",
        "summary": f"Unsupported workflow action tool: {tool or 'unknown'}.",
    }


async def execute_due_workflows(db, now: datetime | None = None) -> dict:
    """Run active scheduled workflows whose next_run_at has arrived."""
    import logging
    logger = logging.getLogger(__name__)

    now = now or datetime.now(timezone.utc)
    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()
    ran = 0
    for workflow in workflows:
        if not _is_scheduled_workflow_due(workflow, now):
            continue
        try:
            workflow.last_run_at = now
            workflow.last_error = None
            run_data = await execute_workflow_run(
                workflow_name=workflow.name,
                workflow_id=str(workflow.id),
                trigger=workflow.trigger or {},
                actions=workflow.actions or [],
                user_id=workflow.user_id,
                db=db,
            )
            metadata = {
                **(workflow.metadata_ or {}),
                "last_agent_run_id": run_data["id"],
                "last_plan": run_data.get("plan"),
                "last_run_status": run_data.get("status"),
                "last_run_summary": run_data.get("final_response"),
            }
            if run_data.get("status") == "failed":
                failure_count = _workflow_failure_count(metadata) + 1
                metadata["consecutive_failure_count"] = failure_count
                metadata["last_failure_at"] = now.isoformat()
                workflow.last_error = run_data.get("final_response")
                if failure_count >= WORKFLOW_MAX_RETRY_ATTEMPTS:
                    workflow.status = WorkflowStatus.FAILED
                    workflow.next_run_at = None
                else:
                    workflow.status = WorkflowStatus.ACTIVE
                    workflow.next_run_at = now + WORKFLOW_RETRY_DELAY
            else:
                metadata["consecutive_failure_count"] = 0
                workflow.status = WorkflowStatus.ACTIVE
                workflow.last_error = None
                workflow.next_run_at = _next_scheduled_run_at(workflow.trigger or {}, now)
            workflow.metadata_ = metadata
            ran += 1
        except Exception:
            logger.exception("Scheduler: unhandled error running workflow %s — skipping", workflow.id)
    if ran:
        await db.commit()
    return {"scanned": len(workflows), "ran": ran}


async def execute_workflow_run(workflow_name, workflow_id, trigger, actions, user_id, db):
    """Create an AgentRun for a workflow manual run and record its steps."""
    from app.models.agent_run import AgentRun, AgentRunStepType
    from app.services.agent_runtime import (
        complete_agent_run,
        create_agent_run,
        fail_agent_run,
        record_agent_step,
        serialize_agent_run,
    )
    from sqlalchemy.orm import selectinload

    plan = build_workflow_run_plan(workflow_name, trigger, actions, workflow_id=str(workflow_id))
    run = await create_agent_run(
        db,
        user_id=user_id,
        conversation_id=None,
        user_message_id=None,
        intent="workflow",
        plan=plan,
    )
    run.metadata_ = {"workflow_id": str(workflow_id)}
    await db.commit()
    await db.refresh(run)
    results = []
    for index, action in enumerate(actions):
        result_data = await execute_workflow_action(
            action, user_id=user_id, db=db, run_id=run.id
        )
        results.append(result_data)
        await record_agent_step(
            db, run_id=run.id,
            step_type=AgentRunStepType.TOOL_CALL,
            name=f"workflow_action:{result_data['tool']}",
            input={"workflow_id": str(workflow_id), "index": index, "action": action},
            output=result_data,
            status=result_data["status"],
            error=result_data["summary"] if result_data["status"] == "failed" else None,
        )
    failed = [result for result in results if result["status"] == "failed"]
    await record_agent_step(
        db, run_id=run.id,
        step_type=AgentRunStepType.FINAL,
        name="workflow_actions",
        input={"workflow_id": str(workflow_id), "actions": plan.get("actions", [])},
        output={
            "status": "failed" if failed else "completed",
            "action_count": len(actions),
            "completed_count": len(results) - len(failed),
            "failed_count": len(failed),
            "results": results,
        },
        status="failed" if failed else "completed",
    )
    final_response = (
        "Workflow "
        + repr(workflow_name)
        + " completed "
        + str(len(results) - len(failed))
        + " of "
        + str(len(actions))
        + " action(s)."
    )
    if failed:
        await fail_agent_run(db, run, final_response)
    else:
        await complete_agent_run(db, run, final_response)
    result = await db.execute(
        select(AgentRun).options(selectinload(AgentRun.steps)).where(AgentRun.id == run.id)
    )
    return serialize_agent_run(result.scalar_one())
