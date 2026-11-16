'use client';
/**
 * Dashboard grid: widgets on 12 columns × 32 px rows. Always arrangeable (no edit mode): grab a widget
 * by its header (or the grabber at its top edge) and it lifts and follows the pointer while the others
 * glide out of its way; a recessed slot shows where it will land and it settles there on release.
 * The corner handle resizes, snapped to whole columns and rows within the widget's limits. Both work
 * from the keyboard (arrows on the grabber or the corner handle) with a live announcement. The layout
 * is a stored UI preference. Narrow containers stack the widgets in one column.
 *
 * Motion: every change of position (drag, keyboard, resize, reset) is animated FLIP-style with the
 * Web Animations API from where each widget is drawn to where it now sits, so a change mid-flight
 * continues smoothly. The entrance also runs through WAAPI: a CSS animation would restart each time a
 * reorder moves the element in the DOM. All of it is skipped under reduced motion.
 *
 * Pointer gestures use window listeners registered once per gesture through stable wrappers that
 * call the latest handlers (refs), so a re-render during a drag can never detach them.
 */
import {
  useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode,
} from 'react';
import { readPref, writePref } from '../../lib/session';
import {
  GRID_COLS, isDefaultLayout, keyboardMove, keyboardResize, moveItem, normalizeLayout, reorderTarget, resizeItem, sizeFromPointer,
  type LayoutItem, type WidgetLimits,
} from '../../lib/ui/layout';
import { WidgetContext, type WidgetChrome } from '../../components/ui/WidgetContext';
import { useFresh } from '../../components/ui/useFresh';

export interface WidgetDef { id: string; title: string; limits: WidgetLimits; render: () => ReactNode; section?: string; bare?: boolean }

const LAYOUT_PREF = 'dashboard.layout.v1';
const ROW_PX = 32;
const GAP_PX = 16;
const STACK_BELOW_PX = 880;
/** Pointer travel before a press on a header becomes a drag (a click stays a click). */
const DRAG_THRESHOLD_PX = 5;
const EASE = 'cubic-bezier(0.22, 1, 0.36, 1)';
const FLIP_MS = 460;
const ENTER_MS = 520;
/** Elements a press on the header should leave alone (they have their own action). */
const INTERACTIVE = 'button, a, input, select, textarea, [role="radiogroup"], [role="radio"], [role="listbox"]';

function readLayout(defaults: readonly LayoutItem[], limits: Record<string, WidgetLimits>): LayoutItem[] {
  try {
    const raw = readPref(LAYOUT_PREF);
    return normalizeLayout(raw ? JSON.parse(raw) : null, defaults, limits);
  } catch {
    return [...defaults];
  }
}

/**
 * Same rule as styles/motion.css: never while the page is hidden or with animations off in Settings;
 * on when turned on; otherwise (auto) unless the system asks for reduced motion.
 */
