/**
 * Per-holding trailing 1-year return from an overview (api.md §3.9).
 *
 * Contract 1.6.0 added `holdingReturns`, one entry per held position. An API before 1.6.0 (the
 * deployed 1.4.0 one) sends only `concentration.topPositions`, the five largest holdings; then
 * the other holdings have no entry and the table shows "—" for them.
 */
import type { OverviewResponse } from '../contracts/types';

export interface HoldingReturnCell {
  pct: number | null;
  factId: string | null;
}

export function holdingReturnsOf(
  overview: Pick<OverviewResponse, 'holdingReturns' | 'concentration'>,
): Map<string, HoldingReturnCell> {
  if (overview.holdingReturns) {
    return new Map(overview.holdingReturns.map(r => [r.ticker, { pct: r.return1yPct, factId: r.return1yFactId }]));
  }
  return new Map(overview.concentration.topPositions.map(p => [p.ticker, { pct: p.return1yPct, factId: null }]));
}
