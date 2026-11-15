'use client';
/**
 * Dictation into a text field with the browser's speech recognition (helpers in lib/dictation.ts).
 * One utterance per press: words arrive while the person speaks; recognition ends after a pause or
 * on a second press. A cancelled recognizer is detached first, so nothing it reports later lands.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { I18NText, Lang } from '../../contracts/types';
import { dictationMessage, findSpeechRecognition, heardText, speechLang, type SpeechRecognizer } from '../../lib/dictation';

/** After a stop, a browser that never reports the end is abandoned after this delay. */
const STOP_GRACE_MS = 2000;

export interface Dictation {
  /** False before mount and where the browser has no recognizer: show no microphone then. */
  supported: boolean;
  listening: boolean;
  /** Why the last dictation stopped early, until dismissed or the next one starts. */
  message: I18NText | null;
  start: () => void;
  /** Ends listening and keeps the words: the last result arrives before the end. */
  stop: () => void;
  /** Ends listening at once; anything the browser reports afterwards is ignored. */
  cancel: () => void;
  dismiss: () => void;
}

export function useDictation(lang: Lang, onHeard: (heard: string) => void, onEnd?: () => void): Dictation {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [message, setMessage] = useState<I18NText | null>(null);
  const active = useRef<SpeechRecognizer | null>(null);
  const grace = useRef<ReturnType<typeof setTimeout> | null>(null);
  const callbacks = useRef({ onHeard, onEnd });
  useEffect(() => { callbacks.current = { onHeard, onEnd }; });

  useEffect(() => { setSupported(findSpeechRecognition(window) !== null); }, []);

  /** True when `recognizer` was the current one; afterwards none of its events reach the field. */
  const detach = useCallback((recognizer: SpeechRecognizer): boolean => {
    if (active.current !== recognizer) return false;
    active.current = null;
    if (grace.current) { clearTimeout(grace.current); grace.current = null; }
    setListening(false);
    return true;
  }, []);

  const start = useCallback(() => {
    const Recognizer = findSpeechRecognition(window);
    if (!Recognizer || active.current) return;
    setMessage(null);
    let recognizer: SpeechRecognizer;
    try { recognizer = new Recognizer(); } catch { setMessage(dictationMessage('')); return; }
    recognizer.lang = speechLang(lang);
    recognizer.continuous = false;
    recognizer.interimResults = true;
    recognizer.maxAlternatives = 1;
    recognizer.onresult = event => { if (active.current === recognizer) callbacks.current.onHeard(heardText(event.results)); };
    recognizer.onerror = event => { if (active.current === recognizer) setMessage(dictationMessage(event.error)); };
    recognizer.onend = () => { if (detach(recognizer)) callbacks.current.onEnd?.(); };
    active.current = recognizer;
    setListening(true);
    try { recognizer.start(); } catch { detach(recognizer); setMessage(dictationMessage('')); }
  }, [lang, detach]);

  const stop = useCallback(() => {
    const recognizer = active.current;
    if (!recognizer || grace.current) return;
    recognizer.stop();
    grace.current = setTimeout(() => {
      if (!detach(recognizer)) return;
      recognizer.abort();
      callbacks.current.onEnd?.();
    }, STOP_GRACE_MS);
  }, [detach]);

  const cancel = useCallback(() => {
    const recognizer = active.current;
    if (recognizer && detach(recognizer)) recognizer.abort();
  }, [detach]);

  // Leaving the page or switching the language abandons the current dictation.
  useEffect(() => cancel, [cancel, lang]);

  const dismiss = useCallback(() => setMessage(null), []);
  return { supported, listening, message, start, stop, cancel, dismiss };
}
