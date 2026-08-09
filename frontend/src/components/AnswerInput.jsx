import React, { useState, useEffect, useRef } from 'react';

/**
 * AnswerInput — Combined voice + typed answer input.
 *
 * STT feeds into the existing answer field (same pipeline).
 * Never auto-submits. Candidate explicitly clicks Submit Answer.
 *
 * Props:
 *   value             (string)   — controlled value
 *   onChange           (fn)       — change handler
 *   onSubmit           (fn)       — submit handler
 *   isSubmitting       (bool)     — disables input/button while processing
 *   processingLabel    (string)   — custom label shown while processing
 *   speechRecognition  (object)   — return value of useSpeechRecognition hook
 */
export default function AnswerInput({
  value,
  onChange,
  onSubmit,
  isSubmitting = false,
  processingLabel = 'Analyzing response…',
  speechRecognition = null,
}) {
  const [voiceMode, setVoiceMode] = useState(false);
  const prevTranscriptRef = useRef('');

  const stt = speechRecognition;
  const voiceSupported = stt?.isSupported ?? false;

  // When STT produces a final transcript, append it to the answer field
  useEffect(() => {
    if (!stt || !stt.transcript) return;
    if (stt.transcript !== prevTranscriptRef.current) {
      prevTranscriptRef.current = stt.transcript;
      // Place transcript into answer field — does NOT auto-submit
      onChange(stt.transcript);
    }
  }, [stt?.transcript, onChange]);

  function handleKeyDown(e) {
    // Ctrl+Enter or Cmd+Enter to submit
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (!isSubmitting && value?.trim()) onSubmit();
    }
  }

  function handleStartSpeaking() {
    if (stt) {
      stt.reset();
      prevTranscriptRef.current = '';
      stt.start();
      setVoiceMode(true);
    }
  }

  function handleStopSpeaking() {
    if (stt) {
      stt.stop();
    }
  }

  function handleReRecord() {
    if (stt) {
      stt.reset();
      prevTranscriptRef.current = '';
      onChange('');
      stt.start();
    }
  }

  function handleSwitchToTyping() {
    if (stt) {
      stt.stop();
    }
    setVoiceMode(false);
  }

  // Listening timer
  const ListeningTimer = () => {
    const [elapsed, setElapsed] = useState(0);
    const startTime = stt?.listenStartTime;
    useEffect(() => {
      if (!startTime) return;
      const interval = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    }, [startTime]);
    if (!startTime) return null;
    return <span className="voice-answer__timer">{elapsed}s</span>;
  };

  return (
    <div className="answer-input">
      <label htmlFor="answer-textarea" className="answer-input__label">
        Your Answer
        <span className="answer-input__hint">Ctrl + Enter to submit</span>
      </label>

      {isSubmitting ? (
        <div className="answer-input__processing" aria-live="polite">
          <div className="processing-steps">
            <div className="processing-step processing-step--active">
              <span className="processing-step__dot" aria-hidden="true" />
              <span>Evaluating your response…</span>
            </div>
            <div className="processing-step">
              <span className="processing-step__dot" aria-hidden="true" />
              <span>Selecting your next question…</span>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Voice/Type mode toggle */}
          {voiceSupported && (
            <div className="voice-answer__toggle">
              <button
                type="button"
                className={`voice-answer__mode-btn ${!voiceMode ? 'voice-answer__mode-btn--active' : ''}`}
                onClick={handleSwitchToTyping}
                aria-pressed={!voiceMode}
              >
                ⌨ Type Answer
              </button>
              <button
                type="button"
                className={`voice-answer__mode-btn ${voiceMode ? 'voice-answer__mode-btn--active' : ''}`}
                onClick={() => { setVoiceMode(true); }}
                aria-pressed={voiceMode}
              >
                🎙 Voice Answer
              </button>
            </div>
          )}

          {/* Voice answer controls */}
          {voiceMode && voiceSupported && stt && (
            <div className="voice-answer">
              {stt.isListening ? (
                <div className="voice-answer__listening">
                  <div className="voice-answer__indicator">
                    <span className="voice-answer__pulse" aria-hidden="true" />
                    <span className="voice-answer__status">🔴 Listening…</span>
                    <ListeningTimer />
                  </div>
                  <button
                    type="button"
                    className="btn btn--secondary btn--sm"
                    onClick={handleStopSpeaking}
                    id="voice-stop-listening-btn"
                  >
                    ⏹ Stop
                  </button>
                  {/* Interim transcript (subtle) */}
                  {stt.interimTranscript && (
                    <div className="voice-answer__interim" aria-live="polite">
                      {stt.interimTranscript}
                    </div>
                  )}
                </div>
              ) : (
                <div className="voice-answer__controls">
                  {value?.trim() ? (
                    <button
                      type="button"
                      className="btn btn--secondary btn--sm"
                      onClick={handleReRecord}
                      id="voice-rerecord-btn"
                    >
                      🎙 Re-record
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn--primary btn--sm voice-answer__start-btn"
                      onClick={handleStartSpeaking}
                      id="voice-start-btn"
                    >
                      🎙 Start Speaking
                    </button>
                  )}
                </div>
              )}

              {/* Error display */}
              {stt.error && (
                <div className="voice-answer__error" role="alert">
                  {stt.error}
                </div>
              )}
            </div>
          )}

          {/* Textarea — always present, always editable */}
          <textarea
            id="answer-textarea"
            className="answer-input__textarea"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={voiceMode ? 'Voice transcript will appear here. You can also type or edit…' : 'Type your answer here…'}
            rows={7}
            disabled={isSubmitting}
            aria-required="true"
            aria-label="Answer field"
          />
        </>
      )}

      <div className="answer-input__footer">
        {!isSubmitting && (
          <span className="answer-input__char-count">
            {value?.length || 0} characters
          </span>
        )}
        <button
          id="submit-answer-btn"
          className="btn btn--primary btn--lg"
          onClick={onSubmit}
          disabled={isSubmitting || !value?.trim()}
          aria-label="Submit answer"
        >
          {isSubmitting ? processingLabel : 'Submit Answer'}
        </button>
      </div>
    </div>
  );
}
