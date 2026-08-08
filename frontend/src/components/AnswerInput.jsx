import React from 'react';

/**
 * AnswerInput — Text area for the candidate to type their answer.
 * Props:
 *   value       (string)   — controlled value
 *   onChange    (fn)       — change handler
 *   onSubmit    (fn)       — submit handler
 *   isSubmitting (bool)    — disables input/button while processing
 *   processingLabel (string) — custom label shown while processing
 */
export default function AnswerInput({
  value,
  onChange,
  onSubmit,
  isSubmitting = false,
  processingLabel = 'Analyzing response…',
}) {
  function handleKeyDown(e) {
    // Ctrl+Enter or Cmd+Enter to submit
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (!isSubmitting && value?.trim()) onSubmit();
    }
  }

  return (
    <div className="answer-input">
      <label htmlFor="answer-textarea" className="answer-input__label">
        Your Answer
        <span className="answer-input__hint">Ctrl + Enter to submit</span>
      </label>

      {isSubmitting ? (
        <div className="answer-input__processing" aria-live="polite">
          <div className="processing-steps">
            <div className="processing-step processing-step--active">
              <span className="processing-step__dot" aria-hidden="true" />
              <span>Evaluating your response…</span>
            </div>
            <div className="processing-step">
              <span className="processing-step__dot" aria-hidden="true" />
              <span>Selecting your next question…</span>
            </div>
          </div>
        </div>
      ) : (
        <textarea
          id="answer-textarea"
          className="answer-input__textarea"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your answer here…"
          rows={7}
          disabled={isSubmitting}
          aria-required="true"
          aria-label="Answer field"
        />
      )}

      <div className="answer-input__footer">
        {!isSubmitting && (
          <span className="answer-input__char-count">
            {value?.length || 0} characters
          </span>
        )}
        <button
          id="submit-answer-btn"
          className="btn btn--primary btn--lg"
          onClick={onSubmit}
          disabled={isSubmitting || !value?.trim()}
          aria-label="Submit answer"
        >
          {isSubmitting ? processingLabel : 'Submit Answer'}
        </button>
      </div>
    </div>
  );
}
