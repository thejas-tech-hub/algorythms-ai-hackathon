"""
Interview session schemas.
Owner: THEJAS

Defines the full request/response contract for the interview lifecycle:
create → ask → respond → summarize.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.common import BaseSchema, InterviewStatus, DifficultyLevel


class InterviewSessionCreate(BaseSchema):
    """Request body to start a new interview session."""

    candidate_id: str = Field(
        ...,
        description="ID of the candidate to interview (e.g. CAND-001)",
        examples=["CAND-001"],
    )


class InterviewMessage(BaseSchema):
    """A single message in the interview conversation."""

    role: str = Field(
        ...,
        description="Message author: 'interviewer' or 'candidate'",
    )
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict | None = None


class CandidateAnswer(BaseSchema):
    """Request body when the candidate submits an answer."""

    answer: str = Field(
        ...,
        min_length=1,
        description="The candidate's response text",
    )


class InterviewSession(BaseSchema):
    """Full state of an interview session — persisted in the session store."""

    session_id: str
    candidate_id: str
    status: InterviewStatus = InterviewStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    messages: list[InterviewMessage] = Field(default_factory=list)
    current_topic: str | None = None
    difficulty: DifficultyLevel = DifficultyLevel.FOUNDATIONAL
    current_question: str | None = None
    question: str | None = None
    question_number: int = 1
    questions_asked: int = 0
    metadata: dict = Field(default_factory=dict)


class InterviewSummary(BaseSchema):
    """Summary returned when an interview session ends."""

    session_id: str
    candidate_id: str
    status: InterviewStatus
    total_questions: int
    duration_seconds: float | None = None
    topics_covered: list[str] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # TODO: Add these fields when scoring / feedback is implemented
    # ------------------------------------------------------------------
    # overall_score: float | None = None
    # strengths: list[str] = Field(default_factory=list)
    # areas_for_improvement: list[str] = Field(default_factory=list)
    # recommendation: str | None = None
