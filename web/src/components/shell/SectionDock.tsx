'use client';
/**
 * Floating dock for the sections of the current page, plus the one shortcut every page shares: test a
 * move. Sections are any element in <main> with `data-section` (its label) and an `id`; the dock
 * appears when a page has at least three. The highlighted section follows the scroll.
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Plus } from 'lucide-react';
import { useEffect, useState } from 'react';
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

  // Scroll spy: the last section whose top has passed the upper third of the viewport.
  useEffect(() => {
    if (sections.length < 3) return undefined;
    const onScroll = () => {
      const line = window.innerHeight * 0.33;
      let active = sections[0]?.id ?? null;
      for (const s of sections) {
        const el = document.getElementById(s.id);
        if (el && el.getBoundingClientRect().top <= line) active = s.id;
      }
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) active = sections[sections.length - 1]?.id ?? active;
      setCurrent(active);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => { window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll); };
  }, [sections]);

  const go = (id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    setCurrent(id);
    // Move focus for keyboard and screen-reader users without scrolling twice.
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
    el.focus({ preventScroll: true });
  };

  const showSections = sections.length >= 3;
  const onDecide = pathname.startsWith('/decision-desk');
  return (
    <nav className="dock chrome" aria-label={tr({ en: 'On this page', fr: 'Sur cette page' })} data-tour="dock">
      {showSections && (
        <div className="dock-list" ref={ref}>
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
        <button type="button" className="dock-plus" onClick={() => go('request')} data-tour="dock-plus"
          aria-label={tr({ en: 'Describe a move', fr: 'Décrire un mouvement' })} title={tr({ en: 'Describe a move', fr: 'Décrire un mouvement' })}>
          <Plus aria-hidden="true" size={22} strokeWidth={2} />
        </button>
      ) : (
        <Link href="/decision-desk/" className="dock-plus" data-tour="dock-plus"
          aria-label={tr({ en: 'Test a move', fr: 'Tester un mouvement' })} title={tr({ en: 'Test a move', fr: 'Tester un mouvement' })}>
          <Plus aria-hidden="true" size={22} strokeWidth={2} />
        </Link>
      )}
    </nav>
  );
}
