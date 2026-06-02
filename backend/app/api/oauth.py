"""OAuth2 routes — initiate, callback, and disconnect for all supported tools."""

import base64
import hashlib
import logging
import secrets
import time as _time
from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_clerk_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.tool_connection import ConnectionStatus, ToolConnection, ToolType
from app.models.user import User
from app.services.sync.scheduler import trigger_immediate_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["oauth"])


class ApiKeyCredentials(BaseModel):
    credentials: dict[str, str]

# ── PKCE helpers (required by Slack for http:// redirect URIs) ────────────────

# Tools that require PKCE in the authorization flow
# Slack: required for http:// redirect URIs
# Dropbox: required for newer scoped apps
_PKCE_TOOLS = {ToolType.SLACK, ToolType.DROPBOX}

# Dropbox PKCE replaces client_secret (public-client PKCE).
# Slack PKCE is additional security — client_secret is still sent.
_PKCE_NO_SECRET_TOOLS = {ToolType.DROPBOX}

# In-process store: state_nonce → (code_verifier, expires_at)
# TTL = 10 minutes — enough for any human to complete the OAuth dance
_pkce_store: dict[str, tuple[str, float]] = {}


def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256 method."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _pkce_save(nonce: str, verifier: str) -> None:
    now = _time.monotonic()
    _pkce_store[nonce] = (verifier, now + 600)
    # Prune expired entries so the dict doesn't grow unbounded
    for k in [k for k, v in _pkce_store.items() if v[1] < now]:
        del _pkce_store[k]


def _pkce_pop(nonce: str) -> str | None:
    """Retrieve and remove a stored verifier. Returns None if missing or expired."""
    entry = _pkce_store.pop(nonce, None)
    if entry is None:
        return None
    verifier, expires_at = entry
    return verifier if _time.monotonic() < expires_at else None

# ──────────────────────────────────────────────────────────────────────────────
# OAuth2 provider definitions
# Each entry maps ToolType → provider configuration factory.
# Credentials are read lazily from settings so they don't blow up at import.
# ──────────────────────────────────────────────────────────────────────────────

def _frontend_url() -> str:
    """Return the frontend URL from settings (supports production override via _frontend_url() env var)."""
    return get_settings().frontend_url


def _build_provider(tool: ToolType) -> dict:
    s = get_settings()
    providers: dict[ToolType, dict] = {
        ToolType.GMAIL: {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id": s.gmail_client_id,
            "client_secret": s.gmail_client_secret,
            "redirect_uri": s.gmail_redirect_uri,
            "scopes": "https://mail.google.com/ https://www.googleapis.com/auth/gmail.send",
            "extra_params": {"access_type": "offline", "prompt": "consent"},
        },
        ToolType.CALENDAR: {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            # Fall back to Gmail credentials if Calendar-specific ones are not set.
            # Many Google Cloud projects use a single OAuth2 client for all Google APIs.
            "client_id": s.calendar_client_id or s.gmail_client_id,
            "client_secret": s.calendar_client_secret or s.gmail_client_secret,
            "redirect_uri": s.calendar_redirect_uri,
            "scopes": "https://www.googleapis.com/auth/calendar",
            "extra_params": {"access_type": "offline", "prompt": "consent"},
        },
        ToolType.GITHUB: {
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "client_id": s.github_client_id,
            "client_secret": s.github_client_secret,
            "redirect_uri": s.github_redirect_uri,
            "scopes": "repo read:user user:email",
            "extra_params": {},
        },
        ToolType.SLACK: {
            "auth_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "client_id": s.slack_client_id,
            "client_secret": s.slack_client_secret,
            "redirect_uri": s.slack_redirect_uri,
            "scopes": (
                "channels:read channels:history "
                "groups:read groups:history "
                "chat:write "
                "im:read im:write im:history "
                "users:read users:read.email "
                "reactions:write"
            ),
            "extra_params": {},
        },
        ToolType.JIRA: {
            "auth_url": "https://auth.atlassian.com/authorize",
            "token_url": "https://auth.atlassian.com/oauth/token",
            "client_id": s.jira_client_id,
            "client_secret": s.jira_client_secret,
            "redirect_uri": s.jira_redirect_uri,
            "scopes": "read:jira-work write:jira-work offline_access",
            "extra_params": {"audience": "api.atlassian.com", "prompt": "consent"},
        },
        ToolType.TRELLO: {
            # Trello simplified token flow — returns token directly, no code exchange
            "auth_url": "https://trello.com/1/authorize",
            "token_url": None,
            "client_id": s.trello_api_key,
            "client_secret": s.trello_api_secret,
            "redirect_uri": s.trello_redirect_uri,
            "scopes": "read,write",
            "extra_params": {"name": "ByteOps", "expiration": "never"},
        },
        ToolType.DROPBOX: {
            "auth_url": "https://www.dropbox.com/oauth2/authorize",
            "token_url": "https://api.dropboxapi.com/oauth2/token",
            "client_id": s.dropbox_client_id,
            "client_secret": s.dropbox_client_secret,
            "redirect_uri": s.dropbox_redirect_uri,
            "scopes": "files.metadata.read files.metadata.write files.content.read files.content.write sharing.read sharing.write",
            "extra_params": {"token_access_type": "offline"},
        },
    }
    cfg = providers.get(tool)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool}")
    if not cfg["client_id"]:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"{tool.value} OAuth2 credentials not configured. Add {tool.value.upper()}_CLIENT_ID and {tool.value.upper()}_CLIENT_SECRET to .env",
        )
    return cfg


