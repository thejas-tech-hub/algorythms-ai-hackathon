"""
Candidate lookup endpoints.
Owner: THEJAS

Read-only endpoints for browsing the candidate dataset.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_candidate_service
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.get(
    "",
    summary="List all candidates",
    description="Return every candidate in the dataset.",
)
async def list_candidates(
    service: CandidateService = Depends(get_candidate_service),
) -> dict:
    """Return all candidates in the dataset."""
    candidates = service.list_all()
    return {
        "candidates": [c.model_dump(mode="json") for c in candidates],
        "total": len(candidates),
    }


@router.get(
    "/{candidate_id}",
    summary="Get a single candidate",
    description="Return a candidate by ID.",
)
async def get_candidate(
    candidate_id: str,
    service: CandidateService = Depends(get_candidate_service),
) -> dict:
    """Return a single candidate by ID."""
    candidate = service.get_by_id(candidate_id)
    return candidate.model_dump(mode="json")
