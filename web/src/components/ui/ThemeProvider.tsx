'use client';
/**
 * Theme context: the stored preference (light / dark / system) and the resolved mode on
 * html[data-theme]. The <head> boot script already applied the right mode before paint; this only
 * keeps it in sync with the toggle and with OS changes while the preference is `system`.
 */
import { MotionConfig } from 'motion/react';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { readPref, writePref } from '../../lib/session';
import { THEME_PREF_KEY, isThemePref, themeColorFor, themeToApply, type ThemeMode, type ThemePref } from '../../lib/ui/theme';

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

export function ThemeProvider({ children }: { children: ReactNode }) {
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

/** Client-side UI providers: theme plus a global "respect the user's reduced-motion setting" rule. */
export function UiProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </ThemeProvider>
  );
}
