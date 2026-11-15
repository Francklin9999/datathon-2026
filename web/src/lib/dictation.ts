/**
 * Ask Aplomb dictation through the browser's own speech recognition (Web Speech API): finding the
 * recognizer, its language, the words heard, the field they produce and the message for each error.
 * Recognition belongs to the browser; in Chrome, for example, the audio goes to its speech service.
 * The words only fill the field: Decide still interprets them and nothing runs before confirmation.
 */
import type { I18NText, Lang } from '../contracts/types';

/** One recognition result as the browser delivers it: final or still interim, best alternative first. */
export interface HeardResult {
  readonly isFinal: boolean;
  readonly length: number;
  readonly [alternative: number]: { readonly transcript: string };
}

/** Every result of the current utterance, in order. */
export interface HeardResults {
  readonly length: number;
  readonly [index: number]: HeardResult;
}

/** The part of the recognizer used here; TypeScript's DOM library does not declare SpeechRecognition. */
export interface SpeechRecognizer {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: { readonly results: HeardResults }) => void) | null;
  onerror: ((event: { readonly error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export type SpeechRecognizerConstructor = new () => SpeechRecognizer;

/** The standard or WebKit-prefixed recognizer; null without one, or outside a secure context. */
export function findSpeechRecognition(scope: unknown): SpeechRecognizerConstructor | null {
  if (typeof scope !== 'object' || scope === null) return null;
  const found = scope as { isSecureContext?: unknown; SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
  if (found.isSecureContext === false) return null;
  const recognizer = found.SpeechRecognition ?? found.webkitSpeechRecognition;
  return typeof recognizer === 'function' ? recognizer as SpeechRecognizerConstructor : null;
}

/** Recognition language for the interface language: Canadian English or Canadian French. */
export function speechLang(lang: Lang): string {
  return lang === 'fr' ? 'fr-CA' : 'en-CA';
}

/** The words heard so far: the best alternative of every result, final or interim, in order. */
export function heardText(results: HeardResults): string {
  const words: string[] = [];
  for (let index = 0; index < results.length; index++) {
    const best = results[index]?.[0]?.transcript.trim();
    if (best) words.push(best);
  }
  return words.join(' ');
}

/** The field during dictation: what was already typed, one space, then the words heard, capped at `max`. */
export function withDictation(typed: string, heard: string, max: number): string {
  const before = typed.trimEnd();
  const words = heard.trim();
  return (before && words ? `${before} ${words}` : before || words).slice(0, max);
}

/** What to tell the person when dictation stops on an error; null when they stopped it themselves. */
export function dictationMessage(error: string): I18NText | null {
  switch (error) {
    case 'aborted':
      return null;
    case 'no-speech':
      return { en: 'No speech was heard. Press the microphone and try again.', fr: 'Aucune parole entendue. Appuyez sur le micro et réessayez.' };
    case 'not-allowed':
      return {
        en: 'Microphone access is blocked. Allow it for this site in your browser, or type the request.',
        fr: 'L’accès au micro est bloqué. Autorisez-le pour ce site dans votre navigateur, ou tapez la demande.',
      };
    case 'service-not-allowed':
      return {
        en: 'Your browser does not allow its speech service here. Type the request instead.',
        fr: 'Votre navigateur n’autorise pas son service vocal ici. Tapez plutôt la demande.',
      };
    case 'audio-capture':
      return { en: 'No microphone was found. Type the request instead.', fr: 'Aucun micro détecté. Tapez plutôt la demande.' };
    case 'network':
      return {
        en: 'Your browser’s speech service could not be reached. Type the request instead.',
        fr: 'Le service vocal de votre navigateur est injoignable. Tapez plutôt la demande.',
      };
    case 'language-not-supported':
      return {
        en: 'Your browser cannot transcribe this language. Type the request instead.',
        fr: 'Votre navigateur ne peut pas transcrire cette langue. Tapez plutôt la demande.',
      };
    default:
      return { en: 'Dictation stopped. Type the request instead.', fr: 'La dictée s’est arrêtée. Tapez plutôt la demande.' };
  }
}
