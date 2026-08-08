"""
Tests for adaptive interview intelligence domain contracts.
Owner: THEJAS

Covers:
    - Model construction (all 9 new models + CompetencyScore)
    - Validation (boundary values, required fields, constraints)
    - Serialization (JSON round-trip)
    - Enum values (every new enum)
    - Nested objects (deeply nested graphs)
    - Backward compatibility (existing models untouched)
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

# ── Adaptive models under test ──────────────────────────────────────
from app.models.adaptive import (
    AdaptiveAction,
    AdaptiveDecision,
    AnswerEvaluation,
    CandidateIntelligenceProfile,
    Competency,
    CompetencyCategory,
    CompetencyScore,
    CompetencyState,
    EvidenceStrength,
    FinalInterviewReport,
    OverallRecommendation,
    ProficiencyLevel,
    QuestionPlan,
    QuestionType,
    RubricEvidence,
    SessionMemorySnapshot,
)

# ── Existing models (backward compatibility check) ──────────────────
from app.models.common import (
    BaseSchema,
    DifficultyLevel,
    InterviewStatus,
    MissionOutcome,
    PaginatedResponse,
    ErrorResponse,
)
from app.models.interview import (
    InterviewSession,
    InterviewSessionCreate,
    InterviewMessage,
    InterviewSummary,
    CandidateAnswer,
)
from app.models.candidate import (
    Mission,
    EngagementSignals,
    CandidateProfile,
    CandidateDetail,
    CandidateListResponse,
)


# =====================================================================
# SECTION 1: ENUM TESTS
# =====================================================================


class TestCompetencyCategory:
    """Verify all CompetencyCategory enum members."""

    def test_all_members_exist(self):
        assert CompetencyCategory.TECHNICAL == "technical"
        assert CompetencyCategory.PROBLEM_SOLVING == "problem_solving"
        assert CompetencyCategory.SYSTEM_DESIGN == "system_design"
        assert CompetencyCategory.COMMUNICATION == "communication"
        assert CompetencyCategory.BEHAVIORAL == "behavioral"

    def test_member_count(self):
        assert len(CompetencyCategory) == 5

    def test_is_string_enum(self):
        assert isinstance(CompetencyCategory.TECHNICAL, str)

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            CompetencyCategory("nonexistent")


class TestProficiencyLevel:
    """Verify all ProficiencyLevel enum members."""

    def test_all_members_exist(self):
        assert ProficiencyLevel.NONE == "none"
        assert ProficiencyLevel.BEGINNER == "beginner"
        assert ProficiencyLevel.INTERMEDIATE == "intermediate"
        assert ProficiencyLevel.ADVANCED == "advanced"
        assert ProficiencyLevel.EXPERT == "expert"

    def test_member_count(self):
        assert len(ProficiencyLevel) == 5


class TestEvidenceStrength:
    """Verify all EvidenceStrength enum members."""

    def test_all_members_exist(self):
        assert EvidenceStrength.WEAK == "weak"
        assert EvidenceStrength.MODERATE == "moderate"
        assert EvidenceStrength.STRONG == "strong"
        assert EvidenceStrength.CONCLUSIVE == "conclusive"

    def test_member_count(self):
        assert len(EvidenceStrength) == 4


class TestAdaptiveAction:
    """Verify all AdaptiveAction enum members."""

    def test_all_members_exist(self):
        assert AdaptiveAction.CONTINUE_SAME_TOPIC == "continue_same_topic"
        assert AdaptiveAction.INCREASE_DIFFICULTY == "increase_difficulty"
        assert AdaptiveAction.DECREASE_DIFFICULTY == "decrease_difficulty"
        assert AdaptiveAction.SWITCH_TOPIC == "switch_topic"
        assert AdaptiveAction.DEEP_DIVE == "deep_dive"
        assert AdaptiveAction.CONCLUDE_INTERVIEW == "conclude_interview"

    def test_member_count(self):
        assert len(AdaptiveAction) == 6


class TestQuestionType:
    """Verify all QuestionType enum members."""

    def test_all_members_exist(self):
        assert QuestionType.CONCEPTUAL == "conceptual"
        assert QuestionType.CODING == "coding"
        assert QuestionType.SCENARIO == "scenario"
        assert QuestionType.SYSTEM_DESIGN == "system_design"
        assert QuestionType.BEHAVIORAL == "behavioral"
        assert QuestionType.FOLLOW_UP == "follow_up"

    def test_member_count(self):
        assert len(QuestionType) == 6


class TestOverallRecommendation:
    """Verify all OverallRecommendation enum members."""

    def test_all_members_exist(self):
        assert OverallRecommendation.STRONG_HIRE == "strong_hire"
        assert OverallRecommendation.HIRE == "hire"
        assert OverallRecommendation.LEAN_HIRE == "lean_hire"
        assert OverallRecommendation.LEAN_NO_HIRE == "lean_no_hire"
        assert OverallRecommendation.NO_HIRE == "no_hire"
        assert OverallRecommendation.NEEDS_FURTHER_EVALUATION == "needs_further_evaluation"

    def test_member_count(self):
        assert len(OverallRecommendation) == 6


# =====================================================================
# SECTION 2: MODEL CONSTRUCTION TESTS
# =====================================================================


class TestCompetency:
    """Test Competency model construction and validation."""

    def test_minimal_construction(self):
        c = Competency(
            competency_id="python-async",
            name="Asynchronous Python",
            category=CompetencyCategory.TECHNICAL,
        )
        assert c.competency_id == "python-async"
        assert c.name == "Asynchronous Python"
        assert c.category == CompetencyCategory.TECHNICAL
        assert c.description == ""
        assert c.weight == 1.0
        assert c.prerequisite_ids == []

    def test_full_construction(self):
        c = Competency(
            competency_id="sys-design",
            name="System Design",
            category=CompetencyCategory.SYSTEM_DESIGN,
            description="Ability to design scalable systems",
            weight=5.0,
            prerequisite_ids=["python-basics", "data-structures"],
        )
        assert c.weight == 5.0
        assert len(c.prerequisite_ids) == 2

    def test_weight_boundaries(self):
        # Min weight
        c = Competency(competency_id="a", name="A", category=CompetencyCategory.TECHNICAL, weight=0.0)
        assert c.weight == 0.0

        # Max weight
        c = Competency(competency_id="b", name="B", category=CompetencyCategory.TECHNICAL, weight=10.0)
        assert c.weight == 10.0

    def test_weight_out_of_range_raises(self):
        with pytest.raises(Exception):
            Competency(competency_id="x", name="X", category=CompetencyCategory.TECHNICAL, weight=11.0)

        with pytest.raises(Exception):
            Competency(competency_id="x", name="X", category=CompetencyCategory.TECHNICAL, weight=-0.1)

    def test_missing_required_field_raises(self):
        with pytest.raises(Exception):
            Competency(name="Missing ID", category=CompetencyCategory.TECHNICAL)


class TestCompetencyState:
    """Test CompetencyState model construction and validation."""

    def test_minimal_construction(self):
        cs = CompetencyState(competency_id="python-async")
        assert cs.competency_id == "python-async"
        assert cs.proficiency == ProficiencyLevel.NONE
        assert cs.confidence == 0.0
        assert cs.questions_asked == 0
        assert cs.questions_answered_correctly == 0
        assert cs.last_difficulty is None
        assert cs.evidence_notes == []

    def test_full_construction(self):
        cs = CompetencyState(
            competency_id="python-async",
            proficiency=ProficiencyLevel.ADVANCED,
            confidence=0.85,
            questions_asked=5,
            questions_answered_correctly=4,
            last_difficulty=DifficultyLevel.ADVANCED,
            evidence_notes=["Strong grasp of coroutines", "Good error handling"],
        )
        assert cs.proficiency == ProficiencyLevel.ADVANCED
        assert cs.confidence == 0.85
        assert len(cs.evidence_notes) == 2

    def test_confidence_boundaries(self):
        cs = CompetencyState(competency_id="x", confidence=0.0)
        assert cs.confidence == 0.0

        cs = CompetencyState(competency_id="x", confidence=1.0)
        assert cs.confidence == 1.0

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(Exception):
            CompetencyState(competency_id="x", confidence=1.1)

        with pytest.raises(Exception):
            CompetencyState(competency_id="x", confidence=-0.01)

    def test_negative_questions_asked_raises(self):
        with pytest.raises(Exception):
            CompetencyState(competency_id="x", questions_asked=-1)


class TestCandidateIntelligenceProfile:
    """Test CandidateIntelligenceProfile model."""

    def test_minimal_construction(self):
        cip = CandidateIntelligenceProfile(candidate_id="CAND-001")
        assert cip.candidate_id == "CAND-001"
        assert cip.strengths == []
        assert cip.weaknesses == []
        assert cip.skipped_areas == []
        assert cip.completion_rate == 0.0
        assert cip.suggested_start_difficulty == DifficultyLevel.FOUNDATIONAL
        assert cip.suggested_focus_areas == []
        assert cip.raw_signals == {}

    def test_full_construction(self):
        cip = CandidateIntelligenceProfile(
            candidate_id="CAND-005",
            strengths=["python-basics", "data-structures"],
            weaknesses=["system-design"],
            skipped_areas=["ml-ops"],
            completion_rate=0.75,
            suggested_start_difficulty=DifficultyLevel.INTERMEDIATE,
            suggested_focus_areas=["system-design", "ml-ops"],
            raw_signals={"commitDays": 25, "missionsCompleted": 18},
        )
        assert cip.completion_rate == 0.75
        assert len(cip.strengths) == 2
        assert cip.raw_signals["commitDays"] == 25

    def test_completion_rate_boundaries(self):
        cip = CandidateIntelligenceProfile(candidate_id="x", completion_rate=0.0)
        assert cip.completion_rate == 0.0

        cip = CandidateIntelligenceProfile(candidate_id="x", completion_rate=1.0)
        assert cip.completion_rate == 1.0

    def test_completion_rate_out_of_range_raises(self):
        with pytest.raises(Exception):
            CandidateIntelligenceProfile(candidate_id="x", completion_rate=1.01)

    def test_missing_candidate_id_raises(self):
        with pytest.raises(Exception):
            CandidateIntelligenceProfile()


class TestRubricEvidence:
    """Test RubricEvidence model."""

    def test_minimal_construction(self):
        re = RubricEvidence(
            competency_id="python-async",
            criterion="Understands event loop mechanics",
            demonstrated=True,
        )
        assert re.competency_id == "python-async"
        assert re.criterion == "Understands event loop mechanics"
        assert re.demonstrated is True
        assert re.strength == EvidenceStrength.MODERATE
        assert re.notes == ""

    def test_full_construction(self):
        re = RubricEvidence(
            competency_id="python-async",
            criterion="Can implement async generators",
            demonstrated=False,
            strength=EvidenceStrength.STRONG,
            notes="Candidate confused generators with coroutines",
        )
        assert re.demonstrated is False
        assert re.strength == EvidenceStrength.STRONG
        assert "confused" in re.notes


class TestQuestionPlan:
    """Test QuestionPlan model."""

    def test_minimal_construction(self):
        qp = QuestionPlan(
            plan_id="qp-001",
            competency_id="python-async",
            target_difficulty=DifficultyLevel.INTERMEDIATE,
        )
        assert qp.plan_id == "qp-001"
        assert qp.question_type == QuestionType.CONCEPTUAL
        assert qp.max_time_seconds == 300
        assert qp.follow_up_to is None
        assert qp.objective == ""
        assert qp.expected_criteria == []
        assert qp.selection_reasoning == ""
        assert qp.generated_question_text is None

    def test_full_construction(self):
        qp = QuestionPlan(
            plan_id="qp-002",
            competency_id="system-design",
            target_difficulty=DifficultyLevel.EXPERT,
            question_type=QuestionType.SYSTEM_DESIGN,
            topic_context="Focus on horizontal scaling patterns",
            follow_up_to="qp-001",
            max_time_seconds=600,
            generated_question_text="Design a distributed cache system...",
        )
        assert qp.question_type == QuestionType.SYSTEM_DESIGN
        assert qp.follow_up_to == "qp-001"
        assert qp.max_time_seconds == 600

    def test_max_time_boundaries(self):
        qp = QuestionPlan(plan_id="x", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL, max_time_seconds=30)
        assert qp.max_time_seconds == 30

        qp = QuestionPlan(plan_id="x", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL, max_time_seconds=1800)
        assert qp.max_time_seconds == 1800

    def test_max_time_out_of_range_raises(self):
        with pytest.raises(Exception):
            QuestionPlan(plan_id="x", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL, max_time_seconds=29)

        with pytest.raises(Exception):
            QuestionPlan(plan_id="x", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL, max_time_seconds=1801)


class TestAnswerEvaluation:
    """Test AnswerEvaluation model."""

    def test_minimal_construction(self):
        ae = AnswerEvaluation(
            evaluation_id="eval-001",
            plan_id="qp-001",
            competency_id="python-async",
            score=7.5,
        )
        assert ae.evaluation_id == "eval-001"
        assert ae.competency_id == "python-async"
        assert ae.score == 7.5
        assert ae.max_score == 10.0
        assert ae.evidence == []
        assert ae.strengths == []
        assert ae.weaknesses == []
        assert ae.follow_up_needed is False
        assert isinstance(ae.evaluated_at, datetime)

    def test_full_construction_with_evidence(self):
        evidence = [
            RubricEvidence(
                competency_id="python-async",
                criterion="Understands event loop",
                demonstrated=True,
                strength=EvidenceStrength.STRONG,
            ),
            RubricEvidence(
                competency_id="python-async",
                criterion="Can write async generators",
                demonstrated=False,
                strength=EvidenceStrength.WEAK,
            ),
        ]
        ae = AnswerEvaluation(
            evaluation_id="eval-002",
            plan_id="qp-001",
            competency_id="python-async",
            score=6.0,
            max_score=10.0,
            evidence=evidence,
            feedback="Good understanding of basics but needs work on advanced patterns",
            follow_up_needed=True,
        )
        assert len(ae.evidence) == 2
        assert ae.evidence[0].demonstrated is True
        assert ae.follow_up_needed is True

    def test_score_boundaries(self):
        ae = AnswerEvaluation(evaluation_id="x", plan_id="x", competency_id="x", score=0.0)
        assert ae.score == 0.0

        ae = AnswerEvaluation(evaluation_id="x", plan_id="x", competency_id="x", score=10.0)
        assert ae.score == 10.0

    def test_score_out_of_range_raises(self):
        with pytest.raises(Exception):
            AnswerEvaluation(evaluation_id="x", plan_id="x", competency_id="x", score=-0.1)

        with pytest.raises(Exception):
            AnswerEvaluation(evaluation_id="x", plan_id="x", competency_id="x", score=10.1)

    def test_score_exceeds_custom_max_raises(self):
        """score must not exceed max_score."""
        with pytest.raises(Exception):
            AnswerEvaluation(evaluation_id="x", plan_id="x", competency_id="x", score=6.0, max_score=5.0)


class TestAdaptiveDecision:
    """Test AdaptiveDecision model."""

    def test_minimal_construction(self):
        ad = AdaptiveDecision(
            decision_id="dec-001",
            evaluation_id="eval-001",
            action=AdaptiveAction.INCREASE_DIFFICULTY,
        )
        assert ad.decision_id == "dec-001"
        assert ad.action == AdaptiveAction.INCREASE_DIFFICULTY
        assert ad.next_competency_id is None
        assert ad.next_difficulty is None
        assert ad.reasoning == ""
        assert isinstance(ad.decided_at, datetime)

    def test_full_construction(self):
        ad = AdaptiveDecision(
            decision_id="dec-002",
            evaluation_id="eval-001",
            action=AdaptiveAction.SWITCH_TOPIC,
            next_competency_id="system-design",
            next_difficulty=DifficultyLevel.INTERMEDIATE,
            reasoning="Candidate demonstrated strong async skills; probing system design next",
        )
        assert ad.next_competency_id == "system-design"
        assert ad.next_difficulty == DifficultyLevel.INTERMEDIATE
        assert "system design" in ad.reasoning

    def test_all_action_types(self):
        """Each AdaptiveAction can be used in construction."""
        for action in AdaptiveAction:
            ad = AdaptiveDecision(
                decision_id=f"dec-{action.value}",
                evaluation_id="eval-x",
                action=action,
            )
            assert ad.action == action


class TestSessionMemorySnapshot:
    """Test SessionMemorySnapshot model."""

    def test_minimal_construction(self):
        snap = SessionMemorySnapshot(
            session_id="sess-001",
            snapshot_index=0,
            candidate_id="CAND-001",
        )
        assert snap.session_id == "sess-001"
        assert snap.snapshot_index == 0
        assert snap.candidate_id == "CAND-001"
        assert snap.competency_states == []
        assert snap.questions_plan_history == []
        assert snap.evaluation_history == []
        assert snap.decision_history == []
        assert snap.current_difficulty == DifficultyLevel.FOUNDATIONAL
        assert snap.current_competency_id is None
        assert snap.total_questions_asked == 0
        assert snap.topics_covered == []

    def test_full_construction_with_nested_objects(self):
        """Build a snapshot with all nested collections populated."""
        comp_state = CompetencyState(
            competency_id="python-async",
            proficiency=ProficiencyLevel.INTERMEDIATE,
            confidence=0.7,
            questions_asked=3,
            questions_answered_correctly=2,
            last_difficulty=DifficultyLevel.INTERMEDIATE,
            evidence_notes=["Solid fundamentals"],
        )
        plan = QuestionPlan(
            plan_id="qp-001",
            competency_id="python-async",
            target_difficulty=DifficultyLevel.INTERMEDIATE,
        )
        evidence = RubricEvidence(
            competency_id="python-async",
            criterion="Event loop understanding",
            demonstrated=True,
        )
        evaluation = AnswerEvaluation(
            evaluation_id="eval-001",
            plan_id="qp-001",
            competency_id="python-async",
            score=7.0,
            evidence=[evidence],
        )
        decision = AdaptiveDecision(
            decision_id="dec-001",
            evaluation_id="eval-001",
            action=AdaptiveAction.INCREASE_DIFFICULTY,
            next_difficulty=DifficultyLevel.ADVANCED,
        )

        snap = SessionMemorySnapshot(
            session_id="sess-001",
            snapshot_index=3,
            candidate_id="CAND-001",
            competency_states=[comp_state],
            questions_plan_history=[plan],
            evaluation_history=[evaluation],
            decision_history=[decision],
            current_difficulty=DifficultyLevel.INTERMEDIATE,
            total_questions_asked=3,
            topics_covered=["python-async"],
        )

        assert len(snap.competency_states) == 1
        assert snap.competency_states[0].proficiency == ProficiencyLevel.INTERMEDIATE
        assert len(snap.evaluation_history) == 1
        assert len(snap.evaluation_history[0].evidence) == 1
        assert snap.decision_history[0].action == AdaptiveAction.INCREASE_DIFFICULTY
        assert snap.total_questions_asked == 3

    def test_negative_snapshot_index_raises(self):
        with pytest.raises(Exception):
            SessionMemorySnapshot(session_id="x", snapshot_index=-1, candidate_id="x")


class TestCompetencyScore:
    """Test CompetencyScore model."""

    def test_minimal_construction(self):
        cs = CompetencyScore(competency_id="python-async")
        assert cs.competency_id == "python-async"
        assert cs.competency_name == ""
        assert cs.category == CompetencyCategory.TECHNICAL
        assert cs.proficiency == ProficiencyLevel.NONE
        assert cs.score == 0.0
        assert cs.max_score == 10.0
        assert cs.confidence == 0.0
        assert cs.evidence_count == 0

    def test_full_construction(self):
        cs = CompetencyScore(
            competency_id="python-async",
            competency_name="Asynchronous Python",
            category=CompetencyCategory.TECHNICAL,
            proficiency=ProficiencyLevel.ADVANCED,
            score=8.5,
            max_score=10.0,
            confidence=0.9,
            evidence_count=5,
            notes="Strong async/await understanding",
        )
        assert cs.score == 8.5
        assert cs.evidence_count == 5


class TestFinalInterviewReport:
    """Test FinalInterviewReport model."""

    def test_minimal_construction(self):
        report = FinalInterviewReport(
            report_id="rpt-001",
            session_id="sess-001",
            candidate_id="CAND-001",
        )
        assert report.report_id == "rpt-001"
        assert report.status == InterviewStatus.COMPLETED
        assert report.overall_score == 0.0
        assert report.recommendation == OverallRecommendation.NEEDS_FURTHER_EVALUATION
        assert report.competency_scores == []
        assert report.strengths == []
        assert report.areas_for_improvement == []
        assert report.total_questions == 0
        assert report.total_duration_seconds is None
        assert report.executive_summary == ""

    def test_full_construction(self):
        scores = [
            CompetencyScore(
                competency_id="python-async",
                competency_name="Asynchronous Python",
                proficiency=ProficiencyLevel.ADVANCED,
                score=8.5,
                confidence=0.9,
                evidence_count=5,
            ),
            CompetencyScore(
                competency_id="system-design",
                competency_name="System Design",
                category=CompetencyCategory.SYSTEM_DESIGN,
                proficiency=ProficiencyLevel.INTERMEDIATE,
                score=6.0,
                confidence=0.7,
                evidence_count=3,
            ),
        ]
        report = FinalInterviewReport(
            report_id="rpt-002",
            session_id="sess-002",
            candidate_id="CAND-005",
            status=InterviewStatus.COMPLETED,
            overall_score=7.25,
            recommendation=OverallRecommendation.HIRE,
            competency_scores=scores,
            strengths=["Strong async Python skills", "Good problem decomposition"],
            areas_for_improvement=["System design needs work"],
            total_questions=10,
            total_duration_seconds=1800.5,
            topics_covered=["python-async", "system-design"],
            executive_summary="Solid candidate with strong fundamentals.",
            detailed_feedback="Detailed feedback goes here...",
        )
        assert report.overall_score == 7.25
        assert report.recommendation == OverallRecommendation.HIRE
        assert len(report.competency_scores) == 2
        assert report.competency_scores[0].score == 8.5
        assert len(report.strengths) == 2
        assert report.total_questions == 10

    def test_overall_score_boundary(self):
        with pytest.raises(Exception):
            FinalInterviewReport(
                report_id="x", session_id="x", candidate_id="x", overall_score=10.1
            )


# =====================================================================
# SECTION 3: SERIALIZATION TESTS (JSON ROUND-TRIP)
# =====================================================================


class TestSerialization:
    """Verify models can serialize to JSON and deserialize back."""

    def test_competency_round_trip(self):
        original = Competency(
            competency_id="python-async",
            name="Asynchronous Python",
            category=CompetencyCategory.TECHNICAL,
            weight=3.5,
            prerequisite_ids=["python-basics"],
        )
        json_str = original.model_dump_json()
        restored = Competency.model_validate_json(json_str)
        assert restored.competency_id == original.competency_id
        assert restored.category == original.category
        assert restored.weight == original.weight
        assert restored.prerequisite_ids == original.prerequisite_ids

    def test_competency_state_round_trip(self):
        original = CompetencyState(
            competency_id="python-async",
            proficiency=ProficiencyLevel.INTERMEDIATE,
            confidence=0.8,
            questions_asked=4,
            last_difficulty=DifficultyLevel.INTERMEDIATE,
            evidence_notes=["Note 1", "Note 2"],
        )
        json_str = original.model_dump_json()
        restored = CompetencyState.model_validate_json(json_str)
        assert restored.proficiency == ProficiencyLevel.INTERMEDIATE
        assert restored.confidence == 0.8
        assert restored.evidence_notes == ["Note 1", "Note 2"]

    def test_candidate_intelligence_profile_round_trip(self):
        original = CandidateIntelligenceProfile(
            candidate_id="CAND-001",
            strengths=["python-basics"],
            weaknesses=["system-design"],
            completion_rate=0.85,
            suggested_start_difficulty=DifficultyLevel.INTERMEDIATE,
            raw_signals={"commitDays": 25},
        )
        json_str = original.model_dump_json()
        restored = CandidateIntelligenceProfile.model_validate_json(json_str)
        assert restored.candidate_id == "CAND-001"
        assert restored.raw_signals == {"commitDays": 25}

    def test_rubric_evidence_round_trip(self):
        original = RubricEvidence(
            competency_id="python-async",
            criterion="Event loop understanding",
            demonstrated=True,
            strength=EvidenceStrength.STRONG,
            notes="Excellent explanation",
        )
        json_str = original.model_dump_json()
        restored = RubricEvidence.model_validate_json(json_str)
        assert restored.demonstrated is True
        assert restored.strength == EvidenceStrength.STRONG

    def test_question_plan_round_trip(self):
        original = QuestionPlan(
            plan_id="qp-001",
            competency_id="python-async",
            target_difficulty=DifficultyLevel.ADVANCED,
            question_type=QuestionType.CODING,
            follow_up_to="qp-000",
            max_time_seconds=600,
            generated_question_text="Write an async generator...",
        )
        json_str = original.model_dump_json()
        restored = QuestionPlan.model_validate_json(json_str)
        assert restored.question_type == QuestionType.CODING
        assert restored.generated_question_text == "Write an async generator..."

    def test_answer_evaluation_round_trip(self):
        original = AnswerEvaluation(
            evaluation_id="eval-001",
            plan_id="qp-001",
            competency_id="python-async",
            score=7.5,
            evidence=[
                RubricEvidence(
                    competency_id="python-async",
                    criterion="Correct usage of await",
                    demonstrated=True,
                ),
            ],
            feedback="Good answer",
            follow_up_needed=True,
        )
        json_str = original.model_dump_json()
        restored = AnswerEvaluation.model_validate_json(json_str)
        assert restored.score == 7.5
        assert len(restored.evidence) == 1
        assert restored.follow_up_needed is True

    def test_adaptive_decision_round_trip(self):
        original = AdaptiveDecision(
            decision_id="dec-001",
            evaluation_id="eval-001",
            action=AdaptiveAction.DEEP_DIVE,
            next_difficulty=DifficultyLevel.EXPERT,
            reasoning="Candidate showing strong ability",
        )
        json_str = original.model_dump_json()
        restored = AdaptiveDecision.model_validate_json(json_str)
        assert restored.action == AdaptiveAction.DEEP_DIVE
        assert restored.next_difficulty == DifficultyLevel.EXPERT

    def test_session_memory_snapshot_round_trip(self):
        """Full nested snapshot survives JSON serialization."""
        original = SessionMemorySnapshot(
            session_id="sess-001",
            snapshot_index=2,
            candidate_id="CAND-001",
            competency_states=[
                CompetencyState(competency_id="python-async", proficiency=ProficiencyLevel.ADVANCED),
            ],
            questions_plan_history=[
                QuestionPlan(plan_id="qp-001", competency_id="python-async", target_difficulty=DifficultyLevel.ADVANCED),
            ],
            evaluation_history=[
                AnswerEvaluation(
                    evaluation_id="eval-001",
                    plan_id="qp-001",
                    competency_id="python-async",
                    score=8.0,
                    evidence=[
                        RubricEvidence(competency_id="python-async", criterion="Correct", demonstrated=True),
                    ],
                ),
            ],
            decision_history=[
                AdaptiveDecision(decision_id="dec-001", evaluation_id="eval-001", action=AdaptiveAction.INCREASE_DIFFICULTY),
            ],
            current_difficulty=DifficultyLevel.ADVANCED,
            total_questions_asked=2,
            topics_covered=["python-async"],
        )
        json_str = original.model_dump_json()
        restored = SessionMemorySnapshot.model_validate_json(json_str)
        assert restored.snapshot_index == 2
        assert restored.competency_states[0].proficiency == ProficiencyLevel.ADVANCED
        assert restored.evaluation_history[0].evidence[0].demonstrated is True
        assert restored.decision_history[0].action == AdaptiveAction.INCREASE_DIFFICULTY

    def test_final_interview_report_round_trip(self):
        original = FinalInterviewReport(
            report_id="rpt-001",
            session_id="sess-001",
            candidate_id="CAND-001",
            overall_score=7.5,
            recommendation=OverallRecommendation.HIRE,
            competency_scores=[
                CompetencyScore(competency_id="python-async", score=8.0, proficiency=ProficiencyLevel.ADVANCED),
            ],
            strengths=["Strong async skills"],
            areas_for_improvement=["System design"],
            total_questions=8,
            total_duration_seconds=1500.0,
            executive_summary="Good candidate",
        )
        json_str = original.model_dump_json()
        restored = FinalInterviewReport.model_validate_json(json_str)
        assert restored.recommendation == OverallRecommendation.HIRE
        assert restored.competency_scores[0].score == 8.0
        assert restored.total_duration_seconds == 1500.0

    def test_model_dump_produces_dict(self):
        """model_dump(mode='json') produces a JSON-serializable dict."""
        c = Competency(
            competency_id="test",
            name="Test",
            category=CompetencyCategory.TECHNICAL,
        )
        data = c.model_dump(mode="json")
        assert isinstance(data, dict)
        # Should be directly JSON-serializable
        json_str = json.dumps(data)
        assert '"competency_id": "test"' in json_str or '"competency_id":"test"' in json_str


# =====================================================================
# SECTION 4: NESTED OBJECT TESTS
# =====================================================================


class TestNestedObjects:
    """Test deep nesting and composition of models."""

    def test_answer_evaluation_with_multiple_evidence(self):
        """AnswerEvaluation can hold multiple RubricEvidence items."""
        evidence_items = [
            RubricEvidence(
                competency_id="python-async",
                criterion=f"Criterion {i}",
                demonstrated=i % 2 == 0,
                strength=EvidenceStrength.MODERATE,
            )
            for i in range(5)
        ]
        ae = AnswerEvaluation(
            evaluation_id="eval-multi",
            plan_id="qp-001",
            competency_id="python-async",
            score=6.5,
            evidence=evidence_items,
        )
        assert len(ae.evidence) == 5
        assert ae.evidence[0].demonstrated is True
        assert ae.evidence[1].demonstrated is False

    def test_final_report_with_all_recommendations(self):
        """FinalInterviewReport can use every OverallRecommendation value."""
        for rec in OverallRecommendation:
            report = FinalInterviewReport(
                report_id=f"rpt-{rec.value}",
                session_id="sess-001",
                candidate_id="CAND-001",
                recommendation=rec,
            )
            assert report.recommendation == rec

    def test_session_memory_empty_history_is_valid(self):
        """Session memory with empty histories is valid (start-of-session state)."""
        snap = SessionMemorySnapshot(
            session_id="sess-new",
            snapshot_index=0,
            candidate_id="CAND-001",
        )
        assert snap.competency_states == []
        assert snap.questions_plan_history == []
        assert snap.evaluation_history == []
        assert snap.decision_history == []

    def test_competency_score_in_report_preserves_category(self):
        """CompetencyScore category propagates through FinalInterviewReport."""
        report = FinalInterviewReport(
            report_id="rpt-cat",
            session_id="sess-001",
            candidate_id="CAND-001",
            competency_scores=[
                CompetencyScore(
                    competency_id="comm-1",
                    category=CompetencyCategory.COMMUNICATION,
                    proficiency=ProficiencyLevel.INTERMEDIATE,
                    score=5.5,
                ),
                CompetencyScore(
                    competency_id="behav-1",
                    category=CompetencyCategory.BEHAVIORAL,
                    proficiency=ProficiencyLevel.BEGINNER,
                    score=3.0,
                ),
            ],
        )
        assert report.competency_scores[0].category == CompetencyCategory.COMMUNICATION
        assert report.competency_scores[1].category == CompetencyCategory.BEHAVIORAL


# =====================================================================
# SECTION 5: BACKWARD COMPATIBILITY TESTS
# =====================================================================


class TestBackwardCompatibility:
    """Ensure existing models are unchanged and still work."""

    def test_existing_enums_unchanged(self):
        """All existing enum values remain valid."""
        assert InterviewStatus.PENDING == "pending"
        assert InterviewStatus.IN_PROGRESS == "in_progress"
        assert InterviewStatus.COMPLETED == "completed"
        assert InterviewStatus.CANCELLED == "cancelled"

        assert DifficultyLevel.FOUNDATIONAL == "foundational"
        assert DifficultyLevel.INTERMEDIATE == "intermediate"
        assert DifficultyLevel.ADVANCED == "advanced"
        assert DifficultyLevel.EXPERT == "expert"

        assert MissionOutcome.PASSED == "passed"
        assert MissionOutcome.FAILED == "failed"
        assert MissionOutcome.SKIPPED == "skipped"

    def test_base_schema_config(self):
        """BaseSchema config is unchanged."""
        config = BaseSchema.model_config
        assert config.get("from_attributes") is True
        assert config.get("populate_by_name") is True
        assert config.get("str_strip_whitespace") is True

    def test_interview_session_create_still_works(self):
        req = InterviewSessionCreate(candidate_id="CAND-001")
        assert req.candidate_id == "CAND-001"

    def test_interview_message_still_works(self):
        msg = InterviewMessage(role="interviewer", content="Hello candidate")
        assert msg.role == "interviewer"
        assert msg.content == "Hello candidate"
        assert isinstance(msg.timestamp, datetime)

    def test_candidate_answer_still_works(self):
        ca = CandidateAnswer(answer="My answer to the question")
        assert ca.answer == "My answer to the question"

    def test_candidate_answer_min_length_validation(self):
        with pytest.raises(Exception):
            CandidateAnswer(answer="")

    def test_interview_session_still_works(self):
        session = InterviewSession(
            session_id="test-session",
            candidate_id="CAND-001",
            status=InterviewStatus.IN_PROGRESS,
        )
        assert session.session_id == "test-session"
        assert session.difficulty == DifficultyLevel.FOUNDATIONAL
        assert session.questions_asked == 0
        assert session.messages == []

    def test_interview_summary_still_works(self):
        summary = InterviewSummary(
            session_id="test-session",
            candidate_id="CAND-001",
            status=InterviewStatus.COMPLETED,
            total_questions=5,
        )
        assert summary.total_questions == 5
        assert summary.topics_covered == []

    def test_paginated_response_still_works(self):
        resp = PaginatedResponse[str](items=["a", "b"], total=2)
        assert resp.items == ["a", "b"]
        assert resp.total == 2

    def test_error_response_still_works(self):
        err = ErrorResponse(error="Not Found", detail="Candidate not found")
        assert err.error == "Not Found"

    def test_candidate_profile_still_works(self):
        cp = CandidateProfile(
            id="CAND-001",
            name="Test User",
            job_role="Developer",
            years_experience=3,
            education="BS CS",
            status="active",
        )
        assert cp.id == "CAND-001"

    def test_mission_model_still_works(self):
        m = Mission(day=1, title="Test Mission", passed=True)
        assert m.outcome == MissionOutcome.PASSED

    def test_engagement_signals_still_works(self):
        es = EngagementSignals(commitDays=5, missionsCompleted=3, missionsFirstTry=2)
        assert es.commit_days == 5
        assert es.missions_completed == 3

    def test_candidate_detail_still_works(self):
        cd = CandidateDetail(
            member=CandidateProfile(
                id="CAND-001",
                name="Test",
                jobRole="Dev",
                yearsExperience=2,
                education="BS",
                status="active",
            ),
            missions=[Mission(day=1, title="M1", passed=True)],
            signals=EngagementSignals(commitDays=5, missionsCompleted=3, missionsFirstTry=2),
        )
        assert cd.member.id == "CAND-001"
        assert len(cd.missions) == 1


# =====================================================================
# SECTION 6: CROSS-MODEL INTEGRATION TESTS
# =====================================================================


class TestCrossModelIntegration:
    """Test that new models integrate with existing interview models."""

    def test_difficulty_level_shared_between_models(self):
        """DifficultyLevel from common.py is used by both old and new models."""
        session = InterviewSession(
            session_id="sess-001",
            candidate_id="CAND-001",
            difficulty=DifficultyLevel.INTERMEDIATE,
        )
        plan = QuestionPlan(
            plan_id="qp-001",
            competency_id="python-async",
            target_difficulty=DifficultyLevel.INTERMEDIATE,
        )
        assert session.difficulty == plan.target_difficulty

    def test_interview_status_shared_between_models(self):
        """InterviewStatus from common.py is used by both old and new models."""
        summary = InterviewSummary(
            session_id="sess-001",
            candidate_id="CAND-001",
            status=InterviewStatus.COMPLETED,
            total_questions=5,
        )
        report = FinalInterviewReport(
            report_id="rpt-001",
            session_id="sess-001",
            candidate_id="CAND-001",
            status=InterviewStatus.COMPLETED,
        )
        assert summary.status == report.status

    def test_new_models_extend_base_schema(self):
        """All new models inherit BaseSchema configuration."""
        # Verify from_attributes is True (inherited from BaseSchema)
        assert Competency.model_config.get("from_attributes") is True
        assert CompetencyState.model_config.get("from_attributes") is True
        assert CandidateIntelligenceProfile.model_config.get("from_attributes") is True
        assert RubricEvidence.model_config.get("from_attributes") is True
        assert QuestionPlan.model_config.get("from_attributes") is True
        assert AnswerEvaluation.model_config.get("from_attributes") is True
        assert AdaptiveDecision.model_config.get("from_attributes") is True
        assert SessionMemorySnapshot.model_config.get("from_attributes") is True
        assert FinalInterviewReport.model_config.get("from_attributes") is True
        assert CompetencyScore.model_config.get("from_attributes") is True

    def test_imports_from_models_package(self):
        """All new models can be imported from the models package."""
        from app.models import (
            Competency,
            CompetencyState,
            CandidateIntelligenceProfile,
            RubricEvidence,
            QuestionPlan,
            AnswerEvaluation,
            AdaptiveDecision,
            SessionMemorySnapshot,
            FinalInterviewReport,
            CompetencyScore,
            CompetencyCategory,
            ProficiencyLevel,
            EvidenceStrength,
            AdaptiveAction,
            QuestionType,
            OverallRecommendation,
        )
        # Just verify they're all importable and are the right types
        assert Competency is not None
        assert CompetencyState is not None
        assert CandidateIntelligenceProfile is not None


# =====================================================================
# SECTION 7: AUDIT-PATCH FIELD TESTS
# =====================================================================


class TestAuditPatchFields:
    """Targeted tests for the 6 fields added from the architecture audit."""

    # ── QuestionPlan: objective ──────────────────────────────────────

    def test_question_plan_objective_default(self):
        qp = QuestionPlan(plan_id="qp-1", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL)
        assert qp.objective == ""

    def test_question_plan_objective_set(self):
        qp = QuestionPlan(
            plan_id="qp-1",
            competency_id="python-async",
            target_difficulty=DifficultyLevel.INTERMEDIATE,
            objective="Verify whether the candidate understands async/await error propagation",
        )
        assert qp.objective == "Verify whether the candidate understands async/await error propagation"

    def test_question_plan_objective_round_trip(self):
        qp = QuestionPlan(
            plan_id="qp-1", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL,
            objective="Test objective",
        )
        restored = QuestionPlan.model_validate_json(qp.model_dump_json())
        assert restored.objective == "Test objective"

    # ── QuestionPlan: expected_criteria ──────────────────────────────

    def test_question_plan_expected_criteria_default(self):
        qp = QuestionPlan(plan_id="qp-1", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL)
        assert qp.expected_criteria == []

    def test_question_plan_expected_criteria_set(self):
        criteria = ["Understands event loop", "Can explain coroutine lifecycle", "Handles exceptions in async code"]
        qp = QuestionPlan(
            plan_id="qp-1",
            competency_id="python-async",
            target_difficulty=DifficultyLevel.INTERMEDIATE,
            expected_criteria=criteria,
        )
        assert qp.expected_criteria == criteria
        assert len(qp.expected_criteria) == 3

    def test_question_plan_expected_criteria_round_trip(self):
        qp = QuestionPlan(
            plan_id="qp-1", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL,
            expected_criteria=["Criterion A", "Criterion B"],
        )
        restored = QuestionPlan.model_validate_json(qp.model_dump_json())
        assert restored.expected_criteria == ["Criterion A", "Criterion B"]

    # ── QuestionPlan: selection_reasoning ────────────────────────────

    def test_question_plan_selection_reasoning_default(self):
        qp = QuestionPlan(plan_id="qp-1", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL)
        assert qp.selection_reasoning == ""

    def test_question_plan_selection_reasoning_set(self):
        qp = QuestionPlan(
            plan_id="qp-1",
            competency_id="python-async",
            target_difficulty=DifficultyLevel.FOUNDATIONAL,
            selection_reasoning="Candidate skipped this topic; probing at foundational level",
        )
        assert "skipped" in qp.selection_reasoning

    def test_question_plan_selection_reasoning_round_trip(self):
        qp = QuestionPlan(
            plan_id="qp-1", competency_id="x", target_difficulty=DifficultyLevel.FOUNDATIONAL,
            selection_reasoning="Reasoning text",
        )
        restored = QuestionPlan.model_validate_json(qp.model_dump_json())
        assert restored.selection_reasoning == "Reasoning text"

    # ── AnswerEvaluation: competency_id ─────────────────────────────

    def test_answer_evaluation_competency_id_required(self):
        """competency_id is required — omitting it raises."""
        with pytest.raises(Exception):
            AnswerEvaluation(evaluation_id="e", plan_id="p", score=5.0)

    def test_answer_evaluation_competency_id_set(self):
        ae = AnswerEvaluation(
            evaluation_id="eval-1",
            plan_id="qp-1",
            competency_id="python-async",
            score=7.0,
        )
        assert ae.competency_id == "python-async"

    def test_answer_evaluation_competency_id_round_trip(self):
        ae = AnswerEvaluation(
            evaluation_id="eval-1", plan_id="qp-1", competency_id="sys-design", score=5.0,
        )
        restored = AnswerEvaluation.model_validate_json(ae.model_dump_json())
        assert restored.competency_id == "sys-design"

    # ── AnswerEvaluation: strengths / weaknesses ────────────────────

    def test_answer_evaluation_strengths_default(self):
        ae = AnswerEvaluation(evaluation_id="e", plan_id="p", competency_id="x", score=5.0)
        assert ae.strengths == []

    def test_answer_evaluation_weaknesses_default(self):
        ae = AnswerEvaluation(evaluation_id="e", plan_id="p", competency_id="x", score=5.0)
        assert ae.weaknesses == []

    def test_answer_evaluation_strengths_weaknesses_set(self):
        ae = AnswerEvaluation(
            evaluation_id="eval-1",
            plan_id="qp-1",
            competency_id="python-async",
            score=6.5,
            strengths=["Clear explanation of event loop", "Good error handling"],
            weaknesses=["Missed edge case with cancellation"],
        )
        assert len(ae.strengths) == 2
        assert len(ae.weaknesses) == 1
        assert "event loop" in ae.strengths[0]

    def test_answer_evaluation_strengths_weaknesses_round_trip(self):
        ae = AnswerEvaluation(
            evaluation_id="eval-1", plan_id="qp-1", competency_id="x", score=5.0,
            strengths=["S1", "S2"], weaknesses=["W1"],
        )
        restored = AnswerEvaluation.model_validate_json(ae.model_dump_json())
        assert restored.strengths == ["S1", "S2"]
        assert restored.weaknesses == ["W1"]

    # ── SessionMemorySnapshot: current_competency_id ────────────────

    def test_session_memory_current_competency_id_default(self):
        snap = SessionMemorySnapshot(session_id="s", snapshot_index=0, candidate_id="c")
        assert snap.current_competency_id is None

    def test_session_memory_current_competency_id_set(self):
        snap = SessionMemorySnapshot(
            session_id="sess-001",
            snapshot_index=1,
            candidate_id="CAND-001",
            current_competency_id="python-async",
        )
        assert snap.current_competency_id == "python-async"

    def test_session_memory_current_competency_id_round_trip(self):
        snap = SessionMemorySnapshot(
            session_id="s", snapshot_index=0, candidate_id="c",
            current_competency_id="sys-design",
        )
        restored = SessionMemorySnapshot.model_validate_json(snap.model_dump_json())
        assert restored.current_competency_id == "sys-design"

    # ── Full integration: all 6 fields in a pipeline-like flow ──────

    def test_full_pipeline_flow_with_new_fields(self):
        """Simulate one complete plan→evaluate→decide cycle using all new fields."""
        # 1. Planner creates a plan with objective, criteria, reasoning
        plan = QuestionPlan(
            plan_id="qp-flow-1",
            competency_id="python-async",
            target_difficulty=DifficultyLevel.INTERMEDIATE,
            objective="Verify async/await error propagation understanding",
            expected_criteria=["Understands try/except in async", "Knows about CancelledError"],
            selection_reasoning="Candidate skipped async topics; probing fundamentals",
        )

        # 2. Evaluator evaluates with competency_id, strengths, weaknesses
        evaluation = AnswerEvaluation(
            evaluation_id="eval-flow-1",
            plan_id=plan.plan_id,
            competency_id=plan.competency_id,
            score=6.0,
            strengths=["Correct try/except usage"],
            weaknesses=["Did not mention CancelledError"],
            evidence=[
                RubricEvidence(
                    competency_id="python-async",
                    criterion="Understands try/except in async",
                    demonstrated=True,
                ),
                RubricEvidence(
                    competency_id="python-async",
                    criterion="Knows about CancelledError",
                    demonstrated=False,
                ),
            ],
            follow_up_needed=True,
        )

        # 3. Decision references the evaluation
        decision = AdaptiveDecision(
            decision_id="dec-flow-1",
            evaluation_id=evaluation.evaluation_id,
            action=AdaptiveAction.DEEP_DIVE,
            next_difficulty=DifficultyLevel.INTERMEDIATE,
            reasoning="Follow up on CancelledError gap",
        )

        # 4. Snapshot tracks current_competency_id
        snap = SessionMemorySnapshot(
            session_id="sess-flow",
            snapshot_index=1,
            candidate_id="CAND-001",
            current_competency_id=plan.competency_id,
            competency_states=[
                CompetencyState(competency_id="python-async", proficiency=ProficiencyLevel.INTERMEDIATE),
            ],
            questions_plan_history=[plan],
            evaluation_history=[evaluation],
            decision_history=[decision],
            current_difficulty=DifficultyLevel.INTERMEDIATE,
            total_questions_asked=1,
            topics_covered=["python-async"],
        )

        # Verify the chain
        assert snap.current_competency_id == "python-async"
        assert snap.questions_plan_history[0].objective != ""
        assert len(snap.questions_plan_history[0].expected_criteria) == 2
        assert snap.questions_plan_history[0].selection_reasoning != ""
        assert snap.evaluation_history[0].competency_id == "python-async"
        assert len(snap.evaluation_history[0].strengths) == 1
        assert len(snap.evaluation_history[0].weaknesses) == 1

        # Verify full round-trip
        restored = SessionMemorySnapshot.model_validate_json(snap.model_dump_json())
        assert restored.current_competency_id == "python-async"
        assert restored.evaluation_history[0].competency_id == "python-async"
        assert restored.evaluation_history[0].strengths == ["Correct try/except usage"]
        assert restored.questions_plan_history[0].expected_criteria == [
            "Understands try/except in async", "Knows about CancelledError",
        ]
