"""Tools API — list connected tool statuses for the current user."""

from typing import Annotated
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.user import User
from app.models.tool_connection import ToolConnection, ToolType, ConnectionStatus

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolConnectionResponse(BaseModel):
    id: uuid.UUID
    tool_type: ToolType
    status: ConnectionStatus
    scopes: str | None
    connected_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_custom(cls, tc: ToolConnection) -> "ToolConnectionResponse":
        return cls(
            id=tc.id,
            tool_type=tc.tool_type,
            status=tc.status,
            scopes=tc.scopes,
            connected_at=tc.created_at,
        )


@router.get("/connections", response_model=list[ToolConnectionResponse])
async def list_connections(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ToolConnectionResponse]:
    """Return all active tool connections for the current user."""
    result = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.status != ConnectionStatus.DISCONNECTED,
        )
    )
    connections = result.scalars().all()
    return [ToolConnectionResponse.from_orm_custom(tc) for tc in connections]
