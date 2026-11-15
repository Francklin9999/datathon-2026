/**
 * Views of a plotted series. They only re-express the points the API returned (no new data):
 * rebased to 100, or as the fall from the running peak. Period change reads the plotted ends.
 */
export interface SeriesPoint { date: string; value: number }

export function indexSeries(points: readonly SeriesPoint[], base = 100): SeriesPoint[] {
  const first = points[0]?.value;
  if (first === undefined || first === 0 || !Number.isFinite(first)) return [];
  return points.map(p => ({ date: p.date, value: (p.value / first) * base }));
}

/** Percent below the highest value seen so far (0 at a new peak, negative below it). */
export function drawdownSeries(points: readonly SeriesPoint[]): SeriesPoint[] {
  let peak = -Infinity;
  return points.map(p => {
    peak = Math.max(peak, p.value);
    return { date: p.date, value: peak > 0 ? (p.value / peak - 1) * 100 : 0 };
  });
}

/** Change from the first to the last plotted point, in percent; null with fewer than two points. */
export function periodChangePct(points: readonly SeriesPoint[]): number | null {
  const first = points[0]?.value;
  const last = points[points.length - 1]?.value;
  if (points.length < 2 || first === undefined || last === undefined || first === 0) return null;
  return (last / first - 1) * 100;
}
