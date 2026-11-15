/**
 * Session capability (A-20): `s_` + UUIDv4 kept in localStorage. It is a bearer capability, not an
 * account: losing it loses access to this browser's private demo state.
 */
const SESSION_KEY = 'aplomb.session';
const SESSION_PATTERN = /^s_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

let memorySession: string | null = null;

export function isSessionId(value: unknown): value is string {
  return typeof value === 'string' && SESSION_PATTERN.test(value);
}

export function newSessionId(): string {
  return `s_${crypto.randomUUID()}`;
}

function storage(): Storage | null {
  try { return typeof window === 'undefined' ? null : window.localStorage; } catch { return null; }
}

/** Restore or create the session. Falls back to an in-memory value when storage is blocked. */
export function ensureSessionId(): string {
  if (memorySession) return memorySession;
  const store = storage();
  let stored: string | null = null;
  try { stored = store?.getItem(SESSION_KEY) ?? null; } catch { stored = null; }
  if (isSessionId(stored)) {
    memorySession = stored;
    return stored;
  }
  const created = newSessionId();
  try { store?.setItem(SESSION_KEY, created); } catch { /* storage blocked: session lasts this tab */ }
  memorySession = created;
  return created;
}

export function getSessionId(): string | null {
  return memorySession;
}

/** UI preferences and selections only; the server stays authoritative for profiles and runs. */
export function readPref(key: string): string | null {
  try { return storage()?.getItem(`aplomb.pref.${key}`) ?? null; } catch { return null; }
}

export function writePref(key: string, value: string): void {
  try { storage()?.setItem(`aplomb.pref.${key}`, value); } catch { /* ignore */ }
}
