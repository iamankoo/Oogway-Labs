from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.models import DEMO_USER_ID, Base, User
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        postgres_host="invalid-host-for-tests",
        postgres_db="lenny_test",
    )


@pytest.fixture
async def db_sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """An isolated in-memory SQLite database, seeded with the demo user.

    Tests never touch a real PostgreSQL instance - this keeps the suite
    fast, hermetic, and independent of any developer's local database.
    A fresh in-memory database is created per test.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        session.add(User(id=DEMO_USER_ID, external_key="local-demo-user", display_name="Demo User"))
        await session.commit()

    yield sessionmaker
    await engine.dispose()


@pytest.fixture(autouse=True)
def _stub_model_provider_by_default(monkeypatch: pytest.MonkeyPatch):
    """Never let a test reach a real model provider unless it asks to.

    Applies to every test automatically: session/message tests that don't
    care about generation (most of test_sessions_api.py) get a safe,
    always-succeeding stub instead of a real network attempt to
    ``localhost:11434``. Tests that *do* care about provider behavior
    (test_generation_api.py) override this with their own
    ``monkeypatch.setattr("app.api.sessions.get_model_provider", ...)``
    within the test itself, which simply takes effect after this one.
    """
    from typing import Any

    from pi_agent.llm import AssistantResponse, NeutralMessage

    class _DefaultStubProvider:
        """Conforms to ``pi_agent.llm.LLMProvider`` without any network access."""

        name = "ollama"
        model = "stub-model"
        supports_streaming = False

        def complete(
            self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
        ) -> AssistantResponse:
            return AssistantResponse(text="stub response")

    monkeypatch.setattr("app.api.sessions.get_model_provider", lambda _settings: _DefaultStubProvider())


@pytest.fixture
async def client(
    settings: Settings, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        async with app.router.lifespan_context(app):
            yield ac
