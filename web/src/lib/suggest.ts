/**
 * Suggestions for search fields. The list is indexed once (folded case and accents), then ranked
 * locally on every keystroke: no request per key and no debounce, so suggestions follow typing.
 * Ranking: exact value, value prefix, a word of the label starting with the query, then the query
 * anywhere. Ties keep the list's own order (callers put the investor's holdings first).
 */
import type { Asset } from '../contracts/types';

export interface Suggestion {
  /** What the field receives when the suggestion is chosen: a ticker, an ISO code. */
  value: string;
  /** Shown beside the value and searched too: the asset or country name; may be empty. */
  label: string;
  /** Short note at the end of the row, such as "Held". */
  meta?: string;
}

interface Entry {
  item: Suggestion;
  order: number;
  value: string;
  label: string;
  words: readonly string[];
}

export interface SuggestIndex {
  readonly entries: readonly Entry[];
}

/** Lower case without accents, for matching only (keeps the length of composed text). */
export function fold(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

/** Indexes suggestions once; a value already listed keeps its first row (a holding before the universe). */
export function buildSuggestIndex(items: readonly Suggestion[]): SuggestIndex {
  const seen = new Set<string>();
  const entries: Entry[] = [];
  for (const item of items) {
    if (!item.value || seen.has(item.value)) continue;
    seen.add(item.value);
    const label = fold(item.label);
    entries.push({ item, order: entries.length, value: fold(item.value), label, words: label.split(/[^a-z0-9]+/).filter(Boolean) });
  }
  return { entries };
}

function score(entry: Entry, query: string): number {
  if (entry.value === query) return 0;
  if (entry.value.startsWith(query)) return 1;
  if (entry.label.startsWith(query) || entry.words.some(word => word.startsWith(query))) return 2;
  if (entry.value.includes(query)) return 3;
  if (entry.label.includes(query)) return 4;
  return -1;
}

/** The best `limit` suggestions for `query`; an empty query lists the first ones in order. */
export function rankSuggestions(index: SuggestIndex, query: string, limit: number): Suggestion[] {
  const folded = fold(query.trim());
  if (!folded) return index.entries.slice(0, limit).map(entry => entry.item);
  const matches: { entry: Entry; score: number }[] = [];
  for (const entry of index.entries) {
    const s = score(entry, folded);
    if (s >= 0) matches.push({ entry, score: s });
  }
  matches.sort((a, b) => a.score - b.score || a.entry.order - b.entry.order);
  return matches.slice(0, limit).map(match => match.entry.item);
}

/**
 * Opening a field that already holds one of the values lists everything, that value first, like a
 * select: a prefilled "CAD" or "individual" would otherwise only ever suggest itself. Null otherwise.
 */
export function browseSuggestions(index: SuggestIndex, value: string, limit: number): Suggestion[] | null {
  const folded = fold(value.trim());
  const exact = folded ? index.entries.find(entry => entry.value === folded) : undefined;
  if (!exact) return null;
  return [exact.item, ...index.entries.filter(entry => entry !== exact).map(entry => entry.item)].slice(0, limit);
}

/** Where `query` first appears in `text` (case-insensitive), to emphasize it; null when it does not. */
export function matchSpan(text: string, query: string): [number, number] | null {
  const q = query.trim().toLowerCase();
  if (!q) return null;
  const at = text.toLowerCase().indexOf(q);
  return at < 0 ? null : [at, at + q.length];
}

/** Ticker suggestions: the investor's holdings first (named when the universe knows them), then the universe. */
export function tickerSuggestions(assets: readonly Pick<Asset, 'ticker' | 'name'>[], held: readonly string[], heldMeta: string): Suggestion[] {
  const names = new Map(assets.map(asset => [asset.ticker, asset.name]));
  return [
    ...held.map(ticker => ({ value: ticker, label: names.get(ticker) ?? '', meta: heldMeta })),
    ...assets.map(asset => ({ value: asset.ticker, label: asset.name })),
  ];
}
