"""Service for loading and querying validated candidate data."""

from __future__ import annotations

from pathlib import Path

from .json_loader import load_json_model
from .models import Candidate, CandidatesData


class CandidateService:
    """Provide read-only helpers over a validated ``candidates.json`` file.

    Progress status comparisons are case-insensitive. A score below
    ``weak_score_threshold`` is also classified as weak when no explicit weak
    topic list is supplied.
    """

    def __init__(self, candidates_path: str | Path, *, weak_score_threshold: float = 60) -> None:
        self._candidates_path = Path(candidates_path)
        self._weak_score_threshold = weak_score_threshold
        self._data = load_json_model(self._candidates_path, CandidatesData)
        self._by_id = {candidate.candidate_id: candidate for candidate in self._data.candidates}
        if len(self._by_id) != len(self._data.candidates):
            raise ValueError("candidates.json contains duplicate candidate_id values")

    def getCandidateById(self, candidate_id: str) -> Candidate | None:
        """Return the candidate with *candidate_id*, or ``None`` if absent."""
        return self._by_id.get(candidate_id)

    def getCompletedTopics(self, candidate_id: str) -> list[str]:
        """Return unique completed topic identifiers for a candidate."""
        return self._topic_ids(candidate_id, "completed_topics", {"completed", "complete", "mastered"})

    def getWeakTopics(self, candidate_id: str) -> list[str]:
        """Return explicit weak topics plus topics scoring below the threshold."""
        candidate = self._require_candidate(candidate_id)
        topic_ids = list(candidate.weak_topics)
        topic_ids.extend(
            progress.topic_id
            for progress in candidate.topic_progress
            if (progress.status or "").casefold() == "weak"
            or (progress.score is not None and progress.score < self._weak_score_threshold)
        )
        return self._unique(topic_ids)

    def getSkippedTopics(self, candidate_id: str) -> list[str]:
        """Return unique skipped topic identifiers for a candidate."""
        return self._topic_ids(candidate_id, "skipped_topics", {"skipped", "skip"})

    def summarizeCandidateProfile(self, candidate_id: str) -> dict[str, object]:
        """Return a compact, serialisable summary suitable for callers or logs."""
        candidate = self._require_candidate(candidate_id)
        completed = self.getCompletedTopics(candidate_id)
        weak = self.getWeakTopics(candidate_id)
        skipped = self.getSkippedTopics(candidate_id)
        return {
            "candidate_id": candidate.candidate_id,
            "name": candidate.name,
            "email": candidate.email,
            "completed_topics": completed,
            "weak_topics": weak,
            "skipped_topics": skipped,
            "progress_records": len(candidate.topic_progress),
        }

    def _topic_ids(self, candidate_id: str, direct_field: str, statuses: set[str]) -> list[str]:
        candidate = self._require_candidate(candidate_id)
        topic_ids = list(getattr(candidate, direct_field))
        topic_ids.extend(
            progress.topic_id
            for progress in candidate.topic_progress
            if (progress.status or "").casefold() in statuses
        )
        return self._unique(topic_ids)

    def _require_candidate(self, candidate_id: str) -> Candidate:
        candidate = self.getCandidateById(candidate_id)
        if candidate is None:
            raise KeyError(f"Unknown candidate_id: {candidate_id}")
        return candidate

    @staticmethod
    def _unique(topic_ids: list[str]) -> list[str]:
        return list(dict.fromkeys(topic_ids))
