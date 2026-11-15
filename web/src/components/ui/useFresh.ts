'use client';
/**
 * True for `ms` after mount, then false. Entrance animations are keyed to it (`data-fresh`), so they
 * play once when content appears or changes (re-keyed) and never again when the dashboard moves the
 * element in the DOM: browsers restart CSS animations on a re-inserted node.
 */
import { useEffect, useState } from 'react';

export function useFresh(ms: number): boolean {
  const [fresh, setFresh] = useState(true);
  useEffect(() => {
    const timer = window.setTimeout(() => setFresh(false), ms);
    return () => window.clearTimeout(timer);
  }, [ms]);
  return fresh;
}
