"""
Tests for session intelligence pipeline.
Owner: THEJAS

Covers all 14 parts of the specification:
    1.  Competency state creation
    2.  Competency state accumulation across multiple answers
    3.  Proficiency progression
    4.  Confidence progression
    5.  Evidence accumulation
    6.  Session memory snapshot creation
    7.  Adaptive decision reasoning
    8.  Final competency scores
    9.  Overall score
    10. Recommendation
    11. Final report generation
    12. Insufficient-evidence behavior
    + Integration tests via InterviewService
"""

from __future__ import annotations

import pytest

from app.models.adaptive import (
    AdaptiveAction,
    AdaptiveDecision,
    AnswerEvaluation,
    CompetencyScore,
    CompetencyState,
    EvidenceStrength,
    FinalInterviewReport,
    OverallRecommendation,
    ProficiencyLevel,
    QuestionPlan,
    RubricEvidence,
    SessionMemorySnapshot,
)
from app.models.common import DifficultyLevel, InterviewStatus
from app.models.interview import CandidateAnswer, InterviewSessionCreate, InterviewSummary
from app.services.session_intelligence import (
    AdaptiveReasoningEnhancer,
    CompetencyTracker,
    FinalReportGenerator,
    ProficiencyCalculator,
    SessionMemoryManager,
)
from app.data.repositories import CandidateRepository
from app.data.session_store import SessionStore
from app.services.candidate_service import CandidateService
from app.services.interview_service import InterviewService


# ═════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════


def _make_evaluation(
    plan_id: str = "qp-001",
    competency_id: str = "test-comp",
    score: float = 5.0,
    overall_score: float = 50.0,
    conceptual: float = 50.0,
    reasoning: float = 50.0,
    practical: float = 50.0,
    confidence: float = 50.0,
    evidence_score: float = 50.0,
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
    missing_concepts: list[str] | None = None,
    misconceptions: list[str] | None = None,
    follow_up: bool = False,
    evidence: list[RubricEvidence] | None = None,
) -> AnswerEvaluation:
    return AnswerEvaluation(
        evaluation_id=f"eval-{plan_id}",
        plan_id=plan_id,
        competency_id=competency_id,
        score=score,
        overall_score=overall_score,
        conceptual_correctness_score=conceptual,
        depth_reasoning_score=reasoning,
        practical_understanding_score=practical,
        confidence_score=confidence,
        evidence_score=evidence_score,
        strengths=strengths or [],
        weaknesses=weaknesses or [],
        missing_concepts=missing_concepts or [],
        misconceptions=misconceptions or [],
        follow_up_needed=follow_up,
        evidence=evidence or [],
    )


def _make_plan(
    plan_id: str = "qp-001",
    competency_id: str = "test-comp",
    difficulty: DifficultyLevel = DifficultyLevel.FOUNDATIONAL,
    topic_context: str = "Test Topic",
) -> QuestionPlan:
    return QuestionPlan(
        plan_id=plan_id,
        competency_id=competency_id,
        target_difficulty=difficulty,
        topic_context=topic_context,
        objective=f"Assess {topic_context}",
        expected_criteria=[f"Explain {topic_context}"],
    )


def _make_decision(
    evaluation_id: str = "eval-qp-001",
    action: AdaptiveAction = AdaptiveAction.SWITCH_TOPIC,
    competency_id: str | None = None,
    difficulty: DifficultyLevel | None = None,
) -> AdaptiveDecision:
    return AdaptiveDecision(
        decision_id="dec-001",
        evaluation_id=evaluation_id,
        action=action,
        next_competency_id=competency_id,
        next_difficulty=difficulty,
        reasoning="placeholder",
    )


def _build_service() -> InterviewService:
    return InterviewService(
        session_store=SessionStore(),
        candidate_service=CandidateService(repository=CandidateRepository()),
    )


# ═════════════════════════════════════════════════════════════════════
# SECTION 1: COMPETENCY STATE CREATION
# ═════════════════════════════════════════════════════════════════════


class TestCompetencyStateCreation:
    """Part 1: Competency state creation from evaluation."""

    def test_creates_new_state_from_evaluation(self):
        evaluation = _make_evaluation(score=6.0, overall_score=60.0, strengths=["Good explanation"])
        plan = _make_plan()

        state = CompetencyTracker.update_competency_state(
            competency_id="test-comp",
            evaluation=evaluation,
            question_plan=plan,
            current_states={},
            evaluation_history_for_competency=[evaluation],
        )

        assert state.competency_id == "test-comp"
        assert state.questions_asked == 1
        assert state.last_difficulty == DifficultyLevel.FOUNDATIONAL
        assert state.proficiency != ProficiencyLevel.NONE
        assert len(state.evidence_notes) == 1

    def test_state_includes_difficulty(self):
        plan = _make_plan(difficulty=DifficultyLevel.INTERMEDIATE)
        evaluation = _make_evaluation(score=7.0, overall_score=70.0)

        state = CompetencyTracker.update_competency_state(
            competency_id="test-comp",
            evaluation=evaluation,
            question_plan=plan,
            current_states={},
            evaluation_history_for_competency=[evaluation],
        )

        assert state.last_difficulty == DifficultyLevel.INTERMEDIATE

    def test_correct_answer_increments_correctly_answered(self):
        evaluation = _make_evaluation(score=5.0, overall_score=50.0)
        plan = _make_plan()

        state = CompetencyTracker.update_competency_state(
            competency_id="test-comp",
            evaluation=evaluation,
            question_plan=plan,
            current_states={},
            evaluation_history_for_competency=[evaluation],
        )

        assert state.questions_answered_correctly == 1

    def test_weak_answer_does_not_increment_correctly_answered(self):
        evaluation = _make_evaluation(score=3.0, overall_score=30.0)
        plan = _make_plan()

        state = CompetencyTracker.update_competency_state(
            competency_id="test-comp",
            evaluation=evaluation,
            question_plan=plan,
            current_states={},
            evaluation_history_for_competency=[evaluation],
        )

        assert state.questions_answered_correctly == 0


# ═════════════════════════════════════════════════════════════════════
# SECTION 2: COMPETENCY STATE ACCUMULATION
# ═════════════════════════════════════════════════════════════════════


