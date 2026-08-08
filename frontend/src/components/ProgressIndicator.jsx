import React from 'react';

/**
 * ProgressIndicator — Shows question number and progress through the interview.
 * Props:
 *   current (number) — current question number (1-indexed)
 *   total   (number) — total number of questions (optional)
 */
export default function ProgressIndicator({ current = 1, total }) {
  const percentage = total && total > 0 ? Math.min((current / total) * 100, 100) : null;

  return (
    <div className="progress-indicator" aria-label={`Question ${current}${total ? ` of ${total}` : ''}`}>
      <div className="progress-indicator__label">
        <span className="progress-indicator__q-label">Question</span>
        <span className="progress-indicator__count">
          {current}
          {total ? <span className="progress-indicator__total"> / {total}</span> : ''}
        </span>
      </div>
      {percentage !== null && (
        <div className="progress-bar" role="progressbar" aria-valuenow={current} aria-valuemin={1} aria-valuemax={total}>
          <div className="progress-bar__fill" style={{ width: `${percentage}%` }} />
        </div>
      )}
    </div>
  );
}
