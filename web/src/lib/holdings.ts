/** Holdings validation shared by the profile creator and holdings editor (api.md 3.3 / 3.8). */
import type { Position } from '../contracts/types';

export const MAX_POSITIONS = 40;
const WEIGHT_TOLERANCE = 0.01;

export interface HoldingsIssue { code: 'empty' | 'too_many' | 'duplicate' | 'negative' | 'sum' | 'capital'; detail: string }

export function weightSum(positions: readonly Position[]): number {
  return Math.round(positions.reduce((sum, p) => sum + (Number.isFinite(p.weightPct) ? p.weightPct : 0), 0) * 1e6) / 1e6;
}

export function validateHoldings(positions: readonly Position[], totalValue: number): HoldingsIssue[] {
  const issues: HoldingsIssue[] = [];
  if (!(totalValue > 0)) issues.push({ code: 'capital', detail: String(totalValue) });
  if (positions.length === 0) issues.push({ code: 'empty', detail: '0' });
  if (positions.length > MAX_POSITIONS) issues.push({ code: 'too_many', detail: String(positions.length) });
  const seen = new Set<string>();
  for (const position of positions) {
    const ticker = position.ticker.trim().toUpperCase();
    if (seen.has(ticker)) issues.push({ code: 'duplicate', detail: ticker });
    seen.add(ticker);
    if (!(position.weightPct >= 0)) issues.push({ code: 'negative', detail: ticker });
  }
  const sum = weightSum(positions);
  if (positions.length > 0 && Math.abs(sum - 100) > WEIGHT_TOLERANCE) issues.push({ code: 'sum', detail: sum.toFixed(2) });
  return issues;
}
