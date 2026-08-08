"""File-backed services for validated application data."""

from .candidate_service import CandidateService
from .curriculum_service import CurriculumService

__all__ = ["CandidateService", "CurriculumService"]