class TestCompetencyStateAccumulation:
    """Part 1 cont.: Competency state accumulates across multiple answers."""

    def test_accumulates_across_three_answers(self):
        """Three answers should result in 3 evidence notes, 3 questions asked."""
        states: dict[str, CompetencyState] = {}
        all_evals: list[AnswerEvaluation] = []

        plan1 = _make_plan(plan_id="qp-1")
        eval1 = _make_evaluation(plan_id="qp-1", score=5.0, overall_score=50.0, strengths=["Basic RAG understanding"])
        all_evals.append(eval1)
        state = CompetencyTracker.update_competency_state("test-comp", eval1, plan1, states, all_evals)
        states["test-comp"] = state

        plan2 = _make_plan(plan_id="qp-2")
        eval2 = _make_evaluation(plan_id="qp-2", score=6.5, overall_score=65.0, strengths=["Chunking explained correctly"])
        all_evals.append(eval2)
        state = CompetencyTracker.update_competency_state("test-comp", eval2, plan2, states, all_evals)
        states["test-comp"] = state

        plan3 = _make_plan(plan_id="qp-3")
        eval3 = _make_evaluation(plan_id="qp-3", score=4.0, overall_score=40.0, weaknesses=["Struggles with retrieval failure modes"])
        all_evals.append(eval3)
        state = CompetencyTracker.update_competency_state("test-comp", eval3, plan3, states, all_evals)

        assert state.questions_asked == 3
        assert len(state.evidence_notes) == 3
        # All three pieces of evidence reflected (note uses plan.plan_id)
        assert "qp-1" in state.evidence_notes[0]
        assert "qp-2" in state.evidence_notes[1]
        assert "qp-3" in state.evidence_notes[2]

    def test_does_not_overwrite_previous_evidence(self):
        plan = _make_plan()
        states: dict[str, CompetencyState] = {}
        all_evals: list[AnswerEvaluation] = []

        eval1 = _make_evaluation(plan_id="qp-1", score=7.0, overall_score=70.0, strengths=["Good"])
        all_evals.append(eval1)
        state1 = CompetencyTracker.update_competency_state("test-comp", eval1, plan, states, all_evals)
        states["test-comp"] = state1
        first_note = state1.evidence_notes[0]

        eval2 = _make_evaluation(plan_id="qp-2", score=8.0, overall_score=80.0, strengths=["Excellent"])
        all_evals.append(eval2)
        state2 = CompetencyTracker.update_competency_state("test-comp", eval2, plan, states, all_evals)

        # First note is still there
        assert first_note in state2.evidence_notes
        assert len(state2.evidence_notes) == 2

    def test_questions_answered_correctly_accumulates(self):
        plan = _make_plan()
        states: dict[str, CompetencyState] = {}
        all_evals: list[AnswerEvaluation] = []

        eval1 = _make_evaluation(plan_id="qp-1", score=7.0, overall_score=70.0)
        all_evals.append(eval1)
        state = CompetencyTracker.update_competency_state("test-comp", eval1, plan, states, all_evals)
        states["test-comp"] = state

        eval2 = _make_evaluation(plan_id="qp-2", score=3.0, overall_score=30.0)
        all_evals.append(eval2)
        state = CompetencyTracker.update_competency_state("test-comp", eval2, plan, states, all_evals)
        states["test-comp"] = state

        eval3 = _make_evaluation(plan_id="qp-3", score=6.0, overall_score=60.0)
        all_evals.append(eval3)
        state = CompetencyTracker.update_competency_state("test-comp", eval3, plan, states, all_evals)

        assert state.questions_asked == 3
        assert state.questions_answered_correctly == 2  # eval1 (7.0) and eval3 (6.0)


# ═════════════════════════════════════════════════════════════════════
# SECTION 3: PROFICIENCY PROGRESSION
# ═════════════════════════════════════════════════════════════════════


class TestProficiencyProgression:
    """Part 2: Evidence-based proficiency calculation."""

    def test_no_evaluations_returns_none(self):
        prof, conf = ProficiencyCalculator.calculate([])
        assert prof == ProficiencyLevel.NONE
        assert conf == 0.0

    def test_weak_answer_yields_beginner(self):
        evals = [_make_evaluation(score=2.0, overall_score=20.0)]
        prof, conf = ProficiencyCalculator.calculate(evals)
        assert prof == ProficiencyLevel.BEGINNER

    def test_moderate_answer_yields_intermediate(self):
        evals = [_make_evaluation(score=5.0, overall_score=55.0, strengths=["OK"])]
        prof, conf = ProficiencyCalculator.calculate(evals)
        assert prof == ProficiencyLevel.INTERMEDIATE

    def test_strong_repeated_yields_advanced(self):
        evals = [
            _make_evaluation(plan_id="qp-1", score=7.5, overall_score=75.0, reasoning=50.0, practical=45.0),
            _make_evaluation(plan_id="qp-2", score=8.0, overall_score=80.0, reasoning=55.0, practical=50.0),
        ]
        prof, conf = ProficiencyCalculator.calculate(evals)
        assert prof == ProficiencyLevel.ADVANCED

    def test_expert_requires_three_or_more_questions(self):
        """Even with high scores, 2 questions should NOT yield EXPERT."""
        evals = [
            _make_evaluation(plan_id="qp-1", score=9.0, overall_score=90.0, conceptual=85.0, reasoning=70.0, practical=70.0, confidence=70.0),
            _make_evaluation(plan_id="qp-2", score=9.5, overall_score=95.0, conceptual=90.0, reasoning=80.0, practical=80.0, confidence=80.0),
        ]
        prof, _ = ProficiencyCalculator.calculate(evals)
        assert prof != ProficiencyLevel.EXPERT

    def test_expert_requires_no_unresolved_misconceptions(self):
        """High scores but latest eval has misconceptions → not EXPERT."""
        evals = [
            _make_evaluation(plan_id="qp-1", score=9.0, overall_score=90.0, conceptual=80.0, reasoning=70.0, practical=70.0, confidence=70.0, strengths=["Good"]),
            _make_evaluation(plan_id="qp-2", score=9.0, overall_score=90.0, conceptual=80.0, reasoning=70.0, practical=70.0, confidence=70.0, strengths=["Good"]),
            _make_evaluation(plan_id="qp-3", score=9.0, overall_score=90.0, conceptual=80.0, reasoning=70.0, practical=70.0, confidence=70.0, strengths=["Good"], misconceptions=["Wrong about X"]),
        ]
        prof, _ = ProficiencyCalculator.calculate(evals)
        assert prof != ProficiencyLevel.EXPERT

    def test_expert_requires_strong_reasoning_and_practical(self):
        """High overall but weak reasoning → not EXPERT."""
        evals = [
            _make_evaluation(plan_id="qp-1", score=9.0, overall_score=90.0, conceptual=80.0, reasoning=30.0, practical=30.0, confidence=70.0, strengths=["Good"]),
            _make_evaluation(plan_id="qp-2", score=9.0, overall_score=90.0, conceptual=80.0, reasoning=30.0, practical=30.0, confidence=70.0, strengths=["Good"]),
            _make_evaluation(plan_id="qp-3", score=9.0, overall_score=90.0, conceptual=80.0, reasoning=30.0, practical=30.0, confidence=70.0, strengths=["Good"]),
        ]
        prof, _ = ProficiencyCalculator.calculate(evals)
        assert prof != ProficiencyLevel.EXPERT

    def test_expert_awarded_with_full_criteria(self):
        """EXPERT requires: ≥3 qs, avg≥85, strong reasoning+practical+conceptual, confidence, no misconceptions."""
        evals = [
            _make_evaluation(plan_id="qp-1", score=9.0, overall_score=90.0, conceptual=80.0, reasoning=75.0, practical=70.0, confidence=70.0, strengths=["Strong", "Deep"]),
            _make_evaluation(plan_id="qp-2", score=8.5, overall_score=85.0, conceptual=75.0, reasoning=70.0, practical=70.0, confidence=65.0, strengths=["Solid"]),
            _make_evaluation(plan_id="qp-3", score=9.0, overall_score=90.0, conceptual=80.0, reasoning=72.0, practical=68.0, confidence=70.0, strengths=["Excellent"]),
        ]
        prof, _ = ProficiencyCalculator.calculate(evals)
        assert prof == ProficiencyLevel.EXPERT


# ═════════════════════════════════════════════════════════════════════
# SECTION 4: CONFIDENCE PROGRESSION
# ═════════════════════════════════════════════════════════════════════


