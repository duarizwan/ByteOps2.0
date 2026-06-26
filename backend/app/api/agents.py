"""Agent-as-a-Service API.

Provides agent templates and CRUD for hired agents — autonomous agents that
run on a schedule using existing workflow infrastructure.

Endpoints:
  GET    /api/agents/templates       — list available agent templates
  GET    /api/agents                 — list user's hired agents
  POST   /api/agents                 — hire an agent from a template
  GET    /api/agents/{id}            — get agent details
  PATCH  /api/agents/{id}            — update agent config
  POST   /api/agents/{id}/pause      — pause agent
  POST   /api/agents/{id}/resume     — resume agent
  POST   /api/agents/{id}/run        — manual trigger
  DELETE /api/agents/{id}            — fire (delete) agent
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.user import User
from app.models.hired_agent import HiredAgent, HiredAgentStatus
from app.models.tool_connection import ToolConnection, ToolType, ConnectionStatus
from app.models.agent_run import AgentRun, AgentRunStatus

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ── Agent Templates (code-defined constants) ─────────────────────────────────

AGENT_TEMPLATES: dict[str, dict] = {
    "inbox_triage": {
        "key": "inbox_triage",
        "name": "Inbox Triage Agent",
        "description": (
            "Automatically reviews your unread Gmail, classifies emails by priority, "
            "labels them, summarizes important threads, and drafts replies for urgent items. "
            "Risky actions (sending, forwarding) go through approval gates."
        ),
        "icon": "mail",
        "color": "#ef4444",
        "required_tools": ["gmail"],
        "optional_tools": ["slack"],
        "default_schedule": "every_2_hours",
        "schedule_options": [
            {"value": "every_30_min", "label": "Every 30 minutes"},
            {"value": "every_hour", "label": "Every hour"},
            {"value": "every_2_hours", "label": "Every 2 hours"},
            {"value": "every_4_hours", "label": "Every 4 hours"},
            {"value": "daily_morning", "label": "Daily at 9 AM"},
        ],
        "config_schema": [
            {"key": "priority_labels", "label": "Auto-label by priority", "type": "boolean", "default": True},
            {"key": "draft_replies", "label": "Draft replies for urgent emails", "type": "boolean", "default": True},
            {"key": "escalate_to_slack", "label": "Escalate urgent items to Slack", "type": "boolean", "default": False},
            {"key": "max_emails", "label": "Max emails to process per run", "type": "number", "default": 20},
        ],
        "capabilities": [
            "Classify emails by urgency (high / medium / low)",
            "Auto-label inbox with priority tags",
            "Summarize important email threads",
            "Draft replies for urgent messages",
            "Escalate critical items to Slack (if connected)",
        ],
        "prompt_template": (
            "You are an Inbox Triage Agent. Review the user's unread Gmail and:\n"
            "1. List all unread emails with sender, subject, and a 1-line summary.\n"
            "2. Classify each as HIGH / MEDIUM / LOW priority.\n"
            "3. For HIGH priority: draft a reply suggestion.\n"
            "4. Summarize key takeaways in 2-3 bullets.\n"
            "Be concise and action-oriented."
        ),
    },
    "dev_standup": {
        "key": "dev_standup",
        "name": "Dev Standup Agent",
        "description": (
            "Generates a daily development standup digest by aggregating GitHub PR/commit "
            "activity and Jira ticket movements. Posts the digest to a chosen Slack channel "
            "and flags stale PRs or blocked tickets."
        ),
        "icon": "code",
        "color": "#8b5cf6",
        "required_tools": ["github"],
        "optional_tools": ["jira", "slack"],
        "default_schedule": "daily_morning",
        "schedule_options": [
            {"value": "daily_morning", "label": "Daily at 9 AM"},
            {"value": "daily_evening", "label": "Daily at 6 PM"},
            {"value": "twice_daily", "label": "Twice daily (9 AM + 6 PM)"},
            {"value": "weekdays_morning", "label": "Weekdays at 9 AM"},
        ],
        "config_schema": [
            {"key": "include_prs", "label": "Include PR activity", "type": "boolean", "default": True},
            {"key": "include_commits", "label": "Include commit summary", "type": "boolean", "default": True},
            {"key": "include_jira", "label": "Include Jira ticket updates", "type": "boolean", "default": True},
            {"key": "flag_stale_prs", "label": "Flag PRs older than 3 days", "type": "boolean", "default": True},
            {"key": "slack_channel", "label": "Slack channel for digest", "type": "string", "default": ""},
            {"key": "lookback_hours", "label": "Hours to look back", "type": "number", "default": 24},
        ],
        "capabilities": [
            "Aggregate GitHub PR and commit activity",
            "Track Jira ticket status changes",
            "Flag stale PRs (>3 days without review)",
            "Identify blocked tickets",
            "Post formatted digest to Slack",
        ],
        "prompt_template": (
            "You are a Dev Standup Agent. Generate a daily development standup by:\n"
            "1. Listing open PRs with status, reviewer, and age.\n"
            "2. Summarizing commits from the last 24 hours.\n"
            "3. Listing Jira tickets that changed status today.\n"
            "4. Flagging stale PRs (>3 days) and blocked tickets.\n"
            "Format as a clean, readable digest. Be concise."
        ),
    },
    "meeting_prep": {
        "key": "meeting_prep",
        "name": "Meeting Prep Agent",
        "description": (
            "Before each meeting, gathers relevant emails, documents, and tickets "
            "related to the meeting topic and attendees. Prepares a briefing note "
            "so you walk in ready."
        ),
        "icon": "calendar",
        "color": "#06b6d4",
        "required_tools": ["calendar"],
        "optional_tools": ["gmail", "jira", "github"],
        "default_schedule": "before_meetings",
        "schedule_options": [
            {"value": "before_meetings", "label": "30 min before each meeting"},
            {"value": "daily_morning", "label": "Daily morning briefing"},
        ],
        "config_schema": [
            {"key": "prep_minutes_before", "label": "Minutes before meeting to prepare", "type": "number", "default": 30},
            {"key": "include_emails", "label": "Include related emails", "type": "boolean", "default": True},
            {"key": "include_tickets", "label": "Include related tickets", "type": "boolean", "default": True},
        ],
        "capabilities": [
            "Scan upcoming calendar events",
            "Find related emails from meeting attendees",
            "Pull relevant Jira tickets and GitHub issues",
            "Generate a pre-meeting briefing note",
        ],
        "prompt_template": (
            "You are a Meeting Prep Agent. For the next upcoming meeting:\n"
            "1. List the meeting details (title, time, attendees).\n"
            "2. Find recent emails from attendees.\n"
            "3. Find related Jira tickets or GitHub issues.\n"
            "4. Generate a 5-bullet briefing note.\n"
            "Be concise and actionable."
        ),
    },
    "task_sync": {
        "key": "task_sync",
        "name": "Task Sync Agent",
        "description": (
            "Keeps your task management in sync across Jira, GitHub Issues, and Slack. "
            "When a Jira ticket is updated, the linked GitHub issue is updated too — and "
            "relevant Slack threads are notified."
        ),
        "icon": "refresh-cw",
        "color": "#10b981",
        "required_tools": ["jira"],
        "optional_tools": ["github", "slack"],
        "default_schedule": "every_hour",
        "schedule_options": [
            {"value": "every_30_min", "label": "Every 30 minutes"},
            {"value": "every_hour", "label": "Every hour"},
            {"value": "every_4_hours", "label": "Every 4 hours"},
        ],
        "config_schema": [
            {"key": "sync_jira_github", "label": "Sync Jira ↔ GitHub Issues", "type": "boolean", "default": True},
            {"key": "notify_slack", "label": "Notify Slack on status changes", "type": "boolean", "default": True},
            {"key": "jira_project", "label": "Jira project key", "type": "string", "default": ""},
        ],
        "capabilities": [
            "Monitor Jira ticket status changes",
            "Sync status to linked GitHub issues",
            "Post updates to Slack channels",
            "Flag overdue tasks",
        ],
        "prompt_template": (
            "You are a Task Sync Agent. Check for recent Jira ticket updates:\n"
            "1. List tickets that changed status in the last hour.\n"
            "2. For each, check if there's a linked GitHub issue.\n"
            "3. Summarize what changed.\n"
            "Be concise."
        ),
    },
}


# ── Request / Response schemas ────────────────────────────────────────────────

class TemplateOut(BaseModel):
    key: str
    name: str
    description: str
    icon: str
    color: str
    required_tools: list[str]
    optional_tools: list[str]
    default_schedule: str
    schedule_options: list[dict]
    config_schema: list[dict]
    capabilities: list[str]
    available: bool = False  # True if user has required tools connected


class HiredAgentOut(BaseModel):
    id: str
    template_key: str
    name: str
    description: str | None
    status: str
    config: dict
    schedule: str
    last_run_at: str | None
    next_run_at: str | None
    last_error: str | None
    total_runs: int
    recent_runs: list[dict] = []
    template: dict | None = None
    created_at: str | None
    updated_at: str | None


class HireAgentRequest(BaseModel):
    template_key: str = Field(min_length=1, max_length=100)
    name: str | None = None
    config: dict = Field(default_factory=dict)
    schedule: str = ""


class UpdateAgentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: dict | None = None
    schedule: str | None = None


class AgentRunOut(BaseModel):
    id: str
    status: str
    intent: str
    created_at: str | None
    flagged: bool
    anomaly_score: float | None
    summary: str | None
    error: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _schedule_to_next_run(schedule: str) -> datetime | None:
    """Convert a schedule label to the next run datetime."""
    now = datetime.now(timezone.utc)
    mapping = {
        "every_30_min": timedelta(minutes=30),
        "every_hour": timedelta(hours=1),
        "every_2_hours": timedelta(hours=2),
        "every_4_hours": timedelta(hours=4),
        "daily_morning": timedelta(days=1),
        "daily_evening": timedelta(days=1),
        "twice_daily": timedelta(hours=12),
        "weekdays_morning": timedelta(days=1),
        "before_meetings": timedelta(hours=1),
    }
    delta = mapping.get(schedule)
    return (now + delta) if delta else None


def _serialize(agent: HiredAgent, recent_runs: list[dict] | None = None) -> HiredAgentOut:
    template = AGENT_TEMPLATES.get(agent.template_key)
    status_value = agent.status.value if hasattr(agent.status, "value") else str(agent.status)
    config = agent.config or {}
    return HiredAgentOut(
        id=str(agent.id),
        template_key=agent.template_key,
        name=agent.name,
        description=agent.description,
        status=status_value,
        config=config,
        schedule=config.get("schedule", ""),
        last_run_at=_iso(agent.last_run_at),
        next_run_at=_iso(agent.next_run_at),
        last_error=agent.last_error,
        total_runs=agent.total_runs or 0,
        recent_runs=recent_runs or [],
        template={
            "name": template["name"],
            "icon": template["icon"],
            "color": template["color"],
            "capabilities": template["capabilities"],
        } if template else None,
        created_at=_iso(agent.created_at),
        updated_at=_iso(agent.updated_at),
    )


async def _get_user_agent(agent_id: UUID, current_user: User, db: AsyncSession) -> HiredAgent:
    agent = await db.get(HiredAgent, agent_id)
    if not agent or agent.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    return agent


async def _get_recent_runs(db: AsyncSession, user_id, agent_name: str, limit: int = 5) -> list[dict]:
    """Fetch recent agent runs that match the hired agent's intent."""
    result = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.user_id == user_id,
            AgentRun.intent.in_(["gmail", "github", "jira", "calendar", "slack"]),
        )
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "intent": r.intent,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "created_at": _iso(r.created_at),
            "flagged": bool(getattr(r, "flagged", False)),
        }
        for r in runs
    ]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(
    response: Response,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TemplateOut]:
    """List all available agent templates with availability status."""
    # Check which tools the user has connected
    result = await db.execute(
        select(ToolConnection.tool_type).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.status == ConnectionStatus.CONNECTED,
        )
    )
    connected = {row[0].value for row in result.all()}

    templates = []
    for tmpl in AGENT_TEMPLATES.values():
        available = all(tool in connected for tool in tmpl["required_tools"])
        templates.append(TemplateOut(
            key=tmpl["key"],
            name=tmpl["name"],
            description=tmpl["description"],
            icon=tmpl["icon"],
            color=tmpl["color"],
            required_tools=tmpl["required_tools"],
            optional_tools=tmpl["optional_tools"],
            default_schedule=tmpl["default_schedule"],
            schedule_options=tmpl["schedule_options"],
            config_schema=tmpl["config_schema"],
            capabilities=tmpl["capabilities"],
            available=available,
        ))
    response.headers["Cache-Control"] = "private, max-age=30"
    return templates


