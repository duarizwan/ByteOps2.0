"""Token refresh utility.

Ensures a ToolConnection has a valid, non-expired access token before
any background sync job runs. Handles Google OAuth2 token refresh only
for now; extend with per-provider logic as more tools are added.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_connection import ConnectionStatus, ToolConnection

logger = logging.getLogger(__name__)

# Shared HTTP client — reused across all token refresh calls
_http_client = httpx.AsyncClient(timeout=10.0)

# Refresh the token if it expires within this window (avoids races)
_EXPIRY_BUFFER = timedelta(minutes=5)

# Google token endpoint (used by Gmail, Calendar)
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Which ToolTypes use Google OAuth (share the same refresh endpoint)
_GOOGLE_TOOLS = {"gmail", "calendar"}


async def ensure_fresh_token(
    connection: ToolConnection,
    db: AsyncSession,
) -> bool:
    """Ensure the connection's access token is valid.

    Returns True if the token is valid (or was refreshed successfully).
    Returns False if the token cannot be refreshed — caller should skip sync.

    Side effects on success:
      - Updates connection.access_token (and token_expires_at) in DB.

    Side effects on revocation:
      - Sets connection.status = EXPIRED in DB.
    """
    tool = connection.tool_type.value.lower()

    # ── 1. Check if token is still fresh enough ───────────────────────────────
    if connection.token_expires_at:
        remaining = connection.token_expires_at - datetime.now(timezone.utc)
        if remaining > _EXPIRY_BUFFER:
            return True  # still valid

    # ── 2. No refresh token means we can't refresh ────────────────────────────
    if not connection.refresh_token:
        logger.warning(
            "No refresh token for %s connection user=%s — skipping sync.",
            tool,
            connection.user_id,
        )
        return False

    # ── 3. Attempt token refresh ──────────────────────────────────────────────
    if tool in _GOOGLE_TOOLS:
        return await _refresh_google_token(connection, db)

    # Other providers not yet implemented — skip gracefully
    logger.warning("Token refresh not implemented for tool: %s", tool)
    return False


async def _refresh_google_token(connection: ToolConnection, db: AsyncSession) -> bool:
    """Refresh a Google OAuth2 access token using the stored refresh_token."""
    from app.core.config import get_settings
    settings = get_settings()

    tool = connection.tool_type.value.lower()
    client_id = (
        settings.gmail_client_id if tool == "gmail" else settings.calendar_client_id
    )
    client_secret = (
        settings.gmail_client_secret if tool == "gmail" else settings.calendar_client_secret
    )

    try:
        resp = await _http_client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": connection.refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )

        if resp.status_code == 200:
            data = resp.json()
            connection.access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            connection.token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=int(expires_in)
            )
            await db.commit()
            logger.info("Refreshed token for %s user=%s", tool, connection.user_id)
            return True

        # 400 invalid_grant = token was revoked by user
        if resp.status_code == 400:
            error = resp.json().get("error", "")
            if error == "invalid_grant":
                logger.warning(
                    "Refresh token revoked for %s user=%s — marking EXPIRED.",
                    tool,
                    connection.user_id,
                )
                connection.status = ConnectionStatus.EXPIRED
                await db.commit()
                return False

        # Any other HTTP error — treat as temporary, don't mark expired
        logger.warning(
            "Unexpected token refresh response %s for %s user=%s: %s",
            resp.status_code,
            tool,
            connection.user_id,
            resp.text[:200],
        )
        return False

    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        logger.warning(
            "Network error refreshing token for %s user=%s: %s",
            tool,
            connection.user_id,
            exc,
        )
        return False
