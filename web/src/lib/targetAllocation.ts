import type { Position } from '../contracts/types';

export function parseFinalTargets(text: string): Position[] {
  const rows: Position[] = [];
  const seen = new Set<string>();
  for (const line of text.split('\n').map(x => x.trim()).filter(Boolean)) {
    const [ticker, input, extra] = line.toUpperCase().split(/\s+/);
    const weightPct = Number(input);
    if (!ticker || !/^[A-Z0-9][A-Z0-9.^=-]*$/.test(ticker) || input === undefined || extra || seen.has(ticker) || !Number.isFinite(weightPct) || weightPct < 0 || weightPct > 100) throw new Error('invalid_target');
    seen.add(ticker); rows.push({ ticker, weightPct });
  }
  if (!rows.length || rows.length > 40 || Math.abs(rows.reduce((s, p) => s + p.weightPct, 0) - 100) > 1e-9) throw new Error('invalid_target_sum');
  return rows;
}

/** A chosen point on a linear weight path; never a monotonic compatible-size bound. */
export function blendFinalTargets(before: Position[], target: Position[], progressPct: number): Position[] {
  if (!Number.isFinite(progressPct) || progressPct < 0 || progressPct > 100) throw new Error('invalid_progress');
  // Validate each endpoint independently: a valid midpoint must never conceal an
  // impossible endpoint, duplicate ticker, non-finite weight or negative position.
  for (const positions of [before, target]) {
    const seen = new Set<string>();
    if (!positions.length || positions.length > 40) throw new Error('invalid_positions');
    for (const position of positions) {
      if (!/^[A-Z0-9][A-Z0-9.^=-]*$/.test(position.ticker) || seen.has(position.ticker) ||
          !Number.isFinite(position.weightPct) || position.weightPct < 0 || position.weightPct > 100) throw new Error('invalid_positions');
      seen.add(position.ticker);
    }
    const endpointTotal = positions.reduce((sum, position) => sum + position.weightPct, 0);
    if (!Number.isFinite(endpointTotal) || Math.abs(endpointTotal - 100) > .011) throw new Error('invalid_weight_sum');
  }
  const a = new Map(before.map(p => [p.ticker, p.weightPct]));
  const b = new Map(target.map(p => [p.ticker, p.weightPct]));
  const t = progressPct / 100;
  const result = [...new Set([...a.keys(), ...b.keys()])].sort().map(ticker => ({ ticker, weightPct: (a.get(ticker) ?? 0) * (1 - t) + (b.get(ticker) ?? 0) * t })).filter(p => p.weightPct > 0);
  if (!result.length || result.length > 40) throw new Error('too_many_blended_holdings');
  const sum = result.reduce((n, p) => n + p.weightPct, 0);
  if (Math.abs(sum - 100) > .011 || !Number.isFinite(sum)) throw new Error('invalid_weight_sum');
  // Normalize only the profile's documented input tolerance, preserving conservation exactly.
  return result.map(p => ({ ticker: p.ticker, weightPct: p.weightPct * 100 / sum }));
}
