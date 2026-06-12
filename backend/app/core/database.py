"""ByteOps async database engine and session management."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


def _create_engine():
    settings = get_settings()
    db_url = settings.database_url

    # asyncpg doesn't understand libpq query params like sslmode, channel_binding.
    # Strip them and pass SSL via connect_args instead.
    import ssl as _ssl
    from urllib.parse import urlparse, urlencode, parse_qs

    connect_args: dict = {}
    parsed = urlparse(db_url)

    if parsed.query:
        # Remove libpq-only params that asyncpg doesn't understand
        libpq_only = {"sslmode", "channel_binding", "options"}
        params = parse_qs(parsed.query)
        needs_ssl = params.get("sslmode", [None])[0] in ("require", "verify-ca", "verify-full", "prefer")

        # Keep only params asyncpg understands
        clean_params = {k: v[0] for k, v in params.items() if k not in libpq_only}
        clean_query = urlencode(clean_params) if clean_params else ""
        db_url = parsed._replace(query=clean_query).geturl()

        if needs_ssl:
            ssl_ctx = _ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = _ssl.CERT_NONE
            connect_args["ssl"] = ssl_ctx

    return create_async_engine(
        db_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=10,       # Increased from 5 for better concurrency under load
        max_overflow=20,    # Increased from 10 — allows bursts without connection errors
        pool_recycle=3600,  # Recycle connections every hour; prevents stale connections on cloud/Railway
        connect_args=connect_args,
    )


engine = _create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
