import React from 'react';

/**
 * CandidateCard — Displays a single candidate in the selection list.
 * Props:
 *   candidate (object) — candidate data from backend
 *   onSelect  (fn)     — called when user clicks Select
 */
export default function CandidateCard({ candidate, onSelect }) {
  const {
    candidate_id,
    name,
    role,
    experience,
    education,
    training,
  } = candidate || {};

  const initials = name
    ? name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : '?';

  return (
    <article className="candidate-card" tabIndex={0} aria-label={`Candidate: ${name || candidate_id}`}>
      <div className="candidate-card__avatar" aria-hidden="true">
        {initials}
      </div>
      <div className="candidate-card__body">
        <h3 className="candidate-card__name">{name || '—'}</h3>
        {role && <p className="candidate-card__role">{role}</p>}
        <div className="candidate-card__meta">
          {candidate_id && (
            <span className="badge badge--neutral">ID: {candidate_id}</span>
          )}
          {experience && (
            <span className="badge badge--neutral">{experience}</span>
          )}
          {education && (
            <span className="badge badge--neutral">{education}</span>
          )}
          {training && (
            <span className="badge badge--accent">{training}</span>
          )}
        </div>
      </div>
      <div className="candidate-card__action">
        <button
          className="btn btn--primary"
          onClick={() => onSelect(candidate)}
          aria-label={`Select candidate ${name || candidate_id}`}
          id={`select-candidate-${candidate_id}`}
        >
          Select
        </button>
      </div>
    </article>
  );
}
