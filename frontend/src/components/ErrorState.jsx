import React from 'react';

/**
 * ErrorState — Displays a user-friendly error message.
 * Props:
 *   title   (string)   — optional title
 *   message (string)   — error message to display
 *   onRetry (function) — optional retry callback
 */
export default function ErrorState({
  title = 'Something went wrong',
  message = 'An unexpected error occurred.',
  onRetry,
}) {
  return (
    <div className="error-state" role="alert">
      <div className="error-state__icon" aria-hidden="true">⚠</div>
      <h3 className="error-state__title">{title}</h3>
      <p className="error-state__message">{message}</p>
      {onRetry && (
        <button className="btn btn--secondary" onClick={onRetry}>
          Try Again
        </button>
      )}
    </div>
  );
}
