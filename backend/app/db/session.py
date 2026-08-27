"""Async PostgreSQL connectivity foundation.

Owns the process-wide async engine/sessionmaker and exposes:

- ``init_engine`` / ``dispose_engine`` - lifecycle hooks called from the
  FastAPI ``lifespan`` in ``app.main``.
- ``check_database_connection`` - used by the ``/health/ready`` endpoint.
- ``get_db`` - a FastAPI dependency yielding a request-scoped
  ``AsyncSession``. Tests override this dependency to point at an
  in-memory SQLite database instead of a real PostgreSQL instance.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


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


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped database session."""
    if _sessionmaker is None:
        raise RuntimeError("Database engine has not been initialized")
    async with _sessionmaker() as session:
        yield session
