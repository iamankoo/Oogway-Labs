"""System/configuration-visibility endpoints.

Separate from ``health.py`` on purpose: health/readiness answer "is the
service up," this answers "which model is actually configured" - the
question the frontend's provider indicator needs answered, reflecting
real settings rather than fake UI state.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import ProviderStatusOut
from app.config import get_settings

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/provider", response_model=ProviderStatusOut)
async def get_provider_status() -> ProviderStatusOut:
    settings = get_settings()
    if settings.llm_provider == "cloud":
        return ProviderStatusOut(provider="cloud", model=settings.cloud_model)
    return ProviderStatusOut(provider="ollama", model=settings.ollama_model)