# ──────────────────────────────────────────────────────────────────────────────
# Initiate — redirect user to provider
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{tool}/initiate")
async def initiate_oauth(
    tool: ToolType,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
) -> dict:
    """Return the OAuth2 authorization URL. Frontend navigates there after receiving it."""
    from urllib.parse import urlencode

    cfg = _build_provider(tool)
    state = secrets.token_urlsafe(32)

    # Trello simplified flow: different param names, token returned directly.
    # Nonce is embedded in the redirect path (not query string) because Trello appends
    # ?token=TOKEN unconditionally — a query-param nonce would create a double-? URL
    # that Python's URL parser collapses into one broken key, losing the token entirely.
    if tool == ToolType.TRELLO:
        nonce = secrets.token_urlsafe(16)
        _pkce_store[nonce] = (str(current_user.id), _time.monotonic() + 600)
        # Trello returns token as URL fragment (#token=...) which the server never sees.
        # Point return_url at the frontend relay page; it reads the hash and POSTs to backend.
        return_url = f"{_frontend_url()}/trello-callback?nonce={nonce}"
        params = {
            "key": cfg["client_id"],
            "return_url": return_url,
            "callback_method": "redirect",
            "response_type": "token",
            "scope": cfg["scopes"],
            **cfg.get("extra_params", {}),
        }
        auth_url = f"{cfg['auth_url']}?{urlencode(params)}"
        return {"auth_url": auth_url}

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": cfg["scopes"],
        "state": f"{current_user.id}:{state}",
        **cfg.get("extra_params", {}),
    }

    # Slack requires PKCE for non-HTTPS (http://) redirect URIs
    if tool in _PKCE_TOOLS:
        verifier, challenge = _pkce_pair()
        _pkce_save(state, verifier)
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"

    auth_url = f"{cfg['auth_url']}?{urlencode(params)}"
    return {"auth_url": auth_url}


# ──────────────────────────────────────────────────────────────────────────────
# Callback — exchange code for tokens, persist connection
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/trello/callback/{nonce}")
async def trello_callback(
    nonce: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    token: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Trello-specific callback: nonce in path, token appended as ?token=TOKEN by Trello."""
    import uuid

    if error:
        return RedirectResponse(url=f"{_frontend_url()}/settings?error={error}&tool=trello")

    logger.info("Trello callback received — nonce=%s has_token=%s", nonce, bool(token))
    if not token:
        logger.warning("Trello callback missing token for nonce=%s", nonce)
        return RedirectResponse(url=f"{_frontend_url()}/settings?error=trello_missing_token&tool=trello")

    entry = _pkce_store.pop(nonce, None)
    if not entry or _time.monotonic() > entry[1]:
        return RedirectResponse(url=f"{_frontend_url()}/settings?error=trello_state_expired&tool=trello")

    try:
        user_id = uuid.UUID(entry[0])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Trello state")

    return await _complete_trello_connection(user_id, token, db, background_tasks)


async def _complete_trello_connection(
    user_id,
    token: str,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    """Shared logic to persist a Trello connection and redirect to settings."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cfg = _build_provider(ToolType.TRELLO)
    existing = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == user_id,
            ToolConnection.tool_type == ToolType.TRELLO,
        )
    )
    connection = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if connection:
        connection.access_token = token
        connection.scopes = cfg["scopes"]
        connection.status = ConnectionStatus.CONNECTED
        connection.updated_at = now
    else:
        connection = ToolConnection(
            user_id=user_id,
            tool_type=ToolType.TRELLO,
            access_token=token,
            refresh_token=None,
            token_expires_at=None,
            scopes=cfg["scopes"],
            status=ConnectionStatus.CONNECTED,
        )
        db.add(connection)

    await db.commit()

    background_tasks.add_task(trigger_immediate_sync, user_id=user_id, tool_type=ToolType.TRELLO)

    return RedirectResponse(url=f"{_frontend_url()}/settings?connected=trello")


