"""
Interview session endpoints.
Owner: THEJAS

CRUD-style endpoints for the interview session lifecycle.
All adaptive logic is delegated to InterviewService (which stubs it for now).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_interview_service
from app.models.interview import (
    InterviewSession,
    InterviewSessionCreate,
    InterviewSummary,
    CandidateAnswer,
)
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/interviews", tags=["Interviews"])


@router.post(
    "",
    response_model=InterviewSession,
    status_code=201,
    summary="Start a new interview",
    description="Create a new adaptive interview session for the specified candidate.",
)
async def create_interview(
    body: InterviewSessionCreate,
    service: InterviewService = Depends(get_interview_service),
) -> InterviewSession:
    """Start a new adaptive interview session for a candidate."""
    return service.create_session(body)


@router.get(
    "/{session_id}",
    response_model=InterviewSession,
    summary="Get interview session state",
    description="Retrieve the current state and message history of an interview session.",
)
async def get_interview(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
) -> InterviewSession:
    """Retrieve the current state of an interview session."""
    return service.get_session(session_id)


@router.post(
    "/{session_id}/respond",
    response_model=InterviewSession,
    summary="Submit an answer",
    description="Submit the candidate's answer and receive the next adaptive question.",
)
async def submit_answer(
    session_id: str,
    body: CandidateAnswer,
    service: InterviewService = Depends(get_interview_service),
) -> InterviewSession:
    """Submit a candidate's answer and receive the next question."""
    return service.submit_answer(session_id, body)


@router.post(
    "/{session_id}/end",
    response_model=InterviewSummary,
    summary="End an interview",
    description="End the interview session and receive a summary of the conversation.",
)
async def end_interview(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
) -> InterviewSummary:
    """End the interview session and receive a summary."""
    return service.end_session(session_id)
