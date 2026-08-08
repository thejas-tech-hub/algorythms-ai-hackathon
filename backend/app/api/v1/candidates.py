"""
Candidate lookup endpoints.
Owner: THEJAS

Read-only endpoints for browsing the candidate dataset.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_candidate_service
from app.models.candidate import CandidateDetail, CandidateListResponse
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.get(
    "",
    response_model=CandidateListResponse,
    summary="List all candidates",
    description="Return every candidate in the dataset with full mission history and signals.",
)
async def list_candidates(
    service: CandidateService = Depends(get_candidate_service),
) -> CandidateListResponse:
    """Return all candidates in the dataset."""
    candidates = service.list_all()
    return CandidateListResponse(candidates=candidates, total=len(candidates))


@router.get(
    "/{candidate_id}",
    response_model=CandidateDetail,
    summary="Get a single candidate",
    description="Return a candidate by ID with their complete profile, missions, and engagement signals.",
)
async def get_candidate(
    candidate_id: str,
    service: CandidateService = Depends(get_candidate_service),
) -> CandidateDetail:
    """Return a single candidate by ID with full mission history."""
    return service.get_by_id(candidate_id)
