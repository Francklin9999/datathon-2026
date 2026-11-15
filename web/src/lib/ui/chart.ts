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
