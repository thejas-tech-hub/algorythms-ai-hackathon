import React from 'react';

/**
 * Interview state machine states:
 *   READY → SPEAKING → LISTENING → ANALYZING → ADAPTING → READY
 *
 * Only ONE state is active at a time.
 */
const STATE_CONFIG = {
  speaking: {
    label: 'AI Speaking',
    icon: '🔊',
    cls: 'interview-state--speaking',
  },
  listening: {
    label: 'Listening',
    icon: '🎙',
    cls: 'interview-state--listening',
  },
  analyzing: {
    label: 'Analyzing Response',
    icon: '⚡',
    cls: 'interview-state--analyzing',
  },
  adapting: {
    label: 'Adapting Interview',
    icon: '🔄',
    cls: 'interview-state--adapting',
  },
  ready: {
    label: 'Ready',
    icon: '✓',
    cls: 'interview-state--ready',
  },
};

/**
 * VoiceControls — Compact voice control bar with single state machine.
 *
 * Props:
 *   voice           (object)  — return value of useVoiceInterviewer hook
 *   interviewState  (string)  — current state: 'ready'|'speaking'|'listening'|'analyzing'|'adapting'
 *
 * Non-blocking: gracefully handles unsupported browsers.
 */
export default function VoiceControls({ voice, interviewState = 'ready' }) {
  if (!voice) return null;

  const {
    isSpeaking,
    isMuted,
    isSupported,
    autoplayBlocked,
    replay,
    stop,
    toggleMute,
  } = voice;

  // Determine effective state
  const effectiveState = isSpeaking ? 'speaking' : interviewState;
  const stateInfo = STATE_CONFIG[effectiveState] || STATE_CONFIG.ready;

  // Unsupported browser — show subtle fallback
  if (!isSupported) {
    return (
      <div className="voice-controls voice-controls--fallback" role="status">
        <span className="voice-controls__fallback-text">
          Voice unavailable in this browser
        </span>
      </div>
    );
  }

  return (
    <div className="voice-controls" role="toolbar" aria-label="Voice controls">
      {/* Interview state indicator */}
      <div className={`interview-state ${stateInfo.cls}`} aria-live="polite">
        <span className="interview-state__icon" aria-hidden="true">{stateInfo.icon}</span>
        <span className="interview-state__label">{stateInfo.label}</span>
      </div>

      {/* Autoplay blocked — show play button */}
      {autoplayBlocked && !isSpeaking && !isMuted && (
        <button
          className="btn btn--secondary btn--sm voice-controls__play"
          onClick={replay}
          aria-label="Play question aloud"
          id="voice-play-btn"
        >
          <span aria-hidden="true">▶</span> Play Question
        </button>
      )}

      {/* Replay */}
      <button
        className="btn btn--ghost btn--sm voice-controls__btn"
        onClick={replay}
        disabled={isMuted}
        aria-label="Replay current question"
        id="voice-replay-btn"
        title="Replay question"
      >
        🔊 Replay
      </button>

      {/* Stop (visible when speaking) */}
      {isSpeaking && (
        <button
          className="btn btn--ghost btn--sm voice-controls__btn"
          onClick={stop}
          aria-label="Stop speech"
          id="voice-stop-btn"
          title="Stop speaking"
        >
          ⏹ Stop
        </button>
      )}

      {/* Mute / Unmute */}
      <button
        className={`btn btn--ghost btn--sm voice-controls__btn ${isMuted ? 'voice-controls__btn--muted' : ''}`}
        onClick={toggleMute}
        aria-label={isMuted ? 'Unmute voice' : 'Mute voice'}
        aria-pressed={isMuted}
        id="voice-mute-btn"
        title={isMuted ? 'Unmute' : 'Mute'}
      >
        {isMuted ? '🔇 Unmuted' : '🔈 Mute'}
      </button>
    </div>
  );
}
