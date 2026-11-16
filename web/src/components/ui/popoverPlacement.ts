/**
 * Where a popover list goes (Listbox, SuggestInput): pure geometry, tested in tests/ui-logic.test.ts.
 * The list is fixed in the viewport, under its trigger, or above it when there is more room there
 * than below and it does not fit below; it is kept inside the viewport on both axes.
 */

export interface Box { top: number; left: number; bottom: number; width: number }
export interface Size { width: number; height: number }

export interface PlaceOptions {
  /** Space between the trigger and the list. */
  gap?: number;
  /** Space kept from the viewport's edges. */
  margin?: number;
  /** Tallest the list may be (it scrolls inside beyond that). */
  maxHeight?: number;
  /** Narrowest the list may be; it is never narrower than its trigger either. */
  minWidth?: number;
  /** Exactly the trigger's width (or minWidth when wider) instead of growing to its content. */
  exactWidth?: boolean;
}

export interface Placement {
  top: number;
  left: number;
  minWidth: number;
  maxWidth: number;
  /** Set only for exactWidth. */
  width?: number;
  maxHeight: number;
  side: 'top' | 'bottom';
}

const clamp = (value: number, lo: number, hi: number) => Math.max(lo, Math.min(value, hi));

export function placePopover(anchor: Box, size: Size, viewport: Size, options: PlaceOptions = {}): Placement {
  const gap = options.gap ?? 6;
  const margin = options.margin ?? 8;
  // The CSS cap of .popover: min(360px, 60vh), never below a few rows.
  const cap = Math.max(160, Math.min(options.maxHeight ?? 360, Math.round(viewport.height * 0.6)));
  const maxWidth = Math.max(0, viewport.width - margin * 2);
  const minWidth = Math.min(maxWidth, Math.max(options.minWidth ?? 0, anchor.width));
  const width = options.exactWidth ? minWidth : clamp(size.width, minWidth, maxWidth);
  const below = viewport.height - anchor.bottom - gap - margin;
  const above = anchor.top - gap - margin;
  const wanted = Math.min(size.height, cap);
  const side: Placement['side'] = wanted <= below || below >= above ? 'bottom' : 'top';
  const room = Math.max(0, side === 'bottom' ? below : above);
  const maxHeight = Math.min(cap, Math.max(room, 96));
  const height = Math.min(size.height, maxHeight);
  const top = side === 'bottom' ? anchor.bottom + gap : anchor.top - gap - height;
  return {
    top: Math.round(clamp(top, margin, Math.max(margin, viewport.height - margin - height))),
    left: Math.round(clamp(anchor.left, margin, Math.max(margin, viewport.width - margin - width))),
    minWidth: Math.round(minWidth),
    maxWidth: Math.round(maxWidth),
    ...(options.exactWidth ? { width: Math.round(width) } : {}),
    maxHeight: Math.round(maxHeight),
    side,
  };
}

/** Longest transition (duration plus delay) in a computed style, in milliseconds: how long an exit lasts. */
export function longestTransitionMs(durations: string, delays: string): number {
  const ms = (value: string) => {
    const v = value.trim();
    const n = Number.parseFloat(v);
    if (!Number.isFinite(n)) return 0;
    return v.endsWith('ms') ? n : n * 1000;
  };
  const d = durations.split(',').map(ms);
  const l = delays.split(',').map(ms);
  return d.reduce((longest, value, i) => Math.max(longest, value + (l[i % Math.max(1, l.length)] ?? 0)), 0);
}

/** Where portals go: the full-screen element while one is shown (only its subtree is painted), else the body. */
export function portalTarget(): HTMLElement {
  return (document.fullscreenElement as HTMLElement | null) ?? document.body;
}
