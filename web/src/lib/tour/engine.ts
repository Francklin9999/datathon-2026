/**
 * Guided tour engine: pure logic shared by the overlay and the tests. A tour is an ordered list of
 * steps; each step may open a route, point at an element marked `data-tour="…"`, and say what it is
 * for. Nothing here touches the DOM.
 */
import type { I18NText } from '../../contracts/types';

export type Placement = 'top' | 'bottom' | 'left' | 'right' | 'center';

export interface TourStep {
  id: string;
  /** Route to open first (exact pathname with trailing slash, e.g. '/portfolio/'). */
  route?: string;
  /** Value of the `data-tour` attribute to highlight; absent for a centred message. */
  target?: string;
  /**
   * Id of the tab that holds the target (Tabs: `{idBase}-tab-{id}`, e.g. 'portfolio-tab-risk'). While the
   * target is not on screen, the tab is clicked once (unless already selected) and the search goes on.
   */
  open?: string;
  title: I18NText;
  body: I18NText;
  placement?: Placement;
  /** Skip silently when the target is missing (feature off, no data, phone layout). */
  optional?: boolean;
}

export interface Tour {
  id: string;
  title: I18NText;
  summary: I18NText;
  /** Page the tour is about, shown in the help menu. */
  route: string;
  steps: readonly TourStep[];
}

export interface Rect { top: number; left: number; width: number; height: number }
export interface Size { width: number; height: number }
export interface BubblePosition { top: number; left: number; placement: Placement }

export const BUBBLE_GAP = 14;
export const VIEWPORT_MARGIN = 12;

const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), Math.max(min, max));

/**
 * Where to put the step bubble: the preferred side first, then bottom, top, right, left; the first
 * side where the bubble fits entirely wins, clamped to the viewport. With no target, or when no side
 * fits, the bubble is centred near the bottom of the viewport so the target stays visible above it.
 */
export function placeBubble(target: Rect | null, bubble: Size, viewport: Size, preferred: Placement = 'bottom'): BubblePosition {
  const centred = (): BubblePosition => ({
    top: target ? clamp(viewport.height - bubble.height - 24, VIEWPORT_MARGIN, viewport.height) : Math.max(VIEWPORT_MARGIN, (viewport.height - bubble.height) / 2),
    left: Math.max(VIEWPORT_MARGIN, (viewport.width - bubble.width) / 2),
    placement: 'center',
  });
  if (!target || preferred === 'center') return centred();
  const order = [preferred, ...(['bottom', 'top', 'right', 'left'] as const).filter(p => p !== preferred)];
  const maxLeft = viewport.width - bubble.width - VIEWPORT_MARGIN;
  const maxTop = viewport.height - bubble.height - VIEWPORT_MARGIN;
  for (const side of order) {
    let top: number;
    let left: number;
    if (side === 'bottom' || side === 'top') {
      top = side === 'bottom' ? target.top + target.height + BUBBLE_GAP : target.top - bubble.height - BUBBLE_GAP;
      left = clamp(target.left + target.width / 2 - bubble.width / 2, VIEWPORT_MARGIN, maxLeft);
      if (top < VIEWPORT_MARGIN || top > maxTop) continue;
    } else {
      left = side === 'right' ? target.left + target.width + BUBBLE_GAP : target.left - bubble.width - BUBBLE_GAP;
      top = clamp(target.top + target.height / 2 - bubble.height / 2, VIEWPORT_MARGIN, maxTop);
      if (left < VIEWPORT_MARGIN || left > maxLeft) continue;
    }
    return { top, left, placement: side };
  }
  return centred();
}

/** The highlighted hole: the target grown by `pad`, kept inside the viewport. */
export function holeRect(target: Rect, viewport: Size, pad = 8): Rect {
  const top = Math.max(4, target.top - pad);
  const left = Math.max(4, target.left - pad);
  const bottom = Math.min(viewport.height - 4, target.top + target.height + pad);
  const right = Math.min(viewport.width - 4, target.left + target.width + pad);
  return { top, left, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
}

/** SVG path of the dimmed layer: the viewport with a rounded hole (even-odd fill). */
export function maskPath(viewport: Size, hole: Rect | null, radius = 16): string {
  const outer = `M0 0H${viewport.width}V${viewport.height}H0Z`;
  if (!hole || hole.width <= 0 || hole.height <= 0) return outer;
  const r = Math.min(radius, hole.width / 2, hole.height / 2);
  const { top: y, left: x, width: w, height: h } = hole;
  return `${outer}M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}V${y + h - r}A${r} ${r} 0 0 1 ${x + w - r} ${y + h}`
    + `H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z`;
}

/** A target that is in the DOM but not drawn (display: none, zero size) counts as missing. */
export function isVisibleRect(rect: Rect | null): rect is Rect {
  return rect !== null && rect.width > 0 && rect.height > 0;
}

/** Route matching that ignores a missing trailing slash. */
export function onRoute(pathname: string, route: string): boolean {
  const norm = (p: string) => (p.endsWith('/') ? p : `${p}/`);
  return norm(pathname) === norm(route);
}

/** Stored progress: whether the welcome was answered and which tours were finished. */
export interface TourProgress { welcomed: boolean; done: string[] }
export const EMPTY_PROGRESS: TourProgress = { welcomed: false, done: [] };

export function parseProgress(raw: string | null): TourProgress {
  if (!raw) return EMPTY_PROGRESS;
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== 'object') return EMPTY_PROGRESS;
    const v = value as Partial<TourProgress>;
    return {
      welcomed: v.welcomed === true,
      done: Array.isArray(v.done) ? v.done.filter((id): id is string => typeof id === 'string') : [],
    };
  } catch {
    return EMPTY_PROGRESS;
  }
}

export function markDone(progress: TourProgress, tourId: string): TourProgress {
  return { welcomed: true, done: progress.done.includes(tourId) ? progress.done : [...progress.done, tourId] };
}
