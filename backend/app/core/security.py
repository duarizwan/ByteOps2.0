"""Clerk JWT verification and auth dependencies for FastAPI."""

from typing import Annotated
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import get_settings

security_scheme = HTTPBearer()


async def verify_clerk_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
) -> dict:
    """Verify a Clerk JWT and return the decoded claims.

    Uses Clerk's backend API to verify the session token.
    Returns the user claims dict with at least 'sub' (clerk user id).
    """
    token = credentials.credentials
    settings = get_settings()

    try:
        # Verify token via Clerk's JWKS / backend verification
        # For production: use PyJWT with Clerk's JWKS endpoint
        # For now: use Clerk's backend API to verify the session
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.clerk.com/v1/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        user_data = response.json()
        return {
            "sub": user_data.get("id"),
            "email": user_data.get("email_addresses", [{}])[0].get("email_address", ""),
            "name": (
                f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                or user_data.get("username", "")
            ),
            "avatar_url": user_data.get("image_url"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        ) from e


async def get_current_user_clerk_id(
    claims: Annotated[dict, Depends(verify_clerk_token)],
) -> str:
    """Extract the Clerk user ID from verified token claims."""
    clerk_id = claims.get("sub")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )
    return clerk_id
