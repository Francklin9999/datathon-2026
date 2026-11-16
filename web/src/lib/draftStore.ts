/**
 * Unsaved editor input kept across a profile reload (web/page-specs/portfolio.md: "version conflict
 * prompts reload with edits preserved locally"). PortfolioPage keys its editors by profile version,
 * so a reload that brings a newer version remounts them; an editor stashes its draft just before
 * it asks for the reload and reads it back on the remount. Memory only, never persisted.
 */

/** A draft older than this is not restored: it belongs to a reload that did not remount the editor. */
export const DRAFT_TTL_MS = 60_000;

interface Entry { version: number; savedAt: number; value: unknown }

const drafts = new Map<string, Entry>();

/** Remember `value`, typed against profile `version`, under `key` (component and profile id). */
export function stashDraft(key: string, version: number, value: unknown, now: number = Date.now()): void {
  drafts.set(key, { version, savedAt: now, value });
}

/**
 * The draft stashed under `key`, only when the profile is now newer than the one it was typed
 * against and the stash is recent; otherwise null. A stale entry is removed. Reading does not
 * consume a usable entry (React may run a state initializer twice); call dropDraft once used.
 */
export function peekDraft<T>(key: string, version: number, now: number = Date.now()): T | null {
  const entry = drafts.get(key);
  if (!entry) return null;
  if (now - entry.savedAt > DRAFT_TTL_MS || now < entry.savedAt) {
    drafts.delete(key);
    return null;
  }
  return version > entry.version ? (entry.value as T) : null;
}

export function dropDraft(key: string): void {
  drafts.delete(key);
}

/**
 * Per-row editor state rebuilt from the reloaded profile (`fresh`), with the stashed value kept for
 * every row that still exists. Rows only in the draft (removed by the newer version) are dropped,
 * and rows only in `fresh` (added by it) start from the profile.
 */
export function mergeDraftRows<T>(fresh: Record<string, T>, draft: Record<string, T> | null | undefined): Record<string, T> {
  if (!draft) return fresh;
  return Object.fromEntries(Object.entries(fresh).map(([key, value]) =>
    [key, Object.prototype.hasOwnProperty.call(draft, key) ? draft[key] as T : value]));
}
