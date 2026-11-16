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
import { useApp } from '../../state/app';
import { readPref, writePref } from '../../lib/session';
import { SIDEBAR_PREF_KEY, isSidebarState, type SidebarState } from '../../lib/ui/theme';
import { isActivePath, visibleNavEntries, type NavEntry } from '../../lib/ui/nav';
import { useSlidingPill } from '../ui/useSlidingPill';

/** Icon of each page (the entries themselves live in lib/ui/nav.ts). */
const NAV_ICON: Readonly<Record<string, LucideIcon>> = {
  '/': LayoutDashboard,
  '/portfolio/': PieChart,
  '/markets/': BookOpen,
  '/risk-intelligence/': ShieldCheck,
  '/decision-desk/': Scale,
  '/strategies/': Workflow,
  '/world-explorer/': Earth,
  '/evidence-audit/': ShieldCheck,
  '/time-machine/': History,
  '/agents-system/': Cpu,
  '/sources/': BookOpen,
};

export function navIcon(href: string): LucideIcon {
  return NAV_ICON[href] ?? BookOpen;
}

/** The pages to list, filtered by the feature flags once /meta has loaded (rail, phone menu, 404 page). */
export function useNavEntries(withSources = false): NavEntry[] {
  const { feature, meta } = useApp();
  return visibleNavEntries({ metaLoaded: Boolean(meta), feature, withSources });
}

/** Rail state, stored as a UI preference; the boot script applied it to <html> before paint. */
function useSidebarState(): [SidebarState, () => void] {
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

/**
 * One page link. The label is in the DOM once (.nav-text: the accessible name, visible when the rail is
 * expanded). The collapsed rail's tooltip is drawn by CSS from data-label (.nav-tip::after in
 * shell.css) on an aria-hidden, empty span, so the link's text content and its name both read "Home",
 * never "HomeHome".
 */
function NavLink({ item, active, onNavigate, pill, index }: { item: NavEntry; active: boolean; onNavigate?: () => void; pill: boolean; index: number }) {
  const { tr } = useApp();
  const Icon = navIcon(item.href);
  const label = tr(item.label);
  return (
    <Link href={item.href} className="nav-link" aria-current={active ? 'page' : undefined} data-tour={item.tour} style={{ '--n': index } as CSSProperties}
      data-pill-target={pill && active ? 'true' : undefined} {...(onNavigate ? { onClick: onNavigate } : {})}>
      <Icon className="nav-icon" aria-hidden="true" size={20} strokeWidth={1.75} />
      <span className="nav-text">{label}</span>
      <span className="nav-tip" aria-hidden="true" data-label={label} />
    </Link>
  );
}

/** The list of pages, with one highlight that glides to the current page (list coordinates). */
export function NavList({ onNavigate, withSources = false }: { onNavigate?: () => void; withSources?: boolean }) {
  const pathname = usePathname() ?? '/';
  const all = useNavEntries(withSources);
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
            <NavLink item={item} index={index} active={isActivePath(pathname, item.href)} pill {...(onNavigate ? { onNavigate } : {})} />
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
      <button type="button" className="rail-toggle" onClick={toggle} aria-controls="sidebar" aria-expanded={expanded} aria-label={toggleLabel}>
        <ChevronsRight aria-hidden="true" size={18} strokeWidth={1.75} className="rail-toggle-icon" />
        <span className="nav-tip" aria-hidden="true" data-label={toggleLabel} />
      </button>
    </nav>
  );
}
