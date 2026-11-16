'use client';
/**
 * One step of a guided tour: dims the page except the highlighted element, and floats a glass bubble
 * beside it with the step's title, text and controls. Opens the step's page first, waits for the
 * element (up to 4 s), scrolls it into view and follows it on scroll or resize. A missing optional
 * target is skipped; a missing required one shows the step centred with a short note.
 * Keyboard: Right / Enter next, Left previous, Escape closes; focus stays in the bubble.
 */
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useApp } from '../../state/app';
import {
  holeRect, isVisibleRect, maskPath, onRoute, placeBubble, type BubblePosition, type Rect, type Size, type Tour,
} from '../../lib/tour/engine';

const SEEK_TIMEOUT_MS = 4000;

function measure(target: string): Rect | null {
  const el = document.querySelector<HTMLElement>(`[data-tour="${target}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

function viewportSize(): Size {
  return { width: window.innerWidth, height: window.innerHeight };
}

export function TourOverlay({ tour, index, onIndex, onClose, onFinish }: {
  tour: Tour; index: number; onIndex: (index: number) => void; onClose: () => void; onFinish: () => void;
}) {
  const { tr } = useApp();
  const router = useRouter();
  const pathname = usePathname() ?? '/';
  const step = tour.steps[index]!;
  const last = index === tour.steps.length - 1;
  const [rect, setRect] = useState<Rect | null>(null);
  const [status, setStatus] = useState<'seeking' | 'found' | 'missing'>('seeking');
  const [viewport, setViewport] = useState<Size>(() => viewportSize());
  const [pos, setPos] = useState<BubblePosition | null>(null);
  const bubble = useRef<HTMLDivElement | null>(null);
  const heading = useRef<HTMLHeadingElement | null>(null);
  const direction = useRef<1 | -1>(1);
  const titleId = useId();
  const bodyId = useId();

  const go = useCallback((delta: 1 | -1) => {
    direction.current = delta;
    const next = index + delta;
    if (next >= tour.steps.length) onFinish();
    else if (next >= 0) onIndex(next);
  }, [index, tour.steps.length, onIndex, onFinish]);

  // Open the step's page.
  useEffect(() => {
    if (step.route && !onRoute(pathname, step.route)) router.push(step.route);
  }, [step, pathname, router]);

  // Find the target once on the right page; skip or centre when it never appears.
  useEffect(() => {
    setRect(null);
    setPos(null);
    if (!step.target) { setStatus('found'); return undefined; }
    setStatus('seeking');
    if (step.route && !onRoute(pathname, step.route)) return undefined;
    let cancelled = false;
    let opened = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const started = performance.now();
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const seek = () => {
      if (cancelled) return;
      // The target sits in another tab: select that tab once, as soon as the page shows it.
      if (step.open && !opened && !isVisibleRect(measure(step.target!))) {
        const tab = document.getElementById(step.open);
        if (tab) {
          opened = true;
          if (tab.getAttribute('aria-selected') !== 'true') tab.click();
        }
      }
      const found = measure(step.target!);
      if (isVisibleRect(found)) {
        const vh = window.innerHeight;
        const offscreen = found.top < 88 || found.top + Math.min(found.height, vh * 0.6) > vh - 24;
        if (offscreen) {
          document.querySelector(`[data-tour="${step.target}"]`)?.scrollIntoView({ block: found.height > vh * 0.6 ? 'start' : 'center', behavior: reduce ? 'auto' : 'smooth' });
        }
        timer = setTimeout(() => {
          if (cancelled) return;
          setRect(measure(step.target!));
          setStatus('found');
        }, offscreen && !reduce ? 420 : 0);
        return;
      }
      if (performance.now() - started > SEEK_TIMEOUT_MS) {
        if (step.optional) go(direction.current);
        else setStatus('missing');
        return;
      }
      timer = setTimeout(seek, 120);
    };
    seek();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
    // `go` changes with the index, which already re-runs this effect through `step`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, pathname]);

  // Follow the target while the step is shown.
  useEffect(() => {
    if (status !== 'found') return undefined;
    const update = () => {
      setViewport(viewportSize());
      if (step.target) setRect(measure(step.target));
    };
    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    const interval = setInterval(update, 500);
    return () => { window.removeEventListener('scroll', update); window.removeEventListener('resize', update); clearInterval(interval); };
  }, [status, step]);

  // Place the bubble once its size is known.
  const shownRect = status === 'found' && isVisibleRect(rect) ? rect : null;
  useLayoutEffect(() => {
    const el = bubble.current;
    if (!el || status === 'seeking') return;
    setPos(placeBubble(shownRect, { width: el.offsetWidth, height: el.offsetHeight }, viewport, step.placement ?? 'bottom'));
  }, [shownRect?.top, shownRect?.left, shownRect?.width, shownRect?.height, viewport, status, step]); // eslint-disable-line react-hooks/exhaustive-deps

  // Each step takes focus, so screen readers announce it and the keys work at once.
  useEffect(() => {
    if (status !== 'seeking') heading.current?.focus({ preventScroll: true });
  }, [status, index]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') { event.preventDefault(); onClose(); return; }
    const inButton = (event.target as HTMLElement).tagName === 'BUTTON';
    if (event.key === 'ArrowRight' || (event.key === 'Enter' && !inButton)) { event.preventDefault(); go(1); return; }
    if (event.key === 'ArrowLeft') { event.preventDefault(); go(-1); return; }
    if (event.key === 'Tab' && bubble.current) {
      const items = Array.from(bubble.current.querySelectorAll<HTMLElement>('button, [tabindex="0"]'));
      const first = items[0];
      const lastItem = items[items.length - 1];
      if (!first || !lastItem) return;
      if (event.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) { event.preventDefault(); lastItem.focus(); }
      else if (!event.shiftKey && document.activeElement === lastItem) { event.preventDefault(); first.focus(); }
    }
  };

  const hole = shownRect ? holeRect(shownRect, viewport) : null;
  return (
    <div className="tour-layer" onKeyDown={onKeyDown}>
      <svg className="tour-mask" width={viewport.width} height={viewport.height} aria-hidden="true">
        <path d={maskPath(viewport, hole)} fillRule="evenodd" />
      </svg>
      {hole && <div className="tour-ring" aria-hidden="true" style={{ top: hole.top, left: hole.left, width: hole.width, height: hole.height }} />}
      <div ref={bubble} className="tour-bubble glass-pop" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={bodyId}
        data-placement={pos?.placement ?? 'center'} data-ready={pos && status !== 'seeking' ? 'true' : undefined}
        style={pos ? { top: pos.top, left: pos.left } : undefined}>
        <p className="tour-progress">
          <span className="sr-only">{tr({ en: `Step ${index + 1} of ${tour.steps.length}`, fr: `Étape ${index + 1} sur ${tour.steps.length}` })}</span>
          <span aria-hidden="true" className="tour-dots">
            {tour.steps.map((s, i) => <span key={s.id} className="tour-dot" data-on={i === index ? 'true' : undefined} data-past={i < index ? 'true' : undefined} />)}
          </span>
          <span aria-hidden="true" className="tour-count">{index + 1}/{tour.steps.length}</span>
        </p>
        <h2 ref={heading} id={titleId} className="tour-title" tabIndex={-1}>{tr(step.title)}</h2>
        <p id={bodyId} className="tour-body">{tr(step.body)}</p>
        {status === 'missing' && (
          <p className="tour-missing">{tr({ en: 'This part is not shown right now (feature off, no data yet, or a narrow screen).', fr: 'Cet élément n’est pas affiché pour l’instant (fonction désactivée, pas encore de données, ou écran étroit).' })}</p>
        )}
        <div className="tour-actions">
          <button type="button" className="tour-skip" onClick={onClose}>{tr({ en: 'Skip tour', fr: 'Quitter' })}</button>
          <span className="tour-spacer" />
          {index > 0 && <button type="button" className="btn ghost btn-sm" onClick={() => go(-1)}>{tr({ en: 'Back', fr: 'Précédent' })}</button>}
          <button type="button" className="btn btn-sm" onClick={() => go(1)}>
            {last ? tr({ en: 'Finish', fr: 'Terminer' }) : tr({ en: 'Next', fr: 'Suivant' })}
          </button>
        </div>
      </div>
    </div>
  );
}
