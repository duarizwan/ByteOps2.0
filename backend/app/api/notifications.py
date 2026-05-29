"""Notifications API.

Provides CRUD endpoints for user notifications.
Notifications are created by agents after tool interactions and
persist in PostgreSQL so the activity feed survives page refreshes.

Endpoints:
  GET    /api/notifications              — list (newest first, optional ?unread_only=true)
  POST   /api/notifications              — create (called by agents internally)
  PATCH  /api/notifications/{id}/read    — mark one as read
  POST   /api/notifications/read-all     — mark all as read
  DELETE /api/notifications/{id}         — dismiss / hard delete
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.user import User
from app.models.notification import Notification, NotificationPriority

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: str
    source_tool: str
    title: str
    content: str | None
    priority: str
    is_read: bool
    created_at: str
    metadata: dict | None = None

    model_config = {"from_attributes": True}


class CreateNotificationRequest(BaseModel):
    source_tool: str
    title: str
    content: str | None = None
    priority: str = "medium"
    metadata: dict | None = None


# ── Helper ────────────────────────────────────────────────────────────────────

def _serialize(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=str(n.id),
        source_tool=n.source_tool,
        title=n.title,
        content=n.content,
        priority=n.priority.value if hasattr(n.priority, "value") else str(n.priority),
        is_read=n.is_read,
        created_at=n.created_at.isoformat(),
        metadata=n.metadata_,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, le=200),
) -> list[NotificationOut]:
    """Return notifications for the current user, newest first."""
    q = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        q = q.where(Notification.is_read == False)  # noqa: E712
    q = q.order_by(Notification.created_at.desc()).limit(limit)

    result = await db.execute(q)
    return [_serialize(n) for n in result.scalars().all()]


@router.post("", response_model=NotificationOut, status_code=201)
async def create_notification(
    body: CreateNotificationRequest,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationOut:
    """Create a notification. Called by agents after tool interactions."""
    priority_map = {
        "low": NotificationPriority.LOW,
        "medium": NotificationPriority.MEDIUM,
        "high": NotificationPriority.HIGH,
        "urgent": NotificationPriority.URGENT,
    }
    priority = priority_map.get(body.priority.lower(), NotificationPriority.MEDIUM)

    notification = Notification(
        user_id=current_user.id,
        source_tool=body.source_tool,
        title=body.title,
        content=body.content,
        priority=priority,
        metadata_=body.metadata or {},
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return _serialize(notification)


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationOut:
    """Mark a single notification as read."""
    n = await db.get(Notification, notification_id)
    if not n or n.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    n.is_read = True
    await db.commit()
    await db.refresh(n)
    return _serialize(n)


@router.post("/read-all", status_code=204)
async def mark_all_read(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Mark all of the current user's notifications as read."""
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await db.commit()


@router.delete("/{notification_id}", status_code=204)
async def dismiss_notification(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Permanently dismiss/delete a notification."""
    n = await db.get(Notification, notification_id)
    if not n or n.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    await db.delete(n)
    await db.commit()
