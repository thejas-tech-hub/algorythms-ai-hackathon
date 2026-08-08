import React, { useEffect, useState } from 'react';
import CandidateOverview from '../components/CandidateOverview';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { getCandidate, startInterview } from '../services/api';

/**
 * InterviewPreparation — Page 2.
 * Shows the full candidate profile and lets the user start the interview.
 *
 * Props:
 *   candidate         (object) — basic candidate data from selection screen
 *   onStartInterview  (fn)     — called with the new session object
 *   onBack            (fn)     — navigate back to selection
 */
export default function InterviewPreparation({ candidate, onStartInterview, onBack }) {
  const [fullProfile, setFullProfile] = useState(candidate);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);

  // Attempt to enrich profile from the /candidates/{id} endpoint
  useEffect(() => {
    if (!candidate?.candidate_id && !candidate?.id) return;
    const id = candidate.candidate_id ?? candidate.id;
    setProfileLoading(true);
    getCandidate(id)
      .then((data) => setFullProfile(data))
      .catch(() => setFullProfile(candidate)) // gracefully fall back to basic data
      .finally(() => setProfileLoading(false));
  }, [candidate]);

  async function handleStart() {
    const id = fullProfile?.candidate_id ?? fullProfile?.id;
    if (!id) return;
    setStarting(true);
    setStartError(null);
    try {
      const session = await startInterview(id);
      onStartInterview(session, fullProfile);
    } catch (err) {
      setStartError(err.message || 'Failed to start interview.');
      setStarting(false);
    }
  }

  return (
    <div className="page page--preparation">
      {/* Nav */}
      <nav className="prep-nav" aria-label="Navigation">
        <button className="btn btn--ghost" onClick={onBack} aria-label="Back to candidate selection">
          ← Back
        </button>
        <span className="prep-nav__label">Interview Preparation</span>
      </nav>

      <main className="page-main" id="main-content">
        <div className="prep-layout">
          {/* Left: candidate profile */}
          <div className="prep-layout__profile">
            <h2 className="prep-section-title">Candidate Profile</h2>
            {profileLoading ? (
              <LoadingState message="Loading full profile…" inline />
            ) : profileError ? (
              <ErrorState title="Profile Error" message={profileError} />
            ) : (
              <CandidateOverview candidate={fullProfile} />
            )}
          </div>

          {/* Right: readiness panel */}
          <div className="prep-layout__readiness">
            <div className="readiness-card">
              <div className="readiness-card__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
              </div>
              <h3 className="readiness-card__title">AI Interview Ready</h3>
              <p className="readiness-card__desc">
                The adaptive interview system will generate questions based on
                this candidate's profile, adjusting difficulty and focus areas
                in real time.
              </p>

              <ul className="readiness-checklist">
                <li className="readiness-checklist__item readiness-checklist__item--ok">
                  Profile loaded
                </li>
                <li className="readiness-checklist__item readiness-checklist__item--ok">
                  Session will be created on start
                </li>
                <li className="readiness-checklist__item readiness-checklist__item--pending">
                  Adaptive engine ready
                </li>
              </ul>

              {startError && (
                <div className="error-inline" role="alert">
                  <strong>Error:</strong> {startError}
                </div>
              )}

              <button
                id="start-interview-btn"
                className="btn btn--primary btn--lg btn--full"
                onClick={handleStart}
                disabled={starting}
                aria-label="Start adaptive interview"
              >
                {starting ? (
                  <>
                    <span className="spinner spinner--sm spinner--inline" />
                    Starting Interview…
                  </>
                ) : (
                  'Start Adaptive Interview'
                )}
              </button>
            </div>

            {/* Pipeline visual */}
            <div className="prep-pipeline" aria-label="Interview pipeline">
              <h4 className="prep-pipeline__title">How it works</h4>
              <ol className="pipeline-list">
                {[
                  ['Candidate Profile', 'Your background shapes the plan'],
                  ['Question Plan', 'Targeted competencies identified'],
                  ['Adaptive Questions', 'Difficulty adjusts in real time'],
                  ['Answer Evaluation', 'Each response is assessed'],
                  ['Final Report', 'Detailed performance summary'],
                ].map(([step, desc]) => (
                  <li key={step} className="pipeline-list__item">
                    <span className="pipeline-list__step">{step}</span>
                    <span className="pipeline-list__desc">{desc}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
