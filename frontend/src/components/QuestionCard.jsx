import React from 'react';

const DIFFICULTY_MAP = {
  easy: { label: 'Easy', cls: 'difficulty--easy' },
  medium: { label: 'Medium', cls: 'difficulty--medium' },
  hard: { label: 'Hard', cls: 'difficulty--hard' },
  beginner: { label: 'Beginner', cls: 'difficulty--easy' },
  foundational: { label: 'Foundational', cls: 'difficulty--easy' },
  intermediate: { label: 'Intermediate', cls: 'difficulty--medium' },
  advanced: { label: 'Advanced', cls: 'difficulty--hard' },
  expert: { label: 'Expert', cls: 'difficulty--expert' },
};

const ACTION_LABELS = {
  continue_same_topic: { label: 'Continue Topic', cls: 'action-badge--continue' },
  increase_difficulty: { label: 'Increase Difficulty', cls: 'action-badge--increase' },
  decrease_difficulty: { label: 'Decrease Difficulty', cls: 'action-badge--decrease' },
  switch_topic: { label: 'Switch Competency', cls: 'action-badge--switch' },
  deep_dive: { label: 'Probe Weakness', cls: 'action-badge--probe' },
  conclude_interview: { label: 'Concluding', cls: 'action-badge--conclude' },
};

/**
 * QuestionCard — Displays the current interview question with adaptive context.
 *
 * Props:
 *   question       (object|string) — question data from backend
 *   questionNum    (number)        — current question number
 *   questionContext (object)       — adaptive context built from session metadata
 */
