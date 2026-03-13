"""FastAPI application factory + Lambda handler.

This module exposes:
  * `app`       — the FastAPI ASGI application (used by uvicorn locally).
  * `handler`   — a Mangum adapter that wraps `app` for AWS Lambda.

Both share the same routes and configuration, so behavior is identical across
local Docker, `pytest`, and production Lambda.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app import __version__
from app.config import get_settings
from app.routers import ingest as ingest_router
from app.routers import query as query_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="DocuMind",
        description="Retrieval-Augmented Document Q&A service",
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ingest_router.router)
    app.include_router(query_router.router)

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/", tags=["health"], include_in_schema=False)
    async def root() -> dict:
        return {"name": "DocuMind", "version": __version__, "docs": "/docs"}

    logger.info(
        "DocuMind v%s started (env=%s)", __version__, settings.APP_ENV
    )
    return app


app = create_app()

# Mangum adapts ASGI -> Lambda event/response. `lifespan="off"` because Lambda
# is request-scoped; FastAPI startup/shutdown events would never fire usefully.
handler = Mangum(app, lifespan="off")
