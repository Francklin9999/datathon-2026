'use client';
/**
 * Portal popovers (Listbox, SuggestInput): placement from the trigger's box, kept current on scroll,
 * resize and content changes, and a presence that keeps the list mounted while it fades out.
 */
import { useEffect, useLayoutEffect, useState, type CSSProperties, type RefObject } from 'react';
import { longestTransitionMs, placePopover, type PlaceOptions, type Placement } from './popoverPlacement';

const same = (a: Placement | null, b: Placement) => a !== null && a.top === b.top && a.left === b.left && a.minWidth === b.minWidth
  && a.maxWidth === b.maxWidth && a.width === b.width && a.maxHeight === b.maxHeight && a.side === b.side;

/** Inline style and side for a fixed popover placed from `anchor`; hidden until first measured. */
export function usePopoverPosition(active: boolean, anchor: RefObject<HTMLElement | null>, pop: RefObject<HTMLElement | null>,
  options: Pick<PlaceOptions, 'minWidth' | 'exactWidth'> = {}): { style: CSSProperties; side: Placement['side'] } {
  const [placement, setPlacement] = useState<Placement | null>(null);
  const { minWidth, exactWidth } = options;
  useLayoutEffect(() => {
    if (!active) return undefined;
    const update = () => {
      const a = anchor.current;
      const p = pop.current;
      if (!a || !p) return;
      const next = placePopover(a.getBoundingClientRect(), { width: p.offsetWidth, height: Math.max(p.offsetHeight, p.scrollHeight) },
        { width: document.documentElement.clientWidth, height: window.innerHeight },
        { ...(minWidth !== undefined ? { minWidth } : {}), ...(exactWidth ? { exactWidth } : {}) });
      setPlacement(prev => (same(prev, next) ? prev : next));
    };
    // Scrolling inside the list itself does not move it.
    const onScroll = (event: Event) => { if (event.target instanceof Node && pop.current?.contains(event.target)) return; update(); };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', onScroll, true);
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update);
    if (pop.current) observer?.observe(pop.current);
    if (anchor.current) observer?.observe(anchor.current);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', onScroll, true);
      observer?.disconnect();
    };
  }, [active, anchor, pop, minWidth, exactWidth]);
  if (!placement) return { style: { top: 0, left: 0, visibility: 'hidden' }, side: 'bottom' };
  return {
    style: {
      top: placement.top, left: placement.left, minWidth: placement.minWidth, maxWidth: placement.maxWidth, maxHeight: placement.maxHeight,
      ...(placement.width !== undefined ? { width: placement.width } : {}),
    },
    side: placement.side,
  };
}

/**
 * Keeps a closing popover mounted until its exit transition ends (read from its computed style, so
 * it is immediate when the motion gate sets the durations to 0s). `leaving` marks the exit.
 */
export function usePresence(open: boolean, element: RefObject<HTMLElement | null>): { present: boolean; leaving: boolean } {
  const [present, setPresent] = useState(open);
  // Opening is immediate (state adjusted during render, React's pattern for derived state).
  if (open && !present) setPresent(true);
  useEffect(() => {
    if (open || !present) return undefined;
    const el = element.current;
    const style = el ? getComputedStyle(el) : null;
    const ms = style ? longestTransitionMs(style.transitionDuration, style.transitionDelay) : 0;
    const timer = window.setTimeout(() => setPresent(false), ms > 0 ? ms + 20 : 0);
    return () => window.clearTimeout(timer);
  }, [open, present, element]);
  return { present: open || present, leaving: !open && present };
}
