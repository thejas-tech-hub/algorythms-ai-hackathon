"""
Interview session orchestration.
Owner: THEJAS

Manages the full interview session lifecycle: create -> ask -> respond -> end.
Adaptive intelligence (competency tracking, session memory, final reporting)
is delegated to SessionIntelligence modules in session_intelligence.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime
import re

from app.core.exceptions import SessionExpiredError, SessionNotFoundError
from app.core.logging import get_logger
from app.data.repositories import CurriculumRepository
from app.data.session_store import SessionStore
from app.models.adaptive import (
    AdaptiveAction,
    AdaptiveDecision,
    AnswerEvaluation,
    CandidateIntelligenceProfile,
    CompetencyState,
    EvidenceStrength,
    QuestionPlan,
    QuestionType,
    RubricEvidence,
)
from app.models.common import DifficultyLevel, InterviewStatus
from app.models.interview import (
    CandidateAnswer,
    InterviewMessage,
    InterviewSession,
    InterviewSessionCreate,
    InterviewSummary,
)
from app.services.candidate_service import CandidateService
from app.services.curriculum_retrieval import LocalCurriculumRetriever
from app.services.session_intelligence import (
    AdaptiveReasoningEnhancer,
    CompetencyTracker,
    FinalReportGenerator,
    SessionMemoryManager,
)

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Stopwords that should not alone satisfy a criterion match
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do",
    "for", "from", "get", "has", "have", "how", "if", "in", "is",
    "it", "its", "let", "my", "not", "of", "on", "or", "our", "own",
    "set", "so", "the", "this", "to", "up", "use", "was", "we",
    "what", "when", "who", "why", "will", "with", "you", "your",
    "one", "two", "new", "all", "any", "may", "but", "run", "day",
    "also", "that", "than", "then", "them", "they", "each", "make",
    "like", "more", "some", "most", "give", "just", "over", "take",
    "would", "should", "could", "about", "using", "through",
    "explain", "describe", "discuss", "understand", "behind",
    "main", "concept", "idea", "core", "first", "based",
})

# Generic words that appear in every topic — should not alone satisfy criteria
_GENERIC_TOPIC_WORDS = frozenset({
    "python", "code", "model", "system", "project", "data",
    "file", "build", "create", "setup", "tool", "test",
    "application", "app", "work", "function", "class",
    "import", "module", "package", "install", "environment",
})


def _tokenize(text: str) -> set[str]:
    """Basic tokenizer: all lowercase tokens > 2 chars."""
    return {token for token in _TOKEN_RE.findall(text.casefold()) if len(token) > 2}


def _tokenize_content(text: str) -> set[str]:
    """Content-aware tokenizer: removes stopwords for meaningful matching."""
    return {
        token for token in _TOKEN_RE.findall(text.casefold())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _topic_name_tokens(topic_name: str) -> set[str]:
    """Extract tokens from the topic name itself (to avoid trivial matches)."""
    return _tokenize_content(topic_name) & _GENERIC_TOPIC_WORDS


class InterviewService:
    """
    Manages the full interview session lifecycle.

    Dependencies are injected via constructor so this service
    can be tested with mocks.
    """

    def __init__(
        self,
        session_store: SessionStore,
        candidate_service: CandidateService,
    ) -> None:
        self._sessions = session_store
        self._candidates = candidate_service

    # ── Persistence helpers ──────────────────────────────────────────
    # SessionStore is a generic dict store; we serialise/deserialise
    # InterviewSession through Pydantic so the data layer stays generic.

    def _save_session(self, session: InterviewSession) -> None:
        self._sessions.set(session.session_id, session.model_dump(mode="json"))

    def _load_session(self, session_id: str) -> InterviewSession | None:
        data = self._sessions.get(session_id)
        if data is None:
            return None
        return InterviewSession.model_validate(data)

    def _build_candidate_intelligence(
        self,
        candidate,
        selected_topic_id: str,
        suggested_difficulty: DifficultyLevel,
    ) -> CandidateIntelligenceProfile:
        completed_topics = [topic_id for topic_id in candidate.completed_topics if topic_id]
        curriculum_topics = CurriculumRepository().list_all()
        completion_rate = 0.0
        if curriculum_topics:
            completion_rate = min(1.0, len(completed_topics) / len(curriculum_topics))

        return CandidateIntelligenceProfile(
            candidate_id=candidate.candidate_id,
            strengths=list(completed_topics[:3]),
            weaknesses=list(candidate.weak_topics[:3]),
            skipped_areas=list(candidate.skipped_topics[:3]),
            completion_rate=round(completion_rate, 3),
            suggested_start_difficulty=suggested_difficulty,
            suggested_focus_areas=list(completed_topics[:3]) or [selected_topic_id],
            raw_signals={
                "completed_topics": completed_topics,
                "topic_progress": [topic.topic_id for topic in getattr(candidate, "topic_progress", [])],
            },
        )

    @staticmethod
    def _topic_name(topic) -> str:
        return topic.title or topic.topic_id

    @staticmethod
    def _difficulty_step(current: DifficultyLevel, direction: int) -> DifficultyLevel:
        ordered = [
            DifficultyLevel.FOUNDATIONAL,
            DifficultyLevel.INTERMEDIATE,
            DifficultyLevel.ADVANCED,
            DifficultyLevel.EXPERT,
        ]
        index = ordered.index(current) + direction
        index = max(0, min(len(ordered) - 1, index))
        return ordered[index]

    def _evaluate_answer(
        self,
        answer_text: str,
        question_plan: QuestionPlan,
        topic_name: str,
    ) -> AnswerEvaluation:
        normalized_answer = answer_text.strip()
        lowered = normalized_answer.casefold()
        answer_tokens = _tokenize(normalized_answer)
        answer_content_tokens = _tokenize_content(normalized_answer)
        plan_tokens = _tokenize(
            " ".join(
                [
                    question_plan.objective,
                    question_plan.topic_context,
                    topic_name,
                    " ".join(question_plan.expected_criteria),
                ]
            )
        )

        # Tokens from the topic name itself — these alone should not satisfy criteria
        trivial_topic_tokens = _topic_name_tokens(topic_name)

        criterion_hits: list[str] = []
        missing_concepts: list[str] = []
        strengths: list[str] = []
        weaknesses: list[str] = []
        misconceptions: list[str] = []
        evidence: list[RubricEvidence] = []

        practical_markers = ("example", "for instance", "in practice", "trade-off", "tradeoff", "use case")
        reasoning_markers = ("because", "therefore", "so that", "if", "when", "compared", "trade-off", "tradeoff")
        uncertainty_markers = ("maybe", "might", "not sure", "i think", "probably", "guess")

        for criterion in question_plan.expected_criteria:
            criterion_content_tokens = _tokenize_content(criterion)
            # Remove trivial topic-name tokens so they don't cause false positives
            meaningful_criterion_tokens = criterion_content_tokens - trivial_topic_tokens
            if not meaningful_criterion_tokens:
                # Criterion is entirely topic-name words; use full tokens as fallback
                meaningful_criterion_tokens = criterion_content_tokens

            # Calculate meaningful overlap (excluding stopwords and trivial topic words)
            meaningful_overlap = meaningful_criterion_tokens & answer_content_tokens
            total_meaningful = len(meaningful_criterion_tokens)

            # Require >= 2 meaningful overlapping tokens, OR >= 50% coverage
            coverage_ratio = len(meaningful_overlap) / max(1, total_meaningful)
            is_demonstrated = (
                len(meaningful_overlap) >= 2
                or (total_meaningful <= 2 and len(meaningful_overlap) >= 1 and coverage_ratio >= 0.5)
            )

            if is_demonstrated:
                strength = EvidenceStrength.STRONG if coverage_ratio >= 0.6 else EvidenceStrength.MODERATE
                criterion_hits.append(criterion)
                evidence.append(
                    RubricEvidence(
                        competency_id=question_plan.competency_id,
                        criterion=criterion,
                        demonstrated=True,
                        strength=strength,
                        notes=f"Matched {len(meaningful_overlap)} content tokens: {sorted(meaningful_overlap)[:4]} (coverage: {coverage_ratio:.0%})",
                    )
                )
            else:
                missing_concepts.append(criterion)
                evidence.append(
                    RubricEvidence(
                        competency_id=question_plan.competency_id,
                        criterion=criterion,
                        demonstrated=False,
                        strength=EvidenceStrength.WEAK,
                        notes=f"Insufficient overlap: {len(meaningful_overlap)} of {total_meaningful} content tokens",
                    )
                )

        concept_overlap = len(answer_tokens & plan_tokens)
        concept_coverage = 0.0
        if plan_tokens:
            concept_coverage = min(1.0, concept_overlap / max(1, len(plan_tokens)))

        word_count = len(answer_tokens)
        length_score = min(100.0, word_count * 2.5)
        coverage_score = min(100.0, concept_coverage * 100.0)
        reasoning_score = min(
            100.0,
            (20.0 if any(marker in lowered for marker in reasoning_markers) else 0.0)
            + (25.0 if any(marker in lowered for marker in practical_markers) else 0.0)
            + min(55.0, len([token for token in ("because", "therefore", "trade-off", "tradeoff", "compared", "however") if token in lowered]) * 18.0),
        )
        practical_score = min(
            100.0,
            (35.0 if any(marker in lowered for marker in practical_markers) else 0.0)
            + (35.0 if any(token in lowered for token in ("implementation", "system", "workflow", "latency", "quality", "retrieval", "architecture")) else 0.0)
            + min(30.0, word_count),
        )

        if any(marker in lowered for marker in uncertainty_markers) and word_count < 12:
            weaknesses.append("The answer sounds uncertain or underdeveloped")
        if any(marker in lowered for marker in ("always", "never", "guaranteed")) and not any(
            marker in lowered for marker in ("usually", "depends", "trade-off", "tradeoff")
        ):
            misconceptions.append("Overly absolute language without acknowledging trade-offs")
        if word_count < 8:
            weaknesses.append("Answer is very short and lacks enough detail")
        elif word_count >= 18:
            strengths.append("Provided enough detail to support a deeper follow-up")
        if concept_coverage >= 0.35:
            strengths.append("Referenced the question context and expected criteria")
        else:
            weaknesses.append("Did not address enough of the expected criteria")
        if reasoning_score >= 50.0:
            strengths.append("Included explicit reasoning or trade-off discussion")
        else:
            missing_concepts.append("Reasoning or trade-off discussion")
        if practical_score >= 50.0:
            strengths.append("Connected the topic to practice or implementation")
        else:
            missing_concepts.append("Practical application or implementation detail")

        confidence_score = min(
            100.0,
            40.0
            + (15.0 if criterion_hits else 0.0)
            + (20.0 if word_count >= 18 else 0.0)
            + (15.0 if not misconceptions else -10.0)
            + (10.0 if concept_overlap else 0.0),
        )
        evidence_score = min(100.0, len([item for item in evidence if item.demonstrated]) * 20.0 + concept_coverage * 40.0)
        overall_score = round(
            min(
                100.0,
                (coverage_score * 0.35)
                + (reasoning_score * 0.25)
                + (practical_score * 0.2)
                + (length_score * 0.1)
                + (confidence_score * 0.1),
            ),
            2,
        )

        normalized_score = round(overall_score / 10.0, 2)
        rationale_parts = [
            f"Matched {len(criterion_hits)} of {len(question_plan.expected_criteria)} expected criteria",
            f"Answer length: {word_count} tokens",
        ]
        if strengths:
            rationale_parts.append(f"Strengths: {', '.join(strengths[:3])}")
        if weaknesses:
            rationale_parts.append(f"Weaknesses: {', '.join(weaknesses[:3])}")

        # Improved follow_up_needed: not triggered by generic criteria misses
        # Only significant when there are real misconceptions, multiple
        # meaningful missing concepts, or genuinely weak performance
        significant_missing = [
            mc for mc in missing_concepts
            if mc not in ("Reasoning or trade-off discussion", "Practical application or implementation detail")
            and not mc.startswith("Explain the core idea")
        ]
        follow_up_needed = (
            overall_score < 50.0
            or bool(misconceptions)
            or len(significant_missing) >= 2
            or (bool(weaknesses) and overall_score < 60.0)
        )

        return AnswerEvaluation(
            evaluation_id=f"eval-{uuid.uuid4().hex[:8]}",
            plan_id=question_plan.plan_id,
            competency_id=question_plan.competency_id,
            question_text=question_plan.generated_question_text or question_plan.objective,
            score=normalized_score,
            overall_score=overall_score,
            conceptual_correctness_score=coverage_score,
            depth_reasoning_score=reasoning_score,
            practical_understanding_score=practical_score,
            confidence_score=confidence_score,
            evidence_score=evidence_score,
            max_score=10.0,
            evidence=evidence,
            feedback=(
                "Strong conceptual alignment with clear reasoning and practical detail."
                if overall_score >= 70.0
                else "Some relevant signals were present, but the answer needs more completeness and detail."
            ),
            strengths=strengths,
            weaknesses=weaknesses,
            missing_concepts=missing_concepts,
            misconceptions=misconceptions,
            rationale="; ".join(rationale_parts),
            follow_up_needed=follow_up_needed,
        )

    def _next_difficulty(self, current: DifficultyLevel, evaluation: AnswerEvaluation) -> DifficultyLevel:
        if evaluation.score >= 7.5:
            return self._difficulty_step(current, 1)
        if evaluation.score <= 4.0:
            return self._difficulty_step(current, -1)
        return current

    def _topic_from_retrieval_result(
        self,
        curriculum_topics: list,
        result,
    ):
        for topic in curriculum_topics:
            if topic.day == result.day and self._topic_name(topic) == result.title:
                return topic
        for topic in curriculum_topics:
            if topic.day == result.day:
                return topic
        for topic in curriculum_topics:
            if self._topic_name(topic).casefold() == result.title.casefold():
                return topic
        return None

    def _select_next_topic(
        self,
        candidate,
        session: InterviewSession,
        evaluation: AnswerEvaluation,
        current_plan: QuestionPlan,
        curriculum_repo: CurriculumRepository,
        retriever: LocalCurriculumRetriever,
    ):
        curriculum_topics = curriculum_repo.list_all()
        if not curriculum_topics:
            raise ValueError("No curriculum topics available")

        current_topic = curriculum_repo.get_by_id(current_plan.competency_id)
        current_day = current_topic.day if current_topic is not None else None
        asked_topic_ids = set(session.metadata.get("asked_topic_ids", []))
        asked_topic_ids.add(current_plan.competency_id)

        skipped_topics = {topic_id for topic_id in candidate.skipped_topics if topic_id}
        completed_topics = [topic_id for topic_id in candidate.completed_topics if topic_id]
        weak_topics = [topic_id for topic_id in candidate.weak_topics if topic_id]

        def to_topic(topic_id: str):
            topic = curriculum_repo.get_by_id(topic_id)
            if topic is None:
                return None
            if topic.topic_id in asked_topic_ids or topic.topic_id in skipped_topics:
                return None
            return topic

        ranked_topics: list = []
        seen: set[str] = set()

        def add_topic(topic) -> None:
            if topic is None:
                return
            if topic.topic_id in seen:
                return
            if topic.topic_id in asked_topic_ids:
                return
            seen.add(topic.topic_id)
            ranked_topics.append(topic)

        if evaluation.score <= 4.0:
            for topic_id in weak_topics:
                add_topic(to_topic(topic_id))
        elif evaluation.score >= 7.5:
            for topic_id in completed_topics:
                add_topic(to_topic(topic_id))

        query_seed = " ".join(
            part for part in [current_plan.topic_context, current_plan.objective, evaluation.feedback] if part
        )
        if query_seed.strip():
            for result in retriever.search(query_seed, limit=8):
                add_topic(self._topic_from_retrieval_result(curriculum_topics, result))

        ordered_topics = sorted(curriculum_topics, key=lambda topic: (topic.day or 0, topic.topic_id))
        if current_day is not None:
            start_index = next(
                (index for index, topic in enumerate(ordered_topics) if topic.topic_id == current_plan.competency_id),
                0,
            )
            for offset in range(1, len(ordered_topics) + 1):
                add_topic(ordered_topics[(start_index + offset) % len(ordered_topics)])
        else:
            for topic in ordered_topics:
                add_topic(topic)

        if not ranked_topics:
            ranked_topics = [topic for topic in ordered_topics if topic.topic_id != current_plan.competency_id] or ordered_topics

        preferred_topic_ids = set()
        if evaluation.score <= 4.0:
            preferred_topic_ids.update(weak_topics)
        elif evaluation.score >= 7.5:
            preferred_topic_ids.update(completed_topics)

        def rank_topic(topic) -> tuple[int, int, int]:
            score = 0
            if topic.topic_id in preferred_topic_ids:
                score += 100
            if topic.topic_id in completed_topics and evaluation.score >= 7.5:
                score += 20
            if topic.topic_id in weak_topics and evaluation.score <= 4.0:
                score += 20
            if topic.topic_id in skipped_topics:
                score -= 25
            if current_day is not None and topic.day is not None:
                if evaluation.score >= 7.5:
                    score += max(0, topic.day - current_day)
                elif evaluation.score <= 4.0:
                    score += max(0, current_day - topic.day)
                else:
                    score -= abs(topic.day - current_day)
            return (score, topic.day or 0, -ordered_topics.index(topic))

        ranked_topics.sort(key=rank_topic, reverse=True)
        return ranked_topics[0]

    def _select_adaptive_action(
        self,
        evaluation: AnswerEvaluation,
        current_plan: QuestionPlan,
        next_difficulty: DifficultyLevel,
        competency_states: dict[str, CompetencyState],
        questions_asked: int,
    ) -> AdaptiveAction:
        """Select the adaptive action BEFORE choosing the next topic.

        Uses multiple signals:
        - evaluation.score (0–10)
        - evaluation.follow_up_needed
        - evaluation.misconceptions
        - evaluation.weaknesses
        - evaluation.missing_concepts
        - competency-level evidence (questions asked, proficiency)
        - difficulty change direction

        The action drives topic selection, not the reverse.
        """
        score = evaluation.score  # 0–10 scale
        overall = evaluation.overall_score or (score * 10)  # 0–100 scale
        has_follow_up = evaluation.follow_up_needed
        has_misconceptions = bool(evaluation.misconceptions)
        has_weaknesses = bool(evaluation.weaknesses)
        has_missing = bool(evaluation.missing_concepts)

        comp_state = competency_states.get(current_plan.competency_id)
        comp_questions = comp_state.questions_asked if comp_state else 1

        difficulty_order = [
            DifficultyLevel.FOUNDATIONAL,
            DifficultyLevel.INTERMEDIATE,
            DifficultyLevel.ADVANCED,
            DifficultyLevel.EXPERT,
        ]
        diff_increased = difficulty_order.index(next_difficulty) > difficulty_order.index(current_plan.target_difficulty)
        diff_decreased = difficulty_order.index(next_difficulty) < difficulty_order.index(current_plan.target_difficulty)

        # ── Strong performance (score ≥ 7.5) ───────────────────────
        if score >= 7.5:
            if diff_increased:
                return AdaptiveAction.INCREASE_DIFFICULTY
            # Strong answer + already at max difficulty or enough evidence
            if comp_questions >= 2:
                return AdaptiveAction.SWITCH_TOPIC
            return AdaptiveAction.INCREASE_DIFFICULTY

        # ── Weak performance with misconceptions (score ≤ 4.0) ──────
        if score <= 4.0:
            if has_misconceptions:
                # Stay on same topic to address misconception
                return AdaptiveAction.CONTINUE_SAME_TOPIC
            if diff_decreased:
                return AdaptiveAction.DECREASE_DIFFICULTY
            # Weak but no misconceptions — deep dive to understand gap
            if has_follow_up or has_missing:
                return AdaptiveAction.DEEP_DIVE
            return AdaptiveAction.DECREASE_DIFFICULTY

        # ── Moderate-weak performance (4.0 < score < 5.5) ───────────
        if score < 5.5:
            if has_misconceptions:
                return AdaptiveAction.CONTINUE_SAME_TOPIC
            if has_follow_up and (has_weaknesses or has_missing):
                return AdaptiveAction.DEEP_DIVE
            if comp_questions >= 2:
                return AdaptiveAction.SWITCH_TOPIC
            return AdaptiveAction.CONTINUE_SAME_TOPIC

        # ── Moderate performance (5.5 ≤ score < 7.0) ───────────────
        if score < 7.0:
            if has_follow_up and has_missing:
                return AdaptiveAction.DEEP_DIVE
            if comp_questions >= 2:
                # Adequate evidence for this competency — broaden
                return AdaptiveAction.SWITCH_TOPIC
            if has_weaknesses:
                return AdaptiveAction.CONTINUE_SAME_TOPIC
            return AdaptiveAction.SWITCH_TOPIC

        # ── Good performance (7.0 ≤ score < 7.5) ───────────────────
        if diff_increased:
            return AdaptiveAction.INCREASE_DIFFICULTY
        if comp_questions >= 2:
            return AdaptiveAction.SWITCH_TOPIC
        return AdaptiveAction.CONTINUE_SAME_TOPIC

    def _extract_gap_context(
        self,
        evaluation: AnswerEvaluation,
        action: AdaptiveAction,
        competency_state: CompetencyState | None,
    ) -> dict:
        """Derive a structured gap_context from the evaluation evidence.

        Prioritises: misconceptions > missing_concepts > weaknesses > rotation.
        All data comes from real evaluation output — nothing fabricated.
        """
        missing = list(evaluation.missing_concepts)
        misconceptions = list(evaluation.misconceptions)
        weaknesses = list(evaluation.weaknesses)
        strengths = list(evaluation.strengths)

        # What the candidate DID demonstrate (from criterion hits)
        previously_demonstrated = [
            ev.criterion for ev in evaluation.evidence
            if ev.demonstrated
        ]

        # ── Determine the single most important target gap ──
        target_gap: str | None = None
        question_intent: str | None = None

        if misconceptions:
            target_gap = misconceptions[0]
            question_intent = "challenge misconception"
        elif action == AdaptiveAction.DEEP_DIVE:
            # Deep dive: target the most specific missing concept
            specific_missing = [
                mc for mc in missing
                if not mc.startswith("Explain the core idea")
                and mc not in ("Reasoning or trade-off discussion", "Practical application or implementation detail")
            ]
            if specific_missing:
                target_gap = specific_missing[0]
                question_intent = "probe specific gap"
            elif "Practical application or implementation detail" in missing:
                target_gap = "practical application"
                question_intent = "probe practical depth"
            elif "Reasoning or trade-off discussion" in missing:
                target_gap = "reasoning and trade-offs"
                question_intent = "probe reasoning depth"
            elif weaknesses:
                target_gap = weaknesses[0]
                question_intent = "address weakness"
        elif action == AdaptiveAction.CONTINUE_SAME_TOPIC:
            if weaknesses:
                target_gap = weaknesses[0]
                question_intent = "address weakness"
            elif missing:
                specific_missing = [
                    mc for mc in missing
                    if not mc.startswith("Explain the core idea")
                ]
                if specific_missing:
                    target_gap = specific_missing[0]
                    question_intent = "assess missing concept"
        elif action == AdaptiveAction.INCREASE_DIFFICULTY:
            question_intent = "increase depth and complexity"
        elif action == AdaptiveAction.DECREASE_DIFFICULTY:
            question_intent = "verify foundational understanding"
            if weaknesses:
                target_gap = weaknesses[0]
        elif action == AdaptiveAction.SWITCH_TOPIC:
            question_intent = "assess new competency"

        # Build evidence basis from real data
        evidence_basis: list[str] = []
        if previously_demonstrated:
            evidence_basis.append(f"candidate demonstrated: {', '.join(previously_demonstrated[:2])}")
        if target_gap:
            evidence_basis.append(f"gap identified: {target_gap}")
        if misconceptions:
            evidence_basis.append(f"misconception: {misconceptions[0]}")
        if not evidence_basis and weaknesses:
            evidence_basis.append(f"weakness: {weaknesses[0]}")

        return {
            "missing_concepts": missing,
            "misconceptions": misconceptions,
            "weaknesses": weaknesses,
            "strengths": strengths,
            "previously_demonstrated": previously_demonstrated,
            "target_gap": target_gap,
            "question_intent": question_intent,
            "evidence_basis": evidence_basis,
        }

    @staticmethod
    def _get_assessed_objectives(
        competency_id: str,
        session_metadata: dict,
    ) -> list[str]:
        """Collect objectives/criteria already used for this competency from plan history."""
        assessed: list[str] = []
        seen: set[str] = set()
        for plan_data in session_metadata.get("plan_history", []):
            if not isinstance(plan_data, dict):
                continue
            if plan_data.get("competency_id") != competency_id:
                continue
            for criterion in plan_data.get("expected_criteria", []):
                if criterion not in seen:
                    seen.add(criterion)
                    assessed.append(criterion)
        return assessed

    @staticmethod
    def _select_rotated_criteria(
        all_objectives: list[str],
        assessed_objectives: list[str],
        topic_name: str,
        gap_context: dict,
    ) -> list[str]:
        """Select the next unassessed objectives for criteria, rotating through all available.

        If gap_context has a specific target, include that. Otherwise rotate
        to objectives not yet assessed.
        """
        assessed_set = set(assessed_objectives)

        # Filter out objectives that have already been used as criteria
        remaining = [obj for obj in all_objectives if obj not in assessed_set]

        criteria: list[str] = []

        # If we have a specific gap target from the evaluation, use it as a criterion
        target_gap = gap_context.get("target_gap")
        if target_gap and not target_gap.startswith("Explain"):
            # Only add if it's a real specific gap, not a generic label
            if target_gap not in ("practical application", "reasoning and trade-offs"):
                criteria.append(target_gap)

        # Add the next unassessed objectives
        for obj in remaining:
            if len(criteria) >= 3:
                break
            if obj not in criteria:
                criteria.append(obj)

        # If all objectives were assessed, cycle back but use different ones
        # than the most recent assessment
        if len(criteria) < 2:
            recent_criteria = set(assessed_objectives[-3:]) if assessed_objectives else set()
            for obj in all_objectives:
                if len(criteria) >= 3:
                    break
                if obj not in criteria and obj not in recent_criteria:
                    criteria.append(obj)

        # Final fallback: just use whatever is available
        if not criteria:
            criteria = list(all_objectives[:2]) if all_objectives else [f"Explain a key aspect of {topic_name}"]

        return criteria

    def _build_question_plan(
        self,
        candidate,
        session: InterviewSession,
        evaluation: AnswerEvaluation,
        current_plan: QuestionPlan,
        curriculum_repo: CurriculumRepository,
        retriever: LocalCurriculumRetriever,
        next_difficulty: DifficultyLevel,
        competency_states: dict[str, CompetencyState],
    ) -> tuple[str, str, DifficultyLevel, QuestionPlan, AdaptiveDecision]:
        # ── Step 1: Select adaptive action FIRST (evidence-driven) ──
        action = self._select_adaptive_action(
            evaluation=evaluation,
            current_plan=current_plan,
            next_difficulty=next_difficulty,
            competency_states=competency_states,
            questions_asked=session.questions_asked,
        )

        # ── Step 2: Extract gap context from evaluation evidence ─────
        comp_state = competency_states.get(current_plan.competency_id)
        gap_context = self._extract_gap_context(evaluation, action, comp_state)

        # ── Step 3: Select topic based on action ─────────────────────
        stay_on_topic = action in (
            AdaptiveAction.CONTINUE_SAME_TOPIC,
            AdaptiveAction.DEEP_DIVE,
        )

        if stay_on_topic:
            current_topic_obj = curriculum_repo.get_by_id(current_plan.competency_id)
            if current_topic_obj is not None:
                next_topic = current_topic_obj
            else:
                next_topic = self._select_next_topic(
                    candidate, session, evaluation, current_plan,
                    curriculum_repo, retriever,
                )
        else:
            next_topic = self._select_next_topic(
                candidate, session, evaluation, current_plan,
                curriculum_repo, retriever,
            )

        topic_name = self._topic_name(next_topic)

        question_type = QuestionType.CONCEPTUAL
        if next_topic.type and "coding" in next_topic.type.lower():
            question_type = QuestionType.CODING
        elif next_topic.tools and any(tool.lower() in {"docker", "kubernetes"} for tool in next_topic.tools):
            question_type = QuestionType.SYSTEM_DESIGN

        retrieval_results = retriever.search(topic_name, limit=1)
        topic_context = retrieval_results[0].title if retrieval_results else topic_name
        # RC-3 fix: Always use the actual selected topic's objectives, not
        # the retrieval result's objectives.  The retriever may return a
        # different topic whose objectives are unrelated to the question.
        all_objectives = list(next_topic.objectives) if next_topic.objectives else (
            retrieval_results[0].objectives if retrieval_results else []
        )

        # ── Step 4: Objective rotation — select unassessed objectives ─
        assessed_objectives = self._get_assessed_objectives(
            competency_id=next_topic.topic_id,
            session_metadata=session.metadata,
        )

        expected_criteria = self._select_rotated_criteria(
            all_objectives=all_objectives,
            assessed_objectives=assessed_objectives,
            topic_name=topic_name,
            gap_context=gap_context,
        )

        # ── Step 5: Build targeted objective ─────────────────────────
        target_gap = gap_context.get("target_gap")
        question_intent = gap_context.get("question_intent")
        evidence_basis = gap_context.get("evidence_basis", [])

        if target_gap and action in (AdaptiveAction.DEEP_DIVE, AdaptiveAction.CONTINUE_SAME_TOPIC):
            objective = f"Probe the candidate's understanding of {target_gap} within {topic_name}"
        elif action == AdaptiveAction.INCREASE_DIFFICULTY:
            objective = f"Assess the candidate's deeper understanding and application of {topic_name}"
        elif action == AdaptiveAction.SWITCH_TOPIC:
            objective = f"Assess the candidate's understanding of {topic_name}"
        else:
            objective = f"Assess the candidate's understanding of {topic_name} after their last answer"

        # Build selection reasoning with evidence
        action_desc = {
            AdaptiveAction.CONTINUE_SAME_TOPIC: f"Continuing on {topic_name} to deepen assessment",
            AdaptiveAction.INCREASE_DIFFICULTY: f"Increasing difficulty for {topic_name} after strong performance",
            AdaptiveAction.DECREASE_DIFFICULTY: f"Decreasing difficulty for {topic_name} to build confidence",
            AdaptiveAction.SWITCH_TOPIC: f"Switching to {topic_name} to broaden competency coverage",
            AdaptiveAction.DEEP_DIVE: f"Probing deeper into {topic_name} to clarify gaps",
            AdaptiveAction.CONCLUDE_INTERVIEW: f"Concluding interview with sufficient evidence",
        }
        reasoning_parts = [
            f"{action_desc.get(action, 'Selected ' + topic_name)}",
            f"Previous answer scored {evaluation.score:.1f}/10",
        ]
        if target_gap:
            reasoning_parts.append(f"Targeting: {target_gap}")
        if question_intent:
            reasoning_parts.append(f"Intent: {question_intent}")
        selection_reasoning = ". ".join(reasoning_parts) + "."

        plan = QuestionPlan(
            plan_id=f"qp-{uuid.uuid4().hex[:8]}",
            competency_id=next_topic.topic_id,
            target_difficulty=next_difficulty,
            question_type=question_type,
            topic_context=topic_context,
            follow_up_to=current_plan.plan_id,
            objective=objective,
            expected_criteria=expected_criteria,
            selection_reasoning=selection_reasoning,
            target_gap=target_gap,
            question_intent=question_intent,
            evidence_basis=evidence_basis,
            assessed_objectives=assessed_objectives,
        )

        # ── Step 6: Generate targeted question text ──────────────────
        previously_asked = session.metadata.get("asked_question_texts", [])

        question_text = self._build_question_text(
            topic_name=topic_name,
            difficulty=next_difficulty,
            question_type=question_type,
            action=action,
            gap_context=gap_context,
            previous_question=session.current_question,
            previously_asked=previously_asked,
            target_criteria=expected_criteria,
        )
        plan.generated_question_text = question_text

        decision = AdaptiveDecision(
            decision_id=f"dec-{uuid.uuid4().hex[:8]}",
            evaluation_id=evaluation.evaluation_id,
            action=action,
            next_competency_id=next_topic.topic_id,
            next_difficulty=next_difficulty,
            reasoning=selection_reasoning,
        )

        return question_text, topic_name, next_difficulty, plan, decision

    def _build_question_text(
        self,
        topic_name: str,
        difficulty: DifficultyLevel,
        question_type: QuestionType,
        action: AdaptiveAction,
        gap_context: dict,
        previous_question: str | None,
        previously_asked: list[str] | None = None,
        target_criteria: list[str] | None = None,
    ) -> str:
        """Generate question text driven by adaptive action and gap evidence.

        Uses deterministic templates that reference actual evaluation gaps.
        """
        target_gap = gap_context.get("target_gap")
        misconceptions = gap_context.get("misconceptions", [])
        weaknesses = gap_context.get("weaknesses", [])
        strengths = gap_context.get("strengths", [])
        previously_demonstrated = gap_context.get("previously_demonstrated", [])
        missing = gap_context.get("missing_concepts", [])

        # Short label for what was demonstrated
        demonstrated_summary = previously_demonstrated[0] if previously_demonstrated else None

        # ── Question type overrides (coding / system design) ─────────
        if question_type == QuestionType.CODING:
            if target_gap:
                question = (
                    f"For {topic_name}, write or describe an implementation that specifically addresses {target_gap}. "
                    f"Explain the key trade-offs in your approach."
                )
            else:
                question = (
                    f"For {topic_name} at {difficulty.value} difficulty, how would you implement this in practice "
                    f"and explain the key trade-offs?"
                )
        elif question_type == QuestionType.SYSTEM_DESIGN:
            if target_gap:
                question = (
                    f"For {topic_name}, design an approach that addresses {target_gap}. "
                    f"Outline the architecture choices, failure modes, and trade-offs."
                )
            else:
                question = (
                    f"For {topic_name} at {difficulty.value} difficulty, outline the architecture choices, "
                    f"failure modes, and trade-offs you would consider."
                )

        # ── DEEP_DIVE: target specific gaps ──────────────────────────
        elif action == AdaptiveAction.DEEP_DIVE:
            if target_gap and demonstrated_summary:
                question = (
                    f"You explained {demonstrated_summary}. Now let's go deeper into {target_gap}. "
                    f"How would you apply it in a real project, and what trade-off would you consider?"
                )
            elif target_gap:
                question = (
                    f"Let's dig deeper into {target_gap} within {topic_name}. "
                    f"Walk me through how this works in practice and what challenges you might encounter."
                )
            else:
                # Fallback for deep dive without a specific gap
                if target_criteria:
                    question = (
                        f"For {topic_name}, let's explore further: {target_criteria[0]}. "
                        f"Explain with a concrete example."
                    )
                else:
                    question = (
                        f"For {topic_name} at {difficulty.value} difficulty, walk me through the core concept "
                        f"more carefully and correct the gap from your last answer."
                    )

        # ── CONTINUE_SAME_TOPIC with misconception ───────────────────
        elif action == AdaptiveAction.CONTINUE_SAME_TOPIC and misconceptions:
            question = (
                f"You mentioned that {misconceptions[0].lower()}. Let's examine that assumption. "
                f"When would it not hold, and what would be the correct approach for {topic_name}?"
            )

        # ── CONTINUE_SAME_TOPIC with weakness ────────────────────────
        elif action == AdaptiveAction.CONTINUE_SAME_TOPIC and target_gap:
            question = (
                f"Let's revisit {topic_name}. Your previous answer was weaker on {target_gap}. "
                f"Walk me through that part using a concrete example."
            )

        # ── CONTINUE_SAME_TOPIC (general — rotate objective) ─────────
        elif action == AdaptiveAction.CONTINUE_SAME_TOPIC:
            if target_criteria:
                question = (
                    f"Still on {topic_name}: {target_criteria[0]}. "
                    f"Explain this in your own words and give one concrete example."
                )
            else:
                question = (
                    f"For {topic_name} at {difficulty.value} difficulty, explain the main idea "
                    f"in your own words and give one concrete example."
                )

        # ── INCREASE_DIFFICULTY ──────────────────────────────────────
        elif action == AdaptiveAction.INCREASE_DIFFICULTY:
            if demonstrated_summary:
                question = (
                    f"Good understanding of {demonstrated_summary}. Now for {topic_name} at "
                    f"{difficulty.value} difficulty, go one level deeper and explain how you "
                    f"would apply this in a realistic scenario with real constraints."
                )
            elif target_criteria:
                question = (
                    f"For {topic_name} at {difficulty.value} difficulty: {target_criteria[0]}. "
                    f"Include trade-offs and edge cases in your answer."
                )
            else:
                question = (
                    f"For {topic_name} at {difficulty.value} difficulty, go one level deeper "
                    f"and explain how you would apply this in a realistic scenario."
                )

        # ── DECREASE_DIFFICULTY ──────────────────────────────────────
        elif action == AdaptiveAction.DECREASE_DIFFICULTY:
            if target_gap:
                question = (
                    f"Let's take a step back on {topic_name}. Can you explain the basics of "
                    f"{target_gap} in simple terms?"
                )
            elif target_criteria:
                question = (
                    f"Let's simplify. For {topic_name}: {target_criteria[0]}. "
                    f"Explain the fundamentals in your own words."
                )
            else:
                question = (
                    f"For {topic_name} at {difficulty.value} difficulty, explain the fundamental "
                    f"concept step by step."
                )

        # ── SWITCH_TOPIC ─────────────────────────────────────────────
        elif action == AdaptiveAction.SWITCH_TOPIC:
            if target_criteria:
                question = (
                    f"Let's move to a new area. For {topic_name}: {target_criteria[0]}. "
                    f"Explain the main idea and one practical consideration."
                )
            else:
                question = (
                    f"For {topic_name}, explain the main concept in your own words "
                    f"and describe one practical example or trade-off you would consider."
                )

        # ── Fallback ─────────────────────────────────────────────────
        else:
            question = (
                f"For {topic_name} at {difficulty.value} difficulty, explain the main idea "
                f"in your own words and give one concrete example."
            )

        # ── Deduplication ────────────────────────────────────────────
        question = self._deduplicate_question(
            question=question,
            previous_question=previous_question,
            previously_asked=previously_asked or [],
            topic_name=topic_name,
            difficulty=difficulty,
            target_criteria=target_criteria,
        )

        return question

    @staticmethod
    def _deduplicate_question(
        question: str,
        previous_question: str | None,
        previously_asked: list[str],
        topic_name: str,
        difficulty: DifficultyLevel,
        target_criteria: list[str] | None,
    ) -> str:
        """Ensure the question differs from previously asked questions."""
        asked_set = set(previously_asked)
        if previous_question:
            asked_set.add(previous_question)

        if question not in asked_set:
            return question

        # Try using the next criterion as an alternate angle
        if target_criteria and len(target_criteria) > 1:
            alt_question = (
                f"For {topic_name} at {difficulty.value} difficulty: {target_criteria[1]}. "
                f"Explain with a specific example and any trade-offs."
            )
            if alt_question not in asked_set:
                return alt_question

        # Final fallback: append differentiator
        return f"{question} Approach this from a different angle than before."

    def _build_first_question(self, candidate) -> tuple[str, str, DifficultyLevel, QuestionPlan]:
        curriculum_repo = CurriculumRepository()
        curriculum_topics = curriculum_repo.list_all()
        retriever = LocalCurriculumRetriever(repository=curriculum_repo)

        completed_topics = [topic_id for topic_id in candidate.completed_topics if topic_id]
        selected_topic = None
        if completed_topics:
            for topic_id in completed_topics:
                topic = curriculum_repo.get_by_id(topic_id)
                if topic is not None:
                    selected_topic = topic
                    break

        if selected_topic is None:
            selected_topic = next((topic for topic in curriculum_topics if topic.day is not None), None)

        if selected_topic is None:
            raise ValueError(f"No curriculum topics available for candidate {candidate.candidate_id}")

        completion_rate = 0.0
        if curriculum_topics:
            completion_rate = min(1.0, len(completed_topics) / len(curriculum_topics))

        if completed_topics and completion_rate >= 0.6:
            suggested_difficulty = DifficultyLevel.INTERMEDIATE
        elif candidate.weak_topics:
            suggested_difficulty = DifficultyLevel.FOUNDATIONAL
        else:
            suggested_difficulty = DifficultyLevel.FOUNDATIONAL

        retrieval_results = retriever.search(selected_topic.title or selected_topic.topic_id, limit=1)
        retrieval_context = retrieval_results[0] if retrieval_results else None
        topic_context = retrieval_context.title if retrieval_context else selected_topic.title or selected_topic.topic_id
        # RC-3 fix: Always use the actual selected topic's objectives.
        objectives = list(selected_topic.objectives) if selected_topic.objectives else (
            retrieval_context.objectives if retrieval_context else []
        )

        target_difficulty = suggested_difficulty
        question_type = QuestionType.CONCEPTUAL
        if selected_topic.type and "coding" in selected_topic.type.lower():
            question_type = QuestionType.CODING
        elif selected_topic.tools and any(tool in {"docker", "kubernetes"} for tool in selected_topic.tools):
            question_type = QuestionType.SYSTEM_DESIGN

        plan = QuestionPlan(
            plan_id=f"qp-{uuid.uuid4().hex[:8]}",
            competency_id=selected_topic.topic_id,
            target_difficulty=target_difficulty,
            question_type=question_type,
            topic_context=topic_context,
            objective=f"Assess the candidate's understanding of {selected_topic.title or selected_topic.topic_id}",
            expected_criteria=[
                f"Explain the core idea behind {selected_topic.title or selected_topic.topic_id}",
                *[objective for objective in objectives[:2]],
            ],
            selection_reasoning=(
                f"Selected {selected_topic.title or selected_topic.topic_id} from the candidate's completed curriculum "
                f"and started at {target_difficulty.value} difficulty."
            ),
        )

        question_text = (
            f"For {selected_topic.title or selected_topic.topic_id}, explain the main concept in your own words "
            f"and describe one practical example or trade-off you would consider."
        )
        plan.generated_question_text = question_text
        return question_text, selected_topic.title or selected_topic.topic_id, target_difficulty, plan

    # ── Public API ───────────────────────────────────────────────────

    def create_session(self, request: InterviewSessionCreate) -> InterviewSession:
        """
        Start a new interview session for a candidate.

        Validates the candidate exists, creates a session, and adds
        an initial welcome message.
        """
        # Validate candidate exists (raises CandidateNotFoundError if not)
        candidate = self._candidates.get_by_id(request.candidate_id)

        session = InterviewSession(
            session_id=str(uuid.uuid4()),
            candidate_id=candidate.candidate_id,
            status=InterviewStatus.IN_PROGRESS,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        question_text, current_topic, difficulty, question_plan = self._build_first_question(candidate)

        welcome = InterviewMessage(
            role="interviewer",
            content=(
                f"Interview session started for candidate {candidate.candidate_id}. "
                f"Welcome! The adaptive interview will begin shortly."
            ),
        )
        session.messages.append(welcome)
        session.messages.append(
            InterviewMessage(role="interviewer", content=question_text, metadata={"question_plan_id": question_plan.plan_id})
        )
        session.current_question = question_text
        session.question = question_text
        session.current_topic = current_topic
        session.difficulty = difficulty
        session.question_number = 1
        session.questions_asked = 1
        intelligence = self._build_candidate_intelligence(
            candidate=candidate,
            selected_topic_id=question_plan.competency_id,
            suggested_difficulty=difficulty,
        )
        # ── Session intelligence initialisation ────────────────────
        initial_snapshot = SessionMemoryManager.create_initial_snapshot(
            session_id=session.session_id,
            candidate_id=candidate.candidate_id,
            first_plan=question_plan,
            difficulty=difficulty,
        )

        # RC-2 fix: Store topic_titles mapping (topic_id → human-readable title)
        first_topic_title = current_topic  # already resolved to title by _build_first_question
        topic_titles = {question_plan.competency_id: first_topic_title}

        session.metadata.update(
            {
                "active_question_plan": question_plan.model_dump(mode="json"),
                "active_question_plan_id": question_plan.plan_id,
                "candidate_intelligence": intelligence.model_dump(mode="json"),
                "asked_topic_ids": [question_plan.competency_id],
                "evaluated_topic_ids": [],  # RC-1 fix: no evaluations yet
                "topic_titles": topic_titles,  # RC-2 fix: id → title mapping
                "competency_states": {},
                "session_memory_snapshot": initial_snapshot.model_dump(mode="json"),
                "snapshot_index": 0,
                "plan_history": [question_plan.model_dump(mode="json")],
                "decision_history": [],
            }
        )

        self._save_session(session)
        logger.info(
            "Created session %s for candidate %s",
            session.session_id,
            session.candidate_id,
        )
        return session

    def get_session(self, session_id: str) -> InterviewSession:
        """
        Retrieve a session by ID.

        Raises:
            SessionNotFoundError: If the session does not exist.
        """
        session = self._load_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def submit_answer(
        self, session_id: str, answer: CandidateAnswer
    ) -> InterviewSession:
        """
        Process a candidate's answer and generate the next question.

        Phase 3 pipeline order:
          1. Evaluate answer
          2. Update competency state (BEFORE question generation)
          3. Select adaptive action + build gap context
          4. Build targeted question plan
          5. Generate targeted question text
          6. Enhance/store reasoning
          7. Update session memory

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionExpiredError: If the session is no longer in progress.
        """
        session = self.get_session(session_id)

        if session.status != InterviewStatus.IN_PROGRESS:
            raise SessionExpiredError(session_id)

        curriculum_repo = CurriculumRepository()
        retriever = LocalCurriculumRetriever(repository=curriculum_repo)
        candidate = self._candidates.get_by_id(session.candidate_id)

        current_plan_data = session.metadata.get("active_question_plan")
        if not isinstance(current_plan_data, dict):
            raise ValueError("Session is missing the active question plan")
        current_plan = QuestionPlan.model_validate(current_plan_data)

        # ── Step 1: Record the candidate's answer ────────────────────
        session.messages.append(
            InterviewMessage(role="candidate", content=answer.answer)
        )

        # ── Step 2: Evaluate the answer ──────────────────────────────
        evaluation = self._evaluate_answer(
            answer_text=answer.answer,
            question_plan=current_plan,
            topic_name=session.current_topic or current_plan.topic_context or current_plan.competency_id,
        )

        evaluation_trace = {
            "evaluation_id": evaluation.evaluation_id,
            "plan_id": current_plan.plan_id,
            "competency_id": current_plan.competency_id,
            "competency_title": current_plan.topic_context or current_plan.objective or current_plan.competency_id,
            "question_text": current_plan.generated_question_text or current_plan.objective,
            "candidate_answer": answer.answer,
            "scores": {
                "score": evaluation.score,
                "overall_score": evaluation.overall_score,
                "conceptual_correctness_score": evaluation.conceptual_correctness_score,
                "depth_reasoning_score": evaluation.depth_reasoning_score,
                "practical_understanding_score": evaluation.practical_understanding_score,
                "confidence_score": evaluation.confidence_score,
                "evidence_score": evaluation.evidence_score,
            },
            "strengths": list(evaluation.strengths),
            "weaknesses": list(evaluation.weaknesses),
            "missing_concepts": list(evaluation.missing_concepts),
            "misconceptions": list(evaluation.misconceptions),
            "evaluation": evaluation.model_dump(mode="json"),
            "question_plan": current_plan.model_dump(mode="json"),
        }

        # ── Step 3: Update evaluation history ────────────────────────
        evaluation_history = session.metadata.get("evaluation_history")
        if not isinstance(evaluation_history, list):
            evaluation_history = []
        evaluation_history.append(evaluation.model_dump(mode="json"))

        # ── Step 4: Update competency state BEFORE question gen ──────
        raw_comp_states = session.metadata.get("competency_states", {})
        competency_states: dict[str, CompetencyState] = {
            cid: CompetencyState.model_validate(data)
            for cid, data in raw_comp_states.items()
            if isinstance(data, dict)
        }

        # Collect ALL evaluations for the current competency
        evals_for_comp = [
            AnswerEvaluation.model_validate(ev_data)
            for ev_data in evaluation_history
            if isinstance(ev_data, dict)
            and ev_data.get("competency_id") == current_plan.competency_id
        ]

        updated_state = CompetencyTracker.update_competency_state(
            competency_id=current_plan.competency_id,
            evaluation=evaluation,
            question_plan=current_plan,
            current_states=competency_states,
            evaluation_history_for_competency=evals_for_comp,
        )

        # Track assessed criteria on the competency state
        assessed_criteria = list(updated_state.assessed_criteria)
        for criterion in current_plan.expected_criteria:
            if criterion not in assessed_criteria:
                assessed_criteria.append(criterion)
        updated_state = updated_state.model_copy(update={"assessed_criteria": assessed_criteria})

        competency_states[current_plan.competency_id] = updated_state

        # ── Step 5: Build question plan (with updated competency) ────
        next_difficulty = self._next_difficulty(session.difficulty, evaluation)

        question_text, current_topic, difficulty, question_plan, decision = self._build_question_plan(
            candidate=candidate,
            session=session,
            evaluation=evaluation,
            current_plan=current_plan,
            curriculum_repo=curriculum_repo,
            retriever=retriever,
            next_difficulty=next_difficulty,
            competency_states=competency_states,
        )

        # ── Step 6: Enhanced adaptive reasoning (after plan) ─────────
        decision.reasoning = AdaptiveReasoningEnhancer.enhance_reasoning(
            evaluation=evaluation,
            competency_state=updated_state,
            decision=decision,
        )
        session.metadata["next_question_reason"] = decision.reasoning

        # ── Step 7: Update session state ─────────────────────────────
        session.messages.append(
            InterviewMessage(role="interviewer", content=question_text, metadata={"question_plan_id": question_plan.plan_id})
        )
        session.question_number += 1
        session.questions_asked += 1
        session.current_question = question_text
        session.question = question_text
        session.current_topic = current_topic
        session.difficulty = difficulty
        asked_topic_ids = list(session.metadata.get("asked_topic_ids", []))
        asked_topic_ids.append(question_plan.competency_id)

        # RC-1 fix: Track evaluated topics separately (only topics with actual answers)
        evaluated_topic_ids = list(session.metadata.get("evaluated_topic_ids", []))
        if current_plan.competency_id not in evaluated_topic_ids:
            evaluated_topic_ids.append(current_plan.competency_id)

        # RC-2 fix: Extend topic_titles mapping with the new topic
        topic_titles = dict(session.metadata.get("topic_titles", {}))
        topic_titles[current_plan.competency_id] = (
            session.current_topic or current_plan.topic_context or current_plan.competency_id
        )
        topic_titles[question_plan.competency_id] = current_topic  # next topic's title

        # Track asked question texts for deduplication
        asked_question_texts = list(session.metadata.get("asked_question_texts", []))
        asked_question_texts.append(question_text)

        # ── Step 8: Session memory snapshot ──────────────────────────
        plan_history_raw = session.metadata.get("plan_history", [])
        plan_history_raw.append(question_plan.model_dump(mode="json"))

        decision_history_raw = session.metadata.get("decision_history", [])
        decision_history_raw.append(decision.model_dump(mode="json"))

        evaluation_trace_history = session.metadata.get("evaluation_traces", [])
        if not isinstance(evaluation_trace_history, list):
            evaluation_trace_history = []
        evaluation_trace_history.append(evaluation_trace)

        snapshot_index = session.metadata.get("snapshot_index", 0) + 1

        topics_covered = list(dict.fromkeys(asked_topic_ids))  # unique, ordered

        snapshot = SessionMemoryManager.create_snapshot(
            session_id=session.session_id,
            candidate_id=session.candidate_id,
            snapshot_index=snapshot_index,
            competency_states=list(competency_states.values()),
            plan_history=[
                QuestionPlan.model_validate(p) for p in plan_history_raw if isinstance(p, dict)
            ],
            evaluation_history=[
                AnswerEvaluation.model_validate(e) for e in evaluation_history if isinstance(e, dict)
            ],
            decision_history=[
                AdaptiveDecision.model_validate(d) for d in decision_history_raw if isinstance(d, dict)
            ],
            current_difficulty=difficulty,
            current_competency_id=question_plan.competency_id,
            total_questions_asked=session.questions_asked,
            topics_covered=topics_covered,
        )

        session.metadata.update(
            {
                "active_question_plan": question_plan.model_dump(mode="json"),
                "active_question_plan_id": question_plan.plan_id,
                "last_answer_evaluation": evaluation.model_dump(mode="json"),
                "evaluation_history": evaluation_history,
                "evaluation_traces": evaluation_trace_history,
                "last_evaluation_trace": evaluation_trace,
                "last_evaluation": evaluation.model_dump(mode="json"),
                "last_adaptive_decision": decision.model_dump(mode="json"),
                "asked_topic_ids": asked_topic_ids,
                "evaluated_topic_ids": evaluated_topic_ids,  # RC-1 fix
                "topic_titles": topic_titles,  # RC-2 fix
                "asked_question_texts": asked_question_texts,
                "competency_states": {
                    cid: state.model_dump(mode="json")
                    for cid, state in competency_states.items()
                },
                "session_memory_snapshot": snapshot.model_dump(mode="json"),
                "snapshot_index": snapshot_index,
                "plan_history": plan_history_raw,
                "decision_history": decision_history_raw,
            }
        )
        session.updated_at = datetime.utcnow()

        self._save_session(session)
        logger.info(
            "Session %s: answer recorded, question #%d generated",
            session_id,
            session.questions_asked,
        )
        return session

    def end_session(self, session_id: str) -> InterviewSummary:
        """
        End a session and produce a summary with full FinalInterviewReport data.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionExpiredError: If the session has already been completed.
        """
        session = self.get_session(session_id)

        if session.status == InterviewStatus.COMPLETED:
            raise SessionExpiredError(session_id)

        session.status = InterviewStatus.COMPLETED
        session.updated_at = datetime.utcnow()
        self._save_session(session)

        duration = (session.updated_at - session.created_at).total_seconds()

        # ── Reconstruct session intelligence state ──────────────────
        raw_comp_states = session.metadata.get("competency_states", {})
        competency_states: dict[str, CompetencyState] = {
            cid: CompetencyState.model_validate(data)
            for cid, data in raw_comp_states.items()
            if isinstance(data, dict)
        }

        evaluation_history_raw = session.metadata.get("evaluation_history", [])
        evaluation_history = [
            AnswerEvaluation.model_validate(e)
            for e in evaluation_history_raw
            if isinstance(e, dict)
        ]

        decision_history_raw = session.metadata.get("decision_history", [])
        decision_history = [
            AdaptiveDecision.model_validate(d)
            for d in decision_history_raw
            if isinstance(d, dict)
        ]

        evaluation_traces_raw = session.metadata.get("evaluation_traces", [])
        evaluation_traces = [
            trace for trace in evaluation_traces_raw
            if isinstance(trace, dict)
        ]

        plan_history_raw = session.metadata.get("plan_history", [])
        plan_history = [
            QuestionPlan.model_validate(p)
            for p in plan_history_raw
            if isinstance(p, dict)
        ]

        # RC-1 fix: Use evaluated_topic_ids (topics with actual answers),
        # not asked_topic_ids (which includes the next unanswered question)
        evaluated_topic_ids = list(dict.fromkeys(
            session.metadata.get("evaluated_topic_ids", [])
        ))

        # RC-2/RC-7 fix: Resolve topic IDs to human-readable titles
        topic_titles = dict(session.metadata.get("topic_titles", {}))
        topics_covered_titles = [
            topic_titles.get(tid, tid) for tid in evaluated_topic_ids
        ]

        # ── Generate FinalInterviewReport (canonical model) ─────────
        report = FinalReportGenerator.generate_report(
            session_id=session.session_id,
            candidate_id=session.candidate_id,
            competency_states=competency_states,
            evaluation_history=evaluation_history,
            decision_history=decision_history,
            plan_history=plan_history,
            total_questions=session.questions_asked,
            duration_seconds=round(duration, 2),
            topics_covered=topics_covered_titles,
            topic_titles=topic_titles,
        )

        # Store the report in session metadata for auditability
        session.metadata["final_report"] = report.model_dump(mode="json")
        self._save_session(session)

        logger.info(
            "Session %s ended. %d questions, %.1fs duration",
            session_id,
            session.questions_asked,
            duration,
        )

        # ── Map FinalInterviewReport → InterviewSummary ─────────────
        # Centralized mapping via FinalReportGenerator.report_to_summary_fields
        report_fields = FinalReportGenerator.report_to_summary_fields(report)

        # Derive accurate counts from actual evaluated data
        responses_evaluated = len(evaluation_history)
        competencies_assessed = len(set(
            e.competency_id for e in evaluation_history
        ))

        return InterviewSummary(
            session_id=session.session_id,
            candidate_id=session.candidate_id,
            status=session.status,
            total_questions=session.questions_asked,
            responses_evaluated=responses_evaluated,
            competencies_assessed=competencies_assessed,
            duration_seconds=round(duration, 2),
            topics_covered=topics_covered_titles,
            **report_fields,
        )
