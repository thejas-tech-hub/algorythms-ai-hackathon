"""
FastAPI dependency injection factories.
Owner: THEJAS

Provides singleton service instances to routers via FastAPI's Depends().
All wiring is centralized here so routers stay thin and testable.
"""

from __future__ import annotations

from app.data.repositories import CandidateRepository
from app.data.session_store import SessionStore
from app.services.candidate_service import CandidateService
from app.services.interview_service import InterviewService


# ── Singletons ───────────────────────────────────────────────────────
# Created lazily on first access, reused for the lifetime of the process.

_candidate_repo: CandidateRepository | None = None
_session_store: SessionStore = SessionStore()


def get_candidate_repo() -> CandidateRepository:
    """Return the singleton CandidateRepository (loads data on first call)."""
    global _candidate_repo
    if _candidate_repo is None:
        _candidate_repo = CandidateRepository()
    return _candidate_repo


def get_candidate_service() -> CandidateService:
    """Return a CandidateService wired to the singleton repository."""
    return CandidateService(repository=get_candidate_repo())


def get_interview_service() -> InterviewService:
    """Return an InterviewService wired to the session store and candidate service."""
    return InterviewService(
        session_store=_session_store,
        candidate_service=get_candidate_service(),
    )
