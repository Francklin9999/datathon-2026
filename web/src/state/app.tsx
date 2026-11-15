'use client';
/**
 * Shared bootstrap (web/SPEC.md §2): fetch /meta, restore or create the session capability, then
 * profiles and the selected profile. Only the session ID, UI preferences and selected IDs are kept
 * locally; the server stays authoritative for profile edits and runs.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode,
} from 'react';
import type { I18NText, Lang, Meta, Profile, WindowCode, WindowSpec } from '../contracts/types';
import { FIXTURES_ENABLED, getApiClient } from '../api/index';
import { asApiError, type ApiRequestError } from '../api/errors';
import { ensureSessionId, readPref, writePref } from '../lib/session';
import { pick } from '../lib/labels';

type Phase = 'booting' | 'ready' | 'error';
export const WINDOW_CODES: readonly WindowCode[] = ['full', '1y', '3y', '5y', 'ytd'];

export interface AppState {
  phase: Phase;
  bootError: ApiRequestError | null;
  meta: Meta | null;
  sessionId: string | null;
  profiles: Profile[];
  profilesLoaded: boolean;
  profilesError: ApiRequestError | null;
  profile: Profile | null;
  selectProfile: (profileId: string) => void;
  /** Replace or add one profile after a server write (new version). */
  applyProfile: (profile: Profile) => void;
  removeProfile: (profileId: string) => void;
  reloadProfiles: () => void;
  lang: Lang;
  setLang: (lang: Lang) => void;
  windowCode: WindowCode;
  windowSpec: WindowSpec;
  setWindow: (code: WindowCode) => void;
  tr: (text: I18NText) => string;
  feature: (flag: string) => boolean;
  fixtures: boolean;
  retryBoot: () => void;
  announce: (message: string) => void;
  announcement: string;
}

const AppContext = createContext<AppState | null>(null);

export function useApp(): AppState {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp outside AppProvider');
  return value;
}

/** Shorthand for bilingual inline text. */
export function useTr(): (text: I18NText) => string {
  return useApp().tr;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>('booting');
  const [bootError, setBootError] = useState<ApiRequestError | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profilesLoaded, setProfilesLoaded] = useState(false);
  const [profilesError, setProfilesError] = useState<ApiRequestError | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [lang, setLangState] = useState<Lang>('en');
  const [windowCode, setWindowState] = useState<WindowCode>('full');
  const [bootNonce, setBootNonce] = useState(0);
  const [profilesNonce, setProfilesNonce] = useState(0);
  const [announcement, setAnnouncement] = useState('');
  const announceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Preferences are read after mount so the static HTML is identical for every visitor.
  useEffect(() => {
    const storedLang = readPref('lang');
    if (storedLang === 'en' || storedLang === 'fr') setLangState(storedLang);
    const storedWindow = readPref('window');
    if (storedWindow && (WINDOW_CODES as readonly string[]).includes(storedWindow)) setWindowState(storedWindow as WindowCode);
    setSelectedId(readPref('profile'));
  }, []);

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  useEffect(() => {
    const controller = new AbortController();
    setPhase('booting');
    setBootError(null);
    getApiClient().meta(controller.signal).then(
      fetched => {
        setMeta(fetched);
        setSessionId(ensureSessionId());
        setPhase('ready');
      },
      error => {
        if (controller.signal.aborted) return;
        setBootError(asApiError(error));
        setPhase('error');
      },
    );
    return () => controller.abort();
  }, [bootNonce]);

  useEffect(() => {
    if (phase !== 'ready' || !sessionId) return undefined;
    const controller = new AbortController();
    setProfilesError(null);
    getApiClient().profiles(controller.signal).then(
      response => { setProfiles(response.items); setProfilesLoaded(true); },
      error => { if (!controller.signal.aborted) { setProfilesError(asApiError(error)); setProfilesLoaded(true); } },
    );
    return () => controller.abort();
  }, [phase, sessionId, profilesNonce]);

  // Bilingual feature off: English repeats (WEB-10).
  const effectiveLang: Lang = meta && meta.features.bilingual === false ? 'en' : lang;

  const profile = useMemo(() => {
    if (profiles.length === 0) return null;
    return profiles.find(p => p.profileId === selectedId) ?? profiles[0] ?? null;
  }, [profiles, selectedId]);

  const selectProfile = useCallback((profileId: string) => {
    setSelectedId(profileId);
    writePref('profile', profileId);
  }, []);
  const applyProfile = useCallback((updated: Profile) => {
    setProfiles(list => (list.some(p => p.profileId === updated.profileId)
      ? list.map(p => (p.profileId === updated.profileId ? updated : p))
      : [...list, updated]));
  }, []);
  const removeProfile = useCallback((profileId: string) => {
    setProfiles(list => list.filter(p => p.profileId !== profileId));
  }, []);
  const reloadProfiles = useCallback(() => setProfilesNonce(n => n + 1), []);
  const retryBoot = useCallback(() => setBootNonce(n => n + 1), []);
  const setLang = useCallback((next: Lang) => { setLangState(next); writePref('lang', next); }, []);
  const setWindow = useCallback((code: WindowCode) => { setWindowState(code); writePref('window', code); }, []);
  const tr = useCallback((text: I18NText) => pick(text, effectiveLang), [effectiveLang]);
  const feature = useCallback(
    (flag: string) => Boolean((meta?.features as Record<string, boolean> | undefined)?.[flag]), [meta]);
  const announce = useCallback((message: string) => {
    if (announceTimer.current) clearTimeout(announceTimer.current);
    setAnnouncement('');
    announceTimer.current = setTimeout(() => setAnnouncement(message), 50);
  }, []);

  const value = useMemo<AppState>(() => ({
    phase, bootError, meta, sessionId, profiles, profilesLoaded, profilesError, profile, selectProfile,
    applyProfile, removeProfile, reloadProfiles, lang: effectiveLang, setLang, windowCode,
    windowSpec: { code: windowCode }, setWindow, tr, feature, fixtures: FIXTURES_ENABLED, retryBoot,
    announce, announcement,
  }), [phase, bootError, meta, sessionId, profiles, profilesLoaded, profilesError, profile, selectProfile,
    applyProfile, removeProfile, reloadProfiles, effectiveLang, setLang, windowCode, setWindow, tr, feature,
    retryBoot, announce, announcement]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

/** Cache-key prefix shared by every query that depends on the selected profile version. */
export function profileKey(app: Pick<AppState, 'sessionId' | 'profile' | 'meta'>): string | null {
  if (!app.sessionId || !app.profile || !app.meta) return null;
  return `${app.sessionId}|${app.profile.profileId}|v${app.profile.version}|${app.meta.dataVersion}`;
}
