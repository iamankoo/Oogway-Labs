"""Liveness and readiness endpoints.

``/health`` answers "is the process alive" and never touches external
dependencies - it must stay fast and unconditionally succeed once the
app has booted.

``/health/ready`` answers "can this instance serve traffic" by checking
PostgreSQL and the currently configured model provider. It is written so
later phases can append checks (retrieval index, ...) without changing
its shape.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app import __version__
from app.config import Settings
from app.core.responses import DependencyStatus, HealthResponse, ReadinessResponse
from app.db.session import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(service=settings.app_name, version=__version__)


async def _check_provider(settings: Settings) -> DependencyStatus:
    """Check the currently configured LLM provider is reachable/configured.

    Ollama: a live, short-timeout ping to ``/api/tags`` (cheap - no
    generation call). Cloud: only confirms an API key is configured -
    readiness deliberately does not spend money on a real completion
    every time this endpoint is polled.
    """
    if settings.llm_provider == "cloud":
        if not settings.cloud_api_key:
            return DependencyStatus(
                name="model_provider",
                status="error",
                detail="Cloud provider selected but CLOUD_API_KEY is not set.",
            )
        return DependencyStatus(name="model_provider", status="ok", detail=None)

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        if response.status_code != 200:
            return DependencyStatus(
                name="model_provider", status="error", detail=f"Ollama returned HTTP {response.status_code}."
            )
        models = {m.get("name") for m in response.json().get("models", [])}
        if settings.ollama_model not in models:
            return DependencyStatus(
                name="model_provider",
                status="error",
                detail=f"Ollama is reachable but '{settings.ollama_model}' isn't pulled yet.",
            )
        return DependencyStatus(name="model_provider", status="ok", detail=None)
    except httpx.HTTPError:
        return DependencyStatus(
            name="model_provider",
            status="error",
            detail=f"Could not reach Ollama at {settings.ollama_base_url}.",
        )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    dependencies: list[DependencyStatus] = []

    db_ok = await check_database_connection()
    dependencies.append(
        DependencyStatus(
            name="postgresql",
            status="ok" if db_ok else "error",
            detail=None if db_ok else "Could not reach the configured PostgreSQL database.",
        )
    )
    dependencies.append(await _check_provider(settings))

    overall_ok = all(dep.status == "ok" for dep in dependencies)
    payload = ReadinessResponse(status="ok" if overall_ok else "degraded", dependencies=dependencies)
    return JSONResponse(
        status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
