"""
Session intelligence pipeline.
Owner: THEJAS

Deterministic, explainable intelligence modules that power the
Session Memory → Competency State → Final Report pipeline.

Modules:
    CompetencyTracker       – persistent per-competency state management
    ProficiencyCalculator   – deterministic proficiency from accumulated evidence
    SessionMemoryManager    – auditable SessionMemorySnapshot lifecycle
    AdaptiveReasoningEnhancer – evidence-based reasoning for AdaptiveDecision
    FinalReportGenerator    – comprehensive FinalInterviewReport from session data

All logic is deterministic, traceable, and free of LLM/API dependencies.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.models.adaptive import (
    AdaptiveAction,
    AdaptiveDecision,
    AnswerEvaluation,
    CompetencyCategory,
    CompetencyScore,
    CompetencyState,
    FinalInterviewReport,
    OverallRecommendation,
    ProficiencyLevel,
    QuestionPlan,
    SessionMemorySnapshot,
)
from app.models.common import DifficultyLevel, InterviewStatus

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# PROFICIENCY CALCULATOR
# ═══════════════════════════════════════════════════════════════════════


class ProficiencyCalculator:
    """Deterministic, explainable proficiency from accumulated evaluations.

    Rules (each level requires ALL conditions to be met):

    NONE      – no answered questions or no demonstrated evidence
    BEGINNER  – any evidence, but weak/basic (avg overall < 40)
    INTERMEDIATE – avg overall 40–69, ≥1 question, some criteria met
    ADVANCED  – avg overall 70–84, ≥2 questions, reasoning + practical depth
    EXPERT    – avg overall ≥ 85, ≥3 questions, consistently strong across
                ALL sub-scores, no unresolved significant misconceptions,
                repeated strong evidence across multiple criteria
    """

    @staticmethod
    def calculate(
        evaluations: list[AnswerEvaluation],
    ) -> tuple[ProficiencyLevel, float]:
        """Return (proficiency, confidence) from evaluations for ONE competency.

        Confidence grows with independent evidence:
            min(1.0, 0.3 + 0.15 * evidence_count)
        """
        if not evaluations:
            return ProficiencyLevel.NONE, 0.0

        evidence_count = len(evaluations)
        confidence = min(1.0, round(0.3 + 0.15 * evidence_count, 2))

        # ── Aggregate metrics ───────────────────────────────────────
        avg_overall = _safe_avg([e.overall_score or (e.score * 10) for e in evaluations])
        avg_conceptual = _safe_avg([e.conceptual_correctness_score for e in evaluations])
        avg_reasoning = _safe_avg([e.depth_reasoning_score for e in evaluations])
        avg_practical = _safe_avg([e.practical_understanding_score for e in evaluations])
        avg_confidence = _safe_avg([e.confidence_score for e in evaluations])
        avg_evidence = _safe_avg([e.evidence_score for e in evaluations])

        total_strengths = sum(len(e.strengths) for e in evaluations)
        total_weaknesses = sum(len(e.weaknesses) for e in evaluations)
        total_misconceptions = sum(len(e.misconceptions) for e in evaluations)
        total_missing = sum(len(e.missing_concepts) for e in evaluations)

        # Does the latest evaluation still have unresolved misconceptions?
        latest = evaluations[-1]
        has_unresolved_misconceptions = bool(latest.misconceptions)

        # ── EXPERT ──────────────────────────────────────────────────
        # Require ALL of:
        #   - ≥3 questions answered
        #   - avg overall ≥ 85
        #   - avg reasoning ≥ 65  (strong reasoning depth)
        #   - avg practical ≥ 65  (strong practical understanding)
        #   - avg conceptual ≥ 70 (strong conceptual correctness)
        #   - avg confidence ≥ 60
        #   - no unresolved significant misconceptions in latest eval
        #   - more strengths than weaknesses across all evaluations
        #   - total misconceptions ≤ 1 across all evaluations
        if (
            evidence_count >= 3
            and avg_overall >= 85.0
            and avg_reasoning >= 65.0
            and avg_practical >= 65.0
            and avg_conceptual >= 70.0
            and avg_confidence >= 60.0
            and not has_unresolved_misconceptions
            and total_misconceptions <= 1
            and total_strengths > total_weaknesses
        ):
            return ProficiencyLevel.EXPERT, confidence

        # ── ADVANCED ────────────────────────────────────────────────
        # Require:
        #   - ≥2 questions answered
        #   - avg overall 70–84 (or ≥85 but failed EXPERT criteria)
        #   - avg reasoning ≥ 40 (shows some reasoning depth)
        #   - avg practical ≥ 35 (shows some practical connection)
        #   - total misconceptions ≤ 2
        if (
            evidence_count >= 2
            and avg_overall >= 70.0
            and avg_reasoning >= 40.0
            and avg_practical >= 35.0
            and total_misconceptions <= 2
        ):
            return ProficiencyLevel.ADVANCED, confidence

        # ── INTERMEDIATE ────────────────────────────────────────────
        # Require:
        #   - ≥1 question answered
        #   - avg overall 40–69 (or ≥70 but failed ADVANCED criteria)
        #   - some criteria met (at least 1 strength demonstrated)
        if (
            evidence_count >= 1
            and avg_overall >= 40.0
            and total_strengths >= 1
        ):
            return ProficiencyLevel.INTERMEDIATE, confidence

        # ── BEGINNER ────────────────────────────────────────────────
        # Any evidence but weak/basic
        if evidence_count >= 1:
            return ProficiencyLevel.BEGINNER, confidence

        return ProficiencyLevel.NONE, 0.0


# ═══════════════════════════════════════════════════════════════════════
# COMPETENCY TRACKER
# ═══════════════════════════════════════════════════════════════════════


class CompetencyTracker:
    """Manages persistent CompetencyState per competency across the interview.

    Evidence is accumulated, never overwritten.
    """

    @staticmethod
    def update_competency_state(
        competency_id: str,
        evaluation: AnswerEvaluation,
        question_plan: QuestionPlan,
        current_states: dict[str, CompetencyState],
        evaluation_history_for_competency: list[AnswerEvaluation],
    ) -> CompetencyState:
        """Update (or create) the CompetencyState for *competency_id*.

        Parameters
        ----------
        competency_id:
            The competency being assessed.
        evaluation:
            The latest AnswerEvaluation for this competency.
        question_plan:
            The QuestionPlan that generated this question.
        current_states:
            Existing competency states keyed by competency_id.
        evaluation_history_for_competency:
            ALL evaluations for this competency so far (including the latest).
        """
        existing = current_states.get(competency_id)
        questions_asked = (existing.questions_asked if existing else 0) + 1
        prev_correct = existing.questions_answered_correctly if existing else 0
        answered_correctly = prev_correct + (1 if evaluation.score >= 5.0 else 0)

        # Accumulate evidence notes — never overwrite
        prev_notes = list(existing.evidence_notes) if existing else []
        new_note = _build_evidence_note(evaluation, question_plan)
        evidence_notes = prev_notes + [new_note]

        # Calculate proficiency from ALL evaluations for this competency
        proficiency, confidence = ProficiencyCalculator.calculate(
            evaluation_history_for_competency
        )

        state = CompetencyState(
            competency_id=competency_id,
            proficiency=proficiency,
            confidence=confidence,
            questions_asked=questions_asked,
            questions_answered_correctly=answered_correctly,
            last_difficulty=question_plan.target_difficulty,
            evidence_notes=evidence_notes,
        )
        logger.debug(
            "CompetencyState updated: %s → %s (confidence=%.2f, q=%d)",
            competency_id,
            proficiency.value,
            confidence,
            questions_asked,
        )
        return state


# ═══════════════════════════════════════════════════════════════════════
# SESSION MEMORY MANAGER
# ═══════════════════════════════════════════════════════════════════════


class SessionMemoryManager:
    """Creates auditable SessionMemorySnapshot objects.

    Snapshot index 0 represents interview initialisation/context and
    does NOT contain competency evidence.  Evidence-bearing snapshots
    begin at index 1 after the first candidate answer.
    """

    @staticmethod
    def create_initial_snapshot(
        session_id: str,
        candidate_id: str,
        first_plan: QuestionPlan,
        difficulty: DifficultyLevel,
    ) -> SessionMemorySnapshot:
        """Create snapshot index 0 — initialisation context only."""
        return SessionMemorySnapshot(
            session_id=session_id,
            snapshot_index=0,
            candidate_id=candidate_id,
            competency_states=[],
            questions_plan_history=[first_plan],
            evaluation_history=[],
            decision_history=[],
            current_difficulty=difficulty,
            current_competency_id=first_plan.competency_id,
            total_questions_asked=1,
            topics_covered=[first_plan.competency_id],
        )

    @staticmethod
    def create_snapshot(
        session_id: str,
        candidate_id: str,
        snapshot_index: int,
        competency_states: list[CompetencyState],
        plan_history: list[QuestionPlan],
        evaluation_history: list[AnswerEvaluation],
        decision_history: list[AdaptiveDecision],
        current_difficulty: DifficultyLevel,
        current_competency_id: str | None,
        total_questions_asked: int,
        topics_covered: list[str],
    ) -> SessionMemorySnapshot:
        """Create an evidence-bearing snapshot (index ≥ 1)."""
        return SessionMemorySnapshot(
            session_id=session_id,
            snapshot_index=snapshot_index,
            candidate_id=candidate_id,
            competency_states=competency_states,
            questions_plan_history=plan_history,
            evaluation_history=evaluation_history,
            decision_history=decision_history,
            current_difficulty=current_difficulty,
            current_competency_id=current_competency_id,
            total_questions_asked=total_questions_asked,
            topics_covered=topics_covered,
        )


# ═══════════════════════════════════════════════════════════════════════
# ADAPTIVE REASONING ENHANCER
# ═══════════════════════════════════════════════════════════════════════


class AdaptiveReasoningEnhancer:
    """Produces evidence-based reasoning for AdaptiveDecision.

    Every statement is traceable to actual evaluation/session data.
    """

    @staticmethod
    def enhance_reasoning(
        evaluation: AnswerEvaluation,
        competency_state: CompetencyState | None,
        decision: AdaptiveDecision,
    ) -> str:
        """Build an explainable reasoning string from evidence."""
        parts: list[str] = []

        score_desc = _score_descriptor(evaluation.overall_score or (evaluation.score * 10))

        action_phrase = {
            AdaptiveAction.INCREASE_DIFFICULTY: "increase difficulty",
            AdaptiveAction.DECREASE_DIFFICULTY: "decrease difficulty",
            AdaptiveAction.CONTINUE_SAME_TOPIC: "maintain difficulty",
            AdaptiveAction.SWITCH_TOPIC: "change competency",
            AdaptiveAction.DEEP_DIVE: "probe weakness",
            AdaptiveAction.CONCLUDE_INTERVIEW: "conclude interview",
        }[decision.action]

        if decision.action == AdaptiveAction.CONTINUE_SAME_TOPIC and (
            evaluation.weaknesses or evaluation.missing_concepts or evaluation.misconceptions
        ):
            action_phrase = "probe weakness"
        elif decision.action == AdaptiveAction.DEEP_DIVE:
            action_phrase = "probe weakness"

        # Performance summary
        parts.append(
            f"Candidate demonstrated {score_desc} performance "
            f"(score {evaluation.score:.1f}/10)"
        )

        parts.append(
            "Evaluation signals: "
            f"conceptual {evaluation.conceptual_correctness_score:.0f}/100, "
            f"reasoning {evaluation.depth_reasoning_score:.0f}/100, "
            f"practical {evaluation.practical_understanding_score:.0f}/100, "
            f"confidence {evaluation.confidence_score:.0f}/100, "
            f"evidence {evaluation.evidence_score:.0f}/100"
        )

        # Strengths
        if evaluation.strengths:
            parts.append(
                f"with strengths in {_join_list(evaluation.strengths[:3])}"
            )

        # Weaknesses / gaps
        if evaluation.weaknesses:
            parts.append(
                f"but showed weakness in {_join_list(evaluation.weaknesses[:3])}"
            )

        # Misconceptions
        if evaluation.misconceptions:
            parts.append(
                f"Misconception detected: {_join_list(evaluation.misconceptions[:2])}"
            )

        # Action-specific reasoning
        action = decision.action
        if action == AdaptiveAction.INCREASE_DIFFICULTY:
            if competency_state and competency_state.questions_asked >= 2:
                parts.append(
                    f"The candidate demonstrated the target competency across "
                    f"{competency_state.questions_asked} questions with "
                    f"{competency_state.proficiency.value} proficiency, "
                    f"so difficulty increased"
                )
            else:
                parts.append(
                    "Strong answer warrants increased difficulty"
                )

        elif action == AdaptiveAction.DECREASE_DIFFICULTY:
            parts.append(
                "Weak performance suggests lowering difficulty to build confidence"
            )

        elif action == AdaptiveAction.CONTINUE_SAME_TOPIC:
            if evaluation.misconceptions:
                parts.append(
                    "Staying on the same competency for a corrective follow-up "
                    "to address the detected misconception"
                )
            elif evaluation.follow_up_needed:
                parts.append(
                    "Follow-up needed to clarify incomplete understanding"
                )
            else:
                parts.append("Continuing same topic to deepen assessment")

        elif action == AdaptiveAction.SWITCH_TOPIC:
            parts.append(
                "Switching to a new competency to broaden assessment coverage"
            )

        elif action == AdaptiveAction.DEEP_DIVE:
            parts.append(
                "Strong conceptual understanding detected — probing deeper "
                "on production trade-offs"
            )

        elif action == AdaptiveAction.CONCLUDE_INTERVIEW:
            parts.append(
                "Sufficient evidence collected across competencies"
            )

        parts.append(f"Decision: {action_phrase}")

        # Competency state context
        if competency_state and competency_state.questions_asked >= 1:
            parts.append(
                f"(Competency: {competency_state.competency_id}, "
                f"proficiency: {competency_state.proficiency.value}, "
                f"confidence: {competency_state.confidence:.0%})"
            )

        return ". ".join(parts) + "."


# ═══════════════════════════════════════════════════════════════════════
# FINAL REPORT GENERATOR
# ═══════════════════════════════════════════════════════════════════════


class FinalReportGenerator:
    """Generates a comprehensive FinalInterviewReport from session data.

    The FinalInterviewReport is the canonical internal report model.
    Mapping to InterviewSummary for the frontend/API layer is handled
    separately via ``report_to_summary_fields()``.
    """

    @staticmethod
    def generate_report(
        session_id: str,
        candidate_id: str,
        competency_states: dict[str, CompetencyState],
        evaluation_history: list[AnswerEvaluation],
        decision_history: list[AdaptiveDecision],
        plan_history: list[QuestionPlan],
        total_questions: int,
        duration_seconds: float,
        topics_covered: list[str],
        topic_titles: dict[str, str] | None = None,
    ) -> FinalInterviewReport:
        """Aggregate ALL accumulated evidence into a FinalInterviewReport."""

        # ── Per-competency scoring ──────────────────────────────────
        competency_scores = _build_competency_scores(
            competency_states, evaluation_history, plan_history,
            topic_titles=topic_titles or {},
        )

        # ── Overall score ───────────────────────────────────────────
        overall_score = _calculate_overall_score(
            competency_scores, evaluation_history
        )

        # ── Recommendation ──────────────────────────────────────────
        recommendation = _calculate_recommendation(
            overall_score, competency_scores, evaluation_history
        )

        # ── Aggregate strengths/improvements ────────────────────────
        strengths, improvements = _aggregate_strengths_improvements(evaluation_history)

        # ── Executive summary ───────────────────────────────────────
        executive_summary = _build_executive_summary(
            competency_scores, strengths, improvements, overall_score, recommendation
        )

        # ── Detailed feedback ───────────────────────────────────────
        detailed_feedback = _build_detailed_feedback(
            competency_scores, evaluation_history, decision_history
        )

        report = FinalInterviewReport(
            report_id=f"rpt-{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            candidate_id=candidate_id,
            status=InterviewStatus.COMPLETED,
            overall_score=overall_score,
            recommendation=recommendation,
            competency_scores=competency_scores,
            strengths=strengths,
            areas_for_improvement=improvements,
            total_questions=total_questions,
            total_duration_seconds=duration_seconds,
            topics_covered=topics_covered,
            executive_summary=executive_summary,
            detailed_feedback=detailed_feedback,
        )
        logger.info(
            "FinalInterviewReport generated: %s (score=%.1f, rec=%s)",
            report.report_id,
            overall_score,
            recommendation.value,
        )
        return report

    @staticmethod
    def report_to_summary_fields(report: FinalInterviewReport) -> dict[str, Any]:
        """Map FinalInterviewReport → fields for InterviewSummary.

        This is the single, centralized mapping point between the
        canonical FinalInterviewReport and the API/frontend-facing
        InterviewSummary compatibility layer.
        """
        # Convert competency scores to dicts the frontend can render.
        # FinalReport.jsx reads: item.name, item.competency, item.score, item.value
        competency_dicts = []
        for cs in report.competency_scores:
            competency_dicts.append({
                "competency_id": cs.competency_id,
                "name": cs.competency_name or cs.competency_id,
                "competency": cs.competency_name or cs.competency_id,
                "category": cs.category.value if cs.category else "technical",
                "proficiency": cs.proficiency.value if cs.proficiency else "none",
                "score": round(cs.score * 10, 1),   # 0-10 → 0-100 for frontend ring
                "value": round(cs.score * 10, 1),
                "max_score": cs.max_score * 10,
                "confidence": cs.confidence,
                "evidence_count": cs.evidence_count,
                "notes": cs.notes,
            })

        return {
            "overall_score": round(report.overall_score * 10, 1),  # 0-10 → 0-100
            "recommendation": report.recommendation.value,
            "competency_scores": competency_dicts,
            "strengths": list(report.strengths),
            "areas_for_improvement": list(report.areas_for_improvement),
            "summary": report.executive_summary,
            "executive_summary": report.executive_summary,
            "detailed_feedback": report.detailed_feedback,
        }


# ═══════════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════════════


def _safe_avg(values: list[float]) -> float:
    """Return average, or 0.0 for empty lists."""
    return round(sum(values) / len(values), 2) if values else 0.0


def _score_descriptor(overall_score: float) -> str:
    """Human-readable score descriptor."""
    if overall_score >= 85:
        return "exceptional"
    if overall_score >= 70:
        return "strong"
    if overall_score >= 50:
        return "moderate"
    if overall_score >= 30:
        return "weak"
    return "very weak"


def _join_list(items: list[str]) -> str:
    """Join strings with commas and 'and'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _build_evidence_note(
    evaluation: AnswerEvaluation, question_plan: QuestionPlan
) -> str:
    """Build a single evidence note from an evaluation."""
    parts = [f"Q[{question_plan.plan_id}]"]

    score = evaluation.overall_score or (evaluation.score * 10)
    parts.append(f"score={score:.0f}/100")

    if evaluation.strengths:
        parts.append(f"strengths: {', '.join(evaluation.strengths[:2])}")
    if evaluation.weaknesses:
        parts.append(f"weaknesses: {', '.join(evaluation.weaknesses[:2])}")
    if evaluation.misconceptions:
        parts.append(f"misconceptions: {', '.join(evaluation.misconceptions[:2])}")
    if evaluation.missing_concepts:
        parts.append(f"gaps: {', '.join(evaluation.missing_concepts[:2])}")

    difficulty = question_plan.target_difficulty.value
    parts.append(f"difficulty={difficulty}")

    return "; ".join(parts)


