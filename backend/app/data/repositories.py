"""
Abstract repository interfaces (protocols).
Owner: MOHAMMED

Defines data-access contracts so services depend on abstractions,
not on concrete storage implementations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models.candidate import CandidateDetail
from app.models.interview import InterviewSession


@runtime_checkable
class CandidateRepository(Protocol):
    """Contract for candidate data access."""

    def get_all(self) -> list[CandidateDetail]:
        """Return all candidates."""
        ...

    def get_by_id(self, candidate_id: str) -> CandidateDetail | None:
        """Return a single candidate by ID, or None if not found."""
        ...


@runtime_checkable
class SessionRepository(Protocol):
    """Contract for interview session persistence."""

    def save(self, session: InterviewSession) -> None:
        """Persist or update a session."""
        ...

    def get(self, session_id: str) -> InterviewSession | None:
        """Retrieve a session by ID, or None if not found."""
        ...

    def list_by_candidate(self, candidate_id: str) -> list[InterviewSession]:
        """List all sessions for a given candidate."""
        ...
