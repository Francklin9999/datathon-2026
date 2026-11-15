/** Annular-sector geometry for the allocation donut. Pure: values in, SVG path data out. */
export interface DonutGeom { cx: number; cy: number; r: number; thickness: number; gapDeg: number }
export interface DonutArc { key: string; d: string; pct: number }

const f = (n: number) => n.toFixed(3);

function point(cx: number, cy: number, radius: number, deg: number): string {
  const rad = (deg * Math.PI) / 180;
  return `${f(cx + radius * Math.cos(rad))},${f(cy + radius * Math.sin(rad))}`;
}

function ring({ cx, cy, r, thickness }: DonutGeom): string {
  const ri = r - thickness;
  // Outer circle clockwise, inner circle counter-clockwise: a hole under both fill rules.
  return `M${f(cx)},${f(cy - r)} A${f(r)},${f(r)} 0 1 1 ${f(cx)},${f(cy + r)} A${f(r)},${f(r)} 0 1 1 ${f(cx)},${f(cy - r)} Z `
    + `M${f(cx)},${f(cy - ri)} A${f(ri)},${f(ri)} 0 1 0 ${f(cx)},${f(cy + ri)} A${f(ri)},${f(ri)} 0 1 0 ${f(cx)},${f(cy - ri)} Z`;
}

/**
 * One arc per positive value, clockwise from 12 o'clock, `pct` relative to the positive sum.
 * Values ≤ 0 are dropped; a single positive value is a full ring. Gaps shrink on thin slices.
 */
export function donutArcs(items: readonly { key: string; value: number }[], geom: DonutGeom): DonutArc[] {
  const positive = items.filter(item => Number.isFinite(item.value) && item.value > 0);
  const total = positive.reduce((sum, item) => sum + item.value, 0);
  if (positive.length === 0 || total <= 0) return [];
  if (positive.length === 1) return [{ key: positive[0]!.key, d: ring(geom), pct: 100 }];

  const { cx, cy, r, thickness, gapDeg } = geom;
  const ri = r - thickness;
  let cursor = -90;
  return positive.map(item => {
    const span = (item.value / total) * 360;
    const gap = Math.min(gapDeg, span / 3);
    const start = cursor + gap / 2;
    const end = cursor + span - gap / 2;
    cursor += span;
    const large = end - start > 180 ? 1 : 0;
    const d = `M${point(cx, cy, r, start)} A${f(r)},${f(r)} 0 ${large} 1 ${point(cx, cy, r, end)} `
      + `L${point(cx, cy, ri, end)} A${f(ri)},${f(ri)} 0 ${large} 0 ${point(cx, cy, ri, start)} Z`;
    return { key: item.key, d, pct: (item.value / total) * 100 };
  });
}
