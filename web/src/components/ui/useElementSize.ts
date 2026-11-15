'use client';
/**
 * Content-box size of an element, kept current with a ResizeObserver. Returns a callback ref and the
 * size (null until measured, or when `enabled` is false). Used to fit content to a widget: a chart
 * that fills its height, a list that shows as many rows as it holds.
 */
import { useEffect, useState } from 'react';

export function useElementSize<T extends HTMLElement>(enabled = true): { ref: (el: T | null) => void; size: { w: number; h: number } | null } {
  const [el, ref] = useState<T | null>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    if (!enabled || !el || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const box = entry?.contentRect;
      if (box && box.width > 0 && box.height > 0) {
        const next = { w: Math.round(box.width), h: Math.round(box.height) };
        setSize(prev => (prev && prev.w === next.w && prev.h === next.h ? prev : next));
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [enabled, el]);
  return { ref, size };
}
