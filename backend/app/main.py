"""ByteOps FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine
from app.api import agent_runs, oauth, tools, users, chat, notifications, sync, workflows
from app.services.sync.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    settings = get_settings()
    print(f"[START] {settings.app_name} starting...")

    # Schema is managed by Alembic (`alembic upgrade head`). Table auto-creation
    # is opt-in for local dev only — never in production, where it would drift
    # the schema away from the migration history.
    import os

    import app.models  # noqa: F401 - register models on Base.metadata

    if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":
        from app.core.database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[OK] Database tables auto-created (AUTO_CREATE_TABLES=true).")
    else:
        print("[OK] Skipping auto-create; schema managed by Alembic.")

    # Start background sync scheduler
    await start_scheduler()
    print("[OK] Sync scheduler started.")

    yield

    await stop_scheduler()
    await engine.dispose()
    print("[STOP] ByteOps API shutting down.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="ByteOps AI-powered platform API",
        lifespan=lifespan,
    )

    # CORS — explicit allowlist (origins come from settings; no wildcards with credentials)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Routers
    app.include_router(users.router)
    app.include_router(tools.router)
    app.include_router(oauth.router)
    app.include_router(chat.router)
    app.include_router(notifications.router)
    app.include_router(agent_runs.router)
    app.include_router(workflows.router)
    app.include_router(sync.router)

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": settings.app_name}

    return app


app = create_app()
