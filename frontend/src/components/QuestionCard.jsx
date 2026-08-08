import React from 'react';

const DIFFICULTY_MAP = {
  easy: { label: 'Easy', cls: 'difficulty--easy' },
  medium: { label: 'Medium', cls: 'difficulty--medium' },
  hard: { label: 'Hard', cls: 'difficulty--hard' },
  beginner: { label: 'Beginner', cls: 'difficulty--easy' },
  intermediate: { label: 'Intermediate', cls: 'difficulty--medium' },
  advanced: { label: 'Advanced', cls: 'difficulty--hard' },
};

/**
 * QuestionCard — Displays the current interview question.
 * Props:
 *   question    (object|string) — question data from backend
 *   questionNum (number)        — current question number
 */
export default function QuestionCard({ question, questionNum }) {
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

  return (
    <div className="question-card" aria-label={`Question ${questionNum}`}>
      <div className="question-card__meta">
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
        <span className="adaptive-indicator" aria-label="Adaptive interview">
          <span className="adaptive-indicator__dot" aria-hidden="true" />
          Adaptive
        </span>
      </div>

      <div className="question-card__text">
        <p>{questionText}</p>
      </div>

      {/* Future: question plan metadata from backend */}
      {question?.context && (
        <div className="question-card__context">
          <span className="question-card__context-label">Context</span>
          <p>{question.context}</p>
        </div>
      )}
    </div>
  );
}
