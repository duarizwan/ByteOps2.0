# Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a thin internal Agent Runtime that makes ByteOps agent work auditable, safe, resumable, and workflow-ready without replacing the existing FastAPI plus MCP specialist-agent architecture.

**Architecture:** Keep the current orchestrator and specialist agents, then wrap each chat/tool workflow in an Agent Run ledger. The first implementation records intent, plan, tool calls, approvals, verification, and extracted follow-up tasks; later workflow execution can reuse the same runtime service.

**Tech Stack:** FastAPI, SQLAlchemy async models, PostgreSQL JSONB, Anthropic tool calling through existing MCP agents, React/Next.js for future run visibility.

---

## File Structure

- Create `backend/app/models/agent_run.py`: SQLAlchemy models and enums for agent runs, steps, approvals, and verification state.
- Modify `backend/app/models/__init__.py`: export new models.
- Modify `backend/app/models/user.py`: add user relationship for agent runs.
- Create `backend/app/services/agent_runtime.py`: runtime service for creating runs, recording plans, tool calls, approvals, and completion.
- Create `backend/app/services/agent_planner.py`: deterministic first-pass planner that converts user intent into a small structured plan.
- Create `backend/app/services/agent_policy.py`: permission policy for read, write, destructive, and external-send tool actions.
- Create `backend/app/api/agent_runs.py`: read-only run history and approval endpoints.
- Modify `backend/app/main.py`: include the agent run router.
- Modify `backend/app/api/chat.py`: create an Agent Run for every chat request and record routing, plan, tool calls, result, and extracted task notifications.
- Create `backend/tests/test_agent_runtime.py`: model-free unit tests for runtime serialization and policy behavior.
- Create `backend/tests/test_agent_policy.py`: focused policy tests for approval requirements.
- Create `backend/tests/test_chat_agent_run.py`: integration-level tests around chat runtime hooks with mocked agents.

## Task 1: Add Agent Run Models

**Files:**
- Create: `backend/app/models/agent_run.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/user.py`
- Test: `backend/tests/test_agent_runtime.py`

- [ ] **Step 1: Write the failing model serialization test**

```python
# backend/tests/test_agent_runtime.py
from datetime import datetime, timezone
from uuid import uuid4

from app.models.agent_run import AgentRun, AgentRunStatus, AgentRunStep, AgentRunStepType
from app.services.agent_runtime import serialize_agent_run


def test_serialize_agent_run_includes_steps_and_status():
    run = AgentRun(
        id=uuid4(),
        user_id=uuid4(),
        conversation_id=uuid4(),
        user_message_id=uuid4(),
        intent="gmail",
        status=AgentRunStatus.COMPLETED,
        plan={"summary": "Summarize unread Gmail messages", "steps": ["Read Gmail", "Summarize"]},
        final_response="You have two important emails.",
        created_at=datetime(2026, 5, 29, 10, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 29, 10, 1, tzinfo=timezone.utc),
    )
    run.steps = [
        AgentRunStep(
            id=uuid4(),
            run_id=run.id,
            step_type=AgentRunStepType.TOOL_CALL,
            name="gmail.search_emails",
            status="completed",
            input={"query": "is:unread"},
            output={"count": 2},
            created_at=datetime(2026, 5, 29, 10, 0, tzinfo=timezone.utc),
        )
    ]

    data = serialize_agent_run(run)

    assert data["status"] == "completed"
    assert data["intent"] == "gmail"
    assert data["plan"]["summary"] == "Summarize unread Gmail messages"
    assert data["steps"][0]["name"] == "gmail.search_emails"
    assert data["steps"][0]["output"] == {"count": 2}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_agent_runtime.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.agent_run'`.

- [ ] **Step 3: Add the Agent Run model**

```python
# backend/app/models/agent_run.py
"""Agent run ledger models for auditable agent execution."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentRunStatus(StrEnum):
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRunStepType(StrEnum):
    ROUTE = "route"
    PLAN = "plan"
    TOOL_CALL = "tool_call"
    APPROVAL = "approval"
    VERIFY = "verify"
    FINAL = "final"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    status: Mapped[AgentRunStatus] = mapped_column(SAEnum(AgentRunStatus, name="agent_run_status_enum"), nullable=False, default=AgentRunStatus.PLANNING)
    plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="agent_runs")
    steps = relationship("AgentRunStep", back_populates="run", cascade="all, delete-orphan", order_by="AgentRunStep.created_at")


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_type: Mapped[AgentRunStepType] = mapped_column(SAEnum(AgentRunStepType, name="agent_run_step_type_enum"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run = relationship("AgentRun", back_populates="steps")
```