function motionAllowed(): boolean {
  if (typeof window === 'undefined') return false;
  const root = document.documentElement.dataset;
  if (root.motion === 'off' || root.anim === 'off') return false;
  if (root.anim === 'on') return true;
  return !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

/** Translation currently applied to an element by its running animation or inline transform. */
function currentShift(el: HTMLElement): { x: number; y: number } {
  const t = getComputedStyle(el).transform;
  if (!t || t === 'none') return { x: 0, y: 0 };
  const m = new DOMMatrixReadOnly(t);
  return { x: m.m41, y: m.m42 };
}

type Gesture =
  | { kind: 'pending'; id: string; startX: number; startY: number; grabX: number; grabY: number }
  | { kind: 'move'; id: string; grabX: number; grabY: number; pointerX: number; pointerY: number }
  | { kind: 'resize'; id: string; startX: number; startY: number; w: number; h: number };

export function DashboardGrid({ widgets, defaults, resetToken, announce, labels, onCustomizedChange, busy = false }: {
  widgets: readonly WidgetDef[];
  defaults: readonly LayoutItem[];
  /** Changing this value restores the default layout. */
  resetToken: number;
  announce: (message: string) => void;
  labels: { moved: (title: string, position: number, total: number) => string; resized: (title: string, w: number, h: number) => string };
  /** Whether the layout differs from the default (to offer a reset). */
  onCustomizedChange?: (customized: boolean) => void;
  /** True while the figures on screen belong to the previous period and the new one loads (dimmed, aria-busy). */
  busy?: boolean;
}) {
  const limits = useMemo(() => Object.fromEntries(widgets.map(w => [w.id, w.limits])), [widgets]);
  const byId = useMemo(() => new Map(widgets.map(w => [w.id, w])), [widgets]);
  // The grid only renders after client-side data arrives (never in the static HTML), so the stored
  // layout can be read on the first render: no default-layout flash.
  const [layout, setLayout] = useState<LayoutItem[]>(() => readLayout(defaults, limits));
  const [stacked, setStacked] = useState(false);
  const [activeGesture, setActiveGesture] = useState<{ kind: 'move' | 'resize'; id: string } | null>(null);
  const grid = useRef<HTMLDivElement | null>(null);
  const slot = useRef<HTMLDivElement | null>(null);
  const gesture = useRef<Gesture | null>(null);
  const layoutRef = useRef(layout);
  layoutRef.current = layout;
  const movable = !stacked;
  // CSS entrances of donuts and bars play while the grid is fresh, never on a later DOM move.
  const fresh = useFresh(1800);

  const save = useCallback((next: LayoutItem[]) => { writePref(LAYOUT_PREF, JSON.stringify(next)); }, []);

  // Reset only when the token really changes (StrictMode re-runs effects; a ref keeps it idempotent).
  const lastReset = useRef(resetToken);
  useEffect(() => {
    if (lastReset.current === resetToken) return;
    lastReset.current = resetToken;
    setLayout([...defaults]);
    save([...defaults]);
  }, [resetToken, defaults, save]);

  const customized = !isDefaultLayout(layout, defaults);
  useEffect(() => { onCustomizedChange?.(customized); }, [customized, onCustomizedChange]);

  useEffect(() => {
    const el = grid.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(([entry]) => setStacked((entry?.contentRect.width ?? 1000) < STACK_BELOW_PX));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const widgetEl = (id: string) => grid.current?.querySelector<HTMLElement>(`:scope > [data-widget="${id}"]`) ?? null;
  const titleOf = (id: string) => byId.get(id)?.title ?? id;

  // ----- Motion: entrance once, then FLIP on every change of position -----
  const positions = useRef(new Map<string, { x: number; y: number }>());
  const running = useRef(new Map<string, Animation>());
  const entered = useRef(false);
  useLayoutEffect(() => {
    const root = grid.current;
    if (!root) return;
    const animate = motionAllowed();
    const dragged = gesture.current?.kind === 'move' ? gesture.current.id : null;
    const els = [...root.querySelectorAll<HTMLElement>(':scope > [data-widget]')];
    if (!entered.current) {
      entered.current = true;
      els.forEach((el, i) => {
        positions.current.set(el.dataset.widget!, { x: el.offsetLeft, y: el.offsetTop });
        if (!animate) return;
        running.current.set(el.dataset.widget!, el.animate(
          [{ opacity: 0, transform: 'translate3d(0, 12px, 0) scale(0.985)' }, { opacity: 1, transform: 'none' }],
          { duration: ENTER_MS, delay: 80 + Math.min(i, 8) * 45, easing: EASE, fill: 'backwards' },
        ));
      });
      return;
    }
    for (const el of els) {
      const id = el.dataset.widget!;
      const now = { x: el.offsetLeft, y: el.offsetTop };
      const before = positions.current.get(id);
      positions.current.set(id, now);
      if (!animate || !before || id === dragged || (before.x === now.x && before.y === now.y)) continue;
      const shift = currentShift(el);
      running.current.get(id)?.cancel();
      const dx = before.x - now.x + shift.x;
      const dy = before.y - now.y + shift.y;
      running.current.set(id, el.animate(
        [{ transform: `translate3d(${dx}px, ${dy}px, 0)` }, { transform: 'none' }],
        { duration: FLIP_MS, easing: EASE },
      ));
    }
  });

  /** Keep the dragged widget under the pointer and the slot on its grid cell. */
  const placeDragged = () => {
    const g = gesture.current;
    const el = g?.kind === 'move' ? widgetEl(g.id) : null;
    if (!g || g.kind !== 'move' || !grid.current || !el) return;
    const rect = grid.current.getBoundingClientRect();
    el.style.transform = `translate3d(${g.pointerX - rect.left - g.grabX - el.offsetLeft}px, ${g.pointerY - rect.top - g.grabY - el.offsetTop}px, 0)`;
    const s = slot.current;
    if (s) {
      s.style.left = `${el.offsetLeft}px`;
      s.style.top = `${el.offsetTop}px`;
      s.style.width = `${el.offsetWidth}px`;
      s.style.height = `${el.offsetHeight}px`;
    }
  };
  useLayoutEffect(() => { if (activeGesture?.kind === 'move') placeDragged(); });

  const startMove = (g: Extract<Gesture, { kind: 'pending' }>, pointerX: number, pointerY: number) => {
    running.current.get(g.id)?.cancel();
    gesture.current = { kind: 'move', id: g.id, grabX: g.grabX, grabY: g.grabY, pointerX, pointerY };
    setActiveGesture({ kind: 'move', id: g.id });
  };

  // Latest gesture handlers, read by the stable listeners below.
  const handlers = useRef({ move: (_e: globalThis.PointerEvent) => {}, end: () => {} });
  handlers.current.move = (event: globalThis.PointerEvent) => {
    const g = gesture.current;
    if (!g) return;
    if (g.kind === 'pending') {
      if (Math.hypot(event.clientX - g.startX, event.clientY - g.startY) < DRAG_THRESHOLD_PX) return;
      startMove(g, event.clientX, event.clientY);
      return;
    }
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
    if (event.clientY < 72) window.scrollBy(0, -16);
    else if (event.clientY > window.innerHeight - 72) window.scrollBy(0, 16);
    placeDragged();
    const root = grid.current;
    if (!root) return;
    // Hit-test against layout boxes (offsets ignore the gliding transforms): stable, no flip-flop.
    const origin = root.getBoundingClientRect();
    const px = event.clientX - origin.left;
    const py = event.clientY - origin.top;
    for (const item of layoutRef.current) {
      if (item.id === g.id) continue;
      const el = widgetEl(item.id);
      if (!el) continue;
      const left = el.offsetLeft;
      const top = el.offsetTop;
      if (px < left || px > left + el.offsetWidth || py < top || py > top + el.offsetHeight) continue;
      // Full-width neighbours split vertically, the others horizontally.
      const before = el.offsetWidth > root.clientWidth * 0.9 ? py < top + el.offsetHeight / 2 : px < left + el.offsetWidth / 2;
      const at = reorderTarget(layoutRef.current, g.id, item.id, before);
      if (at !== null) setLayout(current => moveItem(current, g.id, at));
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
    if (g.kind === 'pending') return;
    const el = widgetEl(g.id);
    if (el && g.kind === 'move') {
      // Settle from where it was dropped into its slot.
      const shift = currentShift(el);
      el.style.transform = '';
      if (motionAllowed() && (shift.x !== 0 || shift.y !== 0)) {
        running.current.set(g.id, el.animate(
          [{ transform: `translate3d(${shift.x}px, ${shift.y}px, 0)` }, { transform: 'none' }],
          { duration: 380, easing: EASE },
        ));
      }
      positions.current.set(g.id, { x: el.offsetLeft, y: el.offsetTop });
    }
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
    if (next.kind !== 'pending') setActiveGesture({ kind: next.kind, id: next.id });
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onEnd);
    window.addEventListener('pointercancel', onEnd);
  };

  const chrome = (item: LayoutItem): WidgetChrome => ({
    id: item.id, w: item.w, h: item.h, title: titleOf(item.id),
    ...(byId.get(item.id)?.section ? { section: byId.get(item.id)!.section! } : {}),
    ...(byId.get(item.id)?.bare ? { bare: true } : {}),
    movable,
    dragging: activeGesture?.kind === 'move' && activeGesture.id === item.id,
    resizing: activeGesture?.kind === 'resize' && activeGesture.id === item.id,
    onMovePointerDown: (event: PointerEvent<HTMLElement>) => {
      if (event.button !== 0 || !movable) return;
      const target = event.target as HTMLElement;
      const fromGrabber = event.currentTarget.classList.contains('widget-grabber');
      if (!fromGrabber && target.closest(INTERACTIVE)) return;
      const el = widgetEl(item.id);
      if (!el) return;
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      const pending = { kind: 'pending' as const, id: item.id, startX: event.clientX, startY: event.clientY, grabX: event.clientX - rect.left, grabY: event.clientY - rect.top };
      begin(pending);
      if (fromGrabber) startMove(pending, event.clientX, event.clientY);
    },
    onMoveKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      const next = keyboardMove(layoutRef.current, item.id, event.key);
      if (!next) return;
      event.preventDefault();
      setLayout(next);
      save(next);
      announce(labels.moved(titleOf(item.id), next.findIndex(i => i.id === item.id) + 1, next.length));
      // Keep focus on the grabber that moved with its widget (React re-inserts the node).
      requestAnimationFrame(() => widgetEl(item.id)?.querySelector<HTMLElement>('.widget-grabber')?.focus());
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
    <div ref={grid} className="dash-grid" data-tour="arrange" data-fresh={fresh ? 'true' : undefined} data-movable={movable ? 'true' : undefined} data-stacked={stacked ? 'true' : undefined}
      data-gesture={activeGesture ? activeGesture.kind : undefined} {...(busy ? { 'aria-busy': true } : {})}>
      {activeGesture?.kind === 'move' && <div ref={slot} className="drop-slot" aria-hidden="true" />}
      {layout.map(item => {
        const def = byId.get(item.id);
        if (!def) return null;
        return <WidgetContext.Provider key={item.id} value={chrome(item)}>{def.render()}</WidgetContext.Provider>;
      })}
    </div>
  );
}
