"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.knowledge import router as knowledge_router
from app.api.sessions import router as sessions_router
from app.api.system import router as system_router
from app.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.db.session import dispose_engine, init_engine
from app.logging_config import configure_logging, get_logger

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application.

    Using a factory (rather than a module-level ``app``) keeps startup
    deterministic and lets tests construct an app with overridden
    settings instead of relying on environment variables.
    """

    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("startup", app_env=settings.app_env, service=settings.app_name)
        init_engine(settings)
        yield
        await dispose_engine()
        logger.info("shutdown")

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.debug,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(system_router)
    app.include_router(knowledge_router)
    # Future routers (artifacts) mount here once the corresponding
    # domain logic exists.

    return app


app = create_app()
