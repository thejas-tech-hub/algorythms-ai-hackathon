import React, { useEffect, useState, useCallback } from 'react';
import CandidateList from '../components/CandidateList';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { getCandidates } from '../services/api';

/**
 * CandidateSelection — Page 1.
 * Fetches the candidate list from the backend and lets the user select one.
 *
 * Props:
 *   onSelectCandidate (fn) — called with the selected candidate object
 */
export default function CandidateSelection({ onSelectCandidate }) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchCandidates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCandidates();
      // Backend may return array directly or wrapped in {candidates: [...]}
      const list = Array.isArray(data) ? data : data?.candidates ?? data?.data ?? [];
      setCandidates(list);
    } catch (err) {
      setError(err.message || 'Failed to load candidates.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCandidates();
  }, [fetchCandidates]);

  return (
    <div className="page page--selection">
      {/* Page header */}
      <header className="page-header">
        <div className="page-header__brand">
          <span className="brand-dot brand-dot--lg" aria-hidden="true" />
          <h1 className="page-header__title">Adaptive AI Interview Agent</h1>
        </div>
        <p className="page-header__subtitle">
          Select a candidate from the AI training cohort to begin an adaptive
          intelligence-driven interview session.
        </p>
        <div className="page-header__pipeline" aria-label="Interview pipeline overview">
          {['Profile', 'Plan', 'Question', 'Evaluate', 'Adapt', 'Report'].map((step, i) => (
            <React.Fragment key={step}>
              <span className="pipeline-step">{step}</span>
              {i < 5 && <span className="pipeline-arrow" aria-hidden="true">→</span>}
            </React.Fragment>
          ))}
        </div>
      </header>

      {/* Content */}
      <main className="page-main" id="main-content">
        <div className="section-label">
          <span>Registered Candidates</span>
          {!loading && !error && (
            <span className="section-label__count">{candidates.length}</span>
          )}
        </div>

        {loading && (
          <LoadingState message="Loading candidates from system…" />
        )}

        {!loading && error && (
          <ErrorState
            title="Backend Unavailable"
            message={error}
            onRetry={fetchCandidates}
          />
        )}

        {!loading && !error && (
          <CandidateList
            candidates={candidates}
            onSelect={onSelectCandidate}
          />
        )}
      </main>
    </div>
  );
}
