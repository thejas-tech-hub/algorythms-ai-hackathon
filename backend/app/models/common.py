"""
Shared schemas, enums, and base models used across the application.
Owner: THEJAS

This module defines the vocabulary that all layers (API, services, data)
agree on. Changes here affect the entire contract.
"""

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base model with shared Pydantic configuration for all schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


# ── Enums ────────────────────────────────────────────────────────────


class InterviewStatus(str, Enum):
    """Lifecycle states for an interview session."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DifficultyLevel(str, Enum):
    """Question difficulty tiers used by the adaptive engine."""

    FOUNDATIONAL = "foundational"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class MissionOutcome(str, Enum):
    """Possible outcomes for a training mission."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ── Generic wrappers ────────────────────────────────────────────────

DataT = TypeVar("DataT")


class PaginatedResponse(BaseSchema, Generic[DataT]):
    """Generic paginated response wrapper."""

    items: list[DataT]
    total: int
    page: int = 1
    page_size: int = 20


class ErrorResponse(BaseSchema):
    """Standard error response body returned by exception handlers."""

    error: str
    detail: str
    request_id: str | None = None
