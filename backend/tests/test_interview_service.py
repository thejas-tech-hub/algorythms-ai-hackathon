from app.data.repositories import CandidateRepository
from app.data.session_store import SessionStore
from app.models.interview import CandidateAnswer, InterviewSessionCreate
from app.models.common import DifficultyLevel
from app.models.adaptive import AnswerEvaluation, QuestionPlan
from app.services.candidate_service import CandidateService
from app.services.interview_service import InterviewService


def build_service() -> InterviewService:
    return InterviewService(
        session_store=SessionStore(),
        candidate_service=CandidateService(repository=CandidateRepository()),
    )


def build_plan(session) -> QuestionPlan:
    plan_data = session.metadata["active_question_plan"]
    return QuestionPlan.model_validate(plan_data)


def test_create_session_returns_first_question() -> None:
    service = build_service()

    session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

    assert session.current_question
    assert session.question == session.current_question
    assert session.current_topic
    assert session.metadata["active_question_plan"]["generated_question_text"] == session.current_question


def test_submit_answer_advances_session_state() -> None:
    service = build_service()
    session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
    previous_question = session.current_question
    previous_topic = session.current_topic
    previous_plan_id = session.metadata["active_question_plan_id"]

    updated = service.submit_answer(
        session.session_id,
        CandidateAnswer(
            answer=(
                "The concept is that embeddings encode semantic meaning as vectors, and in practice you compare similar vectors to retrieve related content. "
                "I would also explain the trade-offs around similarity metrics, dimensionality, and retrieval quality."
            )
        ),
    )

    assert updated.current_question
    assert updated.current_question != previous_question
    assert updated.question == updated.current_question
    assert updated.questions_asked == 2
    assert updated.question_number == 2
    assert updated.current_topic != previous_topic
    assert updated.difficulty in DifficultyLevel
    assert updated.metadata["active_question_plan_id"] != previous_plan_id
    assert updated.metadata["active_question_plan"]["generated_question_text"] == updated.current_question
    assert updated.metadata["last_evaluation"]["plan_id"] == previous_plan_id
    assert updated.metadata["last_answer_evaluation"]["overall_score"] >= 0
    assert updated.metadata["evaluation_history"]
    assert any(message.role == "candidate" and "embeddings encode semantic meaning" in message.content for message in updated.messages)
    assert updated.messages[-1].role == "interviewer"
    assert updated.messages[-1].content == updated.current_question


def test_strong_answer_produces_meaningful_evaluation() -> None:
    service = build_service()
    session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
    plan = build_plan(session)

    evaluation = service._evaluate_answer(  # noqa: SLF001 - direct deterministic evaluator coverage
        answer_text=(
            "VS Code and the Python extension together let me create a virtual environment, run the app, and debug the code. "
            "In practice I would verify the interpreter, launch the app from the editor, and explain the trade-offs around local setup versus convenience."
        ),
        question_plan=plan,
        topic_name=session.current_topic or "",
    )

    assert evaluation.overall_score is not None
    assert evaluation.overall_score >= 60
    assert evaluation.conceptual_correctness_score > 0
    assert evaluation.depth_reasoning_score > 0
    assert evaluation.practical_understanding_score > 0
    assert evaluation.strengths
    assert evaluation.evidence


def test_weak_answer_identifies_gaps_and_lower_evidence() -> None:
    service = build_service()
    session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
    plan = build_plan(session)

    evaluation = service._evaluate_answer(  # noqa: SLF001 - direct deterministic evaluator coverage
        answer_text="Maybe it is about vectors.",
        question_plan=plan,
        topic_name=session.current_topic or "",
    )

    assert evaluation.overall_score is not None
    assert evaluation.overall_score < 40
    assert evaluation.weaknesses
    assert evaluation.missing_concepts
    assert evaluation.evidence_score <= 50
    assert evaluation.follow_up_needed is True


def test_expected_criteria_influence_evaluation() -> None:
    service = build_service()
    session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))
    plan = build_plan(session)
    plan.expected_criteria = ["Explain the core idea", "Provide one practical example"]
    plan.generated_question_text = session.current_question
    evaluation = service._evaluate_answer(  # noqa: SLF001 - direct deterministic evaluator coverage
        answer_text="The core idea is vectors with one practical example using nearest neighbors.",
        question_plan=plan,
        topic_name=session.current_topic or "",
    )

    assert evaluation.overall_score is not None
    assert evaluation.rationale


def test_evaluation_is_persisted_in_session() -> None:
    service = build_service()
    session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

    updated = service.submit_answer(session.session_id, CandidateAnswer(answer="The main idea is retrieval using embeddings, with a practical example."))

    assert updated.metadata["last_answer_evaluation"]
    assert updated.metadata["evaluation_history"]
    assert updated.metadata["evaluation_history"][-1]["competency_id"] == updated.metadata["last_answer_evaluation"]["competency_id"]


def test_consecutive_answers_keep_advancing_questions_and_topics() -> None:
    service = build_service()
    session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

    first_answered = service.submit_answer(
        session.session_id,
        CandidateAnswer(answer="I would focus on the data flow, vector similarity, and why the retrieval path matters for the user experience."),
    )
    first_followup_question = first_answered.current_question
    first_followup_topic = first_answered.current_topic

    second_answered = service.submit_answer(
        session.session_id,
        CandidateAnswer(answer="A stronger follow-up would connect the current topic to an implementation choice, explain trade-offs, and mention edge cases."),
    )

    assert second_answered.questions_asked == 3
    assert second_answered.question_number == 3
    assert second_answered.current_question
    assert second_answered.current_question != first_followup_question
    assert second_answered.current_topic != first_followup_topic
    assert second_answered.metadata["active_question_plan"]["generated_question_text"] == second_answered.current_question
    assert len([message for message in second_answered.messages if message.role == "candidate"]) == 2
    assert len([message for message in second_answered.messages if message.role == "interviewer"]) >= 3
