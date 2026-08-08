"""
Candidate business logic.
Owner: THEJAS

Pure business logic for candidate lookup and analytics.
No HTTP concerns, no direct file I/O — depends on a repository abstraction.
"""

from __future__ import annotations

from app.data.candidate_loader import JSONCandidateLoader
from app.models.candidate import CandidateDetail
from app.core.exceptions import CandidateNotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


class CandidateService:
    """Handles candidate lookup and derived analytics."""

    def __init__(self, repository: JSONCandidateLoader) -> None:
        self._repo = repository

    def list_all(self) -> list[CandidateDetail]:
        """Return all candidates in the dataset."""
        candidates = self._repo.get_all()
        logger.debug("Listing %d candidates", len(candidates))
        return candidates

    def get_by_id(self, candidate_id: str) -> CandidateDetail:
        """
        Return a single candidate by ID.

        Raises:
            CandidateNotFoundError: If the candidate ID does not exist.
        """
        candidate = self._repo.get_by_id(candidate_id)
        if candidate is None:
            logger.warning("Candidate not found: %s", candidate_id)
            raise CandidateNotFoundError(candidate_id)
        return candidate

    # ------------------------------------------------------------------
    # TODO: Add derived analytics methods below
    # ------------------------------------------------------------------
    # def compute_strength_areas(self, candidate_id: str) -> list[str]:
    #     """Identify topics where the candidate excelled (passed first try)."""
    #     ...
    #
    # def compute_struggle_areas(self, candidate_id: str) -> list[str]:
    #     """Identify topics where the candidate struggled (failed/many attempts)."""
    #     ...
    #
    # def compute_completion_rate(self, candidate_id: str) -> float:
    #     """Calculate the percentage of missions completed successfully."""
    #     ...
    #
    # def get_skipped_topics(self, candidate_id: str) -> list[str]:
    #     """Return mission titles the candidate skipped entirely."""
    #     ...
