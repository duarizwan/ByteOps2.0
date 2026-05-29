"""ByteOps FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine
from app.api import oauth, tools, users, chat, notifications, sync, workflows
from app.services.sync.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    settings = get_settings()
    print(f"[START] {settings.app_name} starting...")

    # Auto-create tables if they don't exist
    from app.core.database import Base
    # Import all models so Base.metadata knows about them
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Database tables ready.")

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

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(users.router)
    app.include_router(tools.router)
    app.include_router(oauth.router)
    app.include_router(chat.router)
    app.include_router(notifications.router)
    app.include_router(workflows.router)
    app.include_router(sync.router)

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": settings.app_name}

    return app


app = create_app()
