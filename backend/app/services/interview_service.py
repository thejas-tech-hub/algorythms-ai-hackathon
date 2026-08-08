"""
Interview session orchestration.
Owner: THEJAS

Manages the full interview session lifecycle: create → ask → respond → end.
All adaptive logic (question selection, evaluation, scoring) is stubbed
with TODO markers for future implementation.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.data.session_store import InMemorySessionStore
from app.models.interview import (
    InterviewSession,
    InterviewSessionCreate,
    InterviewMessage,
    InterviewSummary,
    CandidateAnswer,
)
from app.models.common import InterviewStatus
from app.services.candidate_service import CandidateService
from app.core.exceptions import SessionNotFoundError, SessionExpiredError
from app.core.logging import get_logger

logger = get_logger(__name__)


class InterviewService:
    """
    Manages the full interview session lifecycle.

    Dependencies are injected via constructor so this service
    can be tested with mocks.
    """

    def __init__(
        self,
        session_store: InMemorySessionStore,
        candidate_service: CandidateService,
    ) -> None:
        self._sessions = session_store
        self._candidates = candidate_service

    def create_session(self, request: InterviewSessionCreate) -> InterviewSession:
        """
        Start a new interview session for a candidate.

        Validates the candidate exists, creates a session, and adds
        an initial welcome message.
        """
        # Validate candidate exists (raises CandidateNotFoundError if not)
        candidate = self._candidates.get_by_id(request.candidate_id)

        session = InterviewSession(
            session_id=str(uuid.uuid4()),
            candidate_id=candidate.member.id,
            status=InterviewStatus.IN_PROGRESS,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # TODO: Generate the first adaptive question based on candidate profile
        welcome = InterviewMessage(
            role="interviewer",
            content=(
                f"Interview session started for {candidate.member.name}. "
                f"Role: {candidate.member.job_role}. "
                f"Welcome! The adaptive interview will begin shortly."
            ),
        )
        session.messages.append(welcome)
        session.questions_asked = 1

        self._sessions.save(session)
        logger.info(
            "Created session %s for candidate %s (%s)",
            session.session_id,
            session.candidate_id,
            candidate.member.name,
        )
        return session

    def get_session(self, session_id: str) -> InterviewSession:
        """
        Retrieve a session by ID.

        Raises:
            SessionNotFoundError: If the session does not exist.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def submit_answer(
        self, session_id: str, answer: CandidateAnswer
    ) -> InterviewSession:
        """
        Process a candidate's answer and generate the next question.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionExpiredError: If the session is no longer in progress.
        """
        session = self.get_session(session_id)

        if session.status != InterviewStatus.IN_PROGRESS:
            raise SessionExpiredError(session_id)

        # Record the candidate's answer
        session.messages.append(
            InterviewMessage(role="candidate", content=answer.answer)
        )

        # ------------------------------------------------------------------
        # TODO: Implement adaptive logic here
        # 1. Evaluate the answer using the AI engine
        # 2. Determine the next topic based on candidate's mission history
        # 3. Adjust difficulty level based on answer quality
        # 4. Generate the next question via the AI engine
        # ------------------------------------------------------------------
        next_question = InterviewMessage(
            role="interviewer",
            content="[TODO] Next adaptive question will be generated here.",
        )
        session.messages.append(next_question)
        session.questions_asked += 1
        session.updated_at = datetime.utcnow()

        self._sessions.save(session)
        logger.info(
            "Session %s: answer recorded, question #%d generated",
            session_id,
            session.questions_asked,
        )
        return session

    def end_session(self, session_id: str) -> InterviewSummary:
        """
        End a session and produce a summary.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionExpiredError: If the session has already been completed.
        """
        session = self.get_session(session_id)

        if session.status == InterviewStatus.COMPLETED:
            raise SessionExpiredError(session_id)

        session.status = InterviewStatus.COMPLETED
        session.updated_at = datetime.utcnow()
        self._sessions.save(session)

        duration = (session.updated_at - session.created_at).total_seconds()

        # ------------------------------------------------------------------
        # TODO: Generate comprehensive interview summary
        # - Score each topic covered
        # - Identify strengths and weaknesses
        # - Produce a hiring recommendation
        # - Generate detailed feedback via AI engine
        # ------------------------------------------------------------------

        logger.info(
            "Session %s ended. %d questions, %.1fs duration",
            session_id,
            session.questions_asked,
            duration,
        )

        return InterviewSummary(
            session_id=session.session_id,
            candidate_id=session.candidate_id,
            status=session.status,
            total_questions=session.questions_asked,
            duration_seconds=round(duration, 2),
            topics_covered=[],  # TODO: populate from session state
        )
