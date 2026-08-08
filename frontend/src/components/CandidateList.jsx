import React from 'react';
import CandidateCard from './CandidateCard';

/**
 * CandidateList — Renders the full grid of candidate cards.
 * Props:
 *   candidates (array) — list of candidate objects
 *   onSelect   (fn)    — called when a candidate is selected
 */
export default function CandidateList({ candidates = [], onSelect }) {
  if (candidates.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon" aria-hidden="true">👤</div>
        <h3 className="empty-state__title">No candidates found</h3>
        <p className="empty-state__desc">
          No candidates are registered in the system yet.
        </p>
      </div>
    );
  }

  return (
    <div className="candidate-list" role="list" aria-label="Candidate list">
      {candidates.map((c) => (
        <CandidateCard
          key={c.candidate_id ?? c.id ?? Math.random()}
          candidate={c}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
