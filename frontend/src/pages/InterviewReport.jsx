import React from 'react';
import FinalReport from '../components/FinalReport';

/**
 * InterviewReport — Page 4.
 * Displays the Candidate Intelligence Report.
 *
 * Props:
 *   report    (object) — { report, journeyData, competencyEvidence } or raw report
 *   candidate (object) — candidate data
 *   onRestart (fn)     — navigate back to candidate selection
 */
export default function InterviewReport({ report, candidate, onRestart }) {
  const candidateName = candidate?.name || 'Candidate';

  // report may be wrapped { report, journeyData, competencyEvidence }
  // or may be a raw report object
  const actualReport = report?.report ?? report;
  const journeyData = report?.journeyData ?? [];
  const competencyEvidence = report?.competencyEvidence ?? {};

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
          <h1>Candidate Intelligence Report</h1>
          <p className="report-page-subtitle">
            {candidateName}
            {candidate?.role && <span className="report-page-role"> · {candidate.role}</span>}
          </p>
        </div>

        {actualReport ? (
          <FinalReport
            report={actualReport}
            candidate={candidate}
            journeyData={journeyData}
            competencyEvidence={competencyEvidence}
          />
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
