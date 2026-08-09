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


def _tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.casefold()) if len(token) > 2}


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
            criterion_tokens = _tokenize(criterion)
            if criterion_tokens and criterion_tokens.intersection(answer_tokens):
                criterion_hits.append(criterion)
                evidence.append(
                    RubricEvidence(
                        competency_id=question_plan.competency_id,
                        criterion=criterion,
                        demonstrated=True,
                        strength=EvidenceStrength.STRONG if len(criterion_tokens.intersection(answer_tokens)) >= 2 else EvidenceStrength.MODERATE,
                        notes=f"Matched tokens: {sorted(criterion_tokens.intersection(answer_tokens))[:4]}",
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
                        notes="No clear reference detected in the answer",
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
            follow_up_needed=overall_score < 60.0 or bool(missing_concepts),
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

    def _build_question_plan(
        self,
        candidate,
        session: InterviewSession,
        evaluation: AnswerEvaluation,
        current_plan: QuestionPlan,
        curriculum_repo: CurriculumRepository,
        retriever: LocalCurriculumRetriever,
        next_difficulty: DifficultyLevel,
    ) -> tuple[str, str, DifficultyLevel, QuestionPlan, AdaptiveDecision]:
        next_topic = self._select_next_topic(candidate, session, evaluation, current_plan, curriculum_repo, retriever)
        topic_name = self._topic_name(next_topic)

        question_type = QuestionType.CONCEPTUAL
        if next_topic.type and "coding" in next_topic.type.lower():
            question_type = QuestionType.CODING
        elif next_topic.tools and any(tool.lower() in {"docker", "kubernetes"} for tool in next_topic.tools):
            question_type = QuestionType.SYSTEM_DESIGN

        retrieval_results = retriever.search(topic_name, limit=1)
        topic_context = retrieval_results[0].title if retrieval_results else topic_name
        objectives = retrieval_results[0].objectives if retrieval_results else list(next_topic.objectives)

        plan = QuestionPlan(
            plan_id=f"qp-{uuid.uuid4().hex[:8]}",
            competency_id=next_topic.topic_id,
            target_difficulty=next_difficulty,
            question_type=question_type,
            topic_context=topic_context,
            follow_up_to=current_plan.plan_id,
            objective=f"Assess the candidate's understanding of {topic_name} after their last answer",
            expected_criteria=[
                f"Explain the core idea behind {topic_name}",
                *[objective for objective in objectives[:2]],
            ],
            selection_reasoning=f"Selected {topic_name} after evaluating the previous answer at score {evaluation.score:.1f}.",
        )

        question_text = self._build_question_text(
            topic_name=topic_name,
            difficulty=next_difficulty,
            question_type=question_type,
            evaluation=evaluation,
            previous_question=session.current_question,
        )
        plan.generated_question_text = question_text

        difficulty_order = [
            DifficultyLevel.FOUNDATIONAL,
            DifficultyLevel.INTERMEDIATE,
            DifficultyLevel.ADVANCED,
            DifficultyLevel.EXPERT,
        ]
        if difficulty_order.index(next_difficulty) > difficulty_order.index(current_plan.target_difficulty):
            action = AdaptiveAction.INCREASE_DIFFICULTY
        elif difficulty_order.index(next_difficulty) < difficulty_order.index(current_plan.target_difficulty):
            action = AdaptiveAction.DECREASE_DIFFICULTY
        elif next_topic.topic_id == current_plan.competency_id:
            action = AdaptiveAction.CONTINUE_SAME_TOPIC
        else:
            action = AdaptiveAction.SWITCH_TOPIC

        decision = AdaptiveDecision(
            decision_id=f"dec-{uuid.uuid4().hex[:8]}",
            evaluation_id=evaluation.evaluation_id,
            action=action,
            next_competency_id=next_topic.topic_id,
            next_difficulty=next_difficulty,
            reasoning=plan.selection_reasoning,
        )

        return question_text, topic_name, next_difficulty, plan, decision

    def _build_question_text(
        self,
        topic_name: str,
        difficulty: DifficultyLevel,
        question_type: QuestionType,
        evaluation: AnswerEvaluation,
        previous_question: str | None,
    ) -> str:
        if question_type == QuestionType.CODING:
            question = (
                f"For {topic_name} at {difficulty.value} difficulty, how would you implement this in practice and explain the key trade-offs?"
            )
        elif question_type == QuestionType.SYSTEM_DESIGN:
            question = (
                f"For {topic_name} at {difficulty.value} difficulty, outline the architecture choices, failure modes, and trade-offs you would consider."
            )
        elif evaluation.score < 4.0:
            question = (
                f"For {topic_name} at {difficulty.value} difficulty, walk me through the core concept more carefully and correct the gap from your last answer."
            )
        elif evaluation.score >= 7.5:
            question = (
                f"For {topic_name} at {difficulty.value} difficulty, go one level deeper and explain how you would apply this in a realistic scenario."
            )
        else:
            question = (
                f"For {topic_name} at {difficulty.value} difficulty, explain the main idea in your own words and give one concrete example."
            )

        if previous_question and question == previous_question:
            question = f"{question} Use a different angle from the previous question."
        return question

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
        objectives = retrieval_context.objectives if retrieval_context else list(selected_topic.objectives)

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

        session.metadata.update(
            {
                "active_question_plan": question_plan.model_dump(mode="json"),
                "active_question_plan_id": question_plan.plan_id,
                "candidate_intelligence": intelligence.model_dump(mode="json"),
                "asked_topic_ids": [question_plan.competency_id],
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

        # Record the candidate's answer
        session.messages.append(
            InterviewMessage(role="candidate", content=answer.answer)
        )

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

        next_difficulty = self._next_difficulty(session.difficulty, evaluation)

        question_text, current_topic, difficulty, question_plan, decision = self._build_question_plan(
            candidate=candidate,
            session=session,
            evaluation=evaluation,
            current_plan=current_plan,
            curriculum_repo=curriculum_repo,
            retriever=retriever,
            next_difficulty=next_difficulty,
        )

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
        evaluation_history = session.metadata.get("evaluation_history")
        if not isinstance(evaluation_history, list):
            evaluation_history = []
        evaluation_history.append(evaluation.model_dump(mode="json"))

        # ── Session intelligence: competency tracking ───────────────
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
        competency_states[current_plan.competency_id] = updated_state

        # ── Session intelligence: enhanced adaptive reasoning ───────
        decision.reasoning = AdaptiveReasoningEnhancer.enhance_reasoning(
            evaluation=evaluation,
            competency_state=updated_state,
            decision=decision,
        )
        session.metadata["next_question_reason"] = decision.reasoning

        # ── Session intelligence: session memory snapshot ───────────
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

        topics_covered = list(dict.fromkeys(
            session.metadata.get("asked_topic_ids", [])
        ))

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
            topics_covered=topics_covered,
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

        return InterviewSummary(
            session_id=session.session_id,
            candidate_id=session.candidate_id,
            status=session.status,
            total_questions=session.questions_asked,
            duration_seconds=round(duration, 2),
            topics_covered=topics_covered,
            **report_fields,
        )
