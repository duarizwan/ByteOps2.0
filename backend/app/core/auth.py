"""Clerk JWT authentication dependency for FastAPI routes."""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Annotated
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()
_jwks_cache: dict | None = None

# Shared HTTP client — connection pool reused across all requests
_http_client = httpx.AsyncClient(timeout=10.0)

# In-memory user cache: clerk_id -> (snapshot, expires_at)
# Avoids a DB round-trip on every authenticated request after first login.
_USER_CACHE_TTL = 300  # 5 minutes
_user_cache: dict[str, tuple["_CachedUserSnapshot", float]] = {}


@dataclass(frozen=True)
class _CachedUserSnapshot:
    id: uuid.UUID
    clerk_id: str
    email: str
    display_name: str | None
    avatar_url: str | None


def _snapshot_user(user: User) -> _CachedUserSnapshot:
    return _CachedUserSnapshot(
        id=user.id,
        clerk_id=user.clerk_id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )


def _user_from_snapshot(snapshot: _CachedUserSnapshot) -> User:
    """Reconstruct a detached User for read-only auth (uses .id in queries)."""
    return User(
        id=snapshot.id,
        clerk_id=snapshot.clerk_id,
        email=snapshot.email,
        display_name=snapshot.display_name,
        avatar_url=snapshot.avatar_url,
    )


async def _get_clerk_jwks(force_refresh: bool = False) -> dict:
    """Fetch Clerk JWKS (cached after first call).

    Pass force_refresh=True to bypass the cache — used after a JWTError to
    gracefully handle Clerk key rotation without requiring a server restart.
    """
    global _jwks_cache
    if _jwks_cache is not None and not force_refresh:
        return _jwks_cache

    settings = get_settings()
    if not settings.clerk_issuer:
        raise HTTPException(
            status_code=500,
            detail=(
                "CLERK_ISSUER is not configured. "
                "Add CLERK_ISSUER=https://<your-subdomain>.clerk.accounts.dev to backend/.env"
            ),
        )

    issuer = settings.clerk_issuer.rstrip("/")
    resp = await _http_client.get(f"{issuer}/.well-known/jwks.json")
    resp.raise_for_status()
    _jwks_cache = resp.json()
    key_count = len(_jwks_cache.get("keys", []))
    logger.info("Clerk JWKS fetched — %d signing key(s) from %s", key_count, issuer)
    return _jwks_cache


async def _fetch_clerk_user(clerk_id: str) -> tuple[str, str | None]:
    """
    Fetch the user's primary email and display name from the Clerk REST API.
    Used when the JWT doesn't carry email claims (Clerk's default behaviour).
    Returns (email, display_name).
    """
    settings = get_settings()
    if not settings.clerk_secret_key:
        raise HTTPException(
            status_code=500,
            detail="CLERK_SECRET_KEY not configured — cannot fetch user details",
        )

    resp = await _http_client.get(
        f"https://api.clerk.com/v1/users/{clerk_id}",
        headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
    )
    if resp.status_code == 404:
        raise HTTPException(status_code=401, detail="Clerk user not found")
    resp.raise_for_status()

    data = resp.json()

    # Primary email address
    email_addresses = data.get("email_addresses", [])
    primary_email_id = data.get("primary_email_address_id")
    email = next(
        (e["email_address"] for e in email_addresses if e.get("id") == primary_email_id),
        email_addresses[0]["email_address"] if email_addresses else None,
    )

    # Display name
    first = data.get("first_name") or ""
    last = data.get("last_name") or ""
    display_name = f"{first} {last}".strip() or data.get("username") or None

    return email, display_name


async def get_current_clerk_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Validate Clerk JWT and return the corresponding User row.
    Creates the user row on first request by calling the Clerk REST API.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    settings = get_settings()
    issuer = settings.clerk_issuer.rstrip("/") if settings.clerk_issuer else None

    def _decode(jwks: dict) -> dict:
        """Attempt JWT decode, raises JWTError on any failure."""
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=issuer,
            # Clerk session tokens may include an `aud` claim that is not
            # fixed for this backend — skip audience, rely on signature + issuer.
            options={"verify_aud": False},
        )

    try:
        # First attempt with cached JWKS
        jwks = await _get_clerk_jwks()
        try:
            payload = _decode(jwks)
        except JWTError as exc:
            # Cached JWKS might be stale after a Clerk key rotation.
            # Invalidate the cache and retry once with fresh keys.
            logger.warning(
                "JWT decode failed with cached JWKS (%s) — refreshing keys and retrying", exc
            )
            global _jwks_cache
            _jwks_cache = None
            jwks = await _get_clerk_jwks(force_refresh=True)
            payload = _decode(jwks)  # raises JWTError if still invalid

        clerk_id: str | None = payload.get("sub")
        if not clerk_id:
            raise credentials_exception

    except JWTError as exc:
        logger.error(
            "Clerk JWT validation failed — issuer=%s error=%s "
            "(check CLERK_ISSUER in backend/.env matches your Clerk dashboard)",
            issuer, exc,
        )
        raise credentials_exception

    # Fast path: return cached user snapshot without a DB round-trip
    now = time.time()
    cached = _user_cache.get(clerk_id)
    if cached is not None:
        snapshot, expires_at = cached
        if now < expires_at:
            return _user_from_snapshot(snapshot)
        del _user_cache[clerk_id]

    # Cache miss — look up user in DB
    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()

    if user is None:
        # First login — fetch full profile from Clerk REST API
        email, display_name = await _fetch_clerk_user(clerk_id)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot determine email for this Clerk user",
            )
        user = User(clerk_id=clerk_id, email=email, display_name=display_name)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Populate cache for subsequent requests
    _user_cache[clerk_id] = (_snapshot_user(user), now + _USER_CACHE_TTL)
    return user