- [ ] **Step 4: Export and relate the models**

Add to `backend/app/models/__init__.py`:

```python
from app.models.agent_run import AgentRun, AgentRunStatus, AgentRunStep, AgentRunStepType
```

Update `__all__` in `backend/app/models/__init__.py` to:

```python
__all__ = [
    "User",
    "ToolConnection",
    "ToolType",
    "ConnectionStatus",
    "Conversation",
    "Message",
    "MessageRole",
    "Notification",
    "NotificationPriority",
    "Workflow",
    "WorkflowStatus",
    "AgentRun",
    "AgentRunStatus",
    "AgentRunStep",
    "AgentRunStepType",
]
```

Add to `backend/app/models/user.py` inside `User`:

```python
agent_runs = relationship("AgentRun", back_populates="user", cascade="all, delete-orphan")
```

- [ ] **Step 5: Add serialization helper**

```python
# backend/app/services/agent_runtime.py
"""Agent Runtime service helpers."""

from datetime import datetime

from app.models.agent_run import AgentRun


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def serialize_agent_run(run: AgentRun) -> dict:
    return {
        "id": str(run.id),
        "user_id": str(run.user_id),
        "conversation_id": str(run.conversation_id) if run.conversation_id else None,
        "intent": run.intent,
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "plan": run.plan,
        "final_response": run.final_response,
        "error": run.error,
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
        "completed_at": _iso(run.completed_at),
        "steps": [
            {
                "id": str(step.id),
                "step_type": step.step_type.value if hasattr(step.step_type, "value") else str(step.step_type),
                "name": step.name,
                "status": step.status,
                "input": step.input,
                "output": step.output,
                "error": step.error,
                "created_at": _iso(step.created_at),
            }
            for step in getattr(run, "steps", [])
        ],
    }
```

- [ ] **Step 6: Run the model test**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_agent_runtime.py -q
```

Expected: PASS.

## Task 2: Add Tool Permission Policy

**Files:**
- Create: `backend/app/services/agent_policy.py`
- Test: `backend/tests/test_agent_policy.py`

- [ ] **Step 1: Write failing policy tests**

```python
# backend/tests/test_agent_policy.py
from app.services.agent_policy import ToolRisk, classify_tool_call, requires_approval


def test_read_tools_do_not_require_approval():
    decision = classify_tool_call("gmail", "search_emails")

    assert decision.risk == ToolRisk.READ
    assert requires_approval(decision) is False


def test_send_and_delete_tools_require_approval():
    send_decision = classify_tool_call("slack", "send_message")
    delete_decision = classify_tool_call("calendar", "delete_event")

    assert send_decision.risk == ToolRisk.EXTERNAL_SEND
    assert delete_decision.risk == ToolRisk.DESTRUCTIVE
    assert requires_approval(send_decision) is True
    assert requires_approval(delete_decision) is True
```

- [ ] **Step 2: Run policy tests to verify failure**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_agent_policy.py -q
```

Expected: FAIL with missing `app.services.agent_policy`.

- [ ] **Step 3: Implement the policy service**

```python
# backend/app/services/agent_policy.py
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
        return ToolPolicyDecision(tool=tool, action=action, risk=ToolRisk.DESTRUCTIVE, reason="This action can remove or finalize external data.")
    if normalized in EXTERNAL_SEND_ACTIONS:
        return ToolPolicyDecision(tool=tool, action=action, risk=ToolRisk.EXTERNAL_SEND, reason="This action sends or creates visible external content.")
    if normalized.startswith(WRITE_ACTION_PREFIXES):
        return ToolPolicyDecision(tool=tool, action=action, risk=ToolRisk.WRITE, reason="This action changes external state.")
    return ToolPolicyDecision(tool=tool, action=action, risk=ToolRisk.READ, reason="This action only reads external data.")


def requires_approval(decision: ToolPolicyDecision) -> bool:
    return decision.risk in {ToolRisk.WRITE, ToolRisk.EXTERNAL_SEND, ToolRisk.DESTRUCTIVE}
```

