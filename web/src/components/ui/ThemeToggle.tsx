'use client';
/** One button cycling light → dark → system; the accessible name says the current and next mode. */
import { Monitor, Moon, Sun } from 'lucide-react';
import type { I18NText } from '../../contracts/types';
import type { ThemePref } from '../../lib/ui/theme';
import { useApp } from '../../state/app';
import { useTheme } from './ThemeProvider';

const ORDER: readonly ThemePref[] = ['light', 'dark', 'system'];
const NAME: Record<ThemePref, I18NText> = {
  light: { en: 'Light theme', fr: 'Thème clair' },
  dark: { en: 'Dark theme', fr: 'Thème sombre' },
  system: { en: 'System theme', fr: 'Thème du système' },
};

export function ThemeToggle() {
  const { pref, setPref } = useTheme();
  const { tr } = useApp();
  const next = ORDER[(ORDER.indexOf(pref) + 1) % ORDER.length] ?? 'light';
  const Icon = pref === 'light' ? Sun : pref === 'dark' ? Moon : Monitor;
  const label = `${tr(NAME[pref])}. ${tr({ en: 'Switch to', fr: 'Passer au' })} ${tr(NAME[next]).toLowerCase()}`;
  return (
    <button type="button" className="icon-btn theme-toggle" onClick={() => setPref(next)} aria-label={label} title={label}>
      <Icon aria-hidden="true" size={18} strokeWidth={1.75} />
    </button>
  );
}
