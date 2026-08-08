"""
Health and readiness probe endpoints.
Owner: THEJAS

GET /api/v1/health  -- liveness (always OK if server is up)
GET /api/v1/ready   -- readiness (confirms data is loaded)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_candidate_repo
from app.data.repositories import CandidateRepository

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
    repo: CandidateRepository = Depends(get_candidate_repo),
) -> dict:
    """Readiness probe — confirms candidate data is loaded."""
    candidates = repo.list_all()
    return {
        "ready": True,
        "candidates_loaded": len(candidates),
    }
