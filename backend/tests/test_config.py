from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_load_defaults() -> None:
    settings = Settings()
    assert settings.app_name == "Lenny Growth Assistant API"
    assert settings.app_env == "development"
    assert "localhost" in settings.cors_allow_origins_list[0]


def test_settings_parse_cors_origins_list() -> None:
    settings = Settings(cors_allow_origins="https://a.example.com, https://b.example.com")
    assert settings.cors_allow_origins_list == ["https://a.example.com", "https://b.example.com"]


def test_settings_build_database_url() -> None:
    settings = Settings(
        postgres_host="db",
        postgres_port=5432,
        postgres_user="lenny",
        postgres_password="secret",
        postgres_db="lenny_growth_assistant",
    )
    assert settings.database_url.startswith("postgresql+asyncpg://lenny:")
    assert "db:5432/lenny_growth_assistant" in settings.database_url


def test_invalid_app_env_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="staging-typo")
