import React, { useState } from 'react';
import InterviewHeader from '../components/InterviewHeader';
import QuestionCard from '../components/QuestionCard';
import AnswerInput from '../components/AnswerInput';
import ProgressIndicator from '../components/ProgressIndicator';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { submitAnswer, endInterview } from '../services/api';

/**
 * Interview — Page 3.
 * The main active interview screen.
 *
 * Props:
 *   session           (object) — interview session returned by startInterview
 *   candidate         (object) — candidate data
 *   onInterviewEnd    (fn)     — called with the final report when interview ends
 */
export default function Interview({ session, candidate, onInterviewEnd }) {
  // The current question lives either in the session directly or nested
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

  const sessionId = session?.session_id ?? session?.id;

  async function handleSubmit() {
    if (!answer.trim() || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await submitAnswer(sessionId, answer);
      setAnswer('');

      // Extract next question from response — tolerant of varying shapes
      const nextQ =
        result?.current_question ??
        result?.question ??
        result?.next_question ??
        null;

      const nextNum =
        result?.question_number ??
        result?.current_question_number ??
        questionNum + 1;

      const totalQ =
        result?.total_questions ??
        result?.question_count ??
        totalQuestions;

      const newStatus = result?.status ?? sessionStatus;

      setCurrentQuestion(nextQ);
      setQuestionNum(nextNum);
      setTotalQuestions(totalQ);
      setSessionStatus(newStatus);

      // If backend signals interview is complete
      if (
        newStatus === 'completed' ||
        newStatus === 'finished' ||
        !nextQ
      ) {
        // Trigger end if session is done but no explicit end was requested
        if (result?.report || result?.final_report) {
          onInterviewEnd(result?.report ?? result?.final_report);
          return;
        }
      }
    } catch (err) {
      setSubmitError(err.message || 'Failed to submit answer.');
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
    try {
      const result = await endInterview(sessionId);
      const report =
        result?.report ??
        result?.final_report ??
        result?.interview_report ??
        result;
      onInterviewEnd(report);
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
        <aside className="interview-sidebar" aria-label="Interview progress">
          <ProgressIndicator current={questionNum} total={totalQuestions} />

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

          {/* Future: Adaptive decision trace */}
          <div className="interview-sidebar__adaptive">
            <h4 className="sidebar-section-title">Interview Intelligence</h4>
            <div className="adaptive-trace">
              <div className="adaptive-trace__step adaptive-trace__step--active">
                <span className="adaptive-trace__dot" aria-hidden="true" />
                <span>Candidate profile analyzed</span>
              </div>
              <div className={`adaptive-trace__step ${questionNum > 1 ? 'adaptive-trace__step--active' : ''}`}>
                <span className="adaptive-trace__dot" aria-hidden="true" />
                <span>Competencies mapped</span>
              </div>
              <div className={`adaptive-trace__step ${submitting ? 'adaptive-trace__step--processing' : questionNum > 1 ? 'adaptive-trace__step--active' : ''}`}>
                <span className="adaptive-trace__dot" aria-hidden="true" />
                <span>Response evaluated</span>
              </div>
              <div className={`adaptive-trace__step ${submitting ? 'adaptive-trace__step--processing' : ''}`}>
                <span className="adaptive-trace__dot" aria-hidden="true" />
                <span>Next question selected</span>
              </div>
            </div>
          </div>

          {endError && (
            <div className="error-inline" role="alert">{endError}</div>
          )}
        </aside>

        {/* Main interview area */}
        <section className="interview-content" aria-label="Current question">
          {submitting ? (
            <div className="interview-processing">
              <LoadingState message="Analyzing response…" />
              <div className="processing-steps processing-steps--card">
                <div className="processing-step processing-step--active">
                  <span className="processing-step__dot" />
                  Evaluating your response…
                </div>
                <div className="processing-step">
                  <span className="processing-step__dot" />
                  Selecting your next question…
                </div>
              </div>
            </div>
          ) : currentQuestion ? (
            <>
              <QuestionCard question={currentQuestion} questionNum={questionNum} />
              {submitError && (
                <div className="error-inline" role="alert">{submitError}</div>
              )}
              <AnswerInput
                value={answer}
                onChange={setAnswer}
                onSubmit={handleSubmit}
                isSubmitting={submitting}
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