- [ ] **Step 4: Run policy tests**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_agent_policy.py -q
```

Expected: PASS.

## Task 3: Add Planner and Runtime Service

**Files:**
- Create: `backend/app/services/agent_planner.py`
- Modify: `backend/app/services/agent_runtime.py`
- Test: `backend/tests/test_agent_runtime.py`

- [ ] **Step 1: Add failing planner/runtime tests**

Append to `backend/tests/test_agent_runtime.py`:

```python
from app.services.agent_planner import build_agent_plan
from app.services.agent_policy import ToolRisk


def test_build_agent_plan_for_gmail_task():
    plan = build_agent_plan(
        user_message="Summarize my unread emails",
        intent="gmail",
        connected_tools=["gmail"],
    )

    assert plan["intent"] == "gmail"
    assert plan["requires_tools"] == ["gmail"]
    assert plan["steps"] == ["Route to gmail specialist", "Execute requested gmail work", "Verify answer addresses the request"]


def test_plan_marks_missing_tool():
    plan = build_agent_plan(
        user_message="Summarize my unread emails",
        intent="gmail",
        connected_tools=[],
    )

    assert plan["blocked"] is True
    assert plan["block_reason"] == "gmail is not connected"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_agent_runtime.py -q
```

Expected: FAIL with missing `app.services.agent_planner`.

- [ ] **Step 3: Implement deterministic planner**

```python
# backend/app/services/agent_planner.py
"""Small deterministic planner for ByteOps agent runs."""


def build_agent_plan(user_message: str, intent: str, connected_tools: list[str]) -> dict:
    required_tools = [] if intent == "general" else [intent]
    missing_tools = [tool for tool in required_tools if tool not in connected_tools]
    blocked = bool(missing_tools)

    if intent == "general":
        steps = ["Answer directly", "Verify answer addresses the request"]
    else:
        steps = [
            f"Route to {intent} specialist",
            f"Execute requested {intent} work",
            "Verify answer addresses the request",
        ]

    return {
        "summary": user_message.strip()[:160],
        "intent": intent,
        "requires_tools": required_tools,
        "steps": steps,
        "blocked": blocked,
        "block_reason": f"{missing_tools[0]} is not connected" if missing_tools else None,
    }
```

- [ ] **Step 4: Add async runtime methods**

Append to `backend/app/services/agent_runtime.py`:

```python
from datetime import timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, AgentRunStatus, AgentRunStep, AgentRunStepType


async def create_agent_run(
    db: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID | None,
    user_message_id: UUID | None,
    intent: str,
    plan: dict,
) -> AgentRun:
    run = AgentRun(
        user_id=user_id,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        intent=intent,
        status=AgentRunStatus.PLANNING if not plan.get("blocked") else AgentRunStatus.FAILED,
        plan=plan,
        error=plan.get("block_reason"),
    )
    db.add(run)
    await db.flush()
    db.add(AgentRunStep(run_id=run.id, step_type=AgentRunStepType.PLAN, name="initial_plan", input={"intent": intent}, output=plan))
    await db.commit()
    await db.refresh(run)
    return run


