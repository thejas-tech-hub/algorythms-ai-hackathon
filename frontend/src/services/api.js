/**
 * API Service — Centralized backend communication layer.
 * All requests go through this file.
 * Base URL is configurable via VITE_API_BASE_URL.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function request(method, path, body = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== null) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(`${BASE_URL}${path}`, options);

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData?.detail) errorMessage = errorData.detail;
      else if (errorData?.message) errorMessage = errorData.message;
    } catch (_) {
      // ignore parse errors
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

// ─── Health / Readiness ────────────────────────────────────────────────────

export function checkHealth() {
  return request('GET', '/api/v1/health');
}

export function checkReady() {
  return request('GET', '/api/v1/ready');
}

// ─── Candidates ───────────────────────────────────────────────────────────

/**
 * Fetch all candidates.
 * @returns {Promise<Array>} Array of candidate objects.
 */
export function getCandidates() {
  return request('GET', '/api/v1/candidates');
}

/**
 * Fetch a single candidate by ID.
 * @param {string|number} candidateId
 * @returns {Promise<Object>} Candidate object.
 */
export function getCandidate(candidateId) {
  return request('GET', `/api/v1/candidates/${candidateId}`);
}

// ─── Interviews ───────────────────────────────────────────────────────────

/**
 * Start a new interview session for a candidate.
 * @param {string|number} candidateId
 * @returns {Promise<Object>} Interview session object.
 */
export function startInterview(candidateId) {
  return request('POST', '/api/v1/interviews', { candidate_id: candidateId });
}

/**
 * Fetch the current state of an interview session.
 * @param {string} sessionId
 * @returns {Promise<Object>} Interview session state.
 */
export function getInterview(sessionId) {
  return request('GET', `/api/v1/interviews/${sessionId}`);
}

/**
 * Submit a candidate's answer to the current question.
 * @param {string} sessionId
 * @param {string} answer
 * @returns {Promise<Object>} Next question / evaluation result.
 */
export function submitAnswer(sessionId, answer) {
  return request('POST', `/api/v1/interviews/${sessionId}/respond`, { answer });
}

/**
 * End an interview session and trigger final report generation.
 * @param {string} sessionId
 * @returns {Promise<Object>} Final interview report.
 */
export function endInterview(sessionId) {
  return request('POST', `/api/v1/interviews/${sessionId}/end`);
}