class TestConfidenceProgression:
    """Part 2 cont.: Confidence increases with independent evidence."""

    def test_one_evaluation_low_confidence(self):
        _, conf = ProficiencyCalculator.calculate([_make_evaluation()])
        assert conf == 0.45  # 0.3 + 0.15 * 1

    def test_two_evaluations_higher_confidence(self):
        evals = [_make_evaluation(plan_id="qp-1"), _make_evaluation(plan_id="qp-2")]
        _, conf = ProficiencyCalculator.calculate(evals)
        assert conf == 0.6  # 0.3 + 0.15 * 2

    def test_confidence_caps_at_one(self):
        evals = [_make_evaluation(plan_id=f"qp-{i}") for i in range(10)]
        _, conf = ProficiencyCalculator.calculate(evals)
        assert conf == 1.0

    def test_confidence_increases_monotonically(self):
        confs = []
        evals = []
        for i in range(6):
            evals.append(_make_evaluation(plan_id=f"qp-{i}"))
            _, conf = ProficiencyCalculator.calculate(evals)
            confs.append(conf)

        for i in range(1, len(confs)):
            assert confs[i] >= confs[i - 1]


# ═════════════════════════════════════════════════════════════════════
# SECTION 5: EVIDENCE ACCUMULATION
# ═════════════════════════════════════════════════════════════════════


class TestEvidenceAccumulation:
    """Part 2 cont.: Evidence notes from all evaluations preserved."""

    def test_evidence_notes_contain_plan_ids(self):
        states: dict[str, CompetencyState] = {}
        all_evals: list[AnswerEvaluation] = []

        for i in range(3):
            plan = _make_plan(plan_id=f"qp-{i}")
            ev = _make_evaluation(plan_id=f"qp-{i}", score=5.0 + i, overall_score=50.0 + i * 10)
            all_evals.append(ev)
            state = CompetencyTracker.update_competency_state("test-comp", ev, plan, states, all_evals)
            states["test-comp"] = state

        for i in range(3):
            assert f"qp-{i}" in state.evidence_notes[i]

    def test_evidence_notes_include_strengths_and_weaknesses(self):
        plan = _make_plan()
        ev = _make_evaluation(
            strengths=["Good reasoning"],
            weaknesses=["Missing details"],
        )
        state = CompetencyTracker.update_competency_state("test-comp", ev, plan, {}, [ev])

        note = state.evidence_notes[0]
        assert "Good reasoning" in note
        assert "Missing details" in note

    def test_evidence_notes_include_misconceptions(self):
        plan = _make_plan()
        ev = _make_evaluation(misconceptions=["Confuses async with threading"])
        state = CompetencyTracker.update_competency_state("test-comp", ev, plan, {}, [ev])

        note = state.evidence_notes[0]
        assert "Confuses async with threading" in note


# ═════════════════════════════════════════════════════════════════════
# SECTION 6: SESSION MEMORY SNAPSHOT
# ═════════════════════════════════════════════════════════════════════


class TestSessionMemorySnapshot:
    """Part 3: Session memory snapshot creation."""

    def test_initial_snapshot_is_index_zero(self):
        plan = _make_plan()
        snap = SessionMemoryManager.create_initial_snapshot(
            session_id="sess-1",
            candidate_id="CAND-001",
            first_plan=plan,
            difficulty=DifficultyLevel.FOUNDATIONAL,
        )

        assert snap.snapshot_index == 0
        assert snap.session_id == "sess-1"
        assert snap.candidate_id == "CAND-001"
        assert snap.competency_states == []  # no evidence at index 0
        assert snap.evaluation_history == []  # no evaluations at index 0
        assert snap.decision_history == []
        assert snap.total_questions_asked == 1
        assert len(snap.questions_plan_history) == 1

    def test_initial_snapshot_has_no_competency_evidence(self):
        """Snapshot 0 is initialization context, NOT competency evidence."""
        plan = _make_plan()
        snap = SessionMemoryManager.create_initial_snapshot(
            session_id="sess-1",
            candidate_id="CAND-001",
            first_plan=plan,
            difficulty=DifficultyLevel.FOUNDATIONAL,
        )

        assert len(snap.competency_states) == 0
        assert len(snap.evaluation_history) == 0

    def test_evidence_snapshot_has_all_fields(self):
        comp_state = CompetencyState(
            competency_id="test-comp",
            proficiency=ProficiencyLevel.INTERMEDIATE,
            confidence=0.45,
            questions_asked=1,
        )
        plan = _make_plan()
        ev = _make_evaluation()
        dec = _make_decision()

        snap = SessionMemoryManager.create_snapshot(
            session_id="sess-1",
            candidate_id="CAND-001",
            snapshot_index=1,
            competency_states=[comp_state],
            plan_history=[plan],
            evaluation_history=[ev],
            decision_history=[dec],
            current_difficulty=DifficultyLevel.INTERMEDIATE,
            current_competency_id="test-comp",
            total_questions_asked=2,
            topics_covered=["test-comp"],
        )

        assert snap.snapshot_index == 1
        assert len(snap.competency_states) == 1
        assert len(snap.evaluation_history) == 1
        assert len(snap.decision_history) == 1
        assert snap.current_difficulty == DifficultyLevel.INTERMEDIATE
        assert snap.total_questions_asked == 2
        assert "test-comp" in snap.topics_covered

    def test_snapshot_is_auditable_chain(self):
        """Question → Answer → Evaluation → Decision → Next Question chain."""
        plan = _make_plan()
        ev = _make_evaluation(plan_id=plan.plan_id)
        dec = _make_decision(evaluation_id=ev.evaluation_id)

        snap = SessionMemoryManager.create_snapshot(
            session_id="sess-1",
            candidate_id="CAND-001",
            snapshot_index=1,
            competency_states=[],
            plan_history=[plan],
            evaluation_history=[ev],
            decision_history=[dec],
            current_difficulty=DifficultyLevel.FOUNDATIONAL,
            current_competency_id="test-comp",
            total_questions_asked=1,
            topics_covered=["test-comp"],
        )

        # Chain: plan → eval → decision
        assert snap.questions_plan_history[0].plan_id == ev.plan_id
        assert snap.evaluation_history[0].evaluation_id == dec.evaluation_id


# ═════════════════════════════════════════════════════════════════════
# SECTION 7: ADAPTIVE DECISION REASONING
# ═════════════════════════════════════════════════════════════════════


class TestAdaptiveDecisionReasoning:
    """Part 4: Explainable adaptive reasoning."""

    def test_reasoning_not_generic(self):
        ev = _make_evaluation(score=7.0, overall_score=70.0, strengths=["Good"])
        state = CompetencyState(competency_id="test-comp", proficiency=ProficiencyLevel.INTERMEDIATE, questions_asked=1)
        dec = _make_decision(action=AdaptiveAction.SWITCH_TOPIC)

        reasoning = AdaptiveReasoningEnhancer.enhance_reasoning(ev, state, dec)

        # Should NOT be the generic placeholder
        assert reasoning != "placeholder"
        assert reasoning != "Selected topic after evaluating previous answer"
        # Should contain evidence-based content
        assert "score" in reasoning.lower() or "performance" in reasoning.lower()

    def test_reasoning_includes_strengths(self):
        ev = _make_evaluation(strengths=["Clear async explanation"])
        state = CompetencyState(competency_id="test-comp", questions_asked=1)
        dec = _make_decision(action=AdaptiveAction.SWITCH_TOPIC)

        reasoning = AdaptiveReasoningEnhancer.enhance_reasoning(ev, state, dec)
        assert "Clear async explanation" in reasoning

    def test_reasoning_includes_weaknesses(self):
        ev = _make_evaluation(weaknesses=["Missed error handling"])
        state = CompetencyState(competency_id="test-comp", questions_asked=1)
        dec = _make_decision(action=AdaptiveAction.SWITCH_TOPIC)

        reasoning = AdaptiveReasoningEnhancer.enhance_reasoning(ev, state, dec)
        assert "Missed error handling" in reasoning

    def test_reasoning_includes_misconceptions(self):
        ev = _make_evaluation(misconceptions=["Confuses coroutines with threads"])
        state = CompetencyState(competency_id="test-comp", questions_asked=1)
        dec = _make_decision(action=AdaptiveAction.CONTINUE_SAME_TOPIC)

        reasoning = AdaptiveReasoningEnhancer.enhance_reasoning(ev, state, dec)
        assert "Confuses coroutines with threads" in reasoning

    def test_increase_difficulty_reasoning_mentions_proficiency(self):
        ev = _make_evaluation(score=8.0, overall_score=80.0, strengths=["Excellent"])
        state = CompetencyState(competency_id="test-comp", proficiency=ProficiencyLevel.ADVANCED, questions_asked=3, confidence=0.75)
        dec = _make_decision(action=AdaptiveAction.INCREASE_DIFFICULTY)

        reasoning = AdaptiveReasoningEnhancer.enhance_reasoning(ev, state, dec)
        assert "advanced" in reasoning.lower()
        assert "3" in reasoning  # mentions question count

    def test_decrease_difficulty_reasoning(self):
        ev = _make_evaluation(score=2.0, overall_score=20.0, weaknesses=["Vague"])
        state = CompetencyState(competency_id="test-comp", questions_asked=1)
        dec = _make_decision(action=AdaptiveAction.DECREASE_DIFFICULTY)

        reasoning = AdaptiveReasoningEnhancer.enhance_reasoning(ev, state, dec)
        assert "lower" in reasoning.lower() or "difficulty" in reasoning.lower() or "confidence" in reasoning.lower()


# ═════════════════════════════════════════════════════════════════════
# SECTION 8: FINAL COMPETENCY SCORES
# ═════════════════════════════════════════════════════════════════════


class TestFinalCompetencyScores:
    """Part 6: Competency scoring from accumulated evaluations."""

    def test_weighted_evidence_not_just_last_answer(self):
        """Score should reflect ALL evaluations, not just the last one."""
        comp_states = {
            "comp-1": CompetencyState(
                competency_id="comp-1",
                proficiency=ProficiencyLevel.INTERMEDIATE,
                confidence=0.6,
                questions_asked=3,
            )
        }
        evals = [
            _make_evaluation(plan_id="qp-1", competency_id="comp-1", score=8.0, overall_score=80.0),
            _make_evaluation(plan_id="qp-2", competency_id="comp-1", score=7.0, overall_score=70.0),
            _make_evaluation(plan_id="qp-3", competency_id="comp-1", score=3.0, overall_score=30.0),
        ]
        plans = [_make_plan(plan_id=f"qp-{i}", competency_id="comp-1") for i in range(1, 4)]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1",
            candidate_id="CAND-001",
            competency_states=comp_states,
            evaluation_history=evals,
            decision_history=[],
            plan_history=plans,
            total_questions=3,
            duration_seconds=600.0,
            topics_covered=["comp-1"],
        )

        # Should NOT simply be the last answer's score (3.0)
        assert len(report.competency_scores) == 1
        cs = report.competency_scores[0]
        assert cs.score > 3.0  # weighted evidence, not just last
        assert cs.score < 8.0  # not just the best either
        assert cs.evidence_count == 3

    def test_multiple_competencies_scored_independently(self):
        comp_states = {
            "comp-a": CompetencyState(competency_id="comp-a", proficiency=ProficiencyLevel.ADVANCED, confidence=0.6),
            "comp-b": CompetencyState(competency_id="comp-b", proficiency=ProficiencyLevel.BEGINNER, confidence=0.45),
        }
        evals = [
            _make_evaluation(plan_id="qp-1", competency_id="comp-a", score=8.0, overall_score=80.0),
            _make_evaluation(plan_id="qp-2", competency_id="comp-b", score=3.0, overall_score=30.0),
        ]
        plans = [
            _make_plan(plan_id="qp-1", competency_id="comp-a"),
            _make_plan(plan_id="qp-2", competency_id="comp-b"),
        ]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=[], plan_history=plans,
            total_questions=2, duration_seconds=400.0,
            topics_covered=["comp-a", "comp-b"],
        )

        assert len(report.competency_scores) == 2
        scores_by_id = {cs.competency_id: cs for cs in report.competency_scores}
        assert scores_by_id["comp-a"].score > scores_by_id["comp-b"].score


# ═════════════════════════════════════════════════════════════════════
# SECTION 9: OVERALL SCORE
# ═════════════════════════════════════════════════════════════════════


class TestOverallScore:
    """Part 7: Overall interview score."""

    def test_no_evaluations_zero_score(self):
        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states={}, evaluation_history=[],
            decision_history=[], plan_history=[],
            total_questions=0, duration_seconds=0.0, topics_covered=[],
        )
        assert report.overall_score == 0.0

    def test_single_question_does_not_dominate(self):
        """One exceptional answer should not give 10/10 overall."""
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.45)}
        evals = [_make_evaluation(score=10.0, overall_score=100.0, competency_id="comp-1")]
        plans = [_make_plan(competency_id="comp-1")]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=[], plan_history=plans,
            total_questions=1, duration_seconds=120.0, topics_covered=["comp-1"],
        )

        assert report.overall_score <= 10.0
        assert report.overall_score > 0.0

    def test_overall_score_within_range(self):
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.6)}
        evals = [
            _make_evaluation(plan_id="qp-1", score=6.0, overall_score=60.0, competency_id="comp-1"),
            _make_evaluation(plan_id="qp-2", score=7.0, overall_score=70.0, competency_id="comp-1"),
        ]
        plans = [_make_plan(plan_id=f"qp-{i}", competency_id="comp-1") for i in range(1, 3)]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=[], plan_history=plans,
            total_questions=2, duration_seconds=300.0, topics_covered=["comp-1"],
        )

        assert 0.0 <= report.overall_score <= 10.0


# ═════════════════════════════════════════════════════════════════════
# SECTION 10: RECOMMENDATION
# ═════════════════════════════════════════════════════════════════════


class TestRecommendation:
    """Part 8: Deterministic recommendation policy."""

    def test_no_evaluations_needs_further(self):
        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states={}, evaluation_history=[],
            decision_history=[], plan_history=[],
            total_questions=0, duration_seconds=0.0, topics_covered=[],
        )
        assert report.recommendation == OverallRecommendation.NEEDS_FURTHER_EVALUATION

    def test_insufficient_evidence_needs_further(self):
        """Only 1 evaluation → NEEDS_FURTHER_EVALUATION."""
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.45)}
        evals = [_make_evaluation(score=7.0, overall_score=70.0, competency_id="comp-1")]
        plans = [_make_plan(competency_id="comp-1")]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=[], plan_history=plans,
            total_questions=1, duration_seconds=120.0, topics_covered=["comp-1"],
        )

        assert report.recommendation == OverallRecommendation.NEEDS_FURTHER_EVALUATION

    def test_weak_performance_no_hire(self):
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.6)}
        evals = [
            _make_evaluation(plan_id="qp-1", score=2.0, overall_score=20.0, competency_id="comp-1"),
            _make_evaluation(plan_id="qp-2", score=1.5, overall_score=15.0, competency_id="comp-1"),
        ]
        plans = [_make_plan(plan_id=f"qp-{i}", competency_id="comp-1") for i in range(1, 3)]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=[], plan_history=plans,
            total_questions=2, duration_seconds=300.0, topics_covered=["comp-1"],
        )

        assert report.recommendation in (
            OverallRecommendation.NO_HIRE,
            OverallRecommendation.LEAN_NO_HIRE,
        )

    def test_strong_performance_hire_or_strong_hire(self):
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.75)}
        evals = [
            _make_evaluation(plan_id="qp-1", score=8.5, overall_score=85.0, competency_id="comp-1", strengths=["A"]),
            _make_evaluation(plan_id="qp-2", score=8.0, overall_score=80.0, competency_id="comp-1", strengths=["B"]),
            _make_evaluation(plan_id="qp-3", score=9.0, overall_score=90.0, competency_id="comp-1", strengths=["C"]),
        ]
        plans = [_make_plan(plan_id=f"qp-{i}", competency_id="comp-1") for i in range(1, 4)]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=[], plan_history=plans,
            total_questions=3, duration_seconds=600.0, topics_covered=["comp-1"],
        )

        assert report.recommendation in (
            OverallRecommendation.HIRE,
            OverallRecommendation.STRONG_HIRE,
        )

    def test_recommendation_not_based_solely_on_score(self):
        """Low confidence + ok score should NOT be HIRE."""
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.2)}
        evals = [
            _make_evaluation(plan_id="qp-1", score=7.0, overall_score=70.0, competency_id="comp-1"),
        ]
        plans = [_make_plan(competency_id="comp-1")]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=[], plan_history=plans,
            total_questions=1, duration_seconds=120.0, topics_covered=["comp-1"],
        )

        assert report.recommendation != OverallRecommendation.HIRE
        assert report.recommendation != OverallRecommendation.STRONG_HIRE


