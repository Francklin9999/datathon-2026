/** Keyboard model for radio-group style segmented controls, and compact window labels. */
import type { Lang, WindowCode } from '../../contracts/types';

/** Arrow keys move and wrap (both axes, as in a radio group); Home/End jump; other keys → null. */
export function nextSegmentIndex(current: number, key: string, count: number): number | null {
  if (count <= 0) return null;
  switch (key) {
    case 'ArrowRight': case 'ArrowDown': return (current + 1) % count;
    case 'ArrowLeft': case 'ArrowUp': return (current - 1 + count) % count;
    case 'Home': return 0;
    case 'End': return count - 1;
    default: return null;
  }
}

const SHORT: Record<Exclude<WindowCode, 'custom'>, { en: string; fr: string }> = {
  full: { en: 'All', fr: 'Tout' },
  '1y': { en: '1Y', fr: '1A' },
  '3y': { en: '3Y', fr: '3A' },
  '5y': { en: '5Y', fr: '5A' },
  ytd: { en: 'YTD', fr: 'AAJ' },
};

/** Short visible label for a window; the full label stays the accessible name. */
export function windowShortLabel(code: WindowCode, lang: Lang): string {
  return code === 'custom' ? (lang === 'fr' ? 'Perso' : 'Custom') : SHORT[code][lang];
}

/** Accessible name that starts with the visible label (WCAG 2.5.3), e.g. "YTD, Year to date". */
export function segmentAccessibleName(label: string, title: string | undefined): string | undefined {
  return title && title !== label ? `${label}, ${title}` : undefined;
}
