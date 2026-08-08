import React from 'react';

/**
 * CandidateOverview — Summary panel shown during interview preparation.
 * Tolerates missing optional fields gracefully.
 * Props:
 *   candidate (object) — candidate data from backend
 */
export default function CandidateOverview({ candidate }) {
  if (!candidate) return null;

  const {
    candidate_id,
    name,
    role,
    experience,
    education,
    training,
    profile,
    competencies,
  } = candidate;

  const initials = name
    ? name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : '?';

  return (
    <div className="candidate-overview">
      <div className="candidate-overview__header">
        <div className="candidate-overview__avatar" aria-hidden="true">
          {initials}
        </div>
        <div>
          <h2 className="candidate-overview__name">{name || 'Unknown Candidate'}</h2>
          {role && <p className="candidate-overview__role">{role}</p>}
          {candidate_id && (
            <span className="badge badge--neutral" aria-label="Candidate ID">
              ID: {candidate_id}
            </span>
          )}
        </div>
      </div>

      <div className="candidate-overview__grid">
        {experience && (
          <div className="info-block">
            <span className="info-block__label">Experience</span>
            <span className="info-block__value">{experience}</span>
          </div>
        )}
        {education && (
          <div className="info-block">
            <span className="info-block__label">Education</span>
            <span className="info-block__value">{education}</span>
          </div>
        )}
        {training && (
          <div className="info-block">
            <span className="info-block__label">Training</span>
            <span className="info-block__value">{training}</span>
          </div>
        )}
        {profile && (
          <div className="info-block info-block--wide">
            <span className="info-block__label">Profile</span>
            <span className="info-block__value">{profile}</span>
          </div>
        )}
      </div>

      {/* Future: Competency intelligence from backend */}
      {competencies && Array.isArray(competencies) && competencies.length > 0 && (
        <div className="candidate-overview__competencies">
          <h4 className="competencies__label">Candidate Intelligence</h4>
          <div className="competencies__list">
            {competencies.map((c, i) => (
              <div key={i} className="competency-chip">
                <span className="competency-chip__name">{c.name || c}</span>
                {c.level && (
                  <span className={`competency-chip__level competency-chip__level--${c.level.toLowerCase()}`}>
                    {c.level}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
