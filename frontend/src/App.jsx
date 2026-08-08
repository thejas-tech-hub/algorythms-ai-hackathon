import React, { useState } from 'react';
import CandidateSelection from './pages/CandidateSelection';
import InterviewPreparation from './pages/InterviewPreparation';
import Interview from './pages/Interview';
import InterviewReport from './pages/InterviewReport';
import './App.css';

/**
 * Views / "pages" in the app (no router dependency needed).
 */
const VIEWS = {
  SELECTION: 'selection',
  PREPARATION: 'preparation',
  INTERVIEW: 'interview',
  REPORT: 'report',
};

/**
 * App — Root component. Manages page-level navigation via local state.
 * No external router library required.
 */
export default function App() {
  const [view, setView] = useState(VIEWS.SELECTION);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [interviewSession, setInterviewSession] = useState(null);
  const [finalReport, setFinalReport] = useState(null);

  // ── Navigation handlers ──────────────────────────────────────────────────

  function handleCandidateSelect(candidate) {
    setSelectedCandidate(candidate);
    setView(VIEWS.PREPARATION);
  }

  function handleInterviewStart(session, candidate) {
    // candidate may have been enriched during preparation
    if (candidate) setSelectedCandidate(candidate);
    setInterviewSession(session);
    setView(VIEWS.INTERVIEW);
  }

  function handleInterviewEnd(report) {
    setFinalReport(report);
    setView(VIEWS.REPORT);
  }

  function handleRestart() {
    setSelectedCandidate(null);
    setInterviewSession(null);
    setFinalReport(null);
    setView(VIEWS.SELECTION);
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="app-root" data-view={view}>
      {view === VIEWS.SELECTION && (
        <CandidateSelection onSelectCandidate={handleCandidateSelect} />
      )}

      {view === VIEWS.PREPARATION && (
        <InterviewPreparation
          candidate={selectedCandidate}
          onStartInterview={handleInterviewStart}
          onBack={() => setView(VIEWS.SELECTION)}
        />
      )}

      {view === VIEWS.INTERVIEW && (
        <Interview
          session={interviewSession}
          candidate={selectedCandidate}
          onInterviewEnd={handleInterviewEnd}
        />
      )}

      {view === VIEWS.REPORT && (
        <InterviewReport
          report={finalReport}
          candidate={selectedCandidate}
          onRestart={handleRestart}
        />
      )}
    </div>
  );
}
