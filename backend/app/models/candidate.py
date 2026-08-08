"""
Candidate-related Pydantic schemas.
Owner: THEJAS

These schemas mirror the structure of candidates.json exactly.
Field aliases map camelCase JSON keys to snake_case Python attributes.
"""

from __future__ import annotations

from pydantic import Field

from app.models.common import BaseSchema, MissionOutcome


class Mission(BaseSchema):
    """A single training mission attempted by a candidate."""

    day: int
    title: str
    passed: bool | None = None
    skipped: bool | None = None
    attempts: int | None = None

    @property
    def outcome(self) -> MissionOutcome:
        """Derive the mission outcome from the raw flags."""
        if self.skipped:
            return MissionOutcome.SKIPPED
        if self.passed:
            return MissionOutcome.PASSED
        return MissionOutcome.FAILED


class EngagementSignals(BaseSchema):
    """Aggregate engagement metrics for a candidate across the cohort."""

    commit_days: int = Field(alias="commitDays")
    missions_completed: int = Field(alias="missionsCompleted")
    missions_first_try: int = Field(alias="missionsFirstTry")


class CandidateProfile(BaseSchema):
    """Core identity and metadata for a candidate."""

    id: str
    name: str
    job_role: str = Field(alias="jobRole")
    years_experience: int = Field(alias="yearsExperience")
    education: str
    status: str


class CandidateDetail(BaseSchema):
    """
    Full candidate record including profile, mission history, and signals.

    This is the top-level object for each entry in candidates.json.
    """

    member: CandidateProfile
    missions: list[Mission]
    signals: EngagementSignals


class CandidateListResponse(BaseSchema):
    """Response schema for the list-all-candidates endpoint."""

    candidates: list[CandidateDetail]
    total: int
