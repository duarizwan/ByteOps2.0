"""Users API — sync Clerk user data into DB."""

from typing import Annotated
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_clerk_user
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/users", tags=["users"])


class UserResponse(BaseModel):
    id: str
    clerk_id: str
    email: str
    display_name: str | None

    model_config = {"from_attributes": True}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
) -> User:
    """Return the currently authenticated user. Creates the row if it doesn't exist."""
    return current_user


@router.post("/sync", response_model=UserResponse)
async def sync_user(
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Called on dashboard load to ensure the user row exists.
    The auth dependency already handles creation, so this is a no-op if the user exists.
    """
    return current_user