def _plan_display_name(question_plan: QuestionPlan) -> str:
    """Return the most human-readable competency label for a plan."""
    if question_plan.topic_context:
        return question_plan.topic_context

    objective = question_plan.objective.strip()
    prefix = "Assess the candidate's understanding of "
    suffix = " after their last answer"
    if objective.startswith(prefix):
        objective = objective[len(prefix):]
    if objective.endswith(suffix):
        objective = objective[: -len(suffix)]

    return objective or question_plan.competency_id


def _display_competency_name(competency_score: CompetencyScore) -> str:
    """Return a readable competency label without leaking raw IDs when possible."""
    return competency_score.competency_name or competency_score.competency_id


def _build_competency_scores(
    competency_states: dict[str, CompetencyState],
    evaluation_history: list[AnswerEvaluation],
    plan_history: list[QuestionPlan],
    topic_titles: dict[str, str] | None = None,
) -> list[CompetencyScore]:
    """Create CompetencyScore entries only from evaluated question plans."""
    _titles = topic_titles or {}
    plan_by_id = {plan.plan_id: plan for plan in plan_history}

    evals_by_comp: dict[str, list[tuple[AnswerEvaluation, QuestionPlan]]] = {}
    for evaluation in evaluation_history:
        question_plan = plan_by_id.get(evaluation.plan_id)
        if question_plan is None:
            continue
        if question_plan.competency_id != evaluation.competency_id:
            continue
        evals_by_comp.setdefault(evaluation.competency_id, []).append((evaluation, question_plan))

    scores: list[CompetencyScore] = []
    for comp_id in sorted(evals_by_comp):
        comp_pairs = evals_by_comp[comp_id]
        comp_evals = [evaluation for evaluation, _ in comp_pairs]
        state = competency_states.get(comp_id)
        latest_plan = comp_pairs[-1][1]

        weighted_scores: list[float] = []
        for idx, evaluation in enumerate(comp_evals):
            weight = 1.0 + (0.15 * idx)
            raw = (evaluation.overall_score or (evaluation.score * 10)) / 10.0
            weighted_scores.append(raw * weight)

        total_weight = sum(1.0 + 0.15 * idx for idx in range(len(comp_evals)))
        comp_score = min(10.0, round(sum(weighted_scores) / total_weight, 2)) if total_weight else 0.0

        proficiency = state.proficiency if state else ProficiencyLevel.NONE
        confidence = state.confidence if state else 0.0
        evidence_count = len(comp_evals)

        all_strengths = [strength for evaluation in comp_evals for strength in evaluation.strengths]
        all_weaknesses = [weakness for evaluation in comp_evals for weakness in evaluation.weaknesses]
        all_missing = [concept for evaluation in comp_evals for concept in evaluation.missing_concepts]
        all_misconceptions = [item for evaluation in comp_evals for item in evaluation.misconceptions]

        note_parts: list[str] = []
        if all_strengths:
            unique_strengths = list(dict.fromkeys(all_strengths))[:3]
            note_parts.append(f"Strengths: {', '.join(unique_strengths)}")
        if all_weaknesses:
            unique_weaknesses = list(dict.fromkeys(all_weaknesses))[:3]
            note_parts.append(f"Weaknesses: {', '.join(unique_weaknesses)}")
        if all_missing:
            unique_missing = list(dict.fromkeys(all_missing))[:3]
            note_parts.append(f"Missing concepts: {', '.join(unique_missing)}")
        if all_misconceptions:
            unique_misconceptions = list(dict.fromkeys(all_misconceptions))[:3]
            note_parts.append(f"Misconceptions: {', '.join(unique_misconceptions)}")

        # RC-2 fix: Resolve name from topic_titles first, then plan display name
        comp_name = _titles.get(comp_id) or _plan_display_name(latest_plan)

        scores.append(CompetencyScore(
            competency_id=comp_id,
            competency_name=comp_name,
            category=CompetencyCategory.TECHNICAL,
            proficiency=proficiency,
            score=comp_score,
            max_score=10.0,
            confidence=confidence,
            evidence_count=evidence_count,
            notes="; ".join(note_parts),
        ))

    return scores