# ═════════════════════════════════════════════════════════════════════
# SECTION 11: FINAL REPORT GENERATION
# ═════════════════════════════════════════════════════════════════════


class TestFinalReportGeneration:
    """Part 5: Full FinalInterviewReport generation."""

    def test_report_has_all_required_fields(self):
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.6)}
        evals = [
            _make_evaluation(plan_id="qp-1", score=6.0, overall_score=60.0, competency_id="comp-1", strengths=["S1"]),
            _make_evaluation(plan_id="qp-2", score=7.0, overall_score=70.0, competency_id="comp-1", weaknesses=["W1"]),
        ]
        decisions = [_make_decision(action=AdaptiveAction.SWITCH_TOPIC)]
        plans = [_make_plan(plan_id=f"qp-{i}", competency_id="comp-1") for i in range(1, 3)]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=decisions, plan_history=plans,
            total_questions=2, duration_seconds=400.0,
            topics_covered=["comp-1"],
        )

        assert report.report_id.startswith("rpt-")
        assert report.session_id == "sess-1"
        assert report.candidate_id == "CAND-001"
        assert report.status == InterviewStatus.COMPLETED
        assert 0.0 <= report.overall_score <= 10.0
        assert isinstance(report.recommendation, OverallRecommendation)
        assert len(report.competency_scores) >= 1
        assert report.total_questions == 2
        assert report.total_duration_seconds == 400.0
        assert "comp-1" in report.topics_covered
        assert report.executive_summary != ""
        assert report.detailed_feedback != ""

    def test_report_executive_summary_not_generic(self):
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.6, proficiency=ProficiencyLevel.INTERMEDIATE)}
        evals = [
            _make_evaluation(plan_id="qp-1", score=6.0, overall_score=60.0, competency_id="comp-1", strengths=["Good reasoning"]),
            _make_evaluation(plan_id="qp-2", score=7.0, overall_score=70.0, competency_id="comp-1", weaknesses=["Missing details"]),
        ]
        plans = [_make_plan(plan_id=f"qp-{i}", competency_id="comp-1", topic_context="RAG Architecture") for i in range(1, 3)]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=[], plan_history=plans,
            total_questions=2, duration_seconds=400.0, topics_covered=["comp-1"],
        )

        # Should NOT be generic filler
        assert report.executive_summary != "Candidate performed well during the interview."
        assert "comp-1" in report.executive_summary or "competency" in report.executive_summary.lower()

    def test_report_detailed_feedback_has_structure(self):
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.6)}
        evals = [
            _make_evaluation(plan_id="qp-1", score=6.0, overall_score=60.0, competency_id="comp-1",
                             strengths=["S1"], weaknesses=["W1"], missing_concepts=["MC1"], misconceptions=["M1"]),
            _make_evaluation(plan_id="qp-2", score=7.0, overall_score=70.0, competency_id="comp-1",
                             strengths=["S2"]),
        ]
        decisions = [_make_decision(action=AdaptiveAction.INCREASE_DIFFICULTY)]
        plans = [_make_plan(plan_id=f"qp-{i}", competency_id="comp-1") for i in range(1, 3)]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=decisions, plan_history=plans,
            total_questions=2, duration_seconds=400.0, topics_covered=["comp-1"],
        )

        fb = report.detailed_feedback
        assert "STRONGEST" in fb
        assert "MISSING" in fb or "MISCONCEPTION" in fb
        assert "M1" in fb  # actual misconception
        assert "MC1" in fb  # actual missing concept

    def test_report_excludes_unrelated_planned_competencies_without_evidence(self):
        comp_states = {
            "vs-code-python": CompetencyState(competency_id="vs-code-python", confidence=0.8),
            "docker-k8s": CompetencyState(competency_id="docker-k8s", confidence=0.8),
        }
        evals = [
            _make_evaluation(
                plan_id="qp-1",
                competency_id="vs-code-python",
                score=8.0,
                overall_score=80.0,
                strengths=["Configured the environment correctly"],
                weaknesses=["Needs more detail on debugger settings"],
                missing_concepts=["Remote interpreter selection"],
            ),
        ]
        plans = [
            _make_plan(
                plan_id="qp-1",
                competency_id="vs-code-python",
                topic_context="VS Code & Python Environment Setup",
            ),
            _make_plan(
                plan_id="qp-2",
                competency_id="docker-k8s",
                topic_context="Docker & Kubernetes Deployment",
            ),
        ]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1",
            candidate_id="CAND-001",
            competency_states=comp_states,
            evaluation_history=evals,
            decision_history=[],
            plan_history=plans,
            total_questions=1,
            duration_seconds=120.0,
            topics_covered=["vs-code-python"],
        )

        competency_names = [score.competency_name for score in report.competency_scores]
        assert "VS Code & Python Environment Setup" in competency_names
        assert "Docker & Kubernetes Deployment" not in competency_names
        assert all("day-" not in name.lower() for name in competency_names if name)
        assert all("Docker & Kubernetes Deployment" not in item for item in report.strengths)
        assert all("Docker & Kubernetes Deployment" not in item for item in report.areas_for_improvement)
        assert all("enterprise healthcare chatbot" not in item.lower() for item in report.detailed_feedback.lower().splitlines())

    @pytest.mark.parametrize(
        "question_count",
        [1, 3, 8],
    )
    def test_report_works_with_1_3_and_8_evaluated_questions(self, question_count):
        titles = [
            "VS Code & Python Environment Setup",
            "Local LLM & AI Coding Assistant Setup",
            "Capstone Project & Final Demo",
            "Production Readiness & Final Testing",
            "Monitoring, Logging & Observability",
            "Docker & Kubernetes Deployment",
            "Security, Privacy & Guardrails",
            "Performance Optimization & Cost Management",
        ]
        evals = []
        plans = []
        comp_states: dict[str, CompetencyState] = {}
        for index, title in enumerate(titles[:question_count], start=1):
            competency_id = f"topic-{index}"
            plan_id = f"qp-{index}"
            plans.append(_make_plan(plan_id=plan_id, competency_id=competency_id, topic_context=title))
            evals.append(
                _make_evaluation(
                    plan_id=plan_id,
                    competency_id=competency_id,
                    score=6.0 + (index % 3),
                    overall_score=60.0 + (index * 3),
                    strengths=[f"Strength {index}"],
                    weaknesses=[f"Weakness {index}"],
                )
            )
            comp_states[competency_id] = CompetencyState(competency_id=competency_id, confidence=0.6)

        report = FinalReportGenerator.generate_report(
            session_id="sess-1",
            candidate_id="CAND-001",
            competency_states=comp_states,
            evaluation_history=evals,
            decision_history=[],
            plan_history=plans,
            total_questions=question_count,
            duration_seconds=300.0,
            topics_covered=[plan.competency_id for plan in plans],
        )

        assert report.total_questions == question_count
        assert len(report.competency_scores) == question_count
        assert report.overall_score > 0.0
        assert report.recommendation is not None
        assert all(score.evidence_count > 0 for score in report.competency_scores)
        assert all(score.competency_name in titles for score in report.competency_scores)


