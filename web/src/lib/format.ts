/**
 * Formatting for numbers the UI receives as raw numbers (tables, axes). Fact values always use the
 * backend's `display` text instead, so a sentence never shows a re-rounded value.
 */
import type { Currency, Lang, Unit } from '../contracts/types';

const locale = (lang: Lang) => (lang === 'fr' ? 'fr-CA' : 'en-CA');

export function fmtNumber(value: number, lang: Lang, digits = 1): string {
  return new Intl.NumberFormat(locale(lang), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

/** Percent units: 25.0 → "25.0%" ("25,0 %" in French). */
export function fmtPct(value: number, lang: Lang, digits = 1): string {
  return lang === 'fr' ? `${fmtNumber(value, lang, digits)} %` : `${fmtNumber(value, lang, digits)}%`;
}

/** Signed percent with a true minus sign: +3.2% / −4.1%. */
export function fmtSignedPct(value: number, lang: Lang, digits = 1): string {
  const body = fmtPct(Math.abs(value), lang, digits);
  if (value > 0) return `+${body}`;
  if (value < 0) return `−${body}`;
  return body;
}

export function fmtPts(value: number, lang: Lang, digits = 1): string {
  return `${fmtNumber(value, lang, digits)} pts`;
}

export function fmtMoney(value: number, currency: Currency, lang: Lang, digits = 0): string {
  return new Intl.NumberFormat(locale(lang), {
    style: 'currency', currency, currencyDisplay: 'code',
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  }).format(value);
}

/** Format a rule/check value in its unit. */
export function fmtUnit(value: number | null, unit: Unit, lang: Lang): string {
  if (value === null) return '—';
  switch (unit) {
    case 'pct': return fmtPct(value, lang);
    case 'pts': return fmtPts(value, lang);
    case 'ratio': return fmtNumber(value, lang, 2);
    case 'count': return fmtNumber(value, lang, 0);
    case 'days': return `${fmtNumber(value, lang, 0)} ${lang === 'fr' ? 'j' : 'd'}`;
    case 'cad': return fmtMoney(value, 'CAD', lang);
    case 'usd': return fmtMoney(value, 'USD', lang);
    case 'bool': return value ? (lang === 'fr' ? 'oui' : 'yes') : (lang === 'fr' ? 'non' : 'no');
    default: return fmtNumber(value, lang, 2);
  }
}

export function fmtDate(iso: string, lang: Lang): string {
  const date = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(locale(lang), { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' }).format(date);
}

export function fmtDateTime(iso: string, lang: Lang): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(locale(lang), {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    timeZone: 'UTC', timeZoneName: 'short',
  }).format(date);
}

export function fmtDuration(ms: number | null, lang: Lang): string {
  if (ms === null) return '—';
  if (ms < 1000) return `${fmtNumber(ms, lang, 0)} ms`;
  return `${fmtNumber(ms / 1000, lang, 1)} s`;
}

export function comparatorSymbol(comparator: string): string {
  switch (comparator) {
    case '<=': return '≤';
    case '>=': return '≥';
    case '==': return '=';
    default: return '';
  }
}

/**
 * Look up the fact ID for a metric field in a `factIds` map. The contract leaves the keys
 * undocumented: the run fixture uses field names ("volatilityPct") while the live API uses the
 * stem ("volatility"). Both are accepted (docs/T13-T14-HANDOFF.md, contract note 2).
 */
export function factIdFor(map: Record<string, string> | undefined, field: string): string | undefined {
  if (!map) return undefined;
  return map[field] ?? map[field.replace(/Pct$/, '')];
}

/**
 * Fill a rule label's "{threshold}" placeholder. Contract fixtures write the unit after the
 * placeholder ("above {threshold}% of the portfolio"), so a bare number is inserted there;
 * otherwise the value is formatted with its unit (see docs/T13-T14-HANDOFF.md, contract notes).
 */
export function fillThreshold(template: string, threshold: number | null, unit: Unit, lang: Lang): string {
  if (threshold === null) return template.replace('{threshold}', '—');
  const unitFollows = /\{threshold\}\s?(%|pts?\b|\$)/.test(template);
  const digits = unit === 'ratio' ? 2 : unit === 'count' || unit === 'days' ? 0 : 1;
  return template.replace('{threshold}', unitFollows ? fmtNumber(threshold, lang, digits) : fmtUnit(threshold, unit, lang));
}