@router.get("", response_model=list[HiredAgentOut])
async def list_agents(
    response: Response,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[HiredAgentOut]:
    """List all hired agents for the current user."""
    result = await db.execute(
        select(HiredAgent)
        .where(HiredAgent.user_id == current_user.id)
        .order_by(HiredAgent.created_at.desc())
    )
    agents = result.scalars().all()
    response.headers["Cache-Control"] = "private, max-age=30"
    return [_serialize(agent) for agent in agents]


@router.post("", response_model=HiredAgentOut, status_code=201)
async def hire_agent(
    body: HireAgentRequest,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HiredAgentOut:
    """Hire a new agent from a template."""
    template = AGENT_TEMPLATES.get(body.template_key)
    if not template:
        raise HTTPException(status_code=400, detail=f"Unknown template: {body.template_key}")

    # Validate required tools
    result = await db.execute(
        select(ToolConnection.tool_type).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.status == ConnectionStatus.CONNECTED,
        )
    )
    connected = {row[0].value for row in result.all()}
    missing = [t for t in template["required_tools"] if t not in connected]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required tool connections: {', '.join(missing)}. "
                   f"Connect them in Settings → Connections first.",
        )

    # Validate config keys are from the template schema
    allowed_keys = {item["key"] for item in template["config_schema"]}
    unknown = set(body.config.keys()) - allowed_keys
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown config keys: {', '.join(sorted(unknown))}")

    # Validate config value sizes (no oversized strings)
    for key, val in body.config.items():
        if isinstance(val, str) and len(val) > 500:
            raise HTTPException(status_code=400, detail=f"Config value for '{key}' exceeds 500 characters.")

    schedule = body.schedule or template["default_schedule"]
    config = {**{item["key"]: item["default"] for item in template["config_schema"]}, **body.config}
    config["schedule"] = schedule

    agent = HiredAgent(
        user_id=current_user.id,
        template_key=body.template_key,
        name=body.name or template["name"],
        description=template["description"],
        config=config,
        status=HiredAgentStatus.ACTIVE,
        next_run_at=_schedule_to_next_run(schedule),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return _serialize(agent)


@router.get("/{agent_id}", response_model=HiredAgentOut)
async def get_agent(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HiredAgentOut:
    """Get details of a specific hired agent."""
    agent = await _get_user_agent(agent_id, current_user, db)
    recent_runs = await _get_recent_runs(db, current_user.id, agent.name)
    return _serialize(agent, recent_runs)


@router.patch("/{agent_id}", response_model=HiredAgentOut)
async def update_agent(
    agent_id: UUID,
    body: UpdateAgentRequest,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HiredAgentOut:
    """Update an agent's name, config, or schedule."""
    agent = await _get_user_agent(agent_id, current_user, db)
    if body.name is not None:
        agent.name = body.name.strip()
    if body.config is not None:
        agent.config = {**(agent.config or {}), **body.config}
    if body.schedule is not None:
        config = agent.config or {}
        config["schedule"] = body.schedule
        agent.config = config
        agent.next_run_at = _schedule_to_next_run(body.schedule)
    await db.commit()
    await db.refresh(agent)
    return _serialize(agent)


@router.post("/{agent_id}/pause", response_model=HiredAgentOut)
async def pause_agent(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HiredAgentOut:
    """Pause a hired agent."""
    agent = await _get_user_agent(agent_id, current_user, db)
    agent.status = HiredAgentStatus.PAUSED
    agent.next_run_at = None
    await db.commit()
    await db.refresh(agent)
    return _serialize(agent)


@router.post("/{agent_id}/resume", response_model=HiredAgentOut)
async def resume_agent(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HiredAgentOut:
    """Resume a paused agent."""
    agent = await _get_user_agent(agent_id, current_user, db)
    schedule = (agent.config or {}).get("schedule", "every_2_hours")
    agent.status = HiredAgentStatus.ACTIVE
    agent.next_run_at = _schedule_to_next_run(schedule)
    agent.last_error = None
    await db.commit()
    await db.refresh(agent)
    return _serialize(agent)


@router.post("/{agent_id}/run", response_model=HiredAgentOut)
async def run_agent(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HiredAgentOut:
    """Manually trigger a hired agent run. Uses the existing workflow runner."""
    agent = await _get_user_agent(agent_id, current_user, db)
    template = AGENT_TEMPLATES.get(agent.template_key)
    if not template:
        raise HTTPException(status_code=400, detail="Unknown agent template.")

    if agent.status == HiredAgentStatus.PAUSED:
        raise HTTPException(status_code=409, detail="Paused agents cannot run. Resume first.")

    now = datetime.now(timezone.utc)
    agent.status = HiredAgentStatus.RUNNING
    agent.last_run_at = now
    agent.last_error = None
    await db.commit()

    # Execute via existing workflow runner
    try:
        from app.services.workflow_runner import execute_workflow_run
        run_data = await execute_workflow_run(
            workflow_name=agent.name,
            workflow_id=str(agent.id),
            trigger={"type": "agent", "template": agent.template_key},
            actions=[{"tool": t, "operation": "auto", "prompt": template["prompt_template"]}
                     for t in template["required_tools"]],
            user_id=current_user.id,
            db=db,
        )
        agent.status = HiredAgentStatus.ACTIVE
        agent.total_runs = (agent.total_runs or 0) + 1
        metadata = {
            **(agent.metadata_ or {}),
            "last_agent_run_id": run_data.get("id"),
            "last_run_status": run_data.get("status"),
            "last_run_summary": run_data.get("final_response", "")[:500],
        }
        agent.metadata_ = metadata
        if run_data.get("status") == "failed":
            agent.status = HiredAgentStatus.FAILED
            agent.last_error = run_data.get("final_response", "Run failed")[:500]
    except Exception as exc:
        agent.status = HiredAgentStatus.FAILED
        agent.last_error = str(exc)[:500]

    # Schedule next run
    schedule = (agent.config or {}).get("schedule", "every_2_hours")
    agent.next_run_at = _schedule_to_next_run(schedule)
    await db.commit()
    await db.refresh(agent)
    return _serialize(agent)


@router.delete("/{agent_id}", status_code=204)
async def fire_agent(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Fire (delete) a hired agent."""
    agent = await _get_user_agent(agent_id, current_user, db)
    await db.delete(agent)
    await db.commit()


@router.get("/{agent_id}/runs", response_model=list[AgentRunOut])
async def list_agent_runs(
    agent_id: UUID,
    response: Response,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[AgentRunOut]:
    """List run history for a specific hired agent."""
    await _get_user_agent(agent_id, current_user, db)  # ownership check
    limit = min(limit, 200)
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.hired_agent_id == agent_id)
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    runs = result.scalars().all()
    response.headers["Cache-Control"] = "private, max-age=30"
    return [
        AgentRunOut(
            id=str(r.id),
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            intent=r.intent,
            created_at=_iso(r.created_at),
            flagged=bool(r.flagged),
            anomaly_score=r.anomaly_score,
            summary=(r.final_response or "")[:200] or None,
            error=r.error,
        )
        for r in runs
    ]
