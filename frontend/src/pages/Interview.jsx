import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import InterviewHeader from '../components/InterviewHeader';
import QuestionCard from '../components/QuestionCard';
import AnswerInput from '../components/AnswerInput';
import ProgressIndicator from '../components/ProgressIndicator';
import VoiceControls from '../components/VoiceControls';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import useVoiceInterviewer from '../hooks/useVoiceInterviewer';
import useSpeechRecognition from '../hooks/useSpeechRecognition';
import { submitAnswer, endInterview } from '../services/api';

/**
 * Interview — Page 3.
 * The main active interview screen with voice AI, adaptive intelligence
 * sidebar, evaluation panels, and journey tracking.
 *
 * State machine: READY → SPEAKING → LISTENING → ANALYZING → ADAPTING → READY
 * Only ONE state is active at a time.
 *
 * Props:
 *   session           (object) — interview session returned by startInterview
 *   candidate         (object) — candidate data
 *   onInterviewEnd    (fn)     — called with { report, journeyData }
 */
export default function Interview({ session, candidate, onInterviewEnd }) {
  const [sessionState, setSessionState] = useState(session);
  const initialQuestion =
    session?.current_question ??
    session?.question ??
    session?.next_question ??
    null;

  const [currentQuestion, setCurrentQuestion] = useState(initialQuestion);
  const [questionNum, setQuestionNum] = useState(
    session?.question_number ?? session?.current_question_number ?? 1
  );
  const [totalQuestions, setTotalQuestions] = useState(
    session?.total_questions ?? session?.question_count ?? null
  );
  const [sessionStatus, setSessionStatus] = useState(session?.status ?? null);
  const [answer, setAnswer] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState(null);

  // ── Interview state machine ──
  // States: 'ready' | 'speaking' | 'listening' | 'analyzing' | 'adapting'
  const [interviewState, setInterviewState] = useState('ready');

  // ── Journey data — only the minimum needed for final report ──
  const journeyRef = useRef([]);
  const [competencyEvidence, setCompetencyEvidence] = useState({});

  // ── Voice (TTS) ──
  const voice = useVoiceInterviewer();
  const prevQuestionRef = useRef(null);

  // ── Speech Recognition (STT) ──
  const stt = useSpeechRecognition();

  // Sync STT listening state with interview state machine
  useEffect(() => {
    if (stt.isListening && interviewState !== 'analyzing') {
      setInterviewState('listening');
    } else if (!stt.isListening && interviewState === 'listening') {
      setInterviewState('ready');
    }
  }, [stt.isListening, interviewState]);

  // Sync TTS speaking state with interview state machine
  useEffect(() => {
    if (voice.isSpeaking) {
      setInterviewState('speaking');
    } else if (interviewState === 'speaking') {
      setInterviewState('ready');
    }
  }, [voice.isSpeaking, interviewState]);

  useEffect(() => {
    setSessionState(session);
    setCurrentQuestion(
      session?.current_question ??
      session?.question ??
      session?.next_question ??
      null
    );
    setQuestionNum(session?.question_number ?? session?.current_question_number ?? 1);
    setTotalQuestions(session?.total_questions ?? session?.question_count ?? null);
    setSessionStatus(session?.status ?? null);
    setSubmitting(false);
    setSubmitError(null);
    setEnding(false);
    setEndError(null);
  }, [session]);

  // ── Voice: speak when question changes ──
  useEffect(() => {
    if (!currentQuestion || currentQuestion === prevQuestionRef.current) return;
    prevQuestionRef.current = currentQuestion;
    const adaptiveAction = sessionState?.metadata?.last_adaptive_decision?.action ?? null;
    // Non-blocking: attempt to speak, silently fails if autoplay blocked
    voice.speakQuestion(currentQuestion, adaptiveAction);
  }, [currentQuestion]); // eslint-disable-line react-hooks/exhaustive-deps

  const sessionId = session?.session_id ?? session?.id;

  // ── Extract adaptive intelligence from session metadata ──
  const metadata = sessionState?.metadata ?? {};
  const activeQuestionPlan = metadata.active_question_plan ?? null;
  const previousEvaluationTrace = metadata.last_evaluation_trace ?? null;
  const lastEvaluation = metadata.last_answer_evaluation ?? previousEvaluationTrace?.evaluation ?? null;
  const lastDecision = metadata.last_adaptive_decision ?? null;
  const nextQuestionReason = metadata.next_question_reason ?? lastDecision?.reasoning ?? activeQuestionPlan?.selection_reasoning ?? '';
  const rawCompetencyStates = metadata.competency_states ?? {};

  // ── Build competency name lookup from plan history / evaluation traces ──
  const competencyNameMap = useMemo(() => {
    const nameMap = {};
    // From plan history
    const plans = metadata.plan_history ?? [];
    for (const plan of plans) {
      if (plan?.competency_id && (plan?.topic_context || plan?.objective)) {
        nameMap[plan.competency_id] = plan.topic_context || plan.objective;
      }
    }
    // From evaluation traces
    const traces = metadata.evaluation_traces ?? [];
    for (const trace of traces) {
      if (trace?.competency_id && trace?.competency_title) {
        nameMap[trace.competency_id] = trace.competency_title;
      }
    }
    return nameMap;
  }, [metadata.plan_history, metadata.evaluation_traces]);

  // ── Build intelligence state for ProgressIndicator (real data only) ──
  const competencyStateEntries = Object.entries(rawCompetencyStates);
  const latestCompState = lastDecision?.next_competency_id
    ? rawCompetencyStates[lastDecision.next_competency_id]
    : competencyStateEntries.length > 0
      ? competencyStateEntries[competencyStateEntries.length - 1][1]
      : null;

  const pipelineState = {
    isSubmitting: submitting,
    hasEvaluation: Boolean(lastEvaluation),
    hasDecision: Boolean(lastDecision),
    competencyCount: competencyStateEntries.length || null,
    evidenceCount: questionNum > 1 ? questionNum - 1 : null,
    currentProficiency: latestCompState?.proficiency ?? null,
    adaptiveStrategy: lastDecision?.action ?? null,
  };

  // ── Build question context for QuestionCard (real data) ──
  const questionContext = buildQuestionContext({
    activeQuestionPlan,
    previousEvaluationTrace,
    lastDecision,
    nextQuestionReason,
    currentQuestion,
    lastEvaluation,
  });

  // ── Build evaluation panel data (real data) ──
  const evaluationPanel = buildEvaluationPanelData({
    lastEvaluation,
    lastDecision,
    nextQuestionReason,
    previousEvaluationTrace,
    activeQuestionPlan,
  });

  // ── Track competency evidence for sidebar display ──
  useEffect(() => {
    if (Object.keys(rawCompetencyStates).length > 0) {
      setCompetencyEvidence(rawCompetencyStates);
    }
  }, [rawCompetencyStates]);

  // ── Collect journey step after each evaluation ──
  const collectJourneyStep = useCallback((evalTrace, decision, plan, qNum) => {
    if (!evalTrace) return;
    journeyRef.current.push({
      questionNumber: qNum,
      competency: evalTrace.competency_title || evalTrace.competency_id || 'Unknown',
      competencyId: evalTrace.competency_id,
      difficulty: plan?.target_difficulty ?? 'unknown',
      score: evalTrace.scores?.overall_score ?? evalTrace.scores?.score * 10 ?? null,
      action: decision?.action ?? null,
      reasoning: decision?.reasoning ?? '',
      strengths: evalTrace.strengths?.slice(0, 2) ?? [],
      weaknesses: evalTrace.weaknesses?.slice(0, 2) ?? [],
    });
  }, []);

  async function handleSubmit() {
    if (!answer.trim() || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    setInterviewState('analyzing');
    voice.stop(); // Stop any current speech
    stt.stop();   // Stop any active recognition
    try {
      const result = await submitAnswer(sessionId, answer);
      setAnswer('');
      stt.reset(); // Reset STT for next question

      // Briefly show "adapting" state
      setInterviewState('adapting');

      // Collect journey step from the evaluation just performed
      const evalTrace = result?.metadata?.last_evaluation_trace ?? null;
      const decision = result?.metadata?.last_adaptive_decision ?? null;
      const prevPlan = sessionState?.metadata?.active_question_plan ?? null;
      collectJourneyStep(evalTrace, decision, prevPlan, questionNum);

      setSessionState(result);

      const nextQ = result?.current_question ?? result?.question ?? result?.next_question ?? null;
      const nextNum = result?.question_number ?? result?.current_question_number ?? questionNum + 1;
      const totalQ = result?.total_questions ?? result?.question_count ?? totalQuestions;
      const newStatus = result?.status ?? sessionStatus;

      setCurrentQuestion(nextQ);
      setQuestionNum(nextNum);
      setTotalQuestions(totalQ);
      setSessionStatus(newStatus);

      // Transition to ready after brief adapting display
      setTimeout(() => {
        if (setInterviewState) setInterviewState('ready');
      }, 800);

      if (newStatus === 'completed' || newStatus === 'finished' || !nextQ) {
        if (result?.report || result?.final_report) {
          onInterviewEnd({
            report: result?.report ?? result?.final_report,
            journeyData: journeyRef.current,
            competencyEvidence,
          });
          return;
        }
      }
    } catch (err) {
      setSubmitError(err.message || 'Failed to submit answer.');
      setInterviewState('ready');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEnd() {
    if (ending) return;
    const confirmed = window.confirm('Are you sure you want to end this interview?');
    if (!confirmed) return;
    setEnding(true);
    setEndError(null);
    voice.stop(); // Stop speech when interview ends
    stt.stop();
    try {
      const result = await endInterview(sessionId);
      const report = result?.report ?? result?.final_report ?? result?.interview_report ?? result;
      onInterviewEnd({
        report,
        journeyData: journeyRef.current,
        competencyEvidence,
      });
    } catch (err) {
      setEndError(err.message || 'Failed to end interview.');
      setEnding(false);
    }
  }

  return (
    <div className="page page--interview">
      <InterviewHeader
        candidateName={candidate?.name}
        sessionId={sessionId}
        status={sessionStatus}
        onEnd={handleEnd}
        isEnding={ending}
      />

      <main className="interview-main" id="main-content">
        {/* Sidebar */}
        <aside className="interview-sidebar" aria-label="Interview intelligence">
          <ProgressIndicator
            current={questionNum}
            total={totalQuestions}
            intelligenceState={pipelineState}
          />

          <div className="interview-sidebar__candidate">
            <div className="sidebar-avatar" aria-hidden="true">
              {(candidate?.name || '?').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
            </div>
            <div>
              <div className="sidebar-candidate-name">{candidate?.name || 'Candidate'}</div>
              {candidate?.role && (
                <div className="sidebar-candidate-role">{candidate.role}</div>
              )}
            </div>
          </div>

          {/* Competency Evidence — real backend data with proper names */}
          {competencyStateEntries.length > 0 && (
            <div className="interview-sidebar__evidence">
              <h4 className="sidebar-section-title">Competency Evidence</h4>
              <div className="competency-evidence-list">
                {competencyStateEntries.map(([cid, state]) => (
                  <CompetencyEvidenceItem
                    key={cid}
                    competencyId={cid}
                    state={state}
                    displayName={competencyNameMap[cid] || null}
                  />
                ))}
              </div>
            </div>
          )}

          {endError && (
            <div className="error-inline" role="alert">{endError}</div>
          )}
        </aside>

        {/* Main interview area */}
        <section className="interview-content" aria-label="Current question">
          {submitting ? (
            <div className="interview-processing">
              <LoadingState message="Evaluating response…" />
              <div className="processing-steps processing-steps--card">
                <div className="processing-step processing-step--active">
                  <span className="processing-step__dot" />
                  Evaluating response…
                </div>
                <div className="processing-step">
                  <span className="processing-step__dot" />
                  Updating competency state…
                </div>
                <div className="processing-step">
                  <span className="processing-step__dot" />
                  Selecting next question…
                </div>
              </div>
            </div>
          ) : currentQuestion ? (
            <>
              {/* Voice controls with state machine */}
              <VoiceControls
                voice={voice}
                interviewState={interviewState}
              />

              <QuestionCard
                question={currentQuestion}
                questionNum={questionNum}
                questionContext={questionContext}
              />

              {/* Live Evaluation Panel — only shown when evaluation exists */}
              {evaluationPanel && (
                <div className="eval-panel" aria-label="AI evaluation and adaptive decision">
                  {evaluationPanel.evaluation && (
                    <section className="eval-panel__card eval-panel__card--evaluation">
                      <div className="eval-panel__eyebrow">AI Evaluation</div>

                      {/* Overall score */}
                      {evaluationPanel.evaluation.overall_score != null && (
                        <div className="eval-panel__overall">
                          <span className="eval-panel__overall-label">Overall</span>
                          <span className="eval-panel__overall-value">
                            {Math.round(evaluationPanel.evaluation.overall_score)}
                          </span>
                          <span className="eval-panel__overall-max">/ 100</span>
                          <div className="eval-metric__bar-track eval-metric__bar-track--overall">
                            <div
                              className="eval-metric__bar-fill"
                              style={{ width: `${Math.min(evaluationPanel.evaluation.overall_score, 100)}%` }}
                            />
                          </div>
                        </div>
                      )}

                      {/* Dimension scores with bars */}
                      <div className="eval-panel__dimensions">
                        <EvalMetric label="Conceptual" value={evaluationPanel.evaluation.conceptual_correctness_score} />
                        <EvalMetric label="Reasoning" value={evaluationPanel.evaluation.depth_reasoning_score} />
                        <EvalMetric label="Practical" value={evaluationPanel.evaluation.practical_understanding_score} />
                        <EvalMetric label="Confidence" value={evaluationPanel.evaluation.confidence_score} />
                        <EvalMetric label="Evidence" value={evaluationPanel.evaluation.evidence_score} />
                      </div>

                      {/* Strengths */}
                      {evaluationPanel.evaluation.strengths.length > 0 && (
                        <div className="eval-panel__list eval-panel__list--strengths">
                          <span className="eval-panel__list-label">Strengths</span>
                          <ul>
                            {evaluationPanel.evaluation.strengths.map((item) => (
                              <li key={item}>✓ {item}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Knowledge gaps */}
                      {evaluationPanel.gaps.length > 0 && (
                        <div className="eval-panel__list eval-panel__list--gaps">
                          <span className="eval-panel__list-label">Knowledge gaps</span>
                          <ul>
                            {evaluationPanel.gaps.map((item) => (
                              <li key={item}>→ {item}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </section>
                  )}

                  {/* Adaptive Decision */}
                  {evaluationPanel.decision && (
                    <section className="eval-panel__card eval-panel__card--decision">
                      <div className="eval-panel__eyebrow">Adaptive Decision</div>
                      {evaluationPanel.decision.action && (
                        <div className="eval-panel__decision-action">
                          {evaluationPanel.decision.action}
                        </div>
                      )}
                      {evaluationPanel.decision.reason && (
                        <details className="eval-panel__decision-details" open={false}>
                          <summary>View reasoning</summary>
                          <p className="eval-panel__decision-reason">
                            {evaluationPanel.decision.reason}
                          </p>
                        </details>
                      )}
                    </section>
                  )}
                </div>
              )}

              {submitError && (
                <div className="error-inline" role="alert">{submitError}</div>
              )}
              <AnswerInput
                value={answer}
                onChange={setAnswer}
                onSubmit={handleSubmit}
                isSubmitting={submitting}
                speechRecognition={stt}
              />
            </>
          ) : (
            <ErrorState
              title="No question available"
              message="The interview session did not return a question. This may be expected if the interview has ended."
            />
          )}
        </section>
      </main>
    </div>
  );
}

// ── Compact competency evidence item for sidebar ──
function CompetencyEvidenceItem({ competencyId, state, displayName }) {
  if (!state) return null;
  const proficiency = state.proficiency ?? 'none';
  const confidence = state.confidence ?? 0;
  const questionsAsked = state.questions_asked ?? 0;
  const evidenceNotes = Array.isArray(state.evidence_notes) ? state.evidence_notes : [];
  // Use actual competency name from plan history, not raw ID
  const name = displayName || competencyId.replace(/[-_]/g, ' ');

  return (
    <details className="competency-evidence-item">
      <summary className="competency-evidence-item__summary">
        <span className="competency-evidence-item__name" title={name}>{name}</span>
        <span className={`competency-evidence-item__prof prof--${proficiency}`}>
          {proficiency}
        </span>
      </summary>
      <div className="competency-evidence-item__body">
        <div className="competency-evidence-item__stats">
          <span>{questionsAsked} question{questionsAsked !== 1 ? 's' : ''}</span>
          <span>{Math.round(confidence * 100)}% confidence</span>
        </div>
        {evidenceNotes.length > 0 && (
          <ul className="competency-evidence-item__notes">
            {evidenceNotes.slice(-2).map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}

// ── Evaluation metric with bar ──
function EvalMetric({ label, value }) {
  if (value == null || typeof value !== 'number') return null;
  const rounded = Math.round(value);
  return (
    <div className="eval-metric">
      <span className="eval-metric__label">{label}</span>
      <div className="eval-metric__bar-track">
        <div
          className="eval-metric__bar-fill"
          style={{ width: `${Math.min(rounded, 100)}%` }}
        />
      </div>
      <span className="eval-metric__value">{rounded}</span>
    </div>
  );
}

// ── Helper: build question context from real session metadata ──
function buildQuestionContext({
  activeQuestionPlan,
  previousEvaluationTrace,
  lastDecision,
  nextQuestionReason,
  currentQuestion,
  lastEvaluation,
}) {
  if (!activeQuestionPlan && !previousEvaluationTrace && !lastDecision && !nextQuestionReason) {
    return null;
  }

  const previousPlan = previousEvaluationTrace?.question_plan ?? null;
  const difficulty = activeQuestionPlan?.target_difficulty ?? null;
  const previousDifficulty = previousPlan?.target_difficulty ?? null;
  const difficultyTransition = previousDifficulty && difficulty
    ? `${formatDifficulty(previousDifficulty)} → ${formatDifficulty(difficulty)}`
    : formatDifficulty(difficulty);

  // Build previous scores from real evaluation data
  const prevEval = previousEvaluationTrace?.evaluation ?? lastEvaluation ?? null;
  const previousScores = prevEval ? {
    conceptual: prevEval.conceptual_correctness_score ?? null,
    reasoning: prevEval.depth_reasoning_score ?? null,
    practical: prevEval.practical_understanding_score ?? null,
  } : null;
  // Only include if at least one score exists
  const hasScores = previousScores && Object.values(previousScores).some(v => v != null);

  return {
    competencyTitle:
      activeQuestionPlan?.topic_context ??
      activeQuestionPlan?.objective ??
      activeQuestionPlan?.competency_id ??
      null,
    competencyId: activeQuestionPlan?.competency_id ?? null,
    difficulty,
    difficultyLabel: difficultyTransition,
    questionType: activeQuestionPlan?.question_type ?? null,
    adaptiveAction: lastDecision?.action ?? null,
    target: activeQuestionPlan?.topic_context ?? activeQuestionPlan?.objective ?? null,
    selectionReasoning: activeQuestionPlan?.selection_reasoning ?? null,
    previousSignal: previousEvaluationTrace?.evaluation?.rationale ?? previousEvaluationTrace?.evaluation?.feedback ?? null,
    previousStrengths: previousEvaluationTrace?.strengths ?? [],
    previousWeaknesses: previousEvaluationTrace?.weaknesses ?? [],
    previousMissingConcepts: previousEvaluationTrace?.missing_concepts ?? [],
    previousScores: hasScores ? previousScores : null,
    nextQuestionReason,
    currentQuestion,
  };
}

// ── Helper: build evaluation panel data from real backend data ──
function buildEvaluationPanelData({
  lastEvaluation,
  lastDecision,
  nextQuestionReason,
  previousEvaluationTrace,
  activeQuestionPlan,
}) {
  if (!lastEvaluation && !lastDecision && !nextQuestionReason) {
    return null;
  }

  const evaluation = lastEvaluation
    ? {
        overall_score: lastEvaluation.overall_score ?? null,
        conceptual_correctness_score: lastEvaluation.conceptual_correctness_score ?? null,
        depth_reasoning_score: lastEvaluation.depth_reasoning_score ?? null,
        practical_understanding_score: lastEvaluation.practical_understanding_score ?? null,
        confidence_score: lastEvaluation.confidence_score ?? null,
        evidence_score: lastEvaluation.evidence_score ?? null,
        strengths: Array.isArray(lastEvaluation.strengths) ? lastEvaluation.strengths : [],
        weaknesses: Array.isArray(lastEvaluation.weaknesses) ? lastEvaluation.weaknesses : [],
        missing_concepts: Array.isArray(lastEvaluation.missing_concepts) ? lastEvaluation.missing_concepts : [],
      }
    : null;

  const gaps = [];
  if (evaluation?.weaknesses?.length) gaps.push(...evaluation.weaknesses);
  if (evaluation?.missing_concepts?.length) gaps.push(...evaluation.missing_concepts);
  if (!gaps.length && previousEvaluationTrace?.evaluation?.follow_up_needed) {
    gaps.push('Follow-up was needed based on the previous evaluation.');
  }

  const decisionAction = lastDecision?.action ? formatAdaptiveAction(lastDecision.action) : null;
  const reason = nextQuestionReason || lastDecision?.reasoning || previousEvaluationTrace?.evaluation?.rationale || null;

  return {
    evaluation,
    decision: {
      action: decisionAction,
      reason,
      target: activeQuestionPlan?.topic_context ?? activeQuestionPlan?.objective ?? null,
    },
    gaps,
  };
}

function formatDifficulty(value) {
  if (!value) return null;
  return String(value).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatAdaptiveAction(value) {
  if (!value) return null;
  const map = {
    continue_same_topic: 'Continue Topic',
    increase_difficulty: 'Increase Difficulty',
    decrease_difficulty: 'Decrease Difficulty',
    switch_topic: 'Switch Competency',
    deep_dive: 'Probe Weakness',
    conclude_interview: 'Conclude Interview',
  };
  return map[value] ?? String(value).replace(/_/g, ' ');
}