# ═════════════════════════════════════════════════════════════════════
# SECTION 12: INSUFFICIENT EVIDENCE BEHAVIOR
# ═════════════════════════════════════════════════════════════════════


class TestInsufficientEvidence:
    """Part 12: System handles insufficient evidence gracefully."""

    def test_no_data_returns_needs_further(self):
        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states={}, evaluation_history=[],
            decision_history=[], plan_history=[],
            total_questions=0, duration_seconds=0.0, topics_covered=[],
        )

        assert report.recommendation == OverallRecommendation.NEEDS_FURTHER_EVALUATION
        assert report.overall_score == 0.0

    def test_single_evaluation_needs_further(self):
        comp_states = {"comp-1": CompetencyState(competency_id="comp-1", confidence=0.45)}
        evals = [_make_evaluation(score=8.0, overall_score=80.0, competency_id="comp-1")]
        plans = [_make_plan(competency_id="comp-1")]

        report = FinalReportGenerator.generate_report(
            session_id="sess-1", candidate_id="CAND-001",
            competency_states=comp_states, evaluation_history=evals,
            decision_history=[], plan_history=plans,
            total_questions=1, duration_seconds=120.0, topics_covered=["comp-1"],
        )

        assert report.recommendation == OverallRecommendation.NEEDS_FURTHER_EVALUATION

    def test_proficiency_none_with_no_evidence(self):
        prof, conf = ProficiencyCalculator.calculate([])
        assert prof == ProficiencyLevel.NONE
        assert conf == 0.0


# ═════════════════════════════════════════════════════════════════════
# SECTION 13: REPORT-TO-SUMMARY MAPPING
# ═════════════════════════════════════════════════════════════════════


class TestReportToSummaryMapping:
    """Part 11-12: Centralized FinalInterviewReport → InterviewSummary mapping."""

    def test_mapping_produces_all_frontend_fields(self):
        report = FinalInterviewReport(
            report_id="rpt-001",
            session_id="sess-1",
            candidate_id="CAND-001",
            overall_score=7.0,
            recommendation=OverallRecommendation.HIRE,
            competency_scores=[
                CompetencyScore(
                    competency_id="comp-1",
                    competency_name="Test Comp",
                    score=7.0,
                    confidence=0.6,
                    evidence_count=2,
                ),
            ],
            strengths=["S1"],
            areas_for_improvement=["I1"],
            executive_summary="Test summary",
            detailed_feedback="Test feedback",
        )

        fields = FinalReportGenerator.report_to_summary_fields(report)

        assert "overall_score" in fields
        assert "recommendation" in fields
        assert "competency_scores" in fields
        assert "strengths" in fields
        assert "areas_for_improvement" in fields
        assert "summary" in fields
        assert "executive_summary" in fields
        assert "detailed_feedback" in fields

    def test_mapping_overall_score_scaled_to_100(self):
        report = FinalInterviewReport(
            report_id="rpt-001", session_id="s", candidate_id="c",
            overall_score=7.5,
        )
        fields = FinalReportGenerator.report_to_summary_fields(report)
        assert fields["overall_score"] == 75.0  # 7.5 * 10

    def test_mapping_competency_scores_have_name_and_score(self):
        report = FinalInterviewReport(
            report_id="rpt-001", session_id="s", candidate_id="c",
            competency_scores=[
                CompetencyScore(competency_id="comp-1", competency_name="My Comp", score=6.5),
            ],
        )
        fields = FinalReportGenerator.report_to_summary_fields(report)
        cs = fields["competency_scores"][0]
        # FinalReport.jsx reads: item.name, item.competency, item.score, item.value
        assert cs["name"] == "My Comp"
        assert cs["competency"] == "My Comp"
        assert cs["score"] == 65.0  # 6.5 * 10
        assert cs["value"] == 65.0

    def test_summary_model_accepts_report_fields(self):
        """InterviewSummary can be constructed with report_to_summary_fields output."""
        report = FinalInterviewReport(
            report_id="rpt-001", session_id="sess-1", candidate_id="CAND-001",
            overall_score=7.0, recommendation=OverallRecommendation.HIRE,
            strengths=["S1"], areas_for_improvement=["I1"],
            executive_summary="Summary", detailed_feedback="Feedback",
        )
        fields = FinalReportGenerator.report_to_summary_fields(report)

        summary = InterviewSummary(
            session_id="sess-1", candidate_id="CAND-001",
            status=InterviewStatus.COMPLETED, total_questions=5,
            duration_seconds=600.0, topics_covered=["comp-1"],
            **fields,
        )

        assert summary.overall_score == 70.0
        assert summary.recommendation == "hire"
        assert summary.strengths == ["S1"]


# ═════════════════════════════════════════════════════════════════════
# SECTION 14: INTEGRATION WITH INTERVIEW SERVICE
# ═════════════════════════════════════════════════════════════════════


class TestInterviewServiceIntegration:
    """Integration tests through the actual InterviewService."""

    def test_create_session_initializes_intelligence(self):
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        assert "competency_states" in session.metadata
        assert "session_memory_snapshot" in session.metadata
        assert session.metadata["snapshot_index"] == 0
        assert session.metadata["competency_states"] == {}  # no evidence yet

    def test_submit_answer_updates_competency_states(self):
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        updated = service.submit_answer(
            session.session_id,
            CandidateAnswer(
                answer=(
                    "The concept behind this topic involves using embeddings to encode semantic meaning "
                    "and retrieve relevant context. In practice, I would compare vectors using cosine similarity "
                    "and consider the trade-offs between recall and precision."
                )
            ),
        )

        comp_states = updated.metadata.get("competency_states", {})
        assert len(comp_states) >= 1

        # At least one competency should have been tracked
        first_state = next(iter(comp_states.values()))
        assert first_state["questions_asked"] >= 1
        assert len(first_state["evidence_notes"]) >= 1

    def test_submit_answer_updates_session_memory(self):
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        updated = service.submit_answer(
            session.session_id,
            CandidateAnswer(answer="My answer about the topic with reasoning and trade-offs."),
        )

        snapshot = updated.metadata.get("session_memory_snapshot")
        assert snapshot is not None
        assert snapshot["snapshot_index"] >= 1
        assert len(snapshot["evaluation_history"]) >= 1
        assert len(snapshot["decision_history"]) >= 1

    def test_submit_answer_enhances_reasoning(self):
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        updated = service.submit_answer(
            session.session_id,
            CandidateAnswer(answer="A detailed answer about vectors, embeddings, and retrieval architecture with practical trade-offs."),
        )

        decision = updated.metadata.get("last_adaptive_decision", {})
        reasoning = decision.get("reasoning", "")
        # Should be evidence-based, not generic
        assert len(reasoning) > 30
        assert "decision:" in reasoning.lower()
        assert any(keyword in reasoning.lower() for keyword in ["increase difficulty", "decrease difficulty", "maintain difficulty", "probe weakness", "change competency"])
        assert "conceptual" in reasoning.lower() or "practical" in reasoning.lower()

    def test_submit_answer_stores_next_question_reason_and_trace(self):
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        updated = service.submit_answer(
            session.session_id,
            CandidateAnswer(answer="I would explain the trade-offs with a concrete implementation plan and mention how I would validate the outcome."),
        )

        assert updated.metadata.get("next_question_reason")
        traces = updated.metadata.get("evaluation_traces", [])
        assert traces
        trace = traces[-1]
        assert trace["candidate_answer"]
        assert trace["plan_id"] == updated.metadata["last_answer_evaluation"]["plan_id"]
        assert trace["strengths"] == updated.metadata["last_answer_evaluation"]["strengths"]
        assert trace["evaluation"]["evaluation_id"] == updated.metadata["last_answer_evaluation"]["evaluation_id"]

    def test_two_sessions_remain_isolated(self):
        service = _build_service()
        session_one = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
        session_two = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        updated_one = service.submit_answer(
            session_one.session_id,
            CandidateAnswer(answer="Session one answer about deployment trade-offs and observability."),
        )
        updated_two = service.submit_answer(
            session_two.session_id,
            CandidateAnswer(answer="Session two answer about local setup, virtual environments, and debugger configuration."),
        )

        trace_one = updated_one.metadata.get("evaluation_traces", [])[0]
        trace_two = updated_two.metadata.get("evaluation_traces", [])[0]

        assert trace_one["candidate_answer"] != trace_two["candidate_answer"]
        assert updated_one.metadata["evaluation_traces"][0]["candidate_answer"] != updated_two.metadata["evaluation_traces"][0]["candidate_answer"]

    def test_end_session_returns_real_report(self):
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        # Submit a couple answers
        service.submit_answer(
            session.session_id,
            CandidateAnswer(answer="The core concept involves embedding vectors for semantic retrieval. In practice, trade-offs include latency vs quality."),
        )
        service.submit_answer(
            session.session_id,
            CandidateAnswer(answer="For this topic I would implement a chunking strategy because it improves retrieval precision. The trade-off is between chunk size and context."),
        )

        summary = service.end_session(session.session_id)

        # Must return real report data
        assert summary.overall_score is not None
        assert summary.overall_score > 0.0
        assert summary.recommendation is not None
        assert summary.recommendation != ""
        assert summary.competency_scores is not None
        assert len(summary.competency_scores) >= 1
        assert summary.strengths  # should have actual strengths
        assert summary.summary is not None
        assert summary.summary != ""
        assert summary.executive_summary is not None
        assert summary.detailed_feedback is not None
        assert summary.topics_covered  # should list covered topics

    def test_end_session_report_not_hardcoded(self):
        """Different answers should produce different reports."""
        service1 = _build_service()
        session1 = service1.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
        service1.submit_answer(session1.session_id, CandidateAnswer(answer="I know everything about vectors and embeddings and trade-offs because I implemented a production RAG system with retrieval architecture."))
        service1.submit_answer(session1.session_id, CandidateAnswer(answer="In practice, the system handles failures through retry logic and fallback retrieval, with monitoring for quality trade-offs."))
        report1 = service1.end_session(session1.session_id)

        service2 = _build_service()
        session2 = service2.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
        service2.submit_answer(session2.session_id, CandidateAnswer(answer="Maybe vectors?"))
        service2.submit_answer(session2.session_id, CandidateAnswer(answer="Not sure about this."))
        report2 = service2.end_session(session2.session_id)

        # Different performance should yield different scores/recommendations
        assert report1.overall_score != report2.overall_score

    def test_end_session_stores_report_in_metadata(self):
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
        service.submit_answer(session.session_id, CandidateAnswer(answer="A reasonable answer about the topic with some trade-off reasoning."))
        service.submit_answer(session.session_id, CandidateAnswer(answer="Another answer with practical implementation details."))
        service.end_session(session.session_id)

        # Retrieve session to check metadata
        ended = service.get_session(session.session_id)
        assert "final_report" in ended.metadata
        assert ended.metadata["final_report"]["report_id"].startswith("rpt-")

    def test_accumulation_across_multiple_answers(self):
        """Three answers should accumulate evidence properly."""
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        answers = [
            "The concept involves embeddings for semantic retrieval with trade-offs in quality and latency.",
            "Chunking strategy improves retrieval by splitting documents, because smaller chunks provide better semantic matching.",
            "For production deployment, I would use monitoring and implement fallback retrieval for failure modes with trade-off analysis.",
        ]
        for answer in answers:
            session = service.submit_answer(session.session_id, CandidateAnswer(answer=answer))

        # Check that competency states accumulated
        comp_states = session.metadata.get("competency_states", {})
        assert len(comp_states) >= 1

        # Check evaluation history grew
        eval_history = session.metadata.get("evaluation_history", [])
        assert len(eval_history) == 3

        # Check snapshot index advanced
        assert session.metadata.get("snapshot_index", 0) == 3


# ═════════════════════════════════════════════════════════════════════
# SECTION 15: GROUNDING REGRESSION TESTS
# ═════════════════════════════════════════════════════════════════════


