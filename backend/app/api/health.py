"""Liveness and readiness endpoints.

``/health`` answers "is the process alive" and never touches external
dependencies - it must stay fast and unconditionally succeed once the
app has booted.

``/health/ready`` answers "can this instance serve traffic" by checking
the dependencies Phase 1 actually wires up (PostgreSQL). It is written
so later phases can append checks (Ollama, retrieval index, agent
runtime) without changing its shape.
"""

from __future__ import annotations

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


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request) -> JSONResponse:
    dependencies: list[DependencyStatus] = []

    db_ok = await check_database_connection()
    dependencies.append(
        DependencyStatus(
            name="postgresql",
            status="ok" if db_ok else "error",
            detail=None if db_ok else "Could not reach the configured PostgreSQL database.",
        )
    )

    # Ollama, retrieval index, and agent runtime checks are added as
    # those subsystems are actually implemented in later phases.

    overall_ok = all(dep.status == "ok" for dep in dependencies)
    payload = ReadinessResponse(status="ok" if overall_ok else "degraded", dependencies=dependencies)
    return JSONResponse(
        status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
