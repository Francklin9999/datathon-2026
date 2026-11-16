'use client';
/**
 * Theme context: the stored preference (light / dark / system) and the resolved mode on
 * html[data-theme]. The <head> boot script already applied the right mode before paint; this only
 * keeps it in sync with the theme control in Settings and with OS changes while the preference is `system`.
 */
import { MotionConfig } from 'motion/react';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { readPref, writePref } from '../../lib/session';
import { THEME_PREF_KEY, isThemePref, motionReducedFor, themeColorFor, themeToApply, type ThemeMode, type ThemePref } from '../../lib/ui/theme';

interface ThemeState { theme: ThemeMode; pref: ThemePref; setPref: (pref: ThemePref) => void }

function currentDocumentTheme(): ThemeMode {
  if (typeof document === 'undefined') return 'light';
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

const ThemeContext = createContext<ThemeState | null>(null);
const DARK_QUERY = '(prefers-color-scheme: dark)';

function applyTheme(theme: ThemeMode): void {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  // Browser chrome follows the chosen theme too, not only the OS media queries.
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach(meta => { meta.content = themeColorFor(theme); });
}

export function useTheme(): ThemeState {
  const value = useContext(ThemeContext);
  if (!value) throw new Error('useTheme outside ThemeProvider');
  return value;
}

function ThemeProvider({ children }: { children: ReactNode }) {
  // null until the stored preference is read: until then the <head> boot script's choice stands.
  const [pref, setPrefState] = useState<ThemePref | null>(null);
  const [theme, setTheme] = useState<ThemeMode>('light');

  // Read after mount so the static HTML is identical for every visitor (same rule as app.tsx).
  useEffect(() => {
    const stored = readPref(THEME_PREF_KEY);
    setPrefState(isThemePref(stored) ? stored : 'system');
  }, []);

  useEffect(() => {
    const media = window.matchMedia?.(DARK_QUERY);
    const sync = () => {
      const next = themeToApply(pref, Boolean(media?.matches));
      if (next === null) { setTheme(currentDocumentTheme()); return; }
      setTheme(next);
      applyTheme(next);
    };
    sync();
    if (pref !== 'system' || !media) return undefined;
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, [pref]);

  const setPref = useCallback((next: ThemePref) => {
    setPrefState(next);
    writePref(THEME_PREF_KEY, next);
  }, []);

  const value = useMemo(() => ({ theme, pref: pref ?? 'system', setPref }), [theme, pref, setPref]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/**
 * The Settings animation choice (html[data-anim]) as a MotionConfig rule, kept current while the page
 * is open; `user` (follow the system) until mounted and for Auto. Same source as CountUp and the globe.
 */
function useMotionReduced(): 'always' | 'never' | 'user' {
  const [reduced, setReduced] = useState<'always' | 'never' | 'user'>('user');
  useEffect(() => {
    const root = document.documentElement;
    const update = () => setReduced(motionReducedFor(root.dataset.anim));
    update();
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ['data-anim'] });
    return () => observer.disconnect();
  }, []);
  return reduced;
}

/** Client-side UI providers: theme plus a global reduced-motion rule (Settings > Animations, else the system). */
export function UiProviders({ children }: { children: ReactNode }) {
  const reducedMotion = useMotionReduced();
  return (
    <ThemeProvider>
      <MotionConfig reducedMotion={reducedMotion}>{children}</MotionConfig>
    </ThemeProvider>
  );
}
