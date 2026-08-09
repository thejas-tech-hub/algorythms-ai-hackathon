import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * useVoiceInterviewer — Custom hook for Web Speech API voice synthesis.
 *
 * Non-blocking: voice failure never prevents interview flow.
 * Maps adaptive actions to professional interviewer transition phrases.
 *
 * First-question fix: if autoplay is blocked on first speak, the
 * autoplayBlocked flag is set and the consumer shows a Play button.
 * Does NOT retry automatically.
 *
 * Usage:
 *   const voice = useVoiceInterviewer();
 *   voice.speakQuestion(questionText, adaptiveAction);
 *   voice.replay();
 *   voice.toggleMute();
 */

// ── Adaptive transition phrases mapped to real backend AdaptiveAction values ──
// Multiple options per action for natural variety
const TRANSITION_PHRASES = {
  increase_difficulty: [
    "Good. You've demonstrated a strong understanding there. Let's go one level deeper.",
    "Excellent grasp of the topic. Let's raise the bar.",
    "Strong answer. Let's push further on this.",
  ],
  decrease_difficulty: [
    "Let's take a step back and verify the fundamentals.",
    "Let's revisit the basics to build a clearer picture.",
    "Let's step back and strengthen the foundation.",
  ],
  switch_topic: [
    "Good. Let's explore another area.",
    "Let's move to another competency to broaden the assessment.",
    "Now let's switch gears and look at a different area.",
  ],
  deep_dive: [
    "I'd like to explore one part of your previous answer a little further.",
    "Let's go a little deeper into that.",
    "I want to probe that area a bit more.",
  ],
  continue_same_topic: [
    "Let's continue exploring this area.",
    "Let's stay on this topic for one more question.",
    "I'd like to ask a follow-up on the same topic.",
  ],
  conclude_interview: null, // No transition — interview is ending
};

// First question greeting (no previous adaptive action)
const FIRST_QUESTION_PHRASES = [
  "Let's begin the adaptive interview.",
  "Welcome. Let's start the assessment.",
];

function pickRandom(arr) {
  if (!arr || !arr.length) return '';
  return arr[Math.floor(Math.random() * arr.length)];
}

/**
 * Select the best available English voice from the browser's speech synthesis.
 * Prefers natural/premium voices, falls back to any English voice.
 */
function selectVoice() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  // Prefer natural-sounding English voices
  const english = voices.filter(
    (v) => v.lang.startsWith('en') && !v.name.includes('espeak')
  );
  // Prefer Google or Microsoft premium voices
  const premium = english.filter(
    (v) =>
      v.name.includes('Google') ||
      v.name.includes('Microsoft') ||
      v.name.includes('Natural') ||
      v.name.includes('Neural')
  );
  return premium[0] || english[0] || voices[0] || null;
}

export default function useVoiceInterviewer() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [autoplayBlocked, setAutoplayBlocked] = useState(false);

  const lastSpokenRef = useRef({ transition: '', question: '' });
  const voiceRef = useRef(null);
  const mountedRef = useRef(true);

  // ── Check support and load voices ──
  useEffect(() => {
    mountedRef.current = true;
    const synth = window.speechSynthesis;
    if (!synth) {
      setIsSupported(false);
      return;
    }
    setIsSupported(true);
    // Voices may load asynchronously
    voiceRef.current = selectVoice();
    const onVoicesChanged = () => {
      voiceRef.current = selectVoice();
    };
    synth.addEventListener('voiceschanged', onVoicesChanged);
    return () => {
      mountedRef.current = false;
      synth.removeEventListener('voiceschanged', onVoicesChanged);
      synth.cancel();
    };
  }, []);

  // ── Stop all speech ──
  const stop = useCallback(() => {
    try {
      window.speechSynthesis?.cancel();
    } catch (_) {
      /* ignore */
    }
    if (mountedRef.current) setIsSpeaking(false);
  }, []);

  // ── Core speak function (non-blocking, fire-and-forget) ──
  const speak = useCallback(
    (text) => {
      if (!isSupported || !text) return false;
      try {
        const synth = window.speechSynthesis;
        synth.cancel(); // Stop any previous speech

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.92;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        if (voiceRef.current) utterance.voice = voiceRef.current;

        utterance.onstart = () => {
          if (mountedRef.current) {
            setIsSpeaking(true);
            setAutoplayBlocked(false);
          }
        };
        utterance.onend = () => {
          if (mountedRef.current) setIsSpeaking(false);
        };
        utterance.onerror = (e) => {
          if (mountedRef.current) {
            setIsSpeaking(false);
            // Detect autoplay block
            if (e.error === 'not-allowed' || e.error === 'interrupted') {
              setAutoplayBlocked(true);
            }
          }
        };

        synth.speak(utterance);
        return true;
      } catch (_) {
        if (mountedRef.current) setIsSpeaking(false);
        return false;
      }
    },
    [isSupported]
  );

  // ── Speak a question with optional adaptive transition ──
  const speakQuestion = useCallback(
    (questionText, adaptiveAction = null) => {
      if (isMuted || !isSupported || !questionText) return;

      // Build the full spoken text
      let transition = '';
      if (adaptiveAction && TRANSITION_PHRASES[adaptiveAction] !== undefined) {
        const phrases = TRANSITION_PHRASES[adaptiveAction];
        transition = phrases ? pickRandom(phrases) : '';
      } else if (!adaptiveAction) {
        transition = pickRandom(FIRST_QUESTION_PHRASES);
      }

      const fullText = transition
        ? `${transition} ... ${questionText}`
        : questionText;

      lastSpokenRef.current = { transition, question: questionText };

      const success = speak(fullText);
      if (!success && mountedRef.current) {
        setAutoplayBlocked(true);
      }
    },
    [isMuted, isSupported, speak]
  );

  // ── Play question (user-gesture triggered — for first-question fallback) ──
  const playQuestion = useCallback(() => {
    if (!isSupported) return;
    const { transition, question } = lastSpokenRef.current;
    if (!question) return;
    const fullText = transition
      ? `${transition} ... ${question}`
      : question;
    setAutoplayBlocked(false);
    speak(fullText);
  }, [isSupported, speak]);

  // ── Replay last question ──
  const replay = useCallback(() => {
    if (!isSupported) return;
    const { transition, question } = lastSpokenRef.current;
    if (!question) return;
    const fullText = transition
      ? `${transition} ... ${question}`
      : question;
    // Replay always works (user gesture)
    setAutoplayBlocked(false);
    speak(fullText);
  }, [isSupported, speak]);

  // ── Toggle mute ──
  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      if (!prev) {
        // Muting — stop current speech
        stop();
      }
      return !prev;
    });
  }, [stop]);

  return {
    isSpeaking,
    isMuted,
    isSupported,
    autoplayBlocked,
    speakQuestion,
    playQuestion,
    replay,
    stop,
    toggleMute,
  };
}