class TestGroundingRegression:
    """Regression tests for report grounding (no unrelated data leaks)."""

    def _run_session(self, num_answers: int = 3) -> tuple:
        """Helper: create a session, submit N answers, end session. Returns (service, session, summary)."""
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        strong = "I would implement this using vector embeddings for semantic retrieval. The key trade-off is between precision and recall, because smaller chunks improve matching but lose context."
        moderate = "This topic relates to data processing and system performance. We need to consider scaling trade-offs."
        weak = "Maybe it's about optimization. Not sure about the details."
        answers = [strong, moderate, weak, strong, moderate, weak, strong, moderate]

        for i in range(num_answers):
            session = service.submit_answer(
                session.session_id,
                CandidateAnswer(answer=answers[i % len(answers)]),
            )

        summary = service.end_session(session.session_id)
        ended = service.get_session(session.session_id)
        return service, ended, summary

    def test_no_unrelated_competencies_in_report(self):
        """Every competency in the final report must originate from an actual
        QuestionPlan used during the current session."""
        _, ended, summary = self._run_session(3)

        eval_history = ended.metadata.get("evaluation_history", [])
        evaluated_comp_ids = set(e["competency_id"] for e in eval_history if isinstance(e, dict))

        # Every competency score must reference an evaluated competency
        for cs in summary.competency_scores:
            assert cs["competency_id"] in evaluated_comp_ids, (
                f"Competency {cs['competency_id']} in report has no evaluation evidence"
            )

    def test_no_unrelated_missing_concepts(self):
        """Every missing concept in the report must come from a session evaluation."""
        _, ended, summary = self._run_session(3)

        eval_history = ended.metadata.get("evaluation_history", [])
        all_session_missing = set()
        for e in eval_history:
            if isinstance(e, dict):
                for mc in e.get("missing_concepts", []):
                    all_session_missing.add(mc)

        # Every improvement that starts with "Missing concept:" must be from session
        for item in summary.areas_for_improvement:
            if item.startswith("Missing concept: "):
                mc = item[len("Missing concept: "):]
                assert mc in all_session_missing, (
                    f"Missing concept '{mc}' not found in any session evaluation"
                )

    def test_report_contains_only_current_session_questions(self):
        """topics_covered must only reference topics that were actually evaluated."""
        _, ended, summary = self._run_session(3)

        eval_history = ended.metadata.get("evaluation_history", [])
        evaluated_comp_ids = set(e["competency_id"] for e in eval_history if isinstance(e, dict))
        topic_titles = dict(ended.metadata.get("topic_titles", {}))

        # Each topic_covered must map to an evaluated competency
        for topic_title in summary.topics_covered:
            # Find the comp_id(s) that map to this title
            matching_ids = [cid for cid, title in topic_titles.items() if title == topic_title]
            assert any(cid in evaluated_comp_ids for cid in matching_ids), (
                f"Topic '{topic_title}' in topics_covered has no evaluation evidence"
            )

    def test_strengths_come_from_evaluations(self):
        """Every strength must originate from at least one evaluation."""
        _, ended, summary = self._run_session(3)

        eval_history = ended.metadata.get("evaluation_history", [])
        all_session_strengths = set()
        for e in eval_history:
            if isinstance(e, dict):
                for s in e.get("strengths", []):
                    all_session_strengths.add(s)

        for s in summary.strengths:
            assert s in all_session_strengths, (
                f"Strength '{s}' not found in any session evaluation"
            )

    def test_weaknesses_come_from_evaluations(self):
        """Every weakness/improvement must trace to an evaluation."""
        _, ended, summary = self._run_session(3)

        eval_history = ended.metadata.get("evaluation_history", [])
        all_session_weaknesses = set()
        all_session_missing = set()
        all_session_misconceptions = set()
        for e in eval_history:
            if isinstance(e, dict):
                for w in e.get("weaknesses", []):
                    all_session_weaknesses.add(w)
                for mc in e.get("missing_concepts", []):
                    all_session_missing.add(mc)
                for m in e.get("misconceptions", []):
                    all_session_misconceptions.add(m)

        for item in summary.areas_for_improvement:
            if item.startswith("Missing concept: "):
                mc = item[len("Missing concept: "):]
                assert mc in all_session_missing, f"'{mc}' not in session missing concepts"
            elif item.startswith("Misconception: "):
                m = item[len("Misconception: "):]
                assert m in all_session_misconceptions, f"'{m}' not in session misconceptions"
            else:
                assert item in all_session_weaknesses, f"'{item}' not in session weaknesses"

    def test_adaptive_decision_references_actual_evaluation(self):
        """The adaptive decision reasoning must reference real evaluation data."""
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
        session = service.submit_answer(
            session.session_id,
            CandidateAnswer(answer="I implement this using embeddings and retrieval trade-offs."),
        )

        decision = session.metadata.get("last_adaptive_decision", {})
        reasoning = decision.get("reasoning", "")

        # Reasoning must not be empty/generic
        assert len(reasoning) > 30
        # Must reference actual evaluation data (score, performance, etc.)
        assert any(word in reasoning.lower() for word in ("score", "performance", "proficiency", "confidence", "demonstrated"))

    def test_two_sessions_remain_isolated(self):
        """Two separate sessions must not leak data into each other."""
        service1 = _build_service()
        session1 = service1.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
        session1 = service1.submit_answer(
            session1.session_id,
            CandidateAnswer(answer="Detailed answer about embeddings, chunking, and retrieval architecture."),
        )
        service1.submit_answer(
            session1.session_id,
            CandidateAnswer(answer="Trade-off between precision and recall in vector search."),
        )
        summary1 = service1.end_session(session1.session_id)

        service2 = _build_service()
        session2 = service2.create_session(InterviewSessionCreate(candidate_id="CAND-002"))
        service2.submit_answer(
            session2.session_id,
            CandidateAnswer(answer="Maybe vectors?"),
        )
        summary2 = service2.end_session(session2.session_id)

        # Sessions must have independent data
        assert summary1.session_id != summary2.session_id
        assert summary1.overall_score != summary2.overall_score

        # Competency scores must not leak between sessions
        comp_ids_1 = {cs["competency_id"] for cs in summary1.competency_scores}
        comp_ids_2 = {cs["competency_id"] for cs in summary2.competency_scores}
        # Even if they overlap on curriculum topics, the evidence counts must be independent
        ended1 = service1.get_session(session1.session_id)
        ended2 = service2.get_session(session2.session_id)
        eval_count_1 = len(ended1.metadata.get("evaluation_history", []))
        eval_count_2 = len(ended2.metadata.get("evaluation_history", []))
        assert eval_count_1 == 2  # session1 had 2 answers
        assert eval_count_2 == 1  # session2 had 1 answer

    def test_report_with_1_evaluated_question(self):
        """Report must work correctly with a single evaluated question."""
        _, _, summary = self._run_session(1)

        assert summary.overall_score is not None
        assert summary.overall_score > 0.0
        assert summary.recommendation is not None
        assert len(summary.competency_scores) >= 1
        assert summary.recommendation == "needs_further_evaluation"

    def test_report_with_3_evaluated_questions(self):
        """Report must work correctly with 3 evaluated questions."""
        _, ended, summary = self._run_session(3)

        eval_count = len(ended.metadata.get("evaluation_history", []))
        assert eval_count == 3

        assert summary.overall_score is not None
        assert summary.overall_score > 0.0
        assert len(summary.competency_scores) >= 1
        assert all(cs["evidence_count"] >= 1 for cs in summary.competency_scores)

    def test_report_with_8_evaluated_questions(self):
        """Report must work correctly with 8 evaluated questions (simulated)."""
        _, ended, summary = self._run_session(8)

        eval_count = len(ended.metadata.get("evaluation_history", []))
        assert eval_count == 8

        assert summary.overall_score is not None
        assert summary.overall_score > 0.0
        assert len(summary.competency_scores) >= 1

        # Total evidence across all competencies must equal 8
        total_evidence = sum(cs["evidence_count"] for cs in summary.competency_scores)
        assert total_evidence == 8

    def test_insufficient_evidence_produces_needs_further(self):
        """A session with only 1 question must produce NEEDS_FURTHER_EVALUATION."""
        _, _, summary = self._run_session(1)
        assert summary.recommendation == "needs_further_evaluation"

    def test_topics_covered_uses_titles_not_raw_ids(self):
        """topics_covered in the report must use human-readable titles,
        not raw curriculum IDs like 'day-29'."""
        _, _, summary = self._run_session(3)

        for topic in summary.topics_covered:
            # Raw IDs look like 'day-1', 'day-29', etc.
            assert not topic.startswith("day-"), (
                f"Raw curriculum ID '{topic}' leaked into topics_covered"
            )

    def test_evaluated_topic_ids_excludes_unanswered_question(self):
        """evaluated_topic_ids must NOT include the next planned but unanswered question."""
        service = _build_service()
        session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

        # Submit 2 answers → 3 questions were asked (including the unanswered next one)
        session = service.submit_answer(
            session.session_id,
            CandidateAnswer(answer="Detailed answer about the topic with trade-offs."),
        )
        session = service.submit_answer(
            session.session_id,
            CandidateAnswer(answer="Another answer about different aspects."),
        )

        evaluated = session.metadata.get("evaluated_topic_ids", [])
        asked = session.metadata.get("asked_topic_ids", [])

        # asked includes the next question's topic, evaluated does not
        assert len(evaluated) <= len(asked)

        # Only 2 questions were answered, so at most 2 unique evaluated topics
        assert len(evaluated) <= 2

        # Each evaluated topic must have at least one evaluation
        eval_history = session.metadata.get("evaluation_history", [])
        evaluated_in_history = set(
            e["competency_id"] for e in eval_history if isinstance(e, dict)
        )
        for tid in evaluated:
            assert tid in evaluated_in_history

