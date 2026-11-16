/**
 * Formatting for numbers the UI receives as raw numbers (tables, axes). Fact values always use the
 * backend's `display` text instead, so a sentence never shows a re-rounded value.
 */
import type { Currency, Lang, PolicyRule, RuleCheck, Unit } from '../contracts/types';

const locale = (lang: Lang) => (lang === 'fr' ? 'fr-CA' : 'en-CA');

/** A formatted number that shows no digit other than zero: zero at the displayed precision. */
const isZeroText = (text: string) => !/[1-9]/.test(text);

/**
 * A value that is zero at the displayed precision is written without a sign: `-0` and `-0.03` at one
 * decimal give "0.0", never "-0.0".
 */
export function fmtNumber(value: number, lang: Lang, digits = 1): string {
  const format = new Intl.NumberFormat(locale(lang), { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const text = format.format(value);
  return Number.isFinite(value) && isZeroText(text) ? format.format(0) : text;
}

/** Percent units: 25.0 → "25.0%" ("25,0 %" in French). */
export function fmtPct(value: number, lang: Lang, digits = 1): string {
  return lang === 'fr' ? `${fmtNumber(value, lang, digits)} %` : `${fmtNumber(value, lang, digits)}%`;
}

/** Signed percent with a true minus sign: +3.2% / −4.1%. Zero at the displayed precision has no sign. */
export function fmtSignedPct(value: number, lang: Lang, digits = 1): string {
  const body = fmtPct(Math.abs(value), lang, digits);
  if (isZeroText(body)) return body;
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

/**
 * An informational rule check (no comparator, no threshold) measured in percent is a return, such as
 * the rate-hiking-cycle replay (flag.rate_cycle): it is shown signed with two decimals, so a small loss
 * reads "−0.02%" instead of an unsigned "0.0%". Every other check keeps its unit format.
 */
export function isInformationalReturn(check: Pick<RuleCheck, 'comparator' | 'threshold' | 'unit'>): boolean {
  return check.comparator === 'none' && check.threshold === null && check.unit === 'pct';
}

export function ruleValueText(check: Pick<RuleCheck, 'comparator' | 'threshold' | 'unit' | 'value'>, lang: Lang): string {
  if (check.value === null) return '—';
  return isInformationalReturn(check) ? fmtSignedPct(check.value, lang, 2) : fmtUnit(check.value, check.unit, lang);
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
 * stem ("volatility"). Both are accepted (contracts/schemas.md, PortfolioSnapshot.metrics.factIds).
 */
export function factIdFor(map: Record<string, string> | undefined, field: string): string | undefined {
  if (!map) return undefined;
  return map[field] ?? map[field.replace(/Pct$/, '')];
}

/**
 * Fill a rule label's "{threshold}" placeholder. Contract fixtures write the unit after the
 * placeholder ("above {threshold}% of the portfolio"), so a bare number is inserted there;
 * otherwise the value is formatted with its unit (see contracts/schemas.md, PolicyRule.label).
 */
export function fillThreshold(template: string, threshold: number | null, unit: Unit, lang: Lang): string {
  if (threshold === null) return template.replace('{threshold}', '—');
  const unitFollows = /\{threshold\}\s?(%|pts?\b|\$)/.test(template);
  const digits = unit === 'ratio' ? 2 : unit === 'count' || unit === 'days' ? 0 : 1;
  return template.replace('{threshold}', unitFollows ? fmtNumber(threshold, lang, digits) : fmtUnit(threshold, unit, lang));
}

/**
 * The sentence of a rule row. With a check, the label is filled with the threshold and unit the check
 * was EVALUATED with (`RuleCheck.threshold`), never the profile's current threshold: a replay re-derives
 * thresholds at its cutoff, an unsaved preview overrides them, and a signed run keeps its own after a
 * later rule edit. Without a rule (removed from the profile, or another profile) the check's own detail
 * is the sentence.
 */
export function ruleSentence(rule: PolicyRule | undefined, check: RuleCheck | null, lang: Lang): string {
  if (!rule) return check ? (check.detail[lang] || check.detail.en) : '';
  const template = rule.label[lang] || rule.label.en;
  return check
    ? fillThreshold(template, check.threshold, check.unit, lang)
    : fillThreshold(template, rule.threshold, rule.unit, lang);
}