@router.get("/{tool}/callback")
async def oauth_callback(
    tool: ToolType,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Handle the OAuth2 callback: exchange code → tokens, upsert ToolConnection."""
    if error:
        return RedirectResponse(url=f"{_frontend_url()}/settings?error={error}&tool={tool}")

    import uuid

    if tool == ToolType.TRELLO:
        # Should not reach here — Trello uses /trello/callback/{nonce} route.
        return RedirectResponse(url=f"{_frontend_url()}/settings?error=trello_wrong_route&tool=trello")

    if not code:
        return RedirectResponse(url=f"{_frontend_url()}/settings?error=missing_code&tool={tool}")
    # Parse user_id and nonce from state
    try:
        user_id_str, state_nonce = (state or "").split(":", 1)
        user_id = uuid.UUID(user_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid OAuth2 state parameter")

    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cfg = _build_provider(tool)

    # Exchange code for tokens
    token_body: dict = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": cfg["redirect_uri"],
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
    }

    # For PKCE tools, attach the code_verifier stored during initiation.
    # Dropbox (public-client PKCE): code_verifier replaces client_secret — omit it.
    # Slack (confidential-client PKCE): code_verifier is additional — keep client_secret.
    if tool in _PKCE_TOOLS:
        verifier = _pkce_pop(state_nonce)
        if verifier:
            token_body["code_verifier"] = verifier
        else:
            logger.warning("PKCE verifier not found or expired for %s OAuth callback", tool)
        if tool in _PKCE_NO_SECRET_TOOLS:
            token_body.pop("client_secret", None)

    token_data: dict = {}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            cfg["token_url"],
            data=token_body,
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return RedirectResponse(
                url=f"{_frontend_url()}/settings?error=token_exchange_failed&tool={tool}"
            )
        token_data = resp.json()

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    scopes = token_data.get("scope", cfg["scopes"])

    token_expires_at = None
    if expires_in:
        from datetime import timedelta
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    # For Slack: bot token lives at token_data["access_token"] for app installs,
    # but for user-scoped bots the bot token is at token_data.authed_user.access_token.
    # Prefer the top-level access_token (bot token) which is what we pass to the MCP server.
    # (already set above)

    # For Jira: fetch accessible cloud resources to get the cloud_id and base URL
    connection_metadata: dict = {}
    if tool == ToolType.JIRA and access_token:
        async with httpx.AsyncClient() as meta_client:
            resources_resp = await meta_client.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            if resources_resp.status_code == 200:
                resources = resources_resp.json()
                if resources:
                    cloud = resources[0]  # use first/primary cloud instance
                    connection_metadata = {
                        "cloud_id": cloud.get("id", ""),
                        "cloud_name": cloud.get("name", ""),
                        "cloud_url": cloud.get("url", ""),
                    }

    # Upsert ToolConnection
    existing = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == user_id,
            ToolConnection.tool_type == tool,
        )
    )
    connection = existing.scalar_one_or_none()

    if connection:
        connection.access_token = access_token
        if refresh_token:
            connection.refresh_token = refresh_token
        connection.token_expires_at = token_expires_at
        connection.scopes = scopes
        connection.status = ConnectionStatus.CONNECTED
        connection.updated_at = datetime.now(timezone.utc)
        if connection_metadata:
            connection.metadata_ = connection_metadata
    else:
        connection = ToolConnection(
            user_id=user_id,
            tool_type=tool,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            scopes=scopes,
            status=ConnectionStatus.CONNECTED,
            metadata_=connection_metadata or None,
        )
        db.add(connection)

    await db.commit()

    # Fire background sync immediately (non-blocking)
    background_tasks.add_task(
        trigger_immediate_sync,
        user_id=user_id,
        tool_type=tool,
    )

    return RedirectResponse(url=f"{_frontend_url()}/settings?connected={tool}")


# ──────────────────────────────────────────────────────────────────────────────
# Silent token refresh — no OAuth redirect required
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{tool}/refresh")
async def refresh_tool_token(
    tool: ToolType,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> dict:
    """Silently refresh an access token using the stored refresh token.

    Only works for tools that support refresh tokens (Gmail, Calendar).
    Returns {"refreshed": true} on success or raises 400/404 on failure.
    """
    from app.services.sync.token_refresh import ensure_fresh_token

    result = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.tool_type == tool,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail=f"No {tool} connection found")

    if not connection.refresh_token:
        raise HTTPException(
            status_code=400,
            detail=f"{tool} has no stored refresh token — please reconnect via OAuth.",
        )

    ok = await ensure_fresh_token(connection, db)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=f"Could not refresh {tool} token — it may have been revoked. Please reconnect.",
        )

    if connection.status == ConnectionStatus.EXPIRED:
        connection.status = ConnectionStatus.CONNECTED
        await db.commit()

    background_tasks.add_task(
        trigger_immediate_sync,
        user_id=current_user.id,
        tool_type=tool,
    )

    return {"refreshed": True}


# ──────────────────────────────────────────────────────────────────────────────
# API Key connection — validate credentials then upsert ToolConnection
# ──────────────────────────────────────────────────────────────────────────────

_APIKEY_SUPPORTED = {ToolType.GITHUB, ToolType.JIRA, ToolType.SLACK, ToolType.TRELLO, ToolType.DROPBOX}


async def _validate_apikey_credentials(tool: ToolType, creds: dict[str, str]) -> None:
    """Make a lightweight test call to confirm credentials are valid. Raises HTTPException on failure."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        if tool == ToolType.GITHUB:
            token = creds.get("token", "")
            if not token:
                raise HTTPException(status_code=400, detail="token is required")
            resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid GitHub token")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"GitHub API error: {resp.status_code}")

        elif tool == ToolType.JIRA:
            workspace = creds.get("workspace", "").strip().rstrip("/")
            email = creds.get("email", "")
            token = creds.get("token", "")
            if not workspace:
                raise HTTPException(status_code=400, detail="workspace is required")
            if not email or not token:
                raise HTTPException(status_code=400, detail="email and token are required")
            auth = base64.b64encode(f"{email}:{token}".encode()).decode()
            resp = await client.get(
                f"https://{workspace}/rest/api/3/myself",
                headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid Jira credentials — check email and token")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Jira API error: {resp.status_code}")

        elif tool == ToolType.SLACK:
            token = creds.get("token", "")
            if not token:
                raise HTTPException(status_code=400, detail="token is required")
            resp = await client.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code not in (200, 400):
                raise HTTPException(status_code=400, detail=f"Slack API error: {resp.status_code}")
            data = resp.json()
            if not data.get("ok"):
                raise HTTPException(status_code=400, detail=f"Invalid Slack token: {data.get('error', 'unknown')}")

        elif tool == ToolType.TRELLO:
            api_key = creds.get("api_key", "")
            token = creds.get("token", "")
            if not api_key or not token:
                raise HTTPException(status_code=400, detail="api_key and token are required")
            resp = await client.get(
                f"https://api.trello.com/1/members/me?key={api_key}&token={token}",
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid Trello credentials")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Trello API error: {resp.status_code}")

        elif tool == ToolType.DROPBOX:
            token = creds.get("token", "")
            if not token:
                raise HTTPException(status_code=400, detail="token is required")
            resp = await client.post(
                "https://api.dropboxapi.com/2/users/get_current_account",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                content=b"null",
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid Dropbox token")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Dropbox API error: {resp.status_code}")


def _extract_token_and_metadata(tool: ToolType, creds: dict[str, str]) -> tuple[str, dict]:
    """Return (access_token_to_store, metadata_dict) from raw credentials."""
    if tool == ToolType.JIRA:
        return creds["token"], {
            "auth_method": "apikey",
            "workspace": creds["workspace"].strip().rstrip("/"),
            "email": creds["email"],
        }
    if tool == ToolType.TRELLO:
        return creds["token"], {"auth_method": "apikey", "api_key": creds["api_key"]}
    return creds["token"], {"auth_method": "apikey"}


@router.post("/{tool}/connect-apikey")
async def connect_tool_apikey(
    tool: ToolType,
    body: ApiKeyCredentials,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> dict:
    """Connect a tool using a user-supplied API key / personal access token."""
    if tool not in _APIKEY_SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"{tool} does not support API key auth. Use OAuth.",
        )

    await _validate_apikey_credentials(tool, body.credentials)
    access_token, metadata = _extract_token_and_metadata(tool, body.credentials)

    existing = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.tool_type == tool,
        )
    )
    connection = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if connection:
        connection.access_token = access_token
        connection.refresh_token = None
        connection.token_expires_at = None
        connection.scopes = None
        connection.status = ConnectionStatus.CONNECTED
        connection.updated_at = now
        connection.metadata_ = metadata
    else:
        connection = ToolConnection(
            user_id=current_user.id,
            tool_type=tool,
            access_token=access_token,
            refresh_token=None,
            token_expires_at=None,
            scopes=None,
            status=ConnectionStatus.CONNECTED,
            metadata_=metadata,
        )
        db.add(connection)

    await db.commit()

    background_tasks.add_task(trigger_immediate_sync, user_id=current_user.id, tool_type=tool)

    return {"status": "connected", "tool_type": tool}


# ──────────────────────────────────────────────────────────────────────────────
# Disconnect — remove ToolConnection row
# ──────────────────────────────────────────────────────────────────────────────

@router.delete("/{tool}/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_tool(
    tool: ToolType,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Mark a tool connection as disconnected."""
    result = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.tool_type == tool,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail=f"No active {tool} connection found")

    connection.status = ConnectionStatus.DISCONNECTED
    await db.commit()
