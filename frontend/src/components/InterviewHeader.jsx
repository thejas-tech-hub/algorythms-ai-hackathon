import React from 'react';

/**
 * InterviewHeader — Top bar shown during the active interview.
 * Props:
 *   candidateName (string) — name of the candidate
 *   sessionId     (string) — interview session ID
 *   status        (string) — interview status from backend
 *   onEnd         (fn)     — called when user clicks End Interview
 *   isEnding      (bool)   — disables button while ending
 */
export default function InterviewHeader({
  candidateName,
  sessionId,
  status,
  onEnd,
  isEnding = false,
}) {
  return (
    <header className="interview-header" role="banner">
      <div className="interview-header__left">
        <div className="interview-header__brand">
          <span className="brand-dot" aria-hidden="true" />
          <span className="interview-header__app-name">Adaptive AI Interview</span>
        </div>
        {candidateName && (
          <div className="interview-header__candidate">
            <span className="interview-header__candidate-name">{candidateName}</span>
            {sessionId && (
              <span className="interview-header__session" aria-label="Session ID">
                Session: {sessionId}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="interview-header__right">
        {status && (
          <span className={`status-badge status-badge--${(status || '').toLowerCase().replace(/\s+/g, '-')}`}>
            {status}
          </span>
        )}
        <button
          className="btn btn--danger"
          onClick={onEnd}
          disabled={isEnding}
          id="end-interview-btn"
          aria-label="End interview session"
        >
          {isEnding ? 'Ending…' : 'End Interview'}
        </button>
      </div>
    </header>
  );
}
