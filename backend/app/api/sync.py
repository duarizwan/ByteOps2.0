"""Sync API — trigger, status, and debug endpoints."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.notification import Notification
from app.models.tool_connection import ConnectionStatus, ToolConnection, ToolType
from app.models.user import User
from app.services.sync.scheduler import trigger_immediate_sync, _SYNC_INTERVAL_MINUTES
from app.services.sync.token_refresh import ensure_fresh_token

router = APIRouter(prefix="/api/sync", tags=["sync"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class ToolSyncStatus(BaseModel):
    tool: str
    is_syncing: bool
    last_synced_at: str | None        # ISO string or null
    next_sync_at: str | None          # ISO string or null
    status: str                        # "syncing" | "ok" | "never" | "expired"


class SyncStatusResponse(BaseModel):
    tools: list[ToolSyncStatus]
    sync_interval_minutes: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SyncStatusResponse:
    """Return sync state for each of the user's connected tools."""
    result = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.status.in_([ConnectionStatus.CONNECTED, ConnectionStatus.EXPIRED]),
        )
    )
    connections = result.scalars().all()

    tools_out: list[ToolSyncStatus] = []
    for conn in connections:
        meta: dict = conn.metadata_ or {}
        is_syncing: bool = meta.get("is_syncing", False)
        last_synced_raw: str | None = meta.get("last_synced_at")

        # Compute next_sync_at
        if last_synced_raw:
            last_dt = datetime.fromisoformat(last_synced_raw)
            next_dt = last_dt + timedelta(minutes=_SYNC_INTERVAL_MINUTES)
            next_sync_at = next_dt.isoformat()
        else:
            next_sync_at = None

        # Determine status label
        if conn.status == ConnectionStatus.EXPIRED:
            status_label = "expired"
        elif is_syncing:
            status_label = "syncing"
        elif last_synced_raw is None:
            status_label = "never"
        else:
            status_label = "ok"

        tools_out.append(
            ToolSyncStatus(
                tool=conn.tool_type.value,
                is_syncing=is_syncing,
                last_synced_at=last_synced_raw,
                next_sync_at=next_sync_at,
                status=status_label,
            )
        )

    return SyncStatusResponse(
        tools=tools_out,
        sync_interval_minutes=_SYNC_INTERVAL_MINUTES,
    )


@router.post("/trigger", status_code=202)
async def trigger_sync(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Trigger an immediate sync for all of the current user's connected tools."""
    result = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.status == ConnectionStatus.CONNECTED,
        )
    )
    connections = result.scalars().all()

    triggered = []
    for conn in connections:
        await trigger_immediate_sync(
            user_id=conn.user_id,
            tool_type=conn.tool_type,
        )
        triggered.append(conn.tool_type.value)

    return {
        "message": f"Sync triggered for {len(triggered)} tool(s).",
        "tools": triggered,
    }


@router.post("/reset", status_code=200)
async def reset_sync_flags(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Clear any stuck is_syncing flags — use after a server crash or deploy."""
    result = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == current_user.id,
        )
    )
    connections = result.scalars().all()

    fixed = 0
    for conn in connections:
        meta = dict(conn.metadata_ or {})
        if meta.get("is_syncing"):
            conn.metadata_ = {**meta, "is_syncing": False}
            fixed += 1

    await db.commit()
    return {"message": f"Reset {fixed} stuck connection(s)."}


@router.get("/debug/gmail")
async def debug_gmail_sync(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Synchronous debug endpoint. Runs the exact query the sync job uses and returns raw results."""
    conn = await db.scalar(
        select(ToolConnection).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.tool_type == ToolType.GMAIL,
        )
    )
    if not conn:
        return {"error": "No Gmail connection"}

    token_ok = await ensure_fresh_token(conn, db)
    
    meta = conn.metadata_ or {}
    last_synced = meta.get("last_synced_at")
    
    # Replicate query logic
    if not last_synced:
        query = "is:unread newer_than:7d"
    else:
        dt = datetime.fromisoformat(last_synced)
        query = f"is:unread after:{dt.strftime('%Y/%m/%d')}"

    headers = {"Authorization": f"Bearer {conn.access_token}"}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            list_resp = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params={"q": query, "maxResults": 10},
            )
            
            return {
                "token_fresh": token_ok,
                "query": query,
                "status_code": list_resp.status_code,
                "raw_response": list_resp.json() if list_resp.status_code == 200 else list_resp.text
            }
    except Exception as e:
        return {"error": str(e)}
