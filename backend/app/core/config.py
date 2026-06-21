"""ByteOps backend application configuration."""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Any


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- App ---
    app_name: str = "ByteOps API"
    debug: bool = False

    # --- Database (Neon PostgreSQL) ---
    database_url: str = "postgresql+asyncpg://localhost/byteops"

    # --- Secrets ---
    # Fernet key (generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())").
    # When set, OAuth tokens are encrypted at rest. When empty, tokens are stored
    # plaintext (legacy behavior) — set this in production.
    token_encryption_key: str = ""

    # --- Clerk Authentication ---
    clerk_secret_key: str = ""
    clerk_webhook_secret: str = ""
    # Your Clerk Frontend API URL, e.g. https://sacred-hawk-87.clerk.accounts.dev
    # Find it in Clerk Dashboard → API Keys → Advanced. Required — must be set in .env.
    clerk_issuer: str = ""

    # --- CORS ---
    backend_cors_origins: str = "http://localhost:3000"

    # --- AI / LLM ---
    # LLM_PROVIDER can be "auto", "claude", "gemini", or "groq".
    # In auto mode, first present key wins: Claude > Gemini > Groq.
    llm_provider: str = "auto"
    claude_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    # Optional: override the default model for the active provider
    llm_model: str = ""

    # --- OAuth2 Tool Secrets ---
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/api/auth/gmail/callback"

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"

    jira_client_id: str = ""
    jira_client_secret: str = ""
    jira_redirect_uri: str = "http://localhost:8000/api/auth/jira/callback"

    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_redirect_uri: str = "http://localhost:8000/api/auth/slack/callback"

    trello_api_key: str = ""
    trello_api_secret: str = ""
    trello_redirect_uri: str = "http://localhost:8000/api/auth/trello/callback"

    dropbox_client_id: str = ""
    dropbox_client_secret: str = ""
    dropbox_redirect_uri: str = "http://localhost:8000/api/auth/dropbox/callback"

    calendar_client_id: str = ""
    calendar_client_secret: str = ""
    calendar_redirect_uri: str = "http://localhost:8000/api/auth/calendar/callback"

    # Frontend URL — used for OAuth2 redirect-back after callback
    frontend_url: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",")]

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value: Any) -> Any:
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