def _calculate_overall_score(
    competency_scores: list[CompetencyScore],
    evaluation_history: list[AnswerEvaluation],
) -> float:
    """Calculate overall interview score (0.0–10.0).

    No single question dominates.  Account for competency performance,
    evidence confidence, number of questions, and consistency.
    """
    if not competency_scores:
        if not evaluation_history:
            return 0.0
        # Fallback: average of all evaluation scores
        raw = _safe_avg([e.score for e in evaluation_history])
        return round(min(10.0, raw), 2)

    # Weighted average of competency scores by confidence
    total_weighted = 0.0
    total_weight = 0.0
    for cs in competency_scores:
        if cs.evidence_count == 0:
            continue
        weight = max(0.1, cs.confidence) * max(1, cs.evidence_count)
        total_weighted += cs.score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    base_score = total_weighted / total_weight

    # Consistency adjustment: penalise high variance across evaluations
    if len(evaluation_history) >= 2:
        eval_scores = [e.score for e in evaluation_history]
        mean_score = _safe_avg(eval_scores)
        variance = _safe_avg([(s - mean_score) ** 2 for s in eval_scores])
        # Small penalty for inconsistency (max 0.5 penalty)
        consistency_penalty = min(0.5, variance * 0.1)
        base_score = max(0.0, base_score - consistency_penalty)

    return round(min(10.0, max(0.0, base_score)), 2)


