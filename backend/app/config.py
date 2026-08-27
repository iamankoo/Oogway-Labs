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

    # --- Ollama --------------------------------------------------------
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

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
