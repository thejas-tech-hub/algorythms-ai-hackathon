"""Pydantic schemas and loaders for candidate and curriculum JSON data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .json_loader import load_json_model


class DataRecord(BaseModel):
    """Permit source metadata while validating fields used by the application."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class TopicProgress(DataRecord):
    """A candidate's recorded progress for one curriculum topic."""

    topic_id: str
    status: str | None = None
    score: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def normalise_source_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        record = dict(value)
        record.setdefault("topic_id", record.get("topicId", record.get("id")))
        return record


class Candidate(DataRecord):
    """Validated candidate profile read from ``candidates.json``."""

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
        record = dict(value)
        # The actual JSON nests the ID inside "member.id"
        member = record.get("member")
        member_id = member.get("id") if isinstance(member, dict) else None
        record.setdefault("candidate_id", record.get("candidateId", record.get("id", member_id)))
        record.setdefault("name", member.get("name") if isinstance(member, dict) else None)
        record.setdefault("topic_progress", record.get("topicProgress", record.get("progress", [])))
        record.setdefault("completed_topics", record.get("completedTopics", []))
        record.setdefault("weak_topics", record.get("weakTopics", []))
        record.setdefault("skipped_topics", record.get("skippedTopics", []))
        return record


class CandidatesDocument(DataRecord):
    """Accepted root shape for ``candidates.json``."""

    candidates: list[Candidate]

    @model_validator(mode="before")
    @classmethod
    def normalise_root(cls, value: Any) -> Any:
        return {"candidates": value} if isinstance(value, list) else value


class CurriculumTopic(DataRecord):
    """Validated curriculum topic read from ``curriculum.json``."""

    topic_id: str
    title: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalise_source_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        record = dict(value)
        record.setdefault("topic_id", record.get("topicId", record.get("id")))
        record.setdefault("title", record.get("name"))
        return record


class CurriculumDocument(DataRecord):
    """Accepted root shape for ``curriculum.json``."""

    topics: list[CurriculumTopic]

    @model_validator(mode="before")
    @classmethod
    def normalise_root(cls, value: Any) -> Any:
        return {"topics": value} if isinstance(value, list) else value


def load_candidates() -> list[Candidate]:
    """Read and validate the application's ``candidates.json`` file."""
    return load_json_model("candidates.json", CandidatesDocument).candidates


def load_curriculum() -> list[CurriculumTopic]:
    """Read and validate the application's ``curriculum.json`` file."""
    return load_json_model("curriculum.json", CurriculumDocument).topics
