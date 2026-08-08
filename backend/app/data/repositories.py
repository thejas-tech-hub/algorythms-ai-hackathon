"""Read-only repositories over the application JSON data files."""

from __future__ import annotations

from .candidate_loader import Candidate, CurriculumTopic, load_candidates, load_curriculum


class CandidateRepository:
    """Provide indexed, read-only access to candidates and their topic state."""

    def __init__(self, candidates: list[Candidate] | None = None) -> None:
        source = candidates if candidates is not None else load_candidates()
        self._by_id = {candidate.candidate_id: candidate for candidate in source}
        if len(self._by_id) != len(source):
            raise ValueError("candidates.json contains duplicate candidate_id values")

    def get_by_id(self, candidate_id: str) -> Candidate | None:
        """Return a candidate, or ``None`` when no matching ID exists."""
        return self._by_id.get(candidate_id)

    def list_all(self) -> list[Candidate]:
        """Return candidates in the order supplied by the source JSON."""
        return list(self._by_id.values())


class CurriculumRepository:
    """Provide indexed, read-only access to curriculum topics."""

    def __init__(self, topics: list[CurriculumTopic] | None = None) -> None:
        source = topics if topics is not None else load_curriculum()
        self._by_id = {topic.topic_id: topic for topic in source}
        if len(self._by_id) != len(source):
            raise ValueError("curriculum.json contains duplicate topic_id values")

    def get_by_id(self, topic_id: str) -> CurriculumTopic | None:
        """Return a curriculum topic, or ``None`` when no matching ID exists."""
        return self._by_id.get(topic_id)

    def list_all(self) -> list[CurriculumTopic]:
        """Return curriculum topics in the order supplied by the source JSON."""
        return list(self._by_id.values())
