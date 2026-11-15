'use client';
/**
 * Navigation: the floating icon rail (labels as tooltips, or beside the icons when expanded) and the
 * same list inside the phone menu drawer. One white disc glides to the current page.
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BookOpen, ChevronsRight, Cpu, Earth, History, LayoutDashboard, PieChart, Scale, ShieldCheck, type LucideIcon, Workflow,
} from 'lucide-react';
import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import type { I18NText } from '../../contracts/types';
import { useApp } from '../../state/app';
import { readPref, writePref } from '../../lib/session';
import { SIDEBAR_PREF_KEY, isSidebarState, type SidebarState } from '../../lib/ui/theme';
import { useSlidingPill } from '../ui/useSlidingPill';

export interface NavItem { href: string; label: I18NText; icon: LucideIcon; flag?: string; tour: string }

export const NAV: readonly NavItem[] = [
  { href: '/', label: { en: 'Home', fr: 'Accueil' }, icon: LayoutDashboard, tour: 'nav-home' },
  { href: '/portfolio/', label: { en: 'Portfolio', fr: 'Portefeuille' }, icon: PieChart, tour: 'nav-portfolio' },
  { href: '/markets/', label: { en: 'Markets', fr: 'Marchés' }, icon: BookOpen, tour: 'nav-markets' },
  { href: '/risk-intelligence/', label: { en: 'Risk', fr: 'Risques' }, icon: ShieldCheck, tour: 'nav-risk' },
  { href: '/decision-desk/', label: { en: 'Decide', fr: 'Décider' }, icon: Scale, tour: 'nav-decide' },
  { href: '/strategies/', label: { en: 'Strategies', fr: 'Stratégies' }, icon: Workflow, tour: 'nav-strategies' },
  { href: '/world-explorer/', label: { en: 'World', fr: 'Monde' }, icon: Earth, flag: 'world_explorer', tour: 'nav-world' },
  { href: '/evidence-audit/', label: { en: 'Evidence', fr: 'Preuves' }, icon: ShieldCheck, tour: 'nav-evidence' },
  { href: '/time-machine/', label: { en: 'Replay', fr: 'Rejouer' }, icon: History, flag: 'time_machine', tour: 'nav-replay' },
  { href: '/agents-system/', label: { en: 'System', fr: 'Système' }, icon: Cpu, tour: 'nav-system' },
];

export const SOURCES_ITEM: NavItem = { href: '/sources/', label: { en: 'Sources', fr: 'Sources' }, icon: BookOpen, tour: 'nav-sources' };

function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname.startsWith(href.replace(/\/$/, ''));
}

/** Rail state, stored as a UI preference; the boot script applied it to <html> before paint. */
export function useSidebarState(): [SidebarState, () => void] {
  const [state, setState] = useState<SidebarState>('collapsed');
  useEffect(() => {
    const stored = readPref(SIDEBAR_PREF_KEY);
    if (isSidebarState(stored)) setState(stored);
  }, []);
  const toggle = useCallback(() => {
    setState(current => {
      const next: SidebarState = current === 'collapsed' ? 'expanded' : 'collapsed';
      writePref(SIDEBAR_PREF_KEY, next);
      if (next === 'expanded') document.documentElement.dataset.sidebar = 'expanded';
      else delete document.documentElement.dataset.sidebar;
      return next;
    });
  }, []);
  return [state, toggle];
}

function NavLink({ item, active, onNavigate, pill, index }: { item: NavItem; active: boolean; onNavigate?: () => void; pill: boolean; index: number }) {
  const { tr } = useApp();
  const Icon = item.icon;
  const label = tr(item.label);
  return (
    <Link href={item.href} className="nav-link" aria-current={active ? 'page' : undefined} data-tour={item.tour} style={{ '--n': index } as CSSProperties}
      data-pill-target={pill && active ? 'true' : undefined} {...(onNavigate ? { onClick: onNavigate } : {})}>
      <Icon className="nav-icon" aria-hidden="true" size={20} strokeWidth={1.75} />
      <span className="nav-text">{label}</span>
      <span className="nav-tip" aria-hidden="true">{label}</span>
    </Link>
  );
}

/** The list of pages, with one highlight that glides to the current page (list coordinates). */
export function NavList({ onNavigate, withSources = false }: { onNavigate?: () => void; withSources?: boolean }) {
  const pathname = usePathname() ?? '/';
  const { feature, meta } = useApp();
  const items = NAV.filter(item => !item.flag || !meta || feature(item.flag));
  const all = withSources ? [...items, SOURCES_ITEM] : items;
  const { ref, box } = useSlidingPill<HTMLDivElement>(`${pathname}|${all.length}`);
  // Glide only after the first placement, so the highlight never slides in on page load.
  const [animate, setAnimate] = useState(false);
  useEffect(() => { if (box && !animate) setAnimate(true); }, [box, animate]);
  return (
    <div className="nav-wrap" ref={ref}>
      {/* Only the vertical position comes from measuring; the width is the column's own (CSS), so the
          highlight widens in step with the rail instead of chasing it. */}
      <span className="nav-pill" aria-hidden="true" data-animate={animate ? 'true' : undefined}
        style={box ? { transform: `translate3d(0, ${box.y}px, 0)`, height: box.h } : { opacity: 0 }} />
      <ul className="nav-list">
        {all.map((item, index) => (
          <li key={item.href}>
            <NavLink item={item} index={index} active={isActive(pathname, item.href)} pill {...(onNavigate ? { onNavigate } : {})} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function NavRail() {
  const { tr } = useApp();
  const [state, toggle] = useSidebarState();
  const expanded = state === 'expanded';
  const toggleLabel = expanded ? tr({ en: 'Hide labels', fr: 'Masquer les libellés' }) : tr({ en: 'Show labels', fr: 'Afficher les libellés' });
  return (
    <nav id="sidebar" className="rail chrome" aria-label={tr({ en: 'Pages', fr: 'Pages' })} data-tour="rail">
      <NavList withSources />
      <div className="rail-sep" aria-hidden="true" />
      <button type="button" className="rail-toggle" onClick={toggle} aria-expanded={expanded} aria-label={toggleLabel}>
        <ChevronsRight aria-hidden="true" size={18} strokeWidth={1.75} className="rail-toggle-icon" />
        <span className="nav-tip" aria-hidden="true">{toggleLabel}</span>
      </button>
    </nav>
  );
}
