import React from 'react';

/**
 * FinalReport — Candidate Intelligence Report.
 *
 * Renders the full post-interview assessment with:
 * - Hero section (score, recommendation, confidence)
 * - Distinct counts: questions presented, responses evaluated, competencies assessed
 * - Competency profile with bars, proficiency, evidence counts
 * - Strengths and areas for improvement
 * - Enhanced adaptive journey timeline (reasoning, decision per step)
 * - Executive summary and detailed feedback
 *
 * All data comes from actual backend response — nothing fabricated.
 *
 * Props:
 *   report       (object)  — final report data from backend
 *   candidate    (object)  — candidate data (name, role)
 *   journeyData  (array)   — adaptive journey steps collected during interview
 *   competencyEvidence (object) — competency states from session metadata
 */
export default function FinalReport({ report, candidate, journeyData = [], competencyEvidence = {} }) {
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
    executive_summary,
    detailed_feedback,
    competency_scores,
    competencies,
    total_questions,
    responses_evaluated,
    competencies_assessed,
    topics_covered,
    duration_seconds,
  } = report;

  const displayScore = overall_score ?? score ?? null;
  const displayRec = recommendation ?? null;
  const displayStatus = status ?? interview_status ?? null;
  const displaySummary = executive_summary ?? summary ?? interview_summary ?? null;
  const displayStrengths = strengths ?? [];
  const displayImprovements = areas_for_improvement ?? improvements ?? [];
  const displayCompetencies = competency_scores ?? competencies ?? [];
  const displayDetailedFeedback = detailed_feedback ?? null;
  const topicsCovered = topics_covered ?? [];

  // ── Derive accurate counts ──
  // questions_presented: total questions the backend asked
  const questionsPresented = total_questions ?? journeyData.length ?? null;
  // responses_evaluated: from backend or count of journey steps (evaluated responses)
  const responsesEvaluated = responses_evaluated ?? journeyData.length ?? null;
  // competencies_assessed: distinct competency IDs from evaluated responses
  const computedCompetenciesAssessed = competencies_assessed ??
    (journeyData.length > 0
      ? new Set(journeyData.map(s => s.competencyId).filter(Boolean)).size
      : displayCompetencies.length) ??
    null;

  const scorePercent = typeof displayScore === 'number'
    ? Math.min(Math.max(displayScore, 0), 100)
    : null;

  const scoreColor =
    scorePercent >= 75 ? 'var(--success)' :
    scorePercent >= 50 ? 'var(--warning)' :
    'var(--danger)';

  const recInfo = getRecommendationInfo(displayRec);

  // Determine confidence from competency data
  const avgConfidence = displayCompetencies.length > 0
    ? displayCompetencies.reduce((sum, c) => sum + (c.confidence ?? 0), 0) / displayCompetencies.length
    : null;
  const confidenceLabel = avgConfidence != null ? getConfidenceLabel(avgConfidence) : null;

  return (
    <div className="final-report">
      {/* ── Hero Section ──────────────────────────────────────── */}
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
              <span className="score-ring__value">{Math.round(scorePercent)}</span>
              <span className="score-ring__unit">/ 100</span>
            </div>
          </div>
        )}
        <div className="report-hero__meta">
          <div className="report-hero__eyebrow">Candidate Intelligence Report</div>
          <h2 className="report-hero__title">
            {candidate?.name || 'Candidate'} — Assessment Complete
          </h2>
          <div className="report-hero__badges">
            {displayRec && (
              <span className={`report-rec-badge ${recInfo.cls}`}>
                {recInfo.label}
              </span>
            )}
            {confidenceLabel && (
              <span className="report-confidence-badge">
                {confidenceLabel} confidence
              </span>
            )}
            {displayStatus && (
              <span className="status-badge">{displayStatus}</span>
            )}
          </div>
          {/* Distinct stat counts derived from actual data */}
          <div className="report-hero__stats">
            {questionsPresented != null && (
              <span className="report-stat">
                <span className="report-stat__value">{questionsPresented}</span> questions presented
              </span>
            )}
            {responsesEvaluated != null && (
              <span className="report-stat">
                <span className="report-stat__value">{responsesEvaluated}</span> responses evaluated
              </span>
            )}
            {computedCompetenciesAssessed != null && (
              <span className="report-stat">
                <span className="report-stat__value">{computedCompetenciesAssessed}</span> competencies assessed
              </span>
            )}
            {duration_seconds != null && (
              <span className="report-stat">
                <span className="report-stat__value">{formatDuration(duration_seconds)}</span>
              </span>
            )}
          </div>
          {displaySummary && (
            <p className="report-summary">{displaySummary}</p>
          )}
        </div>
      </div>

      {/* ── Competency Profile ─────────────────────────────────── */}
      {displayCompetencies.length > 0 && (
        <section className="report-section" aria-label="Competency profile">
          <h3 className="report-section__title">Competency Profile</h3>
          <div className="competency-profile">
            {displayCompetencies.map((item, i) => {
              const compName = item.name ?? item.competency ?? `Competency ${i + 1}`;
              const compScore = item.score ?? item.value ?? null;
              const pct = typeof compScore === 'number' ? Math.min(Math.max(compScore, 0), 100) : null;
              const proficiency = item.proficiency ?? null;
              const confidence = item.confidence ?? null;
              const evidenceCount = item.evidence_count ?? null;
              return (
                <div key={i} className="competency-profile-row">
                  <div className="competency-profile-row__header">
                    <span className="competency-profile-row__name">{compName}</span>
                    <span className="competency-profile-row__score">
                      {pct != null ? Math.round(pct) : '—'}
                    </span>
                  </div>
                  <div className="competency-bar-row__track" aria-label={`${compName}: ${pct ?? '—'}`}>
                    {pct != null && (
                      <div
                        className="competency-bar-row__fill"
                        style={{ width: `${pct}%` }}
                      />
                    )}
                  </div>
                  <div className="competency-profile-row__details">
                    {proficiency && (
                      <span className={`prof-chip prof--${proficiency}`}>
                        {formatProficiency(proficiency)}
                      </span>
                    )}
                    {evidenceCount != null && (
                      <span className="evidence-chip">
                        {evidenceCount} evidence pt{evidenceCount !== 1 ? 's' : ''}
                      </span>
                    )}
                    {confidence != null && (
                      <span className="confidence-chip">
                        {Math.round(confidence * 100)}% confidence
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Strengths + Areas for Improvement ──────────────────── */}
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

      {/* ── Enhanced Adaptive Journey Timeline ─────────────────── */}
      {journeyData.length > 0 && (
        <section className="report-section" aria-label="Adaptive journey">
          <h3 className="report-section__title">Adaptive Interview Journey</h3>
          <p className="report-section__subtitle">How the interview adapted to the candidate</p>
          <div className="journey-timeline">
            {journeyData.map((step, i) => (
              <div key={i} className="journey-step">
                <div className="journey-step__marker">
                  <span className="journey-step__number">Q{step.questionNumber}</span>
                  {i < journeyData.length - 1 && (
                    <span className="journey-step__connector" aria-hidden="true" />
                  )}
                </div>
                <div className="journey-step__content">
                  <div className="journey-step__header">
                    <span className="journey-step__competency">{step.competency}</span>
                    <span className={`difficulty-badge difficulty--${difficultyClass(step.difficulty)}`}>
                      {formatProficiency(step.difficulty)}
                    </span>
                    {step.score != null && (
                      <span className={`journey-step__score ${scoreClass(step.score)}`}>
                        {Math.round(step.score)}
                      </span>
                    )}
                  </div>
                  {/* Evidence: strengths + weaknesses */}
                  {(step.strengths?.length > 0 || step.weaknesses?.length > 0) && (
                    <div className="journey-step__evidence">
                      {step.strengths?.length > 0 && (
                        <div className="journey-step__strengths">
                          {step.strengths.map((s, j) => (
                            <span key={j} className="journey-chip journey-chip--strength">✓ {s}</span>
                          ))}
                        </div>
                      )}
                      {step.weaknesses?.length > 0 && (
                        <div className="journey-step__weaknesses">
                          {step.weaknesses.map((w, j) => (
                            <span key={j} className="journey-chip journey-chip--weakness">→ {w}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {/* Adaptive decision + reasoning */}
                  {step.action && (
                    <div className="journey-step__decision">
                      <span className="journey-step__action-label">Decision:</span>
                      <span className="journey-step__action">{formatAction(step.action)}</span>
                    </div>
                  )}
                  {step.reasoning && (
                    <details className="journey-step__reasoning-details">
                      <summary className="journey-step__reasoning-toggle">View reasoning</summary>
                      <p className="journey-step__reasoning">{step.reasoning}</p>
                    </details>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Detailed Feedback (expandable) ─────────────────────── */}
      {displayDetailedFeedback && (
        <section className="report-section" aria-label="Detailed feedback">
          <details open={false}>
            <summary className="report-section__title report-section__title--expandable">
              Detailed Feedback
            </summary>
            <div className="report-detailed-feedback">
              {displayDetailedFeedback.split('\n').map((line, i) =>
                line.trim() ? <p key={i}>{line}</p> : null
              )}
            </div>
          </details>
        </section>
      )}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────

function getRecommendationInfo(rec) {
  if (!rec) return { label: '', cls: '' };
  const map = {
    strong_hire: { label: 'Strong Hire', cls: 'report-rec-badge--strong-hire' },
    hire: { label: 'Hire', cls: 'report-rec-badge--hire' },
    lean_hire: { label: 'Lean Hire', cls: 'report-rec-badge--lean-hire' },
    lean_no_hire: { label: 'Lean No Hire', cls: 'report-rec-badge--lean-no-hire' },
    no_hire: { label: 'No Hire', cls: 'report-rec-badge--no-hire' },
    needs_further_evaluation: { label: 'Needs Further Evaluation', cls: 'report-rec-badge--further' },
  };
  return map[rec] ?? { label: String(rec).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), cls: '' };
}

function getConfidenceLabel(avgConfidence) {
  if (avgConfidence >= 0.7) return 'High';
  if (avgConfidence >= 0.4) return 'Medium';
  return 'Low';
}

function formatProficiency(value) {
  if (!value) return '';
  return String(value).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatAction(value) {
  if (!value) return '';
  const map = {
    continue_same_topic: 'Continued on same topic',
    increase_difficulty: 'Increased difficulty',
    decrease_difficulty: 'Decreased difficulty',
    switch_topic: 'Switched to new competency',
    deep_dive: 'Probed weakness deeper',
    conclude_interview: 'Concluded interview',
  };
  return map[value] ?? String(value).replace(/_/g, ' ');
}

function formatDuration(seconds) {
  if (seconds == null) return '';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function difficultyClass(value) {
  if (!value) return 'medium';
  const map = {
    foundational: 'easy',
    intermediate: 'medium',
    advanced: 'hard',
    expert: 'expert',
  };
  return map[String(value).toLowerCase()] ?? 'medium';
}

function scoreClass(score) {
  if (typeof score !== 'number') return '';
  if (score >= 70) return 'journey-step__score--strong';
  if (score >= 40) return 'journey-step__score--moderate';
  return 'journey-step__score--weak';
}
