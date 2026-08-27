"""Typed application configuration.

All runtime configuration flows through this module. Nothing in the
application should call ``os.getenv`` directly outside of this file -
that keeps every setting discoverable in one place and lets later phases
(agent orchestration, RAG, artifacts) add config without hunting through
the codebase.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---------------------------------------------------
    app_name: str = "Lenny Growth Assistant API"
    app_env: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api"
    debug: bool = False

    # --- CORS ------------------------------------------------------------
    cors_allow_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- PostgreSQL --------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "lenny"
    postgres_password: str = "lenny"
    postgres_db: str = "lenny_growth_assistant"

    # --- LLM provider ----------------------------------------------------
    # "ollama" (local, mandatory for the demo) or "cloud" (Anthropic Claude).
    # Switching providers is a configuration change only - see
    # app/services/model_providers/ for the abstraction this selects between.
    llm_provider: Literal["ollama", "cloud"] = "ollama"
    # 60s rather than something tighter because CPU-only local inference
    # (the mandatory Ollama path) can legitimately take that long for a
    # full response on modest hardware - see docs/architecture.md
    # "Timeouts and retry" for the measured numbers this is based on.
    model_timeout_seconds: float = 60.0
    # How many of the most recent messages in a session are sent to the
    # model as context. Keeps requests bounded without token counting.
    max_context_messages: int = 20

    # --- Ollama --------------------------------------------------------
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # --- Cloud provider (Anthropic) --------------------------------------
    cloud_provider: Literal["anthropic"] = "anthropic"
    cloud_model: str = "claude-opus-5"
    cloud_api_key: str | None = None

    # --- Frontend --------------------------------------------------------
    frontend_url: str = "http://localhost:5173"

    # --- Logging --------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    @computed_field  # type: ignore[misc]
    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection string.

        Only a connection string is established in Phase 1. Schema and
        ORM models are introduced in Phase 2.
        """
        dsn = PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            path=self.postgres_db,
        )
        return str(dsn)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    Cached so configuration is parsed/validated once per process. Tests
    that need a different configuration should call ``get_settings.cache_clear()``
    after mutating environment variables.
    """
    return Settings()
