import { useState, useEffect, useRef, useCallback } from 'react';

export default function useSpeechRecognition() {
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [error, setError] = useState(null);
  const [listenStartTime, setListenStartTime] = useState(null);

  const recognitionRef = useRef(null);
  const mountedRef = useRef(true);
  const keepListeningRef = useRef(false);
  const restartTimerRef = useRef(null);

  useEffect(() => {
    mountedRef.current = true;

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    setIsSupported(Boolean(SpeechRecognition));

    return () => {
      mountedRef.current = false;
      keepListeningRef.current = false;

      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }

      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (_) { }

        recognitionRef.current = null;
      }
    };
  }, []);

  const start = useCallback(() => {
    if (!isSupported) {
      setError('Speech recognition is not supported in this browser.');
      return;
    }

    if (recognitionRef.current) return;

    keepListeningRef.current = true;

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    const startRecognition = () => {
      if (
        !mountedRef.current ||
        !keepListeningRef.current ||
        recognitionRef.current
      ) {
        return;
      }

      const recognition = new SpeechRecognition();

      recognition.lang = 'en-US';

      // Keep recognition alive as long as possible.
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        if (!mountedRef.current) return;

        setIsListening(true);
        setError(null);
        setListenStartTime((previous) => previous ?? Date.now());
      };

      recognition.onresult = (event) => {
        if (!mountedRef.current) return;

        let interim = '';
        let final = '';

        for (
          let i = event.resultIndex;
          i < event.results.length;
          i++
        ) {
          const result = event.results[i];

          if (result.isFinal) {
            final += result[0].transcript;
          } else {
            interim += result[0].transcript;
          }
        }

        if (final) {
          setTranscript((prev) =>
            prev ? `${prev} ${final}` : final
          );
          setInterimTranscript('');
        } else {
          setInterimTranscript(interim);
        }
      };

      recognition.onerror = (event) => {
        if (!mountedRef.current) return;

        const fatalErrors = {
          'not-allowed':
            'Microphone permission denied. Please allow microphone access.',
          'audio-capture':
            'No microphone found. Please check your device.',
        };

        const recoverableErrors = {
          'no-speech':
            'No speech detected. Listening will continue.',
          network:
            'Network issue. Reconnecting speech recognition…',
          'service-not-available':
            'Speech service unavailable. Reconnecting…',
        };

        if (fatalErrors[event.error]) {
          keepListeningRef.current = false;
          setError(fatalErrors[event.error]);
          setIsListening(false);
        } else if (recoverableErrors[event.error]) {
          setError(recoverableErrors[event.error]);
        }
      };

      recognition.onend = () => {
        if (!mountedRef.current) return;

        recognitionRef.current = null;

        // Browser stopped recognition automatically.
        // Restart it unless the user explicitly pressed Stop.
        if (keepListeningRef.current) {
          setIsListening(true);
          setInterimTranscript('');

          if (!restartTimerRef.current) {
            restartTimerRef.current = setTimeout(() => {
              restartTimerRef.current = null;
              startRecognition();
            }, 200);
          }
        } else {
          setIsListening(false);
          setInterimTranscript('');
        }
      };

      recognitionRef.current = recognition;

      try {
        recognition.start();
      } catch (_) {
        recognitionRef.current = null;

        if (keepListeningRef.current) {
          restartTimerRef.current = setTimeout(() => {
            restartTimerRef.current = null;
            startRecognition();
          }, 300);
        } else if (mountedRef.current) {
          setError('Failed to start speech recognition.');
          setIsListening(false);
        }
      }
    };

    startRecognition();
  }, [isSupported]);

  const stop = useCallback(() => {
    // Prevent automatic restart.
    keepListeningRef.current = false;

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (_) {
        try {
          recognitionRef.current.abort();
        } catch (_) { }
      }
    }

    recognitionRef.current = null;

    if (mountedRef.current) {
      setIsListening(false);
      setInterimTranscript('');
      setListenStartTime(null);
    }
  }, []);

  const reset = useCallback(() => {
    stop();

    if (mountedRef.current) {
      setTranscript('');
      setInterimTranscript('');
      setError(null);
    }
  }, [stop]);

  return {
    transcript,
    interimTranscript,
    isListening,
    isSupported,
    error,
    listenStartTime,
    start,
    stop,
    reset,
  };
}