import React from 'react';

/**
 * LoadingState — Full-page or inline loading indicator.
 * Props:
 *   message (string) — optional message to display
 *   inline  (bool)   — if true, renders a smaller inline variant
 */
export default function LoadingState({ message = 'Loading…', inline = false }) {
  if (inline) {
    return (
      <div className="loading-inline" aria-live="polite" aria-busy="true">
        <span className="spinner spinner--sm" />
        <span className="loading-inline__text">{message}</span>
      </div>
    );
  }

  return (
    <div className="loading-full" aria-live="polite" aria-busy="true">
      <div className="loading-full__inner">
        <span className="spinner" />
        <p className="loading-full__message">{message}</p>
      </div>
    </div>
  );
}