def _calculate_recommendation(
    overall_score: float,
    competency_scores: list[CompetencyScore],
    evaluation_history: list[AnswerEvaluation],
) -> OverallRecommendation:
    """Deterministic recommendation from evidence.

    Considers: overall performance, confidence, evidence sufficiency,
    competency coverage, consistency.  Returns NEEDS_FURTHER_EVALUATION
    when evidence is insufficient.
    """
    if not evaluation_history:
        return OverallRecommendation.NEEDS_FURTHER_EVALUATION

    # ── Evidence sufficiency ────────────────────────────────────────
    total_evidence = len(evaluation_history)
    avg_confidence = _safe_avg([cs.confidence for cs in competency_scores]) if competency_scores else 0.0
    competencies_assessed = sum(1 for cs in competency_scores if cs.evidence_count > 0)

    # Insufficient evidence guard
    if total_evidence < 2 or avg_confidence < 0.3:
        return OverallRecommendation.NEEDS_FURTHER_EVALUATION

    if competencies_assessed == 0:
        return OverallRecommendation.NEEDS_FURTHER_EVALUATION

    # ── Consistency check ───────────────────────────────────────────
    eval_scores = [e.score for e in evaluation_history]
    mean_score = _safe_avg(eval_scores)
    variance = _safe_avg([(s - mean_score) ** 2 for s in eval_scores])
    is_consistent = variance < 4.0  # ~2-point std dev threshold

    # ── Total misconceptions across all evaluations ─────────────────
    total_misconceptions = sum(len(e.misconceptions) for e in evaluation_history)

    # ── Decision matrix ─────────────────────────────────────────────
    if overall_score >= 8.0 and avg_confidence >= 0.6 and is_consistent and total_misconceptions <= 1:
        return OverallRecommendation.STRONG_HIRE

    if overall_score >= 6.5 and avg_confidence >= 0.5 and total_misconceptions <= 2:
        return OverallRecommendation.HIRE

    if overall_score >= 5.0 and avg_confidence >= 0.4:
        return OverallRecommendation.LEAN_HIRE

    if overall_score >= 3.5:
        return OverallRecommendation.LEAN_NO_HIRE

    if overall_score < 3.5 and total_evidence >= 2:
        return OverallRecommendation.NO_HIRE

    return OverallRecommendation.NEEDS_FURTHER_EVALUATION


