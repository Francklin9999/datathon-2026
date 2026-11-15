'use client';
/**
 * A figure that climbs from 0 to its value when it first appears, and from the old value to the new
 * one when it changes. Screen readers get the final text at once; the moving digits are hidden from
 * them. Follows the animation setting (html[data-anim]), else the system's reduce-motion setting;
 * never while the page is hidden (html[data-motion="off"]).
 */
import { useEffect, useRef, useState } from 'react';
import { useApp } from '../../state/app';
import { COUNT_UP_MS, easeOutCubic, formatLike, parseFigure } from '../../lib/ui/countup';
import { animationsAllowed } from '../../lib/ui/theme';

function motionAllowed(): boolean {
  if (typeof window === 'undefined') return false;
  const root = document.documentElement;
  return animationsAllowed(root.dataset.anim, window.matchMedia('(prefers-reduced-motion: reduce)').matches, root.dataset.motion === 'off');
}

export function CountUp({ text, duration = COUNT_UP_MS }: { text: string; duration?: number }) {
  const { lang } = useApp();
  const parts = parseFigure(text, lang);
  const [shown, setShown] = useState(() => (parts && motionAllowed() ? formatLike(parts, 0) : text));
  // The value on screen: the next count starts from it, so an interrupted count (a new value, or
  // React re-running the effect in development) resumes instead of jumping to the end.
  const current = useRef(0);

  useEffect(() => {
    const target = parseFigure(text, lang);
    if (!target || !motionAllowed()) { setShown(text); current.current = target?.value ?? 0; return undefined; }
    const start = current.current;
    const began = performance.now();
    let frame = 0;
    const tick = () => {
      const t = easeOutCubic((performance.now() - began) / duration);
      if (t >= 1) { setShown(text); current.current = target.value; return; }
      current.current = start + (target.value - start) * t;
      setShown(formatLike(target, current.current));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [text, lang, duration]);

  if (!parts) return <>{text}</>;
  return (
    <span className="count">
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">{shown}</span>
    </span>
  );
}
