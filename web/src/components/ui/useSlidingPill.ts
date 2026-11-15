'use client';
/**
 * Measures the element marked `data-pill-target="true"` inside a positioned container and returns
 * its box in container coordinates (offsetLeft/Top). Offsets ignore page scroll, so a pill inside a
 * sticky sidebar or topbar never "jumps" when the page scrolls or a route resets the scroll.
 * Re-measures when `dep` changes and whenever the container resizes (fonts, wrapping, theme).
 */
import { useLayoutEffect, useRef, useState } from 'react';

export interface PillBox { x: number; y: number; w: number; h: number }

export function useSlidingPill<T extends HTMLElement>(dep: unknown) {
  const ref = useRef<T | null>(null);
  const [box, setBox] = useState<PillBox | null>(null);

  useLayoutEffect(() => {
    const root = ref.current;
    if (!root) return undefined;
    const measure = () => {
      const el = root.querySelector<HTMLElement>('[data-pill-target="true"]');
      setBox(el ? { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight } : null);
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    return () => observer.disconnect();
  }, [dep]);

  return { ref, box };
}

export function pillStyle(box: PillBox | null) {
  return box
    ? { transform: `translate3d(${box.x}px, ${box.y}px, 0)`, width: box.w, height: box.h }
    : { opacity: 0 };
}
