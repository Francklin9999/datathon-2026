/**
 * Correlation heatmap colours: a diverging scale with two poles and a neutral middle (never a hue at
 * zero). −1 is cobalt (the app accent: moves the other way, which diversifies), 0 is the glass grey
 * (independent), +1 is a warm orange (moves together, which concentrates risk); orange keeps clear of
 * the red and amber reserved for rule statuses. Colours are interpolated in OKLab so each arm darkens
 * evenly. Every cell picks black or white text, whichever contrasts more: only pure black and white
 * leave no mid-tone where neither ink reaches AA (tests check every step).
 */
import type { ThemeMode } from './theme';

export interface CorrScale { neg: string; mid: string; pos: string; textDark: string; textLight: string }

export const CORR_SCALE: Record<ThemeMode, CorrScale> = {
  light: { neg: '#2F5BFF', mid: '#EEF0F5', pos: '#D9561C', textDark: '#000000', textLight: '#FFFFFF' },
  dark: { neg: '#5B7CFF', mid: '#2A2D36', pos: '#D86A31', textDark: '#000000', textLight: '#FFFFFF' },
};

type Rgb = [number, number, number];
type Lab = [number, number, number];

function hexToRgb(hex: string): Rgb {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

function toLinear(c: number): number {
  const v = c / 255;
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

function fromLinear(v: number): number {
  const c = v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055;
  return Math.round(Math.min(1, Math.max(0, c)) * 255);
}

function rgbToOklab([r, g, b]: Rgb): Lab {
  const lr = toLinear(r); const lg = toLinear(g); const lb = toLinear(b);
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

function oklabToRgb([L, a, b]: Lab): Rgb {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    fromLinear(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    fromLinear(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    fromLinear(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ];
}

const hex2 = (n: number) => n.toString(16).padStart(2, '0');
const rgbToHex =([r, g, b]: Rgb): string => `#${hex2(r)}${hex2(g)}${hex2(b)}`.toUpperCase();

/** Relative luminance and WCAG contrast ratio. */
export function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map(toLinear) as Rgb;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/** Background colour of a cell for a correlation in [−1, 1] (clamped; NaN reads as 0). */
export function corrColor(r: number, theme: ThemeMode): string {
  const scale = CORR_SCALE[theme];
  const v = Number.isFinite(r) ? Math.max(-1, Math.min(1, r)) : 0;
  const pole = rgbToOklab(hexToRgb(v < 0 ? scale.neg : scale.pos));
  const mid = rgbToOklab(hexToRgb(scale.mid));
  const t = Math.abs(v);
  return rgbToHex(oklabToRgb([mid[0] + (pole[0] - mid[0]) * t, mid[1] + (pole[1] - mid[1]) * t, mid[2] + (pole[2] - mid[2]) * t]));
}

/** Text colour for a cell: whichever of the two text inks contrasts more with the background. */
export function corrText(background: string, theme: ThemeMode): string {
  const { textDark, textLight } = CORR_SCALE[theme];
  return contrast(background, textDark) >= contrast(background, textLight) ? textDark : textLight;
}

/** CSS gradient for the legend bar, sampled from the same scale. */
export function corrGradient(theme: ThemeMode): string {
  const stops = [-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1].map((v, i) => `${corrColor(v, theme)} ${i * 12.5}%`);
  return `linear-gradient(90deg, ${stops.join(', ')})`;
}

export type CorrStrength = 'opposite_strong' | 'opposite' | 'opposite_weak' | 'independent' | 'together_weak' | 'together' | 'together_strong';

/** Plain-language strength band used in the cell tooltip. */
export function corrStrength(r: number): CorrStrength {
  const a = Math.abs(r);
  if (a < 0.2) return 'independent';
  if (r > 0) return a >= 0.8 ? 'together_strong' : a >= 0.5 ? 'together' : 'together_weak';
  return a >= 0.8 ? 'opposite_strong' : a >= 0.5 ? 'opposite' : 'opposite_weak';
}
