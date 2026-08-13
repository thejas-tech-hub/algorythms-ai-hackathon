"""
Adaptive interview intelligence domain contracts.
Owner: THEJAS

Shared Pydantic models for the adaptive interview pipeline:

    Candidate Dataset + Job Description / Technical Rubric
        + Candidate Intelligence + Session Memory
        → Interview Orchestrator → Interview Planner
        → Question Generator → Candidate Answer
        → Answer Evaluator → Adaptive Decision
        → Session Memory Update → Next Question / Final Report

These models are pure data contracts — no LLM calls, no RAG,
no external integrations.  They extend the existing BaseSchema and
reuse DifficultyLevel / InterviewStatus from common.py.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from app.models.common import BaseSchema, DifficultyLevel, InterviewStatus


# ── Enums ────────────────────────────────────────────────────────────


class CompetencyCategory(str, Enum):
    """High-level competency categories aligned to the technical rubric."""

    TECHNICAL = "technical"
    PROBLEM_SOLVING = "problem_solving"
    SYSTEM_DESIGN = "system_design"
    COMMUNICATION = "communication"
    BEHAVIORAL = "behavioral"


class ProficiencyLevel(str, Enum):
    """Assessed proficiency for a competency area."""

    NONE = "none"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class EvidenceStrength(str, Enum):
    """Strength of evidence supporting a rubric evaluation."""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    CONCLUSIVE = "conclusive"


class AdaptiveAction(str, Enum):
    """Actions the adaptive engine can take after evaluating an answer."""

    CONTINUE_SAME_TOPIC = "continue_same_topic"
    INCREASE_DIFFICULTY = "increase_difficulty"
    DECREASE_DIFFICULTY = "decrease_difficulty"
    SWITCH_TOPIC = "switch_topic"
    DEEP_DIVE = "deep_dive"
    CONCLUDE_INTERVIEW = "conclude_interview"


class QuestionType(str, Enum):
    """Classification of interview question types."""

    CONCEPTUAL = "conceptual"
    CODING = "coding"
    SCENARIO = "scenario"
    SYSTEM_DESIGN = "system_design"
    BEHAVIORAL = "behavioral"
    FOLLOW_UP = "follow_up"


class OverallRecommendation(str, Enum):
    """Final hiring recommendation derived from the interview."""

    STRONG_HIRE = "strong_hire"
    HIRE = "hire"
    LEAN_HIRE = "lean_hire"
    LEAN_NO_HIRE = "lean_no_hire"
    NO_HIRE = "no_hire"
    NEEDS_FURTHER_EVALUATION = "needs_further_evaluation"


# ── Competency Models ────────────────────────────────────────────────


class Competency(BaseSchema):
    """A single competency that can be assessed during an interview.

    Represents an entry in the technical rubric used by the Interview
    Planner and Answer Evaluator.
    """

    competency_id: str = Field(
        ...,
        description="Unique identifier for the competency (e.g. 'python-async')",
        examples=["python-async", "system-design-scalability"],
    )
    name: str = Field(
        ...,
        description="Human-readable competency name",
        examples=["Asynchronous Python", "Scalable System Design"],
    )
    category: CompetencyCategory = Field(
        ...,
        description="High-level category this competency falls under",
    )
    description: str = Field(
        default="",
        description="Detailed description of what this competency covers",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="Relative importance weight (0.0–10.0) for scoring",
    )
    prerequisite_ids: list[str] = Field(
        default_factory=list,
        description="Competency IDs that should be assessed before this one",
    )


class CompetencyState(BaseSchema):
    """Tracks the assessed state of a single competency within a session.

    Updated by the Answer Evaluator after each question-answer cycle.
    """

    competency_id: str = Field(
        ...,
        description="References a Competency.competency_id",
    )
    proficiency: ProficiencyLevel = Field(
        default=ProficiencyLevel.NONE,
        description="Current assessed proficiency level",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the proficiency assessment (0.0–1.0)",
    )
    questions_asked: int = Field(
        default=0,
        ge=0,
        description="Number of questions asked on this competency",
    )
    questions_answered_correctly: int = Field(
        default=0,
        ge=0,
        description="Number of questions answered satisfactorily",
    )
    last_difficulty: DifficultyLevel | None = Field(
        default=None,
        description="Difficulty of the last question asked on this competency",
    )
    evidence_notes: list[str] = Field(
        default_factory=list,
        description="Evaluator notes supporting the proficiency rating",
    )
    assessed_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria/objectives already assessed for this competency",
    )


# ── Candidate Intelligence ───────────────────────────────────────────


class CandidateIntelligenceProfile(BaseSchema):
    """Pre-interview intelligence derived from the candidate dataset.

    Built by the Candidate Intelligence module from topic progress,
    mission history, and engagement signals.  Consumed by the
    Interview Planner to personalise the question sequence.
    """

    candidate_id: str = Field(
        ...,
        description="References the candidate's ID in the dataset",
        examples=["CAND-001"],
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Topic IDs / areas where the candidate excelled",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Topic IDs / areas where the candidate struggled",
    )
    skipped_areas: list[str] = Field(
        default_factory=list,
        description="Topic IDs the candidate skipped entirely",
    )
    completion_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of curriculum completed (0.0–1.0)",
    )
    suggested_start_difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.FOUNDATIONAL,
        description="Recommended starting difficulty based on profile analysis",
    )
    suggested_focus_areas: list[str] = Field(
        default_factory=list,
        description="Competency / topic IDs the interview should prioritise",
    )
    raw_signals: dict[str, Any] = Field(
        default_factory=dict,
        description="Pass-through engagement signals from the dataset",
    )


# ── Rubric Evidence ──────────────────────────────────────────────────


class RubricEvidence(BaseSchema):
    """A discrete piece of evidence gathered from a candidate's answer.

    The Answer Evaluator produces one or more RubricEvidence items per
    answer.  These are aggregated into CompetencyState updates and feed
    into the Final Report.
    """

    competency_id: str = Field(
        ...,
        description="Competency this evidence relates to",
    )
    criterion: str = Field(
        ...,
        description="Specific rubric criterion being evaluated",
        examples=["Understands event loop mechanics"],
    )
    demonstrated: bool = Field(
        ...,
        description="Whether the candidate demonstrated this criterion",
    )
    strength: EvidenceStrength = Field(
        default=EvidenceStrength.MODERATE,
        description="How strongly the answer supports or refutes the criterion",
    )
    notes: str = Field(
        default="",
        description="Free-form evaluator commentary",
    )


# ── Question Plan ────────────────────────────────────────────────────


class QuestionPlan(BaseSchema):
    """A planned interview question generated by the Interview Planner.

    The Question Generator consumes a QuestionPlan to produce the
    actual question text.
    """

    plan_id: str = Field(
        ...,
        description="Unique plan identifier for traceability",
        examples=["qp-001"],
    )
    competency_id: str = Field(
        ...,
        description="Target competency to assess",
    )
    target_difficulty: DifficultyLevel = Field(
        ...,
        description="Intended difficulty for this question",
    )
    question_type: QuestionType = Field(
        default=QuestionType.CONCEPTUAL,
        description="Type of question to generate",
    )
    topic_context: str = Field(
        default="",
        description="Contextual notes for the question generator",
    )
    follow_up_to: str | None = Field(
        default=None,
        description="plan_id of the prior question if this is a follow-up",
    )
    max_time_seconds: int = Field(
        default=300,
        ge=30,
        le=1800,
        description="Expected maximum time for the candidate to answer (30–1800s)",
    )
    objective: str = Field(
        default="",
        description="Concise statement of what the question should assess",
        examples=["Verify whether the candidate understands async/await error propagation"],
    )
    expected_criteria: list[str] = Field(
        default_factory=list,
        description="Rubric criteria the AnswerEvaluator should check for in the answer",
    )
    selection_reasoning: str = Field(
        default="",
        description="Why the planner selected this competency, difficulty, and question type",
    )
    generated_question_text: str | None = Field(
        default=None,
        description="Populated after the Question Generator produces the text",
    )
    target_gap: str | None = Field(
        default=None,
        description="The specific gap, misconception, or weakness this question targets",
    )
    question_intent: str | None = Field(
        default=None,
        description="What kind of evidence this question seeks (e.g. 'probe misconception', 'assess practical depth')",
    )
    evidence_basis: list[str] = Field(
        default_factory=list,
        description="Evaluation evidence items that drove the creation of this plan",
    )
    assessed_objectives: list[str] = Field(
        default_factory=list,
        description="Objectives already assessed for this competency (for rotation)",
    )


# ── Answer Evaluation ────────────────────────────────────────────────


class AnswerEvaluation(BaseSchema):
    """Structured evaluation of a single candidate answer.

    Produced by the Answer Evaluator.  Feeds into the Adaptive Decision
    and Session Memory Update steps.
    """

    evaluation_id: str = Field(
        ...,
        description="Unique evaluation identifier",
        examples=["eval-001"],
    )
    plan_id: str = Field(
        ...,
        description="References the QuestionPlan that triggered this answer",
    )
    competency_id: str = Field(
        ...,
        description="Competency this evaluation applies to (denormalized from QuestionPlan)",
    )
    question_text: str = Field(
        default="",
        description="Text of the question that was evaluated",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Legacy normalized score (0.0–10.0)",
    )
    overall_score: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Overall score on a 0–100 scale",
    )
    conceptual_correctness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="How well the answer reflects the core concept",
    )
    depth_reasoning_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="How much reasoning, trade-off analysis, or nuance the answer shows",
    )
    practical_understanding_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="How well the answer connects the concept to practice",
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Evaluator confidence in the assessment",
    )
    evidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Evidence strength derived from the answer",
    )
    max_score: float = Field(
        default=10.0,
        ge=0.0,
        le=10.0,
        description="Maximum possible score",
    )
    evidence: list[RubricEvidence] = Field(
        default_factory=list,
        description="Rubric evidence gathered from the answer",
    )
    feedback: str = Field(
        default="",
        description="Textual feedback on the candidate's answer",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Specific strengths demonstrated in the candidate's answer",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Specific weaknesses or gaps in the candidate's answer",
    )
    missing_concepts: list[str] = Field(
        default_factory=list,
        description="Core concepts not yet demonstrated in the answer",
    )
    misconceptions: list[str] = Field(
        default_factory=list,
        description="Incorrect or misleading ideas detected in the answer",
    )
    rationale: str = Field(
        default="",
        description="Concise evaluator rationale",
    )
    follow_up_needed: bool = Field(
        default=False,
        description="Whether the evaluator recommends a follow-up question",
    )
    evaluated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of evaluation",
    )

    @model_validator(mode="after")
    def score_within_max(self) -> "AnswerEvaluation":
        """Ensure score does not exceed max_score."""
        if self.overall_score is None:
            self.overall_score = round(self.score * 10.0, 2)
        if self.score > self.max_score:
            raise ValueError(
                f"score ({self.score}) cannot exceed max_score ({self.max_score})"
            )
        return self


# ── Adaptive Decision ────────────────────────────────────────────────


class AdaptiveDecision(BaseSchema):
    """Decision made by the Adaptive Decision engine after evaluation.

    Determines what happens next in the interview: change topic,
    adjust difficulty, deep-dive, or conclude.
    """

    decision_id: str = Field(
        ...,
        description="Unique decision identifier",
        examples=["dec-001"],
    )
    evaluation_id: str = Field(
        ...,
        description="References the AnswerEvaluation that triggered this decision",
    )
    action: AdaptiveAction = Field(
        ...,
        description="The adaptive action to take",
    )
    next_competency_id: str | None = Field(
        default=None,
        description="Competency to target next (if action involves a switch)",
    )
    next_difficulty: DifficultyLevel | None = Field(
        default=None,
        description="Difficulty for the next question (if adjusting)",
    )
    reasoning: str = Field(
        default="",
        description="Explanation of why this action was chosen",
    )
    decided_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the decision",
    )


# ── Session Memory ───────────────────────────────────────────────────


class SessionMemorySnapshot(BaseSchema):
    """Point-in-time snapshot of the adaptive session memory.

    Maintained by the Session Memory module and consumed by the
    Interview Planner and Adaptive Decision engine.  A new snapshot
    is created after every question-answer-evaluation cycle.
    """

    session_id: str = Field(
        ...,
        description="References the InterviewSession.session_id",
    )
    snapshot_index: int = Field(
        ...,
        ge=0,
        description="Ordinal index of this snapshot within the session",
    )
    candidate_id: str = Field(
        ...,
        description="References the candidate being interviewed",
    )
    competency_states: list[CompetencyState] = Field(
        default_factory=list,
        description="Current assessed state of each competency",
    )
    questions_plan_history: list[QuestionPlan] = Field(
        default_factory=list,
        description="All question plans generated so far",
    )
    evaluation_history: list[AnswerEvaluation] = Field(
        default_factory=list,
        description="All evaluations produced so far",
    )
    decision_history: list[AdaptiveDecision] = Field(
        default_factory=list,
        description="All adaptive decisions taken so far",
    )
    current_difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.FOUNDATIONAL,
        description="Effective difficulty level right now",
    )
    current_competency_id: str | None = Field(
        default=None,
        description="Competency currently being assessed",
    )
    total_questions_asked: int = Field(
        default=0,
        ge=0,
        description="Running count of questions asked",
    )
    topics_covered: list[str] = Field(
        default_factory=list,
        description="Competency IDs already covered",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when this snapshot was created",
    )


# ── Final Interview Report ───────────────────────────────────────────


class CompetencyScore(BaseSchema):
    """Per-competency scoring entry in the final report."""

    competency_id: str
    competency_name: str = Field(default="")
    category: CompetencyCategory = Field(default=CompetencyCategory.TECHNICAL)
    proficiency: ProficiencyLevel = Field(default=ProficiencyLevel.NONE)
    score: float = Field(default=0.0, ge=0.0, le=10.0)
    max_score: float = Field(default=10.0, ge=0.0, le=10.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)
    notes: str = Field(default="")


class FinalInterviewReport(BaseSchema):
    """Comprehensive report generated at the end of an interview.

    Aggregates all session data — competency states, evaluations,
    evidence, and adaptive decisions — into a structured document
    suitable for review by hiring managers.
    """

    report_id: str = Field(
        ...,
        description="Unique report identifier",
        examples=["rpt-001"],
    )
    session_id: str = Field(
        ...,
        description="References the concluded InterviewSession",
    )
    candidate_id: str = Field(
        ...,
        description="References the candidate",
    )
    status: InterviewStatus = Field(
        default=InterviewStatus.COMPLETED,
        description="Interview status at report generation time",
    )
    overall_score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Weighted aggregate score (0.0–10.0)",
    )
    recommendation: OverallRecommendation = Field(
        default=OverallRecommendation.NEEDS_FURTHER_EVALUATION,
        description="Final hiring recommendation",
    )
    competency_scores: list[CompetencyScore] = Field(
        default_factory=list,
        description="Per-competency detailed scores",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Key strengths identified during the interview",
    )
    areas_for_improvement: list[str] = Field(
        default_factory=list,
        description="Areas where the candidate should improve",
    )
    total_questions: int = Field(
        default=0,
        ge=0,
        description="Total questions asked during the interview",
    )
    total_duration_seconds: float | None = Field(
        default=None,
        description="Interview duration in seconds",
    )
    topics_covered: list[str] = Field(
        default_factory=list,
        description="Competency IDs covered during the interview",
    )
    executive_summary: str = Field(
        default="",
        description="Brief narrative summary of the interview",
    )
    detailed_feedback: str = Field(
        default="",
        description="Detailed evaluator feedback",
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of report generation",
    )
