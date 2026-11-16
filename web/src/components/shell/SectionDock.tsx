'use client';
/**
 * Floating dock for the sections of the current page, plus the one shortcut every page shares: test a
 * move. Sections are any element in <main> with `data-section` (its label) and an `id`; the dock
 * appears when a page has at least three. The highlighted section follows the scroll (activeSection):
 * a section chosen in the dock stays highlighted while the page glides to it, and keeps priority over
 * a neighbour that shares its row until the person scrolls by themselves.
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Plus } from 'lucide-react';
import { useEffect, useRef, useState, type RefObject } from 'react';
import { activeSection } from '../../lib/ui/sections';
import { useApp } from '../../state/app';
import { pillStyle, useSlidingPill } from '../ui/useSlidingPill';

interface Section { id: string; label: string }

function readSections(): Section[] {
  const main = document.getElementById('main');
  if (!main) return [];
  return Array.from(main.querySelectorAll<HTMLElement>('[data-section][id]'))
    .map(el => ({ id: el.id, label: el.dataset.section ?? '' }))
    .filter(s => s.label !== '');
}

/**
 * Which edges of a horizontally scrolling list hide more items: 'start', 'end', 'both' or '' (CSS
 * fades those edges). Follows scrolling and resizing.
 */
function useEdgeFade(ref: RefObject<HTMLElement | null>, dep: number): string {
  const [fade, setFade] = useState('');
  useEffect(() => {
    const list = ref.current;
    if (!list) { setFade(''); return undefined; }
    const measure = () => {
      const start = list.scrollLeft > 2;
      const end = list.scrollLeft + list.clientWidth < list.scrollWidth - 2;
      setFade(start && end ? 'both' : start ? 'start' : end ? 'end' : '');
    };
    measure();
    list.addEventListener('scroll', measure, { passive: true });
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure);
    observer?.observe(list);
    return () => { list.removeEventListener('scroll', measure); observer?.disconnect(); };
  }, [ref, dep]);
  return fade;
}

function sameSections(a: Section[], b: Section[]): boolean {
  return a.length === b.length && a.every((s, i) => s.id === b[i]?.id && s.label === b[i]?.label);
}

