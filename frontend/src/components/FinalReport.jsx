import React from 'react';

/**
 * FinalReport — Displays the final interview evaluation report.
 * Tolerates missing optional fields gracefully.
 * Props:
 *   report (object) — final report data from backend
 */
export default function FinalReport({ report }) {
  if (!report) return null;

  const {
    overall_score,
    score,
    recommendation,
    status,
    interview_status,
    strengths,
    areas_for_improvement,
    improvements,
    summary,
    interview_summary,
    competency_scores,
    competencies,
  } = report;

  const displayScore = overall_score ?? score ?? null;
  const displayRec = recommendation ?? null;
  const displayStatus = status ?? interview_status ?? null;
  const displaySummary = summary ?? interview_summary ?? null;
  const displayStrengths = strengths ?? [];
  const displayImprovements = areas_for_improvement ?? improvements ?? [];
  const displayCompetencies = competency_scores ?? competencies ?? [];

  const scorePercent = typeof displayScore === 'number'
    ? Math.min(Math.max(displayScore, 0), 100)
    : null;

  const scoreColor =
    scorePercent >= 75 ? 'var(--success)' :
    scorePercent >= 50 ? 'var(--warning)' :
    'var(--danger)';

  return (
    <div className="final-report">
      {/* Score + Recommendation */}
      <div className="report-hero">
        {scorePercent !== null && (
          <div className="score-ring" aria-label={`Overall score: ${scorePercent}`}>
            <svg viewBox="0 0 100 100" className="score-ring__svg">
              <circle className="score-ring__track" cx="50" cy="50" r="42" />
              <circle
                className="score-ring__fill"
                cx="50"
                cy="50"
                r="42"
                style={{
                  stroke: scoreColor,
                  strokeDashoffset: `${264 - (264 * scorePercent) / 100}`,
                }}
              />
            </svg>
            <div className="score-ring__label">
              <span className="score-ring__value">{scorePercent}</span>
              <span className="score-ring__unit">/ 100</span>
            </div>
          </div>
        )}
        <div className="report-hero__meta">
          <h2 className="report-hero__title">Interview Complete</h2>
          {displayStatus && (
            <span className="status-badge">{displayStatus}</span>
          )}
          {displayRec && (
            <div className="report-recommendation">
              <span className="report-recommendation__label">Recommendation</span>
              <span className="report-recommendation__value">{displayRec}</span>
            </div>
          )}
          {displaySummary && (
            <p className="report-summary">{displaySummary}</p>
          )}
        </div>
      </div>

      {/* Competency Scores */}
      {displayCompetencies.length > 0 && (
        <section className="report-section" aria-label="Competency scores">
          <h3 className="report-section__title">Competency Scores</h3>
          <div className="competency-bars">
            {displayCompetencies.map((item, i) => {
              const compName = item.name ?? item.competency ?? `Competency ${i + 1}`;
              const compScore = item.score ?? item.value ?? null;
              const pct = typeof compScore === 'number' ? Math.min(Math.max(compScore, 0), 100) : null;
              return (
                <div key={i} className="competency-bar-row">
                  <span className="competency-bar-row__name">{compName}</span>
                  <div className="competency-bar-row__track" aria-label={`${compName}: ${pct ?? '—'}`}>
                    {pct !== null && (
                      <div
                        className="competency-bar-row__fill"
                        style={{ width: `${pct}%` }}
                      />
                    )}
                  </div>
                  <span className="competency-bar-row__score">
                    {pct !== null ? pct : '—'}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Strengths + Areas for Improvement */}
      <div className="report-feedback-grid">
        {displayStrengths.length > 0 && (
          <section className="report-section report-section--strengths" aria-label="Strengths">
            <h3 className="report-section__title">Strengths</h3>
            <ul className="feedback-list feedback-list--positive">
              {displayStrengths.map((s, i) => (
                <li key={i} className="feedback-list__item">
                  <span className="feedback-list__icon" aria-hidden="true">✓</span>
                  {typeof s === 'string' ? s : s.text ?? s.description ?? JSON.stringify(s)}
                </li>
              ))}
            </ul>
          </section>
        )}

        {displayImprovements.length > 0 && (
          <section className="report-section report-section--improvements" aria-label="Areas for improvement">
            <h3 className="report-section__title">Areas for Improvement</h3>
            <ul className="feedback-list feedback-list--neutral">
              {displayImprovements.map((item, i) => (
                <li key={i} className="feedback-list__item">
                  <span className="feedback-list__icon" aria-hidden="true">→</span>
                  {typeof item === 'string' ? item : item.text ?? item.description ?? JSON.stringify(item)}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
