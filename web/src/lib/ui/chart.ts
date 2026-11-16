/** Small, pure helpers for the SVG line/area chart: value range, paths and hover lookup. */
export interface Pt { x: number; y: number }

const f = (n: number) => n.toFixed(2);

/** Padded value range; a flat series gets ±1 so the scale never divides by zero. */
export function chartScale(values: readonly number[], padRatio = 0.05): { lo: number; hi: number } {
  const finite = values.filter(Number.isFinite);
  if (finite.length === 0) return { lo: 0, hi: 1 };
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  if (min === max) return { lo: min - 1, hi: max + 1 };
  const pad = (max - min) * padRatio;
  return { lo: min - pad, hi: max + pad };
}

/**
 * Axis labels on round values inside the padded range [lo, hi] (a step of 1, 2, 2.5 or 5 × 10ⁿ, never
 * finer than the displayed `digits`), so the top label is never the padded bound, which reads like a
 * data peak the series never reached. Falls back to [lo, mid, hi] if fewer than two round values fit.
 */
export function axisTicks(lo: number, hi: number, digits = 0, target = 4): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return [lo, (lo + hi) / 2, hi];
  const rough = (hi - lo) / Math.max(1, target);
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const nice = [1, 2, 2.5, 5, 10].map(m => m * magnitude).find(step => step >= rough) ?? 10 * magnitude;
  const step = Math.max(nice, 10 ** -digits);
  const ticks: number[] = [];
  for (let k = Math.ceil(lo / step - 1e-9); k * step <= hi + 1e-9 * step; k += 1) {
    // Round away binary noise (0.1 + 0.2) at the step's precision.
    ticks.push(Number((k * step).toFixed(Math.max(0, digits, -Math.floor(Math.log10(step)) + 1))));
  }
  return ticks.length >= 2 ? ticks : [lo, (lo + hi) / 2, hi];
}

/** Index of the x closest to `x` in an ascending list (binary search); -1 when empty. */
export function nearestIndex(sortedXs: readonly number[], x: number): number {
  const n = sortedXs.length;
  if (n === 0) return -1;
  let lo = 0;
  let hi = n - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if ((sortedXs[mid] ?? 0) < x) lo = mid + 1; else hi = mid;
  }
  if (lo > 0 && Math.abs((sortedXs[lo - 1] ?? 0) - x) <= Math.abs((sortedXs[lo] ?? 0) - x)) return lo - 1;
  return lo;
}

export function linePath(points: readonly Pt[]): string {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${f(p.x)},${f(p.y)}`).join(' ');
}

/** The line closed down to `baseY`, for a gradient area under it. */
export function areaPath(points: readonly Pt[], baseY: number): string {
  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last) return '';
  return `M${f(first.x)},${f(baseY)} L${linePath(points).slice(1)} L${f(last.x)},${f(baseY)} Z`;
}

/**
 * SVG props per series: the solid line gets pathLength=1 for its draw-in; the dashed comparison
 * line must not, because pathLength rescales stroke-dasharray and would turn its dashes solid.
 */
export function chartLineProps(dashed: boolean): { pathLength?: number; strokeDasharray?: string } {
  return dashed ? { strokeDasharray: '5 5' } : { pathLength: 1 };
}
