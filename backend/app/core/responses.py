"""Shared response models for API conventions."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    name: str
    status: str = Field(description="'ok', 'error', or 'not_configured'")
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str


class ReadinessResponse(BaseModel):
    status: str = Field(description="'ok' if every checked dependency is healthy, else 'degraded'")
    dependencies: list[DependencyStatus]
