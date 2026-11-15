/**
 * Dashboard data scope: what the Home widgets show. The period either follows the app window or is
 * a custom date range sent to the API (every window-based figure is recomputed server-side); the
 * benchmark is requested from the API; asset-group and weight filters narrow the holdings widgets.
 */
import type { AssetGroup, SnapshotPosition, WindowCode, WindowSpec } from '../../contracts/types';

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

export function isIsoDate(value: unknown): value is string {
  return typeof value === 'string' && ISO.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`));
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
