"""Pydantic models shared by the data services.

The normalisation aliases support the common snake_case and camelCase forms used
by JSON exports while preserving any additional source fields for callers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataModel(BaseModel):
    """Base model that accepts source-system metadata without discarding it."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class TopicProgress(DataModel):
    """A candidate's recorded state for one curriculum topic."""

    topic_id: str
    status: str | None = None
    score: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def normalise_topic_id(cls, value: Any) -> Any:
        if isinstance(value, dict) and "topic_id" not in value:
            value = dict(value)
            value["topic_id"] = value.get("topicId", value.get("id"))
        return value


class Candidate(DataModel):
    """Validated candidate profile and optional per-topic progress."""

    candidate_id: str
    name: str | None = None
    email: str | None = None
    topic_progress: list[TopicProgress] = Field(default_factory=list)
    completed_topics: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    skipped_topics: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalise_source_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        candidate = dict(value)
        candidate.setdefault("candidate_id", candidate.get("candidateId", candidate.get("id")))
        candidate.setdefault("topic_progress", candidate.get("topicProgress", candidate.get("progress", [])))
        candidate.setdefault("completed_topics", candidate.get("completedTopics", []))
        candidate.setdefault("weak_topics", candidate.get("weakTopics", []))
        candidate.setdefault("skipped_topics", candidate.get("skippedTopics", []))
        return candidate


class CandidatesData(DataModel):
    """Root structure for ``candidates.json``."""

    candidates: list[Candidate]

    @model_validator(mode="before")
    @classmethod
    def normalise_root(cls, value: Any) -> Any:
        return {"candidates": value} if isinstance(value, list) else value


class CurriculumTopic(DataModel):
    """A curriculum topic, retaining source metadata such as descriptions."""

    topic_id: str
    title: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalise_topic_id(cls, value: Any) -> Any:
        if isinstance(value, dict) and "topic_id" not in value:
            value = dict(value)
            value["topic_id"] = value.get("topicId", value.get("id"))
            value.setdefault("title", value.get("name"))
        return value


class CurriculumData(DataModel):
    """Root structure for ``curriculum.json``."""

    topics: list[CurriculumTopic]

    @model_validator(mode="before")
    @classmethod
    def normalise_root(cls, value: Any) -> Any:
        return {"topics": value} if isinstance(value, list) else value