async def record_agent_step(
    db: AsyncSession,
    *,
    run_id: UUID,
    step_type: AgentRunStepType,
    name: str,
    input: dict | None = None,
    output: dict | None = None,
    status: str = "completed",
    error: str | None = None,
) -> AgentRunStep:
    step = AgentRunStep(
        run_id=run_id,
        step_type=step_type,
        name=name,
        status=status,
        input=input,
        output=output,
        error=error,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def complete_agent_run(db: AsyncSession, run: AgentRun, final_response: str) -> AgentRun:
    run.status = AgentRunStatus.COMPLETED
    run.final_response = final_response
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


async def fail_agent_run(db: AsyncSession, run: AgentRun, error: str) -> AgentRun:
    run.status = AgentRunStatus.FAILED
    run.error = error
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run
```

- [ ] **Step 5: Run runtime tests**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_agent_runtime.py -q
```

Expected: PASS.

## Task 4: Wire Runtime Into Chat

**Files:**
- Modify: `backend/app/api/chat.py`
- Test: `backend/tests/test_chat_agent_run.py`

- [ ] **Step 1: Write an integration-style test for runtime hooks**

```python
# backend/tests/test_chat_agent_run.py
from app.agents.orchestrator import detect_intent
from app.services.agent_planner import build_agent_plan


def test_chat_runtime_plan_for_connected_gmail():
    intent = detect_intent("Summarize my unread emails", [])
    plan = build_agent_plan("Summarize my unread emails", intent, ["gmail"])

    assert intent == "gmail"
    assert plan["blocked"] is False
    assert plan["requires_tools"] == ["gmail"]


def test_chat_runtime_plan_blocks_missing_gmail():
    intent = detect_intent("Summarize my unread emails", [])
    plan = build_agent_plan("Summarize my unread emails", intent, [])

    assert intent == "gmail"
    assert plan["blocked"] is True
    assert plan["block_reason"] == "gmail is not connected"
```

- [ ] **Step 2: Run the test**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_chat_agent_run.py -q
```

Expected: PASS after Task 3.

- [ ] **Step 3: Import runtime helpers in chat API**

Add to `backend/app/api/chat.py`:

```python
from app.models.agent_run import AgentRunStepType
from app.services.agent_planner import build_agent_plan
from app.services.agent_runtime import create_agent_run, record_agent_step, complete_agent_run, fail_agent_run
```

- [ ] **Step 4: Capture the persisted user message**

Replace the user message insert in `_run_chat` with:

```python
user_msg = Message(
    conversation_id=conv.id,
    role=MessageRole.USER,
    content=request.message,
)
db.add(user_msg)
await db.commit()
await db.refresh(user_msg)
```

- [ ] **Step 5: Create the run after connected tools are known**

After `connected_tool_names = [conn.tool_type.value for conn in all_connections]`, add:

```python
plan = build_agent_plan(
    user_message=request.message,
    intent=intent,
    connected_tools=connected_tool_names,
)
agent_run = await create_agent_run(
    db,
    user_id=current_user.id,
    conversation_id=conv.id,
    user_message_id=user_msg.id,
    intent=intent,
    plan=plan,
)
await record_agent_step(
    db,
    run_id=agent_run.id,
    step_type=AgentRunStepType.ROUTE,
    name="intent_routing",
    input={"message": request.message},
    output={"intent": intent, "connected_tools": connected_tool_names},
)
```

- [ ] **Step 6: Record final success and failure**

Before `await queue.put(("done", full_text, str(conv.id)))`, add:

```python
await complete_agent_run(db, agent_run, full_text)
```

Inside the `except Exception as exc` block, before queueing the error, add:

```python
if "agent_run" in locals():
    await fail_agent_run(db, agent_run, str(exc))
```

- [ ] **Step 7: Run chat tests**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_chat_agent_run.py backend/tests/test_chat_activity_notification.py -q
```

Expected: PASS.

## Task 5: Add Agent Run API

**Files:**
- Create: `backend/app/api/agent_runs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_agent_runtime.py`

- [ ] **Step 1: Add API serialization test**

Append to `backend/tests/test_agent_runtime.py`:

```python
def test_serialized_failed_run_exposes_clean_error():
    run = AgentRun(
        id=uuid4(),
        user_id=uuid4(),
        intent="slack",
        status=AgentRunStatus.FAILED,
        error="Slack token expired",
    )

    data = serialize_agent_run(run)

    assert data["status"] == "failed"
    assert data["error"] == "Slack token expired"
```

- [ ] **Step 2: Create read-only run API**

```python
# backend/app/api/agent_runs.py
"""Agent run history API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.agent_run import AgentRun
from app.models.user import User
from app.services.agent_runtime import serialize_agent_run

router = APIRouter(prefix="/api/agent-runs", tags=["agent-runs"])


@router.get("")
async def list_agent_runs(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.user_id == current_user.id)
        .order_by(AgentRun.created_at.desc())
        .limit(50)
    )
    return [serialize_agent_run(run) for run in result.scalars().all()]


@router.get("/{run_id}")
async def get_agent_run(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    run = await db.get(AgentRun, run_id)
    if not run or run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found.")
    return serialize_agent_run(run)
```

- [ ] **Step 3: Register router**

In `backend/app/main.py`, update the API imports:

```python
from app.api import agent_runs, oauth, tools, users, chat, notifications, sync, workflows
```

Inside `create_app`, add:

```python
app.include_router(agent_runs.router)
```

- [ ] **Step 4: Run runtime tests**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_agent_runtime.py -q
```

Expected: PASS.

## Task 6: Connect Runtime To Workflows

**Files:**
- Create: `backend/app/services/workflow_runner.py`
- Modify: `backend/app/api/workflows.py`
- Test: `backend/tests/test_workflows.py`

- [ ] **Step 1: Write workflow runner test**

Append to `backend/tests/test_workflows.py`:

```python
from app.services.workflow_runner import build_workflow_run_plan


def test_build_workflow_run_plan_uses_trigger_and_actions():
    plan = build_workflow_run_plan(
        workflow_name="Daily email brief",
        trigger={"type": "schedule", "label": "Every weekday at 9:00 AM"},
        actions=[{"tool": "gmail", "label": "Summarize unread important emails"}],
    )

    assert plan["summary"] == "Run workflow: Daily email brief"
    assert plan["trigger"] == "Every weekday at 9:00 AM"
    assert plan["actions"] == ["Summarize unread important emails"]
```

- [ ] **Step 2: Implement workflow runner plan builder**

```python
# backend/app/services/workflow_runner.py
"""Workflow execution helpers built on the Agent Runtime."""


def build_workflow_run_plan(workflow_name: str, trigger: dict, actions: list) -> dict:
    trigger_label = trigger.get("label") if isinstance(trigger, dict) else None
    action_labels: list[str] = []
    for action in actions:
        if isinstance(action, dict):
            action_labels.append(action.get("label") or action.get("name") or action.get("tool") or "Unnamed action")
        elif isinstance(action, str):
            action_labels.append(action)
    return {
        "summary": f"Run workflow: {workflow_name}",
        "trigger": trigger_label or "Manual run",
        "actions": action_labels,
        "blocked": False,
    }
```

- [ ] **Step 3: Update manual workflow run to record execution metadata**

In `backend/app/api/workflows.py`, import:

```python
from app.services.workflow_runner import build_workflow_run_plan
```

Inside `run_workflow`, before commit:

```python
workflow.metadata_ = {
    **(workflow.metadata_ or {}),
    "last_plan": build_workflow_run_plan(
        workflow_name=workflow.name,
        trigger=workflow.trigger or {},
        actions=workflow.actions or [],
    ),
}
```

If the current `Workflow` model has no `metadata_` column, add one in `backend/app/models/workflow.py`:

```python
metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True, default=dict)
```

- [ ] **Step 4: Run workflow tests**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_workflows.py -q
```

