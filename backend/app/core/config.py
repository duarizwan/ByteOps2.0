"""ByteOps backend application configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- App ---
    app_name: str = "ByteOps API"
    debug: bool = False

    # --- Database (Neon PostgreSQL) ---
    database_url: str = "postgresql+asyncpg://localhost/byteops"

    # --- Clerk Authentication ---
    clerk_secret_key: str = ""
    clerk_webhook_secret: str = ""
    # Your Clerk Frontend API URL, e.g. https://sacred-hawk-87.clerk.accounts.dev
    # Find it in Clerk Dashboard → API Keys → Advanced. Required — must be set in .env.
    clerk_issuer: str = ""

    # --- CORS ---
    backend_cors_origins: str = "http://localhost:3000"

    # --- AI / LLM ---
    claude_api_key: str = ""

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

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
