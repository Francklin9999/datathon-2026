/**
 * Dashboard data scope: what the Home widgets show. The period either follows the app window or is
 * a custom date range sent to the API (every window-based figure is recomputed server-side); the
 * benchmark is requested from the API; asset-group and weight filters narrow the holdings widgets.
 */
import type { AssetGroup, Lang, SnapshotPosition, WindowCode, WindowSpec } from '../../contracts/types';
import { fmtDate, fmtNumber } from '../format';
import { ASSET_GROUP, labelOf } from '../labels';

export type ChartMode = 'value' | 'indexed' | 'drawdown';
export type ScopePeriod = { mode: 'window' } | { mode: 'custom'; start: string; end: string };

export interface DashboardScope {
  period: ScopePeriod;
  benchmark: string | null;
  /** Empty = every asset group. */
  assetGroups: AssetGroup[];
  /** Hide positions below this weight (percent of the portfolio). */
  minWeight: number;
  chartMode: ChartMode;
}

export const ASSET_GROUPS: readonly AssetGroup[] = ['equity', 'fixed_income', 'commodity', 'crypto', 'cash'];
export const MIN_WEIGHT_STEPS: readonly number[] = [0, 1, 2, 5, 10];

export const DEFAULT_SCOPE: DashboardScope = { period: { mode: 'window' }, benchmark: null, assetGroups: [], minWeight: 0, chartMode: 'value' };

const ISO = /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;

function isIsoDate(value: unknown): value is string {
  if (typeof value !== 'string' || !ISO.test(value)) return false;
  const instant = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(instant) && new Date(instant).toISOString().slice(0, 10) === value;
}

/** Error code for a custom range, or null when usable. `dataAsOf` is the last date with data. */
export function validateRange(start: string, end: string, dataAsOf: string): 'format' | 'order' | 'after_data' | null {
  if (!isIsoDate(start) || !isIsoDate(end)) return 'format';
  if (start >= end) return 'order';
  if (end > dataAsOf) return 'after_data';
  return null;
}

export function scopeWindow(scope: DashboardScope, windowCode: WindowCode): WindowSpec {
  return scope.period.mode === 'custom'
    ? { code: 'custom', start: scope.period.start, end: scope.period.end }
    : { code: windowCode };
}

/** Cache-key fragment for the effective window (same notation as the engine's fact keys). */
export function scopeWindowKey(scope: DashboardScope, windowCode: WindowCode): string {
  return scope.period.mode === 'custom' ? `custom:${scope.period.start}..${scope.period.end}` : windowCode;
}

export function normalizeScope(stored: unknown): DashboardScope {
  if (!stored || typeof stored !== 'object') return DEFAULT_SCOPE;
  const s = stored as Record<string, unknown>;
  const p = s.period as Record<string, unknown> | undefined;
  const period: ScopePeriod = p && p.mode === 'custom' && isIsoDate(p.start) && isIsoDate(p.end) && p.start < p.end
    ? { mode: 'custom', start: p.start, end: p.end }
    : { mode: 'window' };
  const assetGroups = Array.isArray(s.assetGroups)
    ? ASSET_GROUPS.filter(g => (s.assetGroups as unknown[]).includes(g))
    : [];
  const rawWeight = typeof s.minWeight === 'number' && Number.isFinite(s.minWeight) ? s.minWeight : 0;
  // Snap down to an offered step so the control always names the filter in force.
  const minWeight = [...MIN_WEIGHT_STEPS].reverse().find(step => step <= rawWeight) ?? 0;
  const chartMode: ChartMode = s.chartMode === 'indexed' || s.chartMode === 'drawdown' ? s.chartMode : 'value';
  const benchmark = typeof s.benchmark === 'string' && /^[A-Z0-9.\-]{1,15}$/.test(s.benchmark) ? s.benchmark : null;
  return { period, benchmark, assetGroups, minWeight, chartMode };
}

/** Holdings in scope: selected asset groups (all when none) and at least the minimum weight. */
export function filterPositions<T extends Pick<SnapshotPosition, 'assetGroup' | 'weightPct'>>(positions: readonly T[], scope: DashboardScope): T[] {
  return positions
    .filter(p => (scope.assetGroups.length === 0 || scope.assetGroups.includes(p.assetGroup)) && p.weightPct >= scope.minWeight)
    .sort((a, b) => b.weightPct - a.weightPct);
}

