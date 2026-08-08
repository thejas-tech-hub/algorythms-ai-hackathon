"""Structured models returned by curriculum retrieval services."""

from __future__ import annotations

from pydantic import Field

from app.models.common import BaseSchema


class CurriculumRetrievalDocument(BaseSchema):
    """One curriculum day represented as a retrieval document."""

    day: int = Field(..., ge=1)
    title: str
    type: str
    tools: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)


class CurriculumRelevance(BaseSchema):
    """Why a curriculum document matched a retrieval request."""

    score: float = Field(..., ge=0)
    match_type: str
    matched_terms: list[str] = Field(default_factory=list)
    matched_fields: dict[str, list[str]] = Field(default_factory=dict)
    explanation: str = ""


class CurriculumRetrievalResult(CurriculumRetrievalDocument):
    """A retrieval document plus relevance metadata."""

    relevance: CurriculumRelevance
