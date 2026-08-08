"""Validated, file-backed data access for the application.

This package deliberately has no FastAPI dependencies.  API handlers and
business services can depend on its repositories without knowing how the JSON
files are stored.
"""

from .candidate_loader import Candidate, CurriculumTopic
from .repositories import CandidateRepository, CurriculumRepository
from .session_store import SessionStore

__all__ = [
    "Candidate",
    "CandidateRepository",
    "CurriculumRepository",
    "CurriculumTopic",
    "SessionStore",
]