def _aggregate_strengths_improvements(
    evaluation_history: list[AnswerEvaluation],
) -> tuple[list[str], list[str]]:
    """Aggregate unique strengths and areas for improvement from evidence."""
    seen_strengths: list[str] = []
    seen_improvements: list[str] = []

    for ev in evaluation_history:
        for s in ev.strengths:
            if s not in seen_strengths:
                seen_strengths.append(s)
        for w in ev.weaknesses:
            if w not in seen_improvements:
                seen_improvements.append(w)

    # Add missing concepts as areas for improvement
    for ev in evaluation_history:
        for mc in ev.missing_concepts:
            note = f"Missing concept: {mc}"
            if note not in seen_improvements:
                seen_improvements.append(note)

    for ev in evaluation_history:
        for misconception in ev.misconceptions:
            note = f"Misconception: {misconception}"
            if note not in seen_improvements:
                seen_improvements.append(note)

    return seen_strengths[:10], seen_improvements[:10]


def _build_executive_summary(
    competency_scores: list[CompetencyScore],
    strengths: list[str],
    improvements: list[str],
    overall_score: float,
    recommendation: OverallRecommendation,
) -> str:
    """Build a deterministic executive summary from actual evidence.

    Every statement is traceable to stored evidence.
    """
    parts: list[str] = []

    # Opening with scope
    assessed_names = [_display_competency_name(cs) for cs in competency_scores if cs.evidence_count > 0]
    if assessed_names:
        topic_list = ", ".join(assessed_names[:5])
        parts.append(
            f"The candidate was assessed across {len(assessed_names)} "
            f"competency area(s): {topic_list}"
        )

    # Strong competencies
    strong = [cs for cs in competency_scores if cs.score >= 7.0 and cs.evidence_count > 0]
    if strong:
        names = [_display_competency_name(cs) for cs in strong]
        parts.append(
            f"Demonstrated strong performance in {_join_list(names)}"
        )

    # Weak competencies
    weak = [cs for cs in competency_scores if cs.score < 4.0 and cs.evidence_count > 0]
    if weak:
        names = [_display_competency_name(cs) for cs in weak]
        parts.append(
            f"Showed weakness in {_join_list(names)}"
        )

    # Key strengths from evidence
    if strengths:
        parts.append(
            f"Key strengths observed: {_join_list(strengths[:3])}"
        )

    # Key improvement areas from evidence
    if improvements:
        parts.append(
            f"Key areas for improvement: {_join_list(improvements[:3])}"
        )

    # Overall assessment
    score_desc = _score_descriptor(overall_score * 10)  # 0-10 → 0-100
    parts.append(
        f"Overall performance was {score_desc} "
        f"(score: {overall_score:.1f}/10, "
        f"recommendation: {recommendation.value.replace('_', ' ')})"
    )

    return ". ".join(parts) + "."