export default function QuestionCard({ question, questionNum, questionContext = null }) {
  if (!question) return null;

  // Backend may return question as a string or structured object
  const questionText =
    typeof question === 'string'
      ? question
      : question.text || question.question || question.content || '';

  const questionType = question?.type || question?.question_type || null;
  const difficulty = question?.difficulty || null;
  const topic = question?.topic || question?.competency || null;

  const difficultyInfo = difficulty
    ? DIFFICULTY_MAP[difficulty.toLowerCase()] || { label: difficulty, cls: 'difficulty--medium' }
    : null;

  const competencyTitle = questionContext?.competencyTitle ?? topic ?? null;
  const competencyDifficulty = questionContext?.difficultyLabel ?? difficultyInfo?.label ?? null;
  const adaptiveAction = questionContext?.adaptiveAction ?? null;
  const selectionReasoning = questionContext?.selectionReasoning ?? null;
  const nextQuestionReason = questionContext?.nextQuestionReason ?? null;
  const previousSignal = questionContext?.previousSignal ?? null;
  const target = questionContext?.target ?? competencyTitle ?? null;
  const previousStrengths = Array.isArray(questionContext?.previousStrengths) ? questionContext.previousStrengths : [];
  const previousWeaknesses = Array.isArray(questionContext?.previousWeaknesses) ? questionContext.previousWeaknesses : [];
  const previousMissingConcepts = Array.isArray(questionContext?.previousMissingConcepts) ? questionContext.previousMissingConcepts : [];
  const previousScores = questionContext?.previousScores ?? null;

  const actionInfo = adaptiveAction ? ACTION_LABELS[adaptiveAction] || null : null;

  const whyQuestionEntries = [
    selectionReasoning && { label: 'Selection reasoning', value: selectionReasoning },
    adaptiveAction && actionInfo && { label: 'Adaptive action', value: actionInfo.label },
    competencyDifficulty && { label: 'Difficulty', value: competencyDifficulty },
    target && { label: 'Target competency', value: target },
  ].filter(Boolean);

  const hasExpandableContent =
    whyQuestionEntries.length > 0 ||
    previousStrengths.length > 0 ||
    previousWeaknesses.length > 0 ||
    previousMissingConcepts.length > 0 ||
    previousScores ||
    nextQuestionReason;

  return (
    <div className="question-card" aria-label={`Question ${questionNum}`}>
      {/* Meta badges row */}
      <div className="question-card__meta">
        <span className="adaptive-indicator" aria-label="Adaptive interview">
          <span className="adaptive-indicator__dot" aria-hidden="true" />
          Adaptive
        </span>
        {actionInfo && (
          <span className={`action-badge ${actionInfo.cls}`}>
            {actionInfo.label}
          </span>
        )}
        {questionType && (
          <span className="badge badge--accent">{questionType}</span>
        )}
        {difficultyInfo && (
          <span className={`difficulty-badge ${difficultyInfo.cls}`}>
            {difficultyInfo.label}
          </span>
        )}
        {topic && (
          <span className="badge badge--neutral">{topic}</span>
        )}
      </div>

      {/* Competency + difficulty display */}
      {competencyTitle && (
        <div className="question-card__competency" aria-label="Current competency">
          <div className="question-card__competency-label">Current competency</div>
          <div className="question-card__competency-name">{competencyTitle}</div>
          {competencyDifficulty && (
            <div className="question-card__competency-difficulty">{competencyDifficulty}</div>
          )}
        </div>
      )}

      {/* Question text */}
      <div className="question-card__text">
        <p>{questionText}</p>
      </div>

      {/* Previous evaluation score badges (compact) */}
      {previousScores && (
        <div className="question-card__prev-scores" aria-label="Previous answer scores">
          <div className="question-card__prev-scores-label">Previous answer signal</div>
          <div className="score-chips">
            {previousScores.conceptual != null && (
              <span className={`score-chip ${scoreChipClass(previousScores.conceptual)}`}>
                Conceptual: {Math.round(previousScores.conceptual)}
              </span>
            )}
            {previousScores.reasoning != null && (
              <span className={`score-chip ${scoreChipClass(previousScores.reasoning)}`}>
                Reasoning: {Math.round(previousScores.reasoning)}
              </span>
            )}
            {previousScores.practical != null && (
              <span className={`score-chip ${scoreChipClass(previousScores.practical)}`}>
                Practical: {Math.round(previousScores.practical)}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Context from backend */}
      {question?.context && (
        <div className="question-card__context">
          <span className="question-card__context-label">Context</span>
          <p>{question.context}</p>
        </div>
      )}

      {/* Why this question? — expandable */}
      {hasExpandableContent && (
        <details className="question-card__why" open={false}>
          <summary className="question-card__why-summary">Why this question?</summary>
          <div className="question-card__why-body">
            {whyQuestionEntries.length > 0 && (
              <dl className="question-card__why-list">
                {whyQuestionEntries.map((item) => (
                  <React.Fragment key={item.label}>
                    <dt>{item.label}</dt>
                    <dd>{item.value}</dd>
                  </React.Fragment>
                ))}
              </dl>
            )}

            {nextQuestionReason && (
              <div className="question-card__why-reason">
                <div className="question-card__why-subtitle">Adaptive reasoning</div>
                <p>{nextQuestionReason}</p>
              </div>
            )}

            {previousSignal && (
              <div className="question-card__why-reason">
                <div className="question-card__why-subtitle">Previous evaluation</div>
                <p>{previousSignal}</p>
              </div>
            )}

            {(previousStrengths.length > 0 || previousWeaknesses.length > 0 || previousMissingConcepts.length > 0) && (
              <div className="question-card__why-signals">
                {previousStrengths.length > 0 && (
                  <div>
                    <div className="question-card__why-subtitle">Previous strengths</div>
                    <ul>
                      {previousStrengths.slice(0, 3).map((item) => (
                        <li key={item}>✓ {item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {previousWeaknesses.length > 0 && (
                  <div>
                    <div className="question-card__why-subtitle">Previous weaknesses</div>
                    <ul>
                      {previousWeaknesses.slice(0, 3).map((item) => (
                        <li key={item}>→ {item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {previousMissingConcepts.length > 0 && (
                  <div>
                    <div className="question-card__why-subtitle">Missing concepts</div>
                    <ul>
                      {previousMissingConcepts.slice(0, 3).map((item) => (
                        <li key={item}>○ {item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

function scoreChipClass(score) {
  if (typeof score !== 'number') return '';
  if (score >= 70) return 'score-chip--strong';
  if (score >= 40) return 'score-chip--moderate';
  return 'score-chip--weak';
}
