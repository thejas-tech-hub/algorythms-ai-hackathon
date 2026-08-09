import React from 'react';

/**
 * ProgressIndicator — Shows question progress and live interview intelligence.
 *
 * Displays real backend data: competency count, evidence count,
 * proficiency level, adaptive strategy. Never fabricates values.
 *
 * Props:
 *   current          (number) — current question number (1-indexed)
 *   total            (number) — total number of questions (optional)
 *   intelligenceState (object) — live pipeline state from session metadata
 */
export default function ProgressIndicator({ current = 1, total, intelligenceState = {} }) {
  const percentage = total && total > 0 ? Math.min((current / total) * 100, 100) : null;
  const isSubmitting = Boolean(intelligenceState.isSubmitting);
  const hasEvaluation = Boolean(intelligenceState.hasEvaluation);
  const hasDecision = Boolean(intelligenceState.hasDecision);

  // Real data from session metadata
  const competencyCount = intelligenceState.competencyCount ?? null;
  const evidenceCount = intelligenceState.evidenceCount ?? null;
  const currentProficiency = intelligenceState.currentProficiency ?? null;
  const adaptiveStrategy = intelligenceState.adaptiveStrategy ?? null;

  const steps = [
    {
      key: 'profile',
      label: 'Candidate profile',
      detail: 'Analyzed',
      state: 'complete',
    },
    {
      key: 'competencies',
      label: 'Competency map',
      detail: competencyCount != null ? `${competencyCount} competencies` : 'Mapped',
      state: 'complete',
    },
    {
      key: 'evidence',
      label: 'Evidence',
      detail: isSubmitting
        ? 'Evaluating…'
        : evidenceCount != null
          ? `${evidenceCount} response${evidenceCount !== 1 ? 's' : ''}`
          : hasEvaluation ? 'Collected' : 'Pending',
      state: isSubmitting ? 'active' : hasEvaluation ? 'complete' : 'pending',
    },
    {
      key: 'assessment',
      label: 'Current assessment',
      detail: currentProficiency
        ? formatProficiency(currentProficiency)
        : hasEvaluation ? 'Assessed' : 'Pending',
      state: hasEvaluation ? 'complete' : 'pending',
    },
    {
      key: 'strategy',
      label: 'Adaptive strategy',
      detail: isSubmitting
        ? 'Deciding…'
        : adaptiveStrategy
          ? formatAction(adaptiveStrategy)
          : hasDecision ? 'Decided' : 'Pending',
      state: isSubmitting ? 'processing' : hasDecision ? 'complete' : 'pending',
    },
    {
      key: 'next-question',
      label: 'Next question',
      detail: isSubmitting ? 'Selecting…' : hasDecision ? 'Selected' : 'Pending',
      state: isSubmitting ? 'processing' : hasDecision ? 'complete' : 'pending',
    },
  ];

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

      <div className="progress-indicator__pipeline" aria-label="Interview intelligence lifecycle">
        {steps.map((step) => (
          <div key={step.key} className={`progress-indicator__step progress-indicator__step--${step.state}`}>
            <span className="progress-indicator__dot" aria-hidden="true" />
            <div className="progress-indicator__step-content">
              <span className="progress-indicator__step-label">{step.label}</span>
              <span className="progress-indicator__step-detail">{step.detail}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatProficiency(value) {
  if (!value) return null;
  return String(value).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatAction(value) {
  if (!value) return null;
  const map = {
    continue_same_topic: 'Continue topic',
    increase_difficulty: 'Increase difficulty',
    decrease_difficulty: 'Decrease difficulty',
    switch_topic: 'Switch competency',
    deep_dive: 'Probe weakness',
    conclude_interview: 'Conclude',
  };
  return map[value] ?? String(value).replace(/_/g, ' ');
}