Expected: PASS.

## Acceptance Checks

- [ ] Every chat request creates an Agent Run.
- [ ] Every Agent Run stores intent, plan, status, and final result or error.
- [ ] Tool calls can be classified as read, write, external-send, or destructive.
- [ ] Write, send, and destructive actions have a backend policy decision that requires approval.
- [ ] Agent Run history is readable through `/api/agent-runs`.
- [ ] Workflows can reuse runtime plan structure.
- [ ] Focused tests pass for runtime, policy, chat hooks, workflows, and activity notifications.

## Commands To Run Before Completion

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests/test_agent_runtime.py backend/tests/test_agent_policy.py backend/tests/test_chat_agent_run.py backend/tests/test_workflows.py backend/tests/test_chat_activity_notification.py -q
```

```powershell
cd frontend
npm run test:run -- tests/context-panel.test.tsx
```

## Risks

- Database migrations are not currently visible in the repo. If production uses migrations, create an Alembic migration for `agent_runs`, `agent_run_steps`, and any workflow metadata column before deployment.
- Existing specialist agents call MCP tools directly. Approval enforcement becomes complete only after tool calls are routed through a shared policy-aware executor.
- The first planner is deterministic by design. Add LLM planning only after ledger, policy, and verification are stable.

## ADR Suggestion

📋 Architectural decision detected: internal Agent Runtime instead of immediate external framework adoption. Document reasoning and tradeoffs? Run `/sp.adr internal-agent-runtime`.
