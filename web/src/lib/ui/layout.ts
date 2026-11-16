/**
 * Dashboard layout model: an ordered list of widgets on a 12-column grid, each with a width in
 * columns and a height in row units, clamped to per-widget limits. Pure; persisted by the caller.
 */
export const GRID_COLS = 12;

export interface LayoutItem { id: string; w: number; h: number }
export interface WidgetLimits { minW: number; maxW: number; minH: number; maxH: number }

const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));

function clampItem(item: LayoutItem, limits: WidgetLimits | undefined): LayoutItem {
  if (!limits) return item;
  return { id: item.id, w: clamp(Math.round(item.w), limits.minW, Math.min(GRID_COLS, limits.maxW)), h: clamp(Math.round(item.h), limits.minH, limits.maxH) };
}

/** Move one widget to `toIndex` (clamped); unknown ids return the same layout. */
export function moveItem(layout: readonly LayoutItem[], id: string, toIndex: number): LayoutItem[] {
  const from = layout.findIndex(i => i.id === id);
  if (from < 0) return layout as LayoutItem[];
  const next = layout.filter(i => i.id !== id);
  next.splice(clamp(toIndex, 0, next.length), 0, layout[from]!);
  return next;
}

export function resizeItem(layout: readonly LayoutItem[], id: string, w: number, h: number, limits: Record<string, WidgetLimits>): LayoutItem[] {
  return layout.map(i => (i.id === id ? clampItem({ id, w, h }, limits[id]) : i));
}

/**
 * Restore a stored layout: keep known widgets in their stored order (first occurrence wins), drop
 * unknown ids, append widgets added since, and clamp sizes. Anything unreadable → the defaults.
 */
export function normalizeLayout(stored: unknown, defaults: readonly LayoutItem[], limits: Record<string, WidgetLimits>): LayoutItem[] {
  if (!Array.isArray(stored)) return [...defaults];
  const byId = new Map(defaults.map(d => [d.id, d]));
  const seen = new Set<string>();
  const out: LayoutItem[] = [];
  for (const raw of stored) {
    if (!raw || typeof raw !== 'object') continue;
    const { id, w, h } = raw as Record<string, unknown>;
    if (typeof id !== 'string' || !byId.has(id) || seen.has(id)) continue;
    const base = byId.get(id)!;
    seen.add(id);
    out.push(clampItem({
      id,
      w: typeof w === 'number' && Number.isFinite(w) ? w : base.w,
      h: typeof h === 'number' && Number.isFinite(h) ? h : base.h,
    }, limits[id]));
  }
  for (const d of defaults) if (!seen.has(d.id)) out.push(d);
  return out;
}

/** Arrow keys on a widget's move handle: Left/Up earlier, Right/Down later, Home/End ends. */
export function keyboardMove(layout: readonly LayoutItem[], id: string, key: string): LayoutItem[] | null {
  const index = layout.findIndex(i => i.id === id);
  if (index < 0) return null;
  const target = key === 'ArrowLeft' || key === 'ArrowUp' ? index - 1
    : key === 'ArrowRight' || key === 'ArrowDown' ? index + 1
      : key === 'Home' ? 0 : key === 'End' ? layout.length - 1 : null;
  if (target === null || target < 0 || target >= layout.length || target === index) return null;
  return moveItem(layout, id, target);
}

/** Arrow keys on a widget's resize handle: Left/Right width, Up/Down height; null when nothing changes. */
export function keyboardResize(layout: readonly LayoutItem[], id: string, key: string, limits: Record<string, WidgetLimits>): LayoutItem[] | null {
  const item = layout.find(i => i.id === id);
  if (!item) return null;
  const delta = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[key];
  if (!delta) return null;
  const next = clampItem({ id, w: item.w + delta[0]!, h: item.h + delta[1]! }, limits[id]);
  if (next.w === item.w && next.h === item.h) return null;
  return layout.map(i => (i.id === id ? next : i));
}

/** Size after dragging the resize handle by (dx, dy) pixels, snapped to whole columns and rows. */
export function sizeFromPointer(start: { w: number; h: number }, dx: number, dy: number, colStep: number, rowStep: number): { w: number; h: number } {
  return { w: start.w + Math.round(dx / Math.max(1, colStep)), h: start.h + Math.round(dy / Math.max(1, rowStep)) };
}

/**
 * Where a dragged widget goes when the pointer is over another one: before it or after it, from the
 * pointer's side of its midpoint (the caller decides the axis). Returns the index to pass to
 * moveItem, or null when the order would not change.
 */
export function reorderTarget(layout: readonly LayoutItem[], draggedId: string, hoveredId: string, before: boolean): number | null {
  if (draggedId === hoveredId) return null;
  const others = layout.filter(i => i.id !== draggedId);
  const hovered = others.findIndex(i => i.id === hoveredId);
  const current = layout.findIndex(i => i.id === draggedId);
  if (hovered < 0 || current < 0) return null;
  const at = hovered + (before ? 0 : 1);
  return at === current ? null : at;
}

/** True when the layout is the default one (same order and sizes). */
export function isDefaultLayout(layout: readonly LayoutItem[], defaults: readonly LayoutItem[]): boolean {
  return layout.length === defaults.length && layout.every((item, i) => {
    const d = defaults[i];
    return d !== undefined && d.id === item.id && d.w === item.w && d.h === item.h;
  });
}

/** How many items of `itemPx` fit in `availablePx` (at least `min`, at most `total`). */
export function fitCount(availablePx: number, itemPx: number, total: number, min = 1): number {
  if (total <= 0) return 0;
  const n = Math.floor(Math.max(0, availablePx) / Math.max(1, itemPx));
  return Math.min(total, Math.max(min, n));
}

/**
 * How many leading rows of measured `heights` fit whole in `availablePx` (at least `min`, at most
 * the number of rows). For rows that wrap, so each has its own height.
 */
export function fitHeights(availablePx: number, heights: readonly number[], min = 0): number {
  let used = 0;
  let n = 0;
  for (const h of heights) {
    used += Math.max(0, h);
    if (used > availablePx) break;
    n += 1;
  }
  return Math.min(heights.length, Math.max(min, n));
}

/**
 * Rows to show when the ones left out are announced by a "more" control of `morePx`: every row when
 * all fit; otherwise the rows that fit beside the control, and the control only if it fits itself.
 */
export function fitRowsWithMore(availablePx: number, heights: readonly number[], morePx: number): { shown: number; more: boolean } {
  const all = fitHeights(availablePx, heights);
  if (all === heights.length) return { shown: all, more: false };
  if (availablePx < morePx) return { shown: 0, more: false };
  return { shown: fitHeights(availablePx - morePx, heights), more: true };
}
