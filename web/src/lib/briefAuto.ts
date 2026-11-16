/**
 * At most one automatic portfolio brief per session, profile and data version (QA 2a), remembered in
 * localStorage so a reload, a new tab or a language switch never writes another one. The key is
 * consumed the first time Home evaluates a loaded brief lookup for it, whether or not a run is then
 * started; storage is written before the run is requested. Blocked storage falls back to memory
 * (this page load only).
 */

const STORAGE_KEY = 'aplomb.brief.auto.v1';
/** Oldest keys are dropped beyond this many. */
export const AUTO_BRIEF_KEEP = 20;

const memory = new Set<string>();

export function autoBriefKey(sessionId: string, profileId: string, dataVersion: string): string {
  return `${sessionId}|${profileId}|${dataVersion}`;
}

/** `list` with `key` appended once, keeping the newest `keep` entries. */
export function rememberKey(list: readonly string[], key: string, keep = AUTO_BRIEF_KEEP): string[] {
  return [...list.filter(k => k !== key), key].slice(-keep);
}

type KeyStore = Pick<Storage, 'getItem' | 'setItem'>;

function defaultStore(): KeyStore | null {
  try { return typeof window === 'undefined' ? null : window.localStorage; } catch { return null; }
}

function read(store: KeyStore | null): string[] {
  try {
    const parsed: unknown = JSON.parse(store?.getItem(STORAGE_KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed.filter((k): k is string => typeof k === 'string') : [];
  } catch { return []; }
}

export function autoBriefUsed(key: string, store: KeyStore | null = defaultStore()): boolean {
  return memory.has(key) || read(store).includes(key);
}

export function markAutoBrief(key: string, store: KeyStore | null = defaultStore()): void {
  memory.add(key);
  try { store?.setItem(STORAGE_KEY, JSON.stringify(rememberKey(read(store), key))); } catch { /* blocked: memory only */ }
}
