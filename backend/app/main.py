"""
FastAPI application factory.

Creates and configures the FastAPI app instance:
- Registers v1 API router
- Registers middleware (CORS, request-ID, timing)
- Registers domain exception → HTTP response handlers
- Manages startup/shutdown lifecycle (data loading)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.api.v1.router import router as v1_router
from app.core.exceptions import (
    InterviewAgentError,
    CandidateNotFoundError,
    SessionNotFoundError,
    SessionExpiredError,
)
from app.core.logging import setup_logging, get_logger
from app.core.middleware import register_middleware
from app.api.deps import get_candidate_repo


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    setup_logging()
    logger.info("Starting AI Interview Agent")

    # Pre-load candidate data at startup
    repo = get_candidate_repo()
    logger.info(
        "Candidate data ready: %d candidates loaded",
        len(repo.list_all()),
    )

    yield  # ── Application is running ──

    logger.info("Shutting down AI Interview Agent")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Adaptive AI-powered interview agent that tailors questions "
            "based on candidate training performance in an AI cohort."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────
    register_middleware(app)

    # ── Routers ──────────────────────────────────────────────────────
    app.include_router(v1_router)

    # ── Exception Handlers ───────────────────────────────────────────

    @app.exception_handler(CandidateNotFoundError)
    async def candidate_not_found_handler(
        request: Request, exc: CandidateNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": "Not Found", "detail": exc.message},
        )

    @app.exception_handler(SessionNotFoundError)
    async def session_not_found_handler(
        request: Request, exc: SessionNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": "Not Found", "detail": exc.message},
        )

    @app.exception_handler(SessionExpiredError)
    async def session_expired_handler(
        request: Request, exc: SessionExpiredError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": "Conflict", "detail": exc.message},
        )

    @app.exception_handler(InterviewAgentError)
    async def generic_agent_error_handler(
        request: Request, exc: InterviewAgentError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Error", "detail": exc.message},
        )

    return app


# ── Module-level app instance (used by uvicorn) ─────────────────────
app = create_app()
