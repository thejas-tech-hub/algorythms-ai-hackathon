"""Service for loading and querying validated curriculum data."""

from __future__ import annotations

from pathlib import Path

from .json_loader import load_json_model
from .models import CurriculumData, CurriculumTopic


class CurriculumService:
    """Provide read-only access to the validated topics in ``curriculum.json``."""

    def __init__(self, curriculum_path: str | Path) -> None:
        self._curriculum_path = Path(curriculum_path)
        self._data = load_json_model(self._curriculum_path, CurriculumData)
        self._by_id = {topic.topic_id: topic for topic in self._data.topics}
        if len(self._by_id) != len(self._data.topics):
            raise ValueError("curriculum.json contains duplicate topic_id values")

    def getTopicById(self, topic_id: str) -> CurriculumTopic | None:
        """Return the topic with *topic_id*, or ``None`` when it is not present."""
        return self._by_id.get(topic_id)

    def getTopics(self) -> list[CurriculumTopic]:
        """Return all validated curriculum topics in their source order."""
        return list(self._data.topics)
