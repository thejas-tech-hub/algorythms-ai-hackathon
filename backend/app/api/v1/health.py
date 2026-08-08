"""
Health and readiness probe endpoints.
Owner: THEJAS

GET /api/v1/health  — liveness (always OK if server is up)
GET /api/v1/ready   — readiness (confirms data is loaded)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_candidate_loader
from app.data.candidate_loader import JSONCandidateLoader

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns OK if the server process is running.",
)
async def health_check() -> dict:
    """Liveness probe — always returns healthy if the server is up."""
    return {"status": "healthy", "service": "ai-interview-agent"}


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Returns readiness status and loaded candidate count.",
)
async def readiness_check(
    loader: JSONCandidateLoader = Depends(get_candidate_loader),
) -> dict:
    """Readiness probe — confirms candidate data is loaded."""
    candidates_loaded = loader.is_loaded
    candidate_count = len(loader.get_all()) if candidates_loaded else 0

    return {
        "ready": candidates_loaded,
        "candidates_loaded": candidate_count,
    }
