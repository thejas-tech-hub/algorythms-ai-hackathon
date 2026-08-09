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
    """Summary returned when an interview session ends.

    Carries optional FinalInterviewReport data as an additive
    compatibility layer for the frontend.  The canonical report model
    (``FinalInterviewReport``) remains the internal source of truth;
    mapping is handled by ``FinalReportGenerator.report_to_summary_fields()``.
    """

    session_id: str
    candidate_id: str
    status: InterviewStatus
    total_questions: int
    responses_evaluated: int | None = None
    competencies_assessed: int | None = None
    duration_seconds: float | None = None
    topics_covered: list[str] = Field(default_factory=list)

    # ── Report fields (additive compatibility layer) ─────────────────
    overall_score: float | None = None
    recommendation: str | None = None
    competency_scores: list[dict] | None = None
    strengths: list[str] = Field(default_factory=list)
    areas_for_improvement: list[str] = Field(default_factory=list)
    summary: str | None = None
    executive_summary: str | None = None
    detailed_feedback: str | None = None
