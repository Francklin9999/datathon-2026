/**
 * Inline completion for Ask Aplomb while the person types: the rest of a request phrase, a ticker
 * or a company name, shown after the caret and accepted with Tab or the right arrow. Code only, no
 * model and no request: the asset universe, the investor's holdings and a few phrases the request
 * parser understands. The bar never offers a completion for dictated text.
 */
import type { Lang } from '../contracts/types';
import { fold } from './suggest';

export interface Completion {
  /** Text shown after what was typed. */
  ghost: string;
  /** The whole field once accepted; a ticker typed in lower case comes back in capitals. */
  accepted: string;
}

/**
 * Request phrases per language (the interface language is tried first). Openers only start a request
 * ("add 5% of NVDA" never becomes "add 5% of Add"); connectors only follow something.
 */
export const PHRASES: Record<Lang, { openers: readonly string[]; connectors: readonly string[] }> = {
  en: {
    openers: ['add', 'more exposure to'],
    connectors: ['funded from cash', 'funded from bonds', 'funded pro rata', 'with new money', 'lose at most'],
  },
  fr: {
    openers: ['ajouter', 'plus d’exposition à'],
    connectors: ['financé par l’encaisse', 'financé par les obligations', 'financé au prorata', 'avec un nouvel apport', 'perdre au plus'],
  },
};

/** After a number: its unit and the next words, as in "add 5% of" or "lose at most 15% in a bad year". */
const AFTER_NUMBER: readonly { pattern: RegExp; ghost: string }[] = [
  { pattern: /\badd\s+\d+(?:[.,]\d+)?$/i, ghost: '% of' },
  { pattern: /\badd\s+\d+(?:[.,]\d+)?\s?%$/i, ghost: ' of' },
  { pattern: /\blose at most\s+\d+(?:[.,]\d+)?$/i, ghost: '%' },
  { pattern: /\blose at most\s+\d+(?:[.,]\d+)?\s?%$/i, ghost: ' in a bad year' },
  { pattern: /\bajouter\s+\d+(?:[.,]\d+)?$/i, ghost: ' % de' },
  { pattern: /\bajouter\s+\d+(?:[.,]\d+)?\s?%$/i, ghost: ' de' },
  { pattern: /\bperdre au plus\s+\d+(?:[.,]\d+)?$/i, ghost: ' %' },
  { pattern: /\bperdre au plus\s+\d+(?:[.,]\d+)?\s?%$/i, ghost: ' sur une mauvaise année' },
];

interface Word { text: string; folded: string }
/** `where`: only at the start of the request, only after it, or anywhere. */
interface WordList { words: readonly Word[]; minTyped: number; canonical: boolean; where: 'start' | 'after' | 'any' }

/** Prepared once per vocabulary change; completing a keystroke then only compares strings. */
export interface CompletionVocab { readonly lists: readonly WordList[] }

/** Matching form: folded case and accents, plain apostrophes and spaces (same length as the text). */
function matchForm(text: string): string {
  return fold(text).replace(/[’‘]/g, "'").replace(/[\u00a0\u202f]/g, ' ');
}

const LEGAL_SUFFIX = /\s+(inc\.?|corp\.?|corporation|ltd\.?|limited|plc|co\.?|company|class [a-z])$/i;

/** The name people say: "Tesla" from "Tesla, Inc.", "Alphabet" from "Alphabet Inc. Class A". */
export function spokenName(name: string): string {
  let short = (name.split(',')[0] ?? '').trim();
  for (let next = short.replace(LEGAL_SUFFIX, '').trim(); next !== short; next = short.replace(LEGAL_SUFFIX, '').trim()) short = next;
  return short;
}

export function buildCompletionVocab(lang: Lang, tickers: readonly string[], names: readonly string[]): CompletionVocab {
  const list = (items: readonly string[], minTyped: number, where: WordList['where'], canonical = false): WordList => {
    const seen = new Set<string>();
    const words: Word[] = [];
    for (const item of items) {
      const text = item.normalize('NFC').trim();
      const folded = matchForm(text);
      if (text && !seen.has(folded)) { seen.add(folded); words.push({ text, folded }); }
    }
    return { words, minTyped, canonical, where };
  };
  const own = PHRASES[lang];
  const other = PHRASES[lang === 'fr' ? 'en' : 'fr'];
  return {
    lists: [
      list(own.openers, 1, 'start'),
      list(own.connectors, 1, 'after'),
      list(tickers.map(ticker => ticker.toUpperCase()), 1, 'any', true),
      list(names.map(spokenName).filter(name => name.length >= 3), 2, 'any'),
      list(other.openers, 2, 'start'),
      list(other.connectors, 2, 'after'),
    ],
  };
}

const SEPARATOR = /[\s,;:()"«»/]/;

/** Where a completion may begin: the start and each word after a separator (the last five suffice). */
function wordStarts(text: string): number[] {
  const starts = [0];
  for (let i = 1; i < text.length; i++) {
    if (SEPARATOR.test(text[i - 1] ?? '') && !SEPARATOR.test(text[i] ?? '')) starts.push(i);
  }
  return starts.slice(-5);
}

/**
 * The completion for `text` with the caret at its end, or null. The longest typed context wins, then
 * the list order (openers, connectors, tickers, names, then the other language's phrases). Several
 * matches complete only as far as they agree, back to a whole word; a ticker only when one matches.
 */
export function completeRequest(text: string, vocab: CompletionVocab): Completion | null {
  if (!text.trim() || /\s$/.test(text)) return null;
  for (const rule of AFTER_NUMBER) {
    if (rule.pattern.test(text)) return { ghost: rule.ghost, accepted: text + rule.ghost };
  }
  for (const start of wordStarts(text)) {
    const typed = matchForm(text.slice(start));
    for (const list of vocab.lists) {
      if (typed.length < list.minTyped || (list.where === 'start' && start > 0) || (list.where === 'after' && start === 0)) continue;
      const found = list.words.filter(word => word.folded.length > typed.length && word.folded.startsWith(typed));
      const first = found[0];
      if (!first || (list.canonical && found.length > 1)) continue;
      let end = first.folded.length;
      for (const word of found) {
        let i = typed.length;
        while (i < end && word.folded[i] === first.folded[i]) i++;
        end = i;
      }
      if (found.length > 1 && end < first.folded.length && first.folded[end] !== ' ') {
        end = Math.max(typed.length, first.folded.lastIndexOf(' ', end - 1));
      }
      const completed = first.text.slice(0, end).trimEnd();
      const ghost = completed.slice(typed.length);
      if (!ghost) continue;
      return { ghost, accepted: list.canonical ? text.slice(0, start) + completed : text + ghost };
    }
  }
  return null;
}
