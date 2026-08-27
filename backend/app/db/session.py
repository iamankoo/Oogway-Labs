"""Async PostgreSQL connectivity foundation.

Phase 1 only establishes the ability to open a connection and reuse it
for a readiness check. Schema/ORM models and session-per-request
dependency wiring belong to Phase 2, once the application tables exist.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.config import Settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker | None = None


def init_engine(settings: Settings) -> AsyncEngine:
    """Create (once) the process-wide async engine."""
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def check_database_connection() -> bool:
    """Run a trivial round-trip query to confirm the database is reachable."""
    if _engine is None:
        return False
    try:
        async with _engine.connect() as connection:
            await connection.exec_driver_sql("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 - readiness checks must not raise
        return False


@asynccontextmanager
async def get_session() -> AsyncIterator:
    """Yield a database session. Reserved for Phase 2 request handlers."""
    if _sessionmaker is None:
        raise RuntimeError("Database engine has not been initialized")
    async with _sessionmaker() as session:
        yield session
