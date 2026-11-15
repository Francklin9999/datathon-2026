/**
 * Count-up for formatted figures. A display string such as "CAD 600,000", "+50.0%", "−4.7 %" or
 * "1 234,5 $" is split around its number; intermediate values are written back with the same sign
 * style, decimals and separators, so only the digits move while the figure climbs to its value.
 */
import type { Lang } from '../../contracts/types';

export interface NumberParts {
  prefix: string;
  suffix: string;
  value: number;
  decimals: number;
  /** Sign written before the number in the source: '+', '-', '−' or ''. */
  sign: string;
  group: string;
  decimal: string;
}

// A number with optional sign, thousands groups (comma, dot, space, no-break spaces) and decimals.
const NUMBER = /([+\-−]?)(\d{1,3}(?:[,.   ]\d{3})+|\d+)(?:([.,])(\d+))?/;

/** Parse the first number in a formatted string, using the language to tell decimals from groups. */
export function parseFigure(text: string, lang: Lang): NumberParts | null {
  const match = NUMBER.exec(text);
  if (!match || match.index === undefined) return null;
  const [whole, sign = '', intPart = '', sep, frac] = match;
  let integer = intPart;
  let decimals = frac ?? '';
  let decimal = sep ?? (lang === 'fr' ? ',' : '.');
  // "600,000" in English is a group, not a decimal; "1,5" in French is a decimal.
  const groupChar = lang === 'fr' ? ' ' : ',';
  if (!frac && /[,.   ]/.test(intPart)) {
    const separators = intPart.replace(/\d/g, '');
    const last = separators[separators.length - 1] ?? '';
    const tail = intPart.slice(intPart.lastIndexOf(last) + 1);
    const looksDecimal = (lang === 'fr' && last === ',') || (lang === 'en' && last === '.');
    if (looksDecimal && separators.length === 1) {
      integer = intPart.slice(0, intPart.lastIndexOf(last));
      decimals = tail;
      decimal = last;
    }
  }
  const groupMatch = integer.match(/[,.   ]/);
  const group = groupMatch ? groupMatch[0] : groupChar;
  const digitsOnly = integer.replace(/[^\d]/g, '');
  const value = Number(`${digitsOnly}${decimals ? `.${decimals}` : ''}`);
  if (!Number.isFinite(value)) return null;
  const negative = sign === '-' || sign === '−';
  return {
    prefix: text.slice(0, match.index),
    suffix: text.slice(match.index + whole.length),
    value: negative ? -value : value,
    decimals: decimals.length,
    sign,
    group,
    decimal,
  };
}

/** Write a value back in the source style (same decimals, separators and sign character). */
export function formatLike(parts: NumberParts, value: number): string {
  const abs = Math.abs(value);
  const fixed = abs.toFixed(parts.decimals);
  const [int = '0', frac] = fixed.split('.');
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, parts.group);
  const body = frac ? `${grouped}${parts.decimal}${frac}` : grouped;
  const isZero = Number(fixed) === 0;
  let sign = '';
  if (value < 0 && !isZero) sign = parts.sign === '-' ? '-' : '−';
  else if (parts.sign === '+' && !isZero) sign = '+';
  return `${parts.prefix}${sign}${body}${parts.suffix}`;
}

/** Ease-out: fast at first, settling on the value. */
export function easeOutCubic(t: number): number {
  const c = Math.min(1, Math.max(0, t));
  return 1 - (1 - c) ** 3;
}

export const COUNT_UP_MS = 1100;
