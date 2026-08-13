"""
Phase 3 — Manual Flow Inspection Script.

Traces the full adaptive pipeline for 4 consecutive answers,
showing that each question responds to WHAT the candidate
demonstrated or missed, not merely HOW WELL they scored.

The "judge" should be able to compare two consecutive questions
and understand: "Why did the AI ask THIS question after THAT answer?"
"""

from app.data.repositories import CandidateRepository
from app.data.session_store import SessionStore
from app.models.interview import CandidateAnswer, InterviewSessionCreate
from app.services.candidate_service import CandidateService
from app.services.interview_service import InterviewService


def build_service():
    return InterviewService(
        session_store=SessionStore(),
        candidate_service=CandidateService(repository=CandidateRepository()),
    )


def trace_step(session, step_label: str):
    """Print a trace of the current state after an answer submission."""
    plan = session.metadata.get("active_question_plan", {})
    decision = session.metadata.get("last_adaptive_decision", {})
    eval_data = session.metadata.get("last_evaluation", {})

    print(f"\n{'='*70}")
    print(f"STEP: {step_label}")
    print(f"{'='*70}")
    print(f"  Topic:      {session.current_topic}")
    print(f"  Difficulty:  {session.difficulty}")
    print(f"  Question:    {session.current_question[:100]}...")
    print()

    if eval_data:
        print(f"  --- EVALUATION (of previous answer) ---")
        print(f"  Score:              {eval_data.get('score', '?')}/10")
        print(f"  Strengths:          {eval_data.get('strengths', [])}")
        print(f"  Weaknesses:         {eval_data.get('weaknesses', [])}")
        print(f"  Missing concepts:   {eval_data.get('missing_concepts', [])}")
        print(f"  Misconceptions:     {eval_data.get('misconceptions', [])}")
        print(f"  Follow-up needed:   {eval_data.get('follow_up_needed', '?')}")
        print()

    if decision:
        print(f"  --- ADAPTIVE DECISION ---")
        print(f"  Action:             {decision.get('action', '?')}")
        print(f"  Reasoning:          {decision.get('reasoning', '?')[:120]}...")
        print()

    if plan:
        print(f"  --- QUESTION PLAN ---")
        print(f"  Plan ID:            {plan.get('plan_id', '?')}")
        print(f"  Objective:          {plan.get('objective', '?')[:80]}...")
        print(f"  Target gap:         {plan.get('target_gap', 'None')}")
        print(f"  Question intent:    {plan.get('question_intent', 'None')}")
        print(f"  Evidence basis:     {plan.get('evidence_basis', [])}")
        print(f"  Expected criteria:  {plan.get('expected_criteria', [])}")
        print(f"  Assessed objectives:{plan.get('assessed_objectives', [])}")
        print(f"  Selection reasoning:{plan.get('selection_reasoning', '?')[:120]}")
        print()


def main():
    service = build_service()
    session = service.create_session(InterviewSessionCreate(candidate_id="CAND-001"))

    print("=" * 70)
    print("PHASE 3 — MANUAL FLOW INSPECTION")
    print("Evidence-Driven Adaptive Questioning Trace")
    print("=" * 70)
    print(f"\nCandidate: CAND-001")
    print(f"Initial topic: {session.current_topic}")
    print(f"Initial question: {session.current_question}")

    # ── Step 1: Misconception answer ────────────────────────────────
    answer1 = (
        "Python environments are always guaranteed to work perfectly. "
        "You never need to worry about dependencies because Python handles everything automatically."
    )
    print(f"\n{'~'*70}")
    print(f"CANDIDATE ANSWER 1: {answer1}")
    session = service.submit_answer(session.session_id, CandidateAnswer(answer=answer1))
    trace_step(session, "After misconception answer")

    # ── Step 2: Weak partial answer ─────────────────────────────────
    answer2 = (
        "Okay so you install Python and VS Code. That's basically it. "
        "I think you also need some extensions maybe."
    )
    print(f"\n{'~'*70}")
    print(f"CANDIDATE ANSWER 2: {answer2}")
    session = service.submit_answer(session.session_id, CandidateAnswer(answer=answer2))
    trace_step(session, "After weak partial answer")

    # ── Step 3: Strong detailed answer ──────────────────────────────
    answer3 = (
        "A virtual environment isolates Python dependencies per project using venv. "
        "The trade-off is disk space versus reproducibility and isolation. "
        "For example, 'python -m venv .venv' creates a sandbox, then 'pip install' "
        "only affects that project. This prevents version conflicts between projects. "
        "Compared to global pip, virtual environments provide much better reproducibility "
        "because you can pin versions in requirements.txt and share them with teammates."
    )
    print(f"\n{'~'*70}")
    print(f"CANDIDATE ANSWER 3: {answer3}")
    session = service.submit_answer(session.session_id, CandidateAnswer(answer=answer3))
    trace_step(session, "After strong detailed answer")

    # ── Step 4: Another decent answer ───────────────────────────────
    answer4 = (
        "Pylance provides IntelliSense and type checking in VS Code. "
        "Because it analyzes type stubs, it catches errors before runtime. "
        "The practical benefit is faster debugging and fewer production bugs. "
        "However, there's a trade-off: strict type checking can slow down iteration speed."
    )
    print(f"\n{'~'*70}")
    print(f"CANDIDATE ANSWER 4: {answer4}")
    session = service.submit_answer(session.session_id, CandidateAnswer(answer=answer4))
    trace_step(session, "After another decent answer")

    # ── Verify no question duplication ──────────────────────────────
    asked_texts = session.metadata.get("asked_question_texts", [])
    unique_questions = set(asked_texts)
    print(f"\n{'='*70}")
    print(f"DEDUPLICATION CHECK")
    print(f"{'='*70}")
    print(f"  Total questions generated: {len(asked_texts)}")
    print(f"  Unique questions:          {len(unique_questions)}")
    if len(asked_texts) == len(unique_questions):
        print(f"  [PASS] No duplicate questions")
    else:
        dupes = [q for q in asked_texts if asked_texts.count(q) > 1]
        print(f"  [WARN] Duplicate questions found: {set(dupes)}")

    # ── Verify objective rotation ───────────────────────────────────
    plan_history = session.metadata.get("plan_history", [])
    all_criteria_sets = []
    for plan in plan_history:
        if isinstance(plan, dict):
            all_criteria_sets.append(set(plan.get("expected_criteria", [])))

    print(f"\n{'='*70}")
    print(f"OBJECTIVE ROTATION CHECK")
    print(f"{'='*70}")
    for i, criteria in enumerate(all_criteria_sets):
        print(f"  Plan {i+1} criteria: {criteria}")
    all_same = all(c == all_criteria_sets[0] for c in all_criteria_sets) if all_criteria_sets else True
    if not all_same:
        print(f"  [PASS] Criteria rotated across plans")
    else:
        print(f"  [INFO] Criteria did not rotate (may be expected if topic changed)")

    # ── End session and verify report ───────────────────────────────
    summary = service.end_session(session.session_id)
    print(f"\n{'='*70}")
    print(f"END SESSION REPORT")
    print(f"{'='*70}")
    print(f"  Total questions:       {summary.total_questions}")
    print(f"  Responses evaluated:   {summary.responses_evaluated}")
    print(f"  Competencies assessed: {summary.competencies_assessed}")
    print(f"  Topics covered:        {summary.topics_covered}")
    print(f"  Duration:              {summary.duration_seconds}s")

    print(f"\n{'='*70}")
    print(f"PHASE 3 MANUAL FLOW INSPECTION COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
