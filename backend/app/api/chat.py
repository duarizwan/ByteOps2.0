"""Chat API endpoint.

Routes user messages through the agent system and manages conversations/messages.

SSE event types (POST /api/chat):
  - "delta"            → text chunk from the model (streaming)
  - "tool_call_start"  → agent started calling an MCP tool
  - "tool_call_result" → MCP tool returned a result
  - "done"             → stream finished; includes conversation_id
  - "error"            → error occurred
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.models.tool_connection import ToolConnection, ToolType, ConnectionStatus

from app.agents.orchestrator import detect_intent_smart, parse_handoff, stream_general_response
from app.agents.gmail_agent import run_gmail_agent
from app.agents.calendar_agent import run_calendar_agent
from app.agents.github_agent import run_github_agent
from app.agents.slack_agent import run_slack_agent
from app.agents.jira_agent import run_jira_agent
from app.agents.dropbox_agent import run_dropbox_agent
from app.services.sync.token_refresh import ensure_fresh_token
from app.models.notification import Notification, NotificationPriority
from app.models.agent_run import AgentRunStatus, AgentRunStepType
from app.services.agent_planner import build_agent_plan
from app.services.agent_runtime import (
    complete_agent_run,
    create_agent_run,
    fail_agent_run,
    record_agent_step,
)
from app.services.workflow_creation import (
    build_workflow_draft,
    create_workflow_from_prompt,
    is_workflow_creation_request,
    workflow_draft_response,
    workflow_creation_response,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# ── Specialist dispatch table ─────────────────────────────────────────────────
# One entry per tool-agent. "refresh" marks OAuth tokens that expire and must be
# refreshed before spawning the MCP subprocess.
_SPECIALISTS: dict[str, dict] = {
    "gmail": {
        "tool_type": ToolType.GMAIL,
        "runner": run_gmail_agent,
        "feature_name": "Gmail",
        "connect_hint": "your Gmail account first",
        "refresh": True,
    },
    "calendar": {
        "tool_type": ToolType.CALENDAR,
        "runner": run_calendar_agent,
        "feature_name": "Calendar",
        "connect_hint": "your Google Calendar account",
        "refresh": True,
    },
    "github": {
        "tool_type": ToolType.GITHUB,
        "runner": run_github_agent,
        "feature_name": "GitHub",
        "connect_hint": "your GitHub account",
        "refresh": False,
    },
    "slack": {
        "tool_type": ToolType.SLACK,
        "runner": run_slack_agent,
        "feature_name": "Slack",
        "connect_hint": "your Slack workspace",
        "refresh": False,
    },
    "jira": {
        "tool_type": ToolType.JIRA,
        "runner": run_jira_agent,
        "feature_name": "Jira",
        "connect_hint": "your Jira account",
        "refresh": True,
    },
    "dropbox": {
        "tool_type": ToolType.DROPBOX,
        "runner": run_dropbox_agent,
        "feature_name": "Dropbox",
        "connect_hint": "your Dropbox account",
        "refresh": False,
    },
}

CHAT_STREAM_IDLE_TIMEOUT_SECONDS = 30

_NOT_CONNECTED_PHRASES = ("please connect", "connect your", "connection has expired", "not connected")
_PRIORITY_MAP = {
    "low": NotificationPriority.LOW,
    "medium": NotificationPriority.MEDIUM,
    "high": NotificationPriority.HIGH,
    "urgent": NotificationPriority.URGENT,
}
_TASK_CUES = (
    "action required",
    "asked you to",
    "assigned to you",
    "your approval",
    "by friday",
    "by tomorrow",
    "follow up",
    "need you to",
    "needs your",
    "please review",
    "waiting on you",
    "waiting for you",
    "todo",
    "to-do",
)
_HIGH_PRIORITY_CUES = (
    "action required",
    "approval",
    "approve",
    "asap",
    "attention",
    "blocked",
    "by friday",
    "by tomorrow",
    "deadline",
    "due",
    "important",
    "needs attention",
    "urgent",
)


def _first_attention_line(response_text: str) -> str:
    """Return a concise user-facing summary from an agent response."""
    cleaned = _clean_activity_text(response_text)
    if not cleaned:
        return "Workspace item needs attention"
    first_sentence = cleaned.split(".")[0].strip()
    title = first_sentence or cleaned
    if first_sentence and cleaned.startswith(f"{first_sentence}."):
        title = f"{first_sentence}."
    return title[:120] + ("..." if len(title) > 120 else "")


def _clean_activity_text(text: str) -> str:
    """Remove markdown/list/table marker characters from activity text."""
    cleaned = " ".join(text.replace("*", " ").replace("-", " ").replace("|", " ").split())
    for mark in (".", ",", "!", "?", ";", ":"):
        cleaned = cleaned.replace(f" {mark}", mark)
    return cleaned


def _build_activity_notification_payload(
    source_tool: str,
    user_message: str,
    response_text: str,
) -> dict:
    """Build an activity item without repeating the raw chat prompt."""
    title = _first_attention_line(response_text)
    text = f"{title} {response_text}".lower()
    is_task = any(cue in text for cue in _TASK_CUES)
    is_high = any(cue in text for cue in _HIGH_PRIORITY_CUES)
    priority = "high" if is_high else "medium"

    return {
        "source_tool": source_tool,
        "title": title,
        "content": _clean_activity_text(response_text)[:300] if response_text else None,
        "priority": priority,
        "metadata": {
            "from_chat": True,
            "category": "task" if is_task else "alert",
            "action_required": is_task,
            "attention_title": title,
            "extracted_priority": priority,
            "user_query": user_message,
        },
    }


async def _save_activity_notification(
    db: AsyncSession,
    user_id,
    source_tool: str,
    user_message: str,
    response_text: str,
) -> None:
    """Persist a chat-triggered tool interaction as a notification so it
    surfaces in the right-panel Alerts / Tasks feed."""
    if not response_text or parse_handoff(response_text):
        return
    # Skip "please connect" or error responses
    snippet = response_text.lower()[:120]
    if any(p in snippet for p in _NOT_CONNECTED_PHRASES):
        return

    payload = _build_activity_notification_payload(source_tool, user_message, response_text)

    db.add(Notification(
        user_id=user_id,
        source_tool=payload["source_tool"],
        title=payload["title"],
        content=payload["content"],
        priority=_PRIORITY_MAP.get(payload["priority"], NotificationPriority.MEDIUM),
        metadata_=payload["metadata"],
    ))
    try:
        await db.commit()
    except Exception:
        await db.rollback()


class ChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[MessageOut]


class RenameRequest(BaseModel):
    title: str


# ── SSE formatting ────────────────────────────────────────────────────────────

def _sse(event_type: str, payload: str, **extra) -> str:
    """Format a single SSE data line."""
    data = json.dumps({"type": event_type, "content": payload, **extra})
    return f"data: {data}\n\n"


# ── Producer ──────────────────────────────────────────────────────────────────

async def _run_chat(
    request: ChatRequest,
    current_user: User,
    db: AsyncSession,
    queue: asyncio.Queue,
) -> None:
    """Producer coroutine: runs the full agent pipeline and pushes events
    into `queue`. Always pushes a terminal tuple at the end."""
    try:
        # ── 1. Resolve or create conversation ────────────────────────────────
        if request.conversation_id:
            conv = await db.get(Conversation, request.conversation_id)
            if not conv or conv.user_id != current_user.id:
                await queue.put(("error", "Conversation not found."))
                return
        else:
            conv = Conversation(
                user_id=current_user.id,
                title=request.message[:80],
            )
            db.add(conv)
            await db.commit()
            await db.refresh(conv)

        # ── 2. Persist user message ───────────────────────────────────────────
        user_msg = Message(
            conversation_id=conv.id,
            role=MessageRole.USER,
            content=request.message,
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)

        # ── 3. Load conversation history ──────────────────────────────────────
        # Fetch only the last 40 messages at the SQL level (ORDER BY DESC LIMIT)
        # to avoid loading the entire history into memory and slicing in Python.
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(40)
        )
        # Reverse so history is oldest-first for the LLM context window
        history = [
            {"role": msg.role.value, "content": msg.content}
            for msg in reversed(result.scalars().all())
            if msg.role in (MessageRole.USER, MessageRole.ASSISTANT)
        ]

        # ── 4. Route based on intent ──────────────────────────────────────────
        intent = "workflow" if is_workflow_creation_request(request.message) else await detect_intent_smart(request.message, history)
        full_text = ""

        # Query ALL connected tools once (used for routing + dynamic prompt)
        all_conns_result = await db.execute(
            select(ToolConnection).where(
                ToolConnection.user_id == current_user.id,
                ToolConnection.status == ConnectionStatus.CONNECTED,
            )
        )
        all_connections = all_conns_result.scalars().all()
        connected_tool_names = [conn.tool_type.value for conn in all_connections]
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
        agent_run.status = AgentRunStatus.RUNNING
        await db.commit()

        if intent == "workflow":
            draft = build_workflow_draft(request.message, connected_tool_names)
            full_text = workflow_draft_response(draft)
            # Chat-created workflows always pause for user review before saving.
            # The workflow_draft event carries all display content; no plain delta needed.
            await queue.put(("workflow_draft", {"run_id": str(agent_run.id), **draft}))
            await record_agent_step(
                db,
                run_id=agent_run.id,
                step_type=AgentRunStepType.FINAL,
                name="workflow_draft_needs_review",
                input={"message": request.message},
                output=draft,
            )
        else:
            async def dispatch_once(active_intent: str) -> str:
                """Run one specialist (or the general orchestrator); return final text."""
                spec = _SPECIALISTS.get(active_intent)
                if spec is None:
                    return await stream_general_response(
                        history, queue, connected_tools=connected_tool_names
                    )

                conn = next(
                    (c for c in all_connections if c.tool_type == spec["tool_type"]),
                    None,
                )
                if not conn:
                    text = (
                        f"To use {spec['feature_name']} features, please connect "
                        f"{spec['connect_hint']} via **Settings → Connections**."
                    )
                    await queue.put(text)
                    return text

                # Refresh expiring OAuth tokens before spawning the MCP subprocess
                if spec["refresh"] and not await ensure_fresh_token(conn, db):
                    text = (
                        f"Your {spec['feature_name']} connection has expired. "
                        "Please reconnect via **Settings → Connections**."
                    )
                    await queue.put(text)
                    return text

                text = await spec["runner"](
                    user_message=request.message,
                    history=history,
                    tool_connection=conn,
                    queue=queue,
                    run_id=agent_run.id,
                    db=db,
                )
                await _save_activity_notification(
                    db, current_user.id, active_intent, request.message, text
                )
                return text

            full_text = await dispatch_once(intent)

            # A specialist returns a HANDOFF sentinel when the request is outside
            # its scope — re-route once, invisibly to the user.
            handoff_target = parse_handoff(full_text)
            if handoff_target is not None:
                next_intent = handoff_target if handoff_target != intent else "general"
                await record_agent_step(
                    db,
                    run_id=agent_run.id,
                    step_type=AgentRunStepType.ROUTE,
                    name="agent_handoff",
                    input={"from": intent, "message": request.message},
                    output={"to": next_intent},
                )
                full_text = await dispatch_once(next_intent)
                if parse_handoff(full_text) is not None:
                    # Second handoff in a row — let the general orchestrator answer.
                    full_text = await dispatch_once("general")

        # ── 5. Persist assistant reply ────────────────────────────────────────
        db.add(Message(
            conversation_id=conv.id,
            role=MessageRole.ASSISTANT,
            content=full_text,
        ))
        await db.commit()
        await complete_agent_run(db, agent_run, full_text)

        await queue.put(("done", full_text, str(conv.id)))

    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "agent_run" in locals():
            await fail_agent_run(db, agent_run, msg)
        if "429" in msg or "rate_limit" in msg.lower() or "quota" in msg.lower():
            await queue.put((
                "error",
                "The AI is rate-limited right now. Please wait 15–30 seconds and try again."
            ))
        elif "401" in msg or "authentication_error" in msg.lower() or "invalid x-api-key" in msg.lower() or "invalid_api_key" in msg.lower():
            await queue.put((
                "error",
                "AI provider authentication failed. Your API key is invalid or expired — "
                "update CLAUDE_API_KEY (or GEMINI_API_KEY / GROQ_API_KEY) in backend/.env and restart the server."
            ))
        else:
            await queue.put(("error", msg))


# ── SSE Consumer / HTTP handler ────────────────────────────────────────────────

@router.post("")
async def chat_handler(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Entry point for all user messages into the ByteOps Agent system."""

    queue: asyncio.Queue = asyncio.Queue()

    async def sse_stream() -> AsyncGenerator[str, None]:
        chat_task = asyncio.create_task(_run_chat(request, current_user, db, queue))
        try:
            while True:
                queue_task = asyncio.create_task(queue.get())
                try:
                    done, pending = await asyncio.wait(
                        {queue_task, chat_task},
                        timeout=CHAT_STREAM_IDLE_TIMEOUT_SECONDS,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                except asyncio.TimeoutError:
                    yield _sse("error", "Chat request timed out before ByteOps could respond.")
                    break

                for pending_task in pending:
                    if pending_task is queue_task:
                        pending_task.cancel()

                if not done:
                    if not chat_task.done():
                        yield _sse("ping", "keepalive")
                        continue
                    yield _sse("error", "Chat request timed out before ByteOps could respond.")
                    break

                if chat_task in done and queue_task not in done:
                    if chat_task.exception():
                        yield _sse("error", "Chat request failed before ByteOps could respond.")
                    else:
                        yield _sse("error", "Chat request ended before ByteOps could respond.")
                    break

                item = queue_task.result()

                if isinstance(item, str):
                    # Plain string → streaming text delta
                    yield _sse("delta", item)

                elif item is None:
                    # Sentinel from stream_general_response — done event follows
                    continue

                elif isinstance(item, tuple):
                    match item:
                        case ("done", content, conv_id):
                            yield _sse("done", content, conversation_id=conv_id)
                            break
                        case ("error", content):
                            yield _sse("error", content)
                            break
                        case ("tool_call_start", tool_name, args_json):
                            yield _sse("tool_call_start", "", tool=tool_name, args=args_json)
                        case ("tool_call_result", tool_name, result_text):
                            yield _sse("tool_call_result", result_text, tool=tool_name)
                        case ("approval_required", approval_data):
                            import json as _json
                            approval_dict = dict(approval_data) if isinstance(approval_data, dict) else {}
                            summary = approval_dict.pop("summary", "")
                            yield _sse("approval_required", summary, **approval_dict)
                        case ("workflow_draft", draft_data):
                            draft_dict = dict(draft_data) if isinstance(draft_data, dict) else {}
                            yield _sse("workflow_draft", "", **draft_dict)
                        case _:
                            # Unknown tuple — ignore
                            pass

        finally:
            chat_task.cancel()

    return StreamingResponse(sse_stream(), media_type="text/event-stream")


# ══════════════════════════════════════════════════════════════════════════════
# Conversation Management Endpoints
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/conversations")
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ConversationSummary]:
    """Return all non-archived conversations for the current user, newest first."""
    # Single query: conversations + their message counts via LEFT JOIN + GROUP BY
    result = await db.execute(
        select(Conversation, func.count(Message.id).label("message_count"))
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.is_archived == False,  # noqa: E712
        )
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    rows = result.all()

    return [
        ConversationSummary(
            id=str(conv.id),
            title=conv.title,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            message_count=count,
        )
        for conv, count in rows
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationDetail:
    """Return a conversation with its full message history."""
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return ConversationDetail(
        id=str(conv.id),
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        messages=[
            MessageOut(
                id=str(msg.id),
                role=msg.role.value,
                content=msg.content,
                created_at=msg.created_at.isoformat(),
            )
            for msg in messages
        ],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Permanently delete a conversation and all its messages."""
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    await db.delete(conv)
    await db.commit()


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: UUID,
    body: RenameRequest,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationSummary:
    """Rename a conversation's title."""
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    conv.title = body.title.strip()[:500]
    await db.commit()
    await db.refresh(conv)

    count_result = await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == conv.id)
    )
    message_count = count_result.scalar_one()

    return ConversationSummary(
        id=str(conv.id),
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        message_count=message_count,
    )
