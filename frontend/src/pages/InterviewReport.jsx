import React from 'react';
import FinalReport from '../components/FinalReport';

/**
 * InterviewReport — Page 4.
 * Displays the final interview report returned by the backend.
 *
 * Props:
 *   report    (object) — final report data
 *   candidate (object) — candidate data
 *   onRestart (fn)     — navigate back to candidate selection
 */
export default function InterviewReport({ report, candidate, onRestart }) {
  const candidateName = candidate?.name || 'Candidate';

  return (
    <div className="page page--report">
      <header className="report-page-header">
        <div className="report-page-header__left">
          <span className="brand-dot brand-dot--lg" aria-hidden="true" />
          <span className="report-page-header__brand">Adaptive AI Interview Agent</span>
        </div>
        <button
          className="btn btn--ghost"
          onClick={onRestart}
          id="new-interview-btn"
          aria-label="Start a new interview session"
        >
          ← New Interview
        </button>
      </header>

      <main className="page-main page-main--report" id="main-content">
        <div className="report-page-title">
          <h1>Interview Report</h1>
          <p className="report-page-subtitle">
            {candidateName}
            {candidate?.role && <span className="report-page-role"> · {candidate.role}</span>}
          </p>
        </div>

        {report ? (
          <FinalReport report={report} />
        ) : (
          <div className="empty-state">
            <div className="empty-state__icon" aria-hidden="true">📋</div>
            <h3 className="empty-state__title">Report Pending</h3>
            <p className="empty-state__desc">
              The backend is generating the final report. This section will
              display full evaluation data once the backend returns it.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
