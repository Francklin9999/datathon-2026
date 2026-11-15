'use client';
/**
 * Dashboard grid: widgets on 12 columns × 32 px rows. In edit mode each widget can be dragged by
 * its handle to a new place (the others reflow) and resized from its corner, snapped to whole
 * columns and rows within its limits; both also work from the keyboard (arrows on the handles).
 * The layout is a stored UI preference. Narrow containers stack the widgets in one column.
 *
 * Pointer gestures use window listeners registered once per gesture through stable wrappers that
 * call the latest handlers (refs), so a re-render during a drag (a query resolving, a language
 * switch, an announcement) can never detach them or lose the gesture.
 */
import {
  useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode,
} from 'react';
import { readPref, writePref } from '../../lib/session';
import {
  GRID_COLS, keyboardMove, keyboardResize, moveItem, normalizeLayout, resizeItem, sizeFromPointer, type LayoutItem, type WidgetLimits,
} from '../../lib/ui/layout';
import { WidgetContext, type WidgetChrome } from '../../components/ui/WidgetContext';

export interface WidgetDef { id: string; title: string; limits: WidgetLimits; render: () => ReactNode; section?: string; bare?: boolean }

const LAYOUT_PREF = 'dashboard.layout.v1';
const ROW_PX = 32;
const GAP_PX = 16;
const STACK_BELOW_PX = 880;

function readLayout(defaults: readonly LayoutItem[], limits: Record<string, WidgetLimits>): LayoutItem[] {
  try {
    const raw = readPref(LAYOUT_PREF);
    return normalizeLayout(raw ? JSON.parse(raw) : null, defaults, limits);
  } catch {
    return [...defaults];
  }
}

type Gesture =
  | { kind: 'move'; id: string; grabX: number; grabY: number; pointerX: number; pointerY: number }
  | { kind: 'resize'; id: string; startX: number; startY: number; w: number; h: number };

