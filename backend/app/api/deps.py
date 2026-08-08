"""
FastAPI dependency injection factories.
Owner: THEJAS

Provides singleton service instances to routers via FastAPI's Depends().
All wiring is centralized here so routers stay thin and testable.
"""

from __future__ import annotations

from app.config import get_settings
from app.data.candidate_loader import JSONCandidateLoader
from app.data.session_store import InMemorySessionStore
from app.services.candidate_service import CandidateService
from app.services.interview_service import InterviewService


# ── Singletons ───────────────────────────────────────────────────────
# Created lazily on first access, reused for the lifetime of the process.

_candidate_loader: JSONCandidateLoader | None = None
_session_store: InMemorySessionStore = InMemorySessionStore()


def get_candidate_loader() -> JSONCandidateLoader:
    """Return the singleton candidate data loader (loading data on first call)."""
    global _candidate_loader
    if _candidate_loader is None:
        settings = get_settings()
        _candidate_loader = JSONCandidateLoader(settings.candidates_file)
        _candidate_loader.load()
    return _candidate_loader


def get_candidate_service() -> CandidateService:
    """Return a CandidateService wired to the singleton loader."""
    return CandidateService(repository=get_candidate_loader())


def get_interview_service() -> InterviewService:
    """Return an InterviewService wired to the session store and candidate service."""
    return InterviewService(
        session_store=_session_store,
        candidate_service=get_candidate_service(),
    )