export function SectionDock() {
  const { tr } = useApp();
  const pathname = usePathname() ?? '/';
  const [sections, setSections] = useState<Section[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const { ref, box } = useSlidingPill<HTMLDivElement>(`${current}|${sections.map(s => s.id).join(',')}`);
  const [animate, setAnimate] = useState(false);
  useEffect(() => { if (box && !animate) setAnimate(true); }, [box, animate]);
  /** Section chosen in the dock: wins its row; cleared when the person scrolls by themselves. */
  const preferred = useRef<string | null>(null);
  /** While the page glides to a chosen section, the highlight stays on it. */
  const gliding = useRef(false);

  // Track which sections exist: pages render them as their data arrives.
  useEffect(() => {
    const main = document.getElementById('main');
    if (!main) return undefined;
    const update = () => setSections(prev => { const next = readSections(); return sameSections(prev, next) ? prev : next; });
    update();
    const observer = new MutationObserver(update);
    observer.observe(main, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-section', 'id'] });
    return () => observer.disconnect();
  }, [pathname]);

  // Scroll spy (lib/ui/sections.ts): the lowest row of sections past the upper third of the viewport.
  useEffect(() => {
    if (sections.length < 3) return undefined;
    let settle = 0;
    const measure = () => {
      if (gliding.current) return;
      const boxes = sections.flatMap(s => {
        const r = document.getElementById(s.id)?.getBoundingClientRect();
        return r ? [{ id: s.id, top: r.top, bottom: r.bottom }] : [];
      });
      setCurrent(activeSection(boxes, {
        line: window.innerHeight * 0.33,
        viewportHeight: window.innerHeight,
        atBottom: window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4,
        preferred: preferred.current,
      }));
    };
    const onScroll = () => {
      // A glide ends when scrolling stops (scrollend where supported, a quiet 150 ms otherwise).
      if (gliding.current) {
        window.clearTimeout(settle);
        settle = window.setTimeout(() => { gliding.current = false; measure(); }, 150);
        return;
      }
      measure();
    };
    const onScrollEnd = () => { if (gliding.current) { window.clearTimeout(settle); gliding.current = false; measure(); } };
    // Scrolling by hand (wheel, touch, keys) ends any glide and drops the dock's choice.
    const onUserScroll = () => { preferred.current = null; if (gliding.current) { gliding.current = false; window.clearTimeout(settle); } };
    const onKey = (event: KeyboardEvent) => { if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) onUserScroll(); };
    measure();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('scrollend', onScrollEnd);
    window.addEventListener('resize', measure);
    window.addEventListener('wheel', onUserScroll, { passive: true });
    window.addEventListener('touchmove', onUserScroll, { passive: true });
    window.addEventListener('keydown', onKey);
    return () => {
      window.clearTimeout(settle);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('scrollend', onScrollEnd);
      window.removeEventListener('resize', measure);
      window.removeEventListener('wheel', onUserScroll);
      window.removeEventListener('touchmove', onUserScroll);
      window.removeEventListener('keydown', onKey);
    };
  }, [sections]);

  // Keep the highlighted section in view when the list scrolls sideways.
  useEffect(() => {
    const list = ref.current;
    const item = list?.querySelector<HTMLElement>('.dock-item[aria-current="true"]');
    if (!list || !item) return;
    const left = item.offsetLeft;
    const right = left + item.offsetWidth;
    if (left < list.scrollLeft) list.scrollLeft = Math.max(0, left - 24);
    else if (right > list.scrollLeft + list.clientWidth) list.scrollLeft = right - list.clientWidth + 24;
  }, [current, ref]);

  const go = (id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    preferred.current = id;
    gliding.current = !reduce;
    setCurrent(id);
    el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    // Already in place (nothing to scroll): no scroll event will end the glide.
    if (!reduce) window.setTimeout(() => { if (gliding.current && Math.abs(el.getBoundingClientRect().top) < 2) gliding.current = false; }, 400);
    // Move focus for keyboard and screen-reader users without scrolling twice.
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
    el.focus({ preventScroll: true });
  };

  const showSections = sections.length >= 3;
  const fade = useEdgeFade(ref, showSections ? sections.length : 0);
  const onDecide = pathname.startsWith('/decision-desk');
  const plusLabel = onDecide ? tr({ en: 'Describe a move', fr: 'Décrire un mouvement' }) : tr({ en: 'Test a move', fr: 'Tester un mouvement' });
  const plusInner = (
    <>
      <Plus aria-hidden="true" size={18} strokeWidth={2.25} />
      <span className="dock-plus-text">{plusLabel}</span>
    </>
  );
  return (
    <nav className="dock chrome" aria-label={tr({ en: 'On this page', fr: 'Sur cette page' })} data-tour="dock">
      {showSections && (
        <div className="dock-list" ref={ref} data-fade={fade || undefined}>
          <span className="dock-pill" aria-hidden="true" data-animate={animate ? 'true' : undefined} style={pillStyle(box)} />
          {sections.map(s => (
            <button key={s.id} type="button" className="dock-item" aria-current={s.id === current ? 'true' : undefined}
              data-pill-target={s.id === current ? 'true' : undefined} onClick={() => go(s.id)}>
              {s.label}
            </button>
          ))}
        </div>
      )}
      {showSections && <span className="dock-sep" aria-hidden="true" />}
      {onDecide ? (
        <button type="button" className="dock-plus" onClick={() => go('request')} data-tour="dock-plus">{plusInner}</button>
      ) : (
        <Link href="/decision-desk/" className="dock-plus" data-tour="dock-plus">{plusInner}</Link>
      )}
    </nav>
  );
}