export function DashboardGrid({ widgets, defaults, editing, resetToken, announce, labels, onStackedChange }: {
  widgets: readonly WidgetDef[];
  defaults: readonly LayoutItem[];
  editing: boolean;
  /** Changing this value restores the default layout. */
  resetToken: number;
  announce: (message: string) => void;
  labels: { moved: (title: string, position: number, total: number) => string; resized: (title: string, w: number, h: number) => string };
  onStackedChange?: (stacked: boolean) => void;
}) {
  const limits = useMemo(() => Object.fromEntries(widgets.map(w => [w.id, w.limits])), [widgets]);
  const byId = useMemo(() => new Map(widgets.map(w => [w.id, w])), [widgets]);
  // The grid only renders after client-side data arrives (never in the static HTML), so the stored
  // layout can be read on the first render: no default-layout flash.
  const [layout, setLayout] = useState<LayoutItem[]>(() => readLayout(defaults, limits));
  const [stacked, setStacked] = useState(false);
  const [activeGesture, setActiveGesture] = useState<{ kind: 'move' | 'resize'; id: string } | null>(null);
  const grid = useRef<HTMLDivElement | null>(null);
  const gesture = useRef<Gesture | null>(null);
  const layoutRef = useRef(layout);
  layoutRef.current = layout;

  const save = useCallback((next: LayoutItem[]) => { writePref(LAYOUT_PREF, JSON.stringify(next)); }, []);

  // Reset only when the token really changes (StrictMode re-runs effects; a ref keeps it idempotent).
  const lastReset = useRef(resetToken);
  useEffect(() => {
    if (lastReset.current === resetToken) return;
    lastReset.current = resetToken;
    setLayout([...defaults]);
    save([...defaults]);
  }, [resetToken, defaults, save]);

  useEffect(() => {
    const el = grid.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(([entry]) => setStacked((entry?.contentRect.width ?? 1000) < STACK_BELOW_PX));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  useEffect(() => { onStackedChange?.(stacked); }, [stacked, onStackedChange]);

  const widgetEl = (id: string) => grid.current?.querySelector<HTMLElement>(`[data-widget="${id}"]`) ?? null;
  const titleOf = (id: string) => byId.get(id)?.title ?? id;

  /** Keep the dragged widget under the pointer: its grid slot moves as the others reflow. */
  const placeDragged = () => {
    const g = gesture.current;
    const el = g?.kind === 'move' ? widgetEl(g.id) : null;
    if (!g || g.kind !== 'move' || !grid.current || !el) return;
    const rect = grid.current.getBoundingClientRect();
    el.style.transform = `translate3d(${g.pointerX - rect.left - g.grabX - el.offsetLeft}px, ${g.pointerY - rect.top - g.grabY - el.offsetTop}px, 0)`;
  };
  useLayoutEffect(() => { if (activeGesture?.kind === 'move') placeDragged(); });

  // Latest gesture handlers, read by the stable listeners below.
  const handlers = useRef({ move: (_e: globalThis.PointerEvent) => {}, end: () => {} });
  handlers.current.move = (event: globalThis.PointerEvent) => {
    const g = gesture.current;
    if (!g) return;
    if (g.kind === 'resize') {
      const width = grid.current?.clientWidth ?? 0;
      const size = sizeFromPointer({ w: g.w, h: g.h }, event.clientX - g.startX, event.clientY - g.startY, (width + GAP_PX) / GRID_COLS, ROW_PX + GAP_PX);
      setLayout(current => {
        const before = current.find(i => i.id === g.id);
        const next = resizeItem(current, g.id, size.w, size.h, limits);
        const after = next.find(i => i.id === g.id);
        return before && after && before.w === after.w && before.h === after.h ? current : next;
      });
      return;
    }
    g.pointerX = event.clientX;
    g.pointerY = event.clientY;
    if (event.clientY < 64) window.scrollBy(0, -16);
    else if (event.clientY > window.innerHeight - 64) window.scrollBy(0, 16);
    placeDragged();
    const gridWidth = grid.current?.clientWidth ?? 0;
    for (const item of layoutRef.current) {
      if (item.id === g.id) continue;
      const r = widgetEl(item.id)?.getBoundingClientRect();
      if (!r || event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) continue;
      // Before or after the hovered widget, from the pointer's side of its midpoint (vertical for
      // full-width widgets): stable, no flip-flop when re-entering the same neighbour.
      const before = r.width > gridWidth * 0.9 ? event.clientY < r.top + r.height / 2 : event.clientX < r.left + r.width / 2;
      const others = layoutRef.current.filter(i => i.id !== g.id);
      const at = others.findIndex(i => i.id === item.id) + (before ? 0 : 1);
      const currentIndex = layoutRef.current.findIndex(i => i.id === g.id);
      if (at !== currentIndex) setLayout(current => moveItem(current, g.id, at));
      break;
    }
  };
  handlers.current.end = () => {
    const g = gesture.current;
    if (!g) return;
    gesture.current = null;
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onEnd);
    window.removeEventListener('pointercancel', onEnd);
    const el = widgetEl(g.id);
    if (el) el.style.transform = '';
    setActiveGesture(null);
    const current = layoutRef.current;
    save(current);
    if (g.kind === 'move') {
      announce(labels.moved(titleOf(g.id), current.findIndex(i => i.id === g.id) + 1, current.length));
    } else {
      const item = current.find(i => i.id === g.id);
      if (item) announce(labels.resized(titleOf(g.id), item.w, item.h));
    }
  };
  const onMove = useCallback((event: globalThis.PointerEvent) => handlers.current.move(event), []);
  const onEnd = useCallback(() => handlers.current.end(), []);
  useEffect(() => () => {
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onEnd);
    window.removeEventListener('pointercancel', onEnd);
  }, [onMove, onEnd]);

  const begin = (next: Gesture) => {
    if (gesture.current) handlers.current.end();
    gesture.current = next;
    setActiveGesture({ kind: next.kind, id: next.id });
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onEnd);
    window.addEventListener('pointercancel', onEnd);
  };

  const chrome = (item: LayoutItem): WidgetChrome => ({
    id: item.id, w: item.w, h: item.h, title: titleOf(item.id),
    ...(byId.get(item.id)?.section ? { section: byId.get(item.id)!.section! } : {}),
    ...(byId.get(item.id)?.bare ? { bare: true } : {}),
    editing: editing && !stacked,
    dragging: activeGesture?.kind === 'move' && activeGesture.id === item.id,
    resizing: activeGesture?.kind === 'resize' && activeGesture.id === item.id,
    onMovePointerDown: (event: PointerEvent<HTMLElement>) => {
      if (event.button !== 0) return;
      const el = widgetEl(item.id);
      if (!el) return;
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      begin({ kind: 'move', id: item.id, grabX: event.clientX - rect.left, grabY: event.clientY - rect.top, pointerX: event.clientX, pointerY: event.clientY });
    },
    onMoveKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      const next = keyboardMove(layoutRef.current, item.id, event.key);
      if (!next) return;
      event.preventDefault();
      setLayout(next);
      save(next);
      announce(labels.moved(titleOf(item.id), next.findIndex(i => i.id === item.id) + 1, next.length));
      // Keep focus on the handle that moved with its widget.
      requestAnimationFrame(() => widgetEl(item.id)?.querySelector<HTMLElement>('.widget-handle')?.focus());
    },
    onResizePointerDown: (event: PointerEvent<HTMLElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      begin({ kind: 'resize', id: item.id, startX: event.clientX, startY: event.clientY, w: item.w, h: item.h });
    },
    onResizeKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      const next = keyboardResize(layoutRef.current, item.id, event.key, limits);
      if (!next) return;
      event.preventDefault();
      setLayout(next);
      save(next);
      const updated = next.find(i => i.id === item.id);
      if (updated) announce(labels.resized(titleOf(item.id), updated.w, updated.h));
    },
  });

  return (
    <div ref={grid} className="dash-grid" data-editing={editing && !stacked ? 'true' : undefined} data-stacked={stacked ? 'true' : undefined}>
      {layout.map(item => {
        const def = byId.get(item.id);
        if (!def) return null;
        return <WidgetContext.Provider key={item.id} value={chrome(item)}>{def.render()}</WidgetContext.Provider>;
      })}
    </div>
  );
}
