"""
In-memory session store.
Owner: MOHAMMED

Dict-backed session persistence. Designed to be replaced with
Redis, PostgreSQL, or any other backend by implementing the
SessionRepository protocol.
"""

from __future__ import annotations

from app.models.interview import InterviewSession
from app.core.logging import get_logger

logger = get_logger(__name__)


class InMemorySessionStore:
    """
    In-memory dict-backed session store.

    Implements the SessionRepository protocol defined in repositories.py.

    Warning:
        All data is lost on server restart. Use only for development
        and testing. Swap to a persistent store for production.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, InterviewSession] = {}

    def save(self, session: InterviewSession) -> None:
        """Persist or update a session in memory."""
        self._sessions[session.session_id] = session
        logger.debug("Session %s saved", session.session_id)

    def get(self, session_id: str) -> InterviewSession | None:
        """Retrieve a session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def list_by_candidate(self, candidate_id: str) -> list[InterviewSession]:
        """Return all sessions belonging to a specific candidate."""
        return [
            s for s in self._sessions.values()
            if s.candidate_id == candidate_id
        ]