export function isScopeDefault(scope: DashboardScope): boolean {
  return scope.period.mode === 'window' && scope.benchmark === null && scope.assetGroups.length === 0 && scope.minWeight === 0 && scope.chartMode === 'value';
}

/**
 * The same date `years` earlier. 29 February becomes the 28th when that year has none: the rule of
 * the engine's preset windows (backend/aplomb/quant/engine.py::_years_before), so a range seeded from
 * a preset is always a valid ISO date.
 */
export function yearsBefore(iso: string, years: number): string {
  const year = String(Number(iso.slice(0, 4)) - years).padStart(4, '0');
  const candidate = `${year}${iso.slice(4)}`;
  return isIsoDate(candidate) ? candidate : `${year}${iso.slice(4, 8)}28`;
}

/**
 * Dates a new custom Range starts from: the period of the window on screen when the overview gave one
 * (the API's resolved first and last day, so the figures stay the same), else the preset counted back
 * from the data date (the engine's rule; year to date starts on 31 December). Full sample, or no
 * known period: the three years up to the data date.
 */
export function defaultRange(windowCode: WindowCode, dataAsOf: string, shown?: { start: string; end: string } | null): { start: string; end: string } {
  if (shown && validateRange(shown.start, shown.end, dataAsOf) === null) return { start: shown.start, end: shown.end };
  if (windowCode === 'ytd') return { start: `${String(Number(dataAsOf.slice(0, 4)) - 1).padStart(4, '0')}-12-31`, end: dataAsOf };
  const years = windowCode === '1y' ? 1 : windowCode === '5y' ? 5 : 3;
  return { start: yearsBefore(dataAsOf, years), end: dataAsOf };
}

/** Filters that sit in the phone "Filters" disclosure and differ from the default (the period stays visible). */
export function hiddenFilterCount(scope: DashboardScope): number {
  return [scope.benchmark !== null, scope.assetGroups.length > 0, scope.minWeight > 0, scope.chartMode !== 'value'].filter(Boolean).length;
}

/**
 * One short phrase per field that differs from the default, in a fixed order (period, asset classes,
 * minimum weight, benchmark, chart view). Empty exactly when `isScopeDefault(scope)`.
 */
export function scopeSummary(scope: DashboardScope, lang: Lang): string[] {
  const t = (en: string, fr: string) => (lang === 'fr' ? fr : en);
  const parts: string[] = [];
  if (scope.period.mode === 'custom') {
    const start = fmtDate(scope.period.start, lang);
    const end = fmtDate(scope.period.end, lang);
    parts.push(t(`${start} to ${end}`, `du ${start} au ${end}`));
  }
  if (scope.assetGroups.length > 0) {
    const names = ASSET_GROUPS.filter(g => scope.assetGroups.includes(g)).map(g => labelOf(ASSET_GROUP, g, lang)).join(' + ');
    parts.push(t(`${names} only`, `${names} seulement`));
  }
  if (scope.minWeight > 0) parts.push(`positions ≥ ${fmtNumber(scope.minWeight, lang, 0)} %`);
  if (scope.benchmark !== null) parts.push(t(`benchmark ${scope.benchmark}`, `indice ${scope.benchmark}`));
  if (scope.chartMode === 'indexed') parts.push(t('Base 100 chart', 'graphique Base 100'));
  if (scope.chartMode === 'drawdown') parts.push(t('Drawdown chart', 'graphique Repli'));
  return parts;
}

/**
 * keepPreviousFrom for a Home query (useQuery): keep the last data on screen while a new period or
 * benchmark loads, only when the previous key is the same query kind for the same session, profile
 * version and data version (`base` is profileKey). A persona, profile edit or data change never keeps it.
 */
export function sameSubject(kind: string, base: string | null): (previousKey: string) => boolean {
  const parts = base ? [kind, ...base.split('|')] : null;
  return previousKey => {
    if (!parts) return false;
    const previous = previousKey.split('|');
    return previous.length > parts.length && parts.every((part, i) => previous[i] === part);
  };
}