def _build_detailed_feedback(
    competency_scores: list[CompetencyScore],
    evaluation_history: list[AnswerEvaluation],
    decision_history: list[AdaptiveDecision],
) -> str:
    """Build detailed structured feedback from actual evidence."""
    sections: list[str] = []

    # 1. Strongest competencies
    assessed = [cs for cs in competency_scores if cs.evidence_count > 0]
    if assessed:
        sorted_by_score = sorted(assessed, key=lambda x: x.score, reverse=True)
        strongest = sorted_by_score[:3]
        lines = [f"  - {_display_competency_name(cs)}: {cs.score:.1f}/10 ({cs.proficiency.value})" for cs in strongest]
        sections.append("STRONGEST COMPETENCIES:\n" + "\n".join(lines))

    # 2. Weakest competencies
    if assessed:
        weakest = sorted(assessed, key=lambda x: x.score)[:3]
        lines = [f"  - {_display_competency_name(cs)}: {cs.score:.1f}/10 ({cs.proficiency.value})" for cs in weakest]
        sections.append("AREAS NEEDING IMPROVEMENT:\n" + "\n".join(lines))

    # 3. Missing concepts
    all_missing = []
    for ev in evaluation_history:
        for mc in ev.missing_concepts:
            if mc not in all_missing:
                all_missing.append(mc)
    if all_missing:
        lines = [f"  - {mc}" for mc in all_missing[:8]]
        sections.append("IMPORTANT MISSING CONCEPTS:\n" + "\n".join(lines))

    # 4. Misconceptions detected
    all_misconceptions = []
    for ev in evaluation_history:
        for m in ev.misconceptions:
            if m not in all_misconceptions:
                all_misconceptions.append(m)
    if all_misconceptions:
        lines = [f"  - {m}" for m in all_misconceptions[:5]]
        sections.append("MISCONCEPTIONS DETECTED:\n" + "\n".join(lines))

    # 5. Adaptation decisions summary
    if decision_history:
        action_counts: dict[str, int] = {}
        for d in decision_history:
            action_counts[d.action.value] = action_counts.get(d.action.value, 0) + 1
        lines = [f"  - {action.replace('_', ' ').title()}: {count} time(s)" for action, count in action_counts.items()]
        sections.append("INTERVIEW ADAPTATION DECISIONS:\n" + "\n".join(lines))

    # 6. Study recommendations
    study_recs = []
    for cs in assessed:
        name = _display_competency_name(cs)
        if cs.score < 4.0:
            study_recs.append(f"  - Deep-dive into {name} fundamentals")
        elif cs.score < 6.0:
            study_recs.append(f"  - Practice more scenarios for {name}")
    if all_missing:
        for mc in all_missing[:3]:
            study_recs.append(f"  - Study: {mc}")
    if study_recs:
        sections.append("RECOMMENDED STUDY AREAS:\n" + "\n".join(study_recs[:8]))

    return "\n\n".join(sections) if sections else "Insufficient data for detailed feedback."
