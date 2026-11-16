'use client';
/**
 * Navigation: the floating rail under the top bar and the same grouped list inside the phone menu
 * drawer. Labels are always visible: a caption under each icon in the compact rail, beside the icon
 * (with the group headings) when the rail is expanded. One white disc glides to the current page.
 */
import { usePathname } from 'next/navigation';
import {
  BadgeCheck, ChevronsRight, Cpu, Database, Earth, FlaskConical, History, LayoutDashboard, PieChart, Repeat, Scale, type LucideIcon,
} from 'lucide-react';
import { Suspense, useCallback, useEffect, useId, useState } from 'react';
import { useApp } from '../../state/app';
import { readPref, writePref } from '../../lib/session';
import { SIDEBAR_PREF_KEY, isSidebarState, type SidebarState } from '../../lib/ui/theme';
import { isActivePath, visibleNavEntries, visibleNavGroups, type NavEntry, type NavGroup, type NavIconName } from '../../lib/ui/nav';
import { useSlidingPill } from '../ui/useSlidingPill';
import { NavLink } from './NavLink';
import { WorldNavFallback, WorldNavLink } from './MiniGlobe';

/** Icon component of each icon name of lib/ui/nav.ts. */
const NAV_ICONS: Readonly<Record<NavIconName, LucideIcon>> = {
  LayoutDashboard, PieChart, Scale, Repeat, History, Earth, BadgeCheck, Cpu, Database, FlaskConical,
};

export function navIcon(entry: NavEntry): LucideIcon {
  return NAV_ICONS[entry.icon];
}

/** The pages to list, filtered by the feature flags once /meta has loaded (the 404 page). */
export function useNavEntries(withFooter = false): NavEntry[] {
  const { feature, meta } = useApp();
  return visibleNavEntries({ metaLoaded: Boolean(meta), feature, withFooter });
}

/** The groups to list, filtered the same way (rail and phone menu). */
export function useNavGroups(withFooter = false): NavGroup[] {
  const { feature, meta } = useApp();
  return visibleNavGroups({ metaLoaded: Boolean(meta), feature, withFooter });
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

function NavItem({ item, index, active, onNavigate, expand }: {
  item: NavEntry; index: number; active: boolean; onNavigate?: () => void; expand: boolean;
}) {
  const nav = { item, index, active, pill: true, ...(onNavigate ? { onNavigate } : {}) };
  if (item.href === '/world-explorer/') {
    return (
      <Suspense fallback={<WorldNavFallback {...nav} />}>
        <WorldNavLink {...nav} expand={expand} />
      </Suspense>
    );
  }
  const Icon = navIcon(item);
  return (
    <NavLink item={item} index={index} active={active} pill {...(onNavigate ? { onClick: () => onNavigate() } : {})}
      icon={<Icon className="nav-icon" aria-hidden="true" size={20} strokeWidth={1.75} />} />
  );
}

function NavGroupList({ group, start, pathname, onNavigate, expand }: {
  group: NavGroup; start: number; pathname: string; onNavigate?: () => void; expand: boolean;
}) {
  const { tr } = useApp();
  const headingId = useId();
  return (
    <div className="nav-group" data-group={group.id}>
      {group.heading
        ? <p className="nav-heading" id={headingId}>{tr(group.heading)}</p>
        : <span className="nav-divider" aria-hidden="true" />}
      <ul className="nav-list" {...(group.heading ? { 'aria-labelledby': headingId } : { 'aria-label': tr(group.name) })}>
        {group.entries.map((item, i) => (
          <li key={item.href}>
            <NavItem item={item} index={start + i} active={isActivePath(pathname, item.href)} expand={expand} {...(onNavigate ? { onNavigate } : {})} />
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The grouped list of pages, with one highlight that glides to the current page (list coordinates).
 * `expand` plays the World globe's expand effect (the rail only).
 */
export function NavList({ onNavigate, withFooter = false, expand = false }: { onNavigate?: () => void; withFooter?: boolean; expand?: boolean }) {
  const pathname = usePathname() ?? '/';
  const groups = useNavGroups(withFooter);
  const count = groups.reduce((sum, group) => sum + group.entries.length, 0);
  const { ref, box } = useSlidingPill<HTMLDivElement>(`${pathname}|${count}`);
  // Glide only after the first placement, so the highlight never slides in on page load.
  const [animate, setAnimate] = useState(false);
  useEffect(() => { if (box && !animate) setAnimate(true); }, [box, animate]);
  const starts = groups.map((_, g) => groups.slice(0, g).reduce((sum, group) => sum + group.entries.length, 0));
  return (
    <div className="nav-wrap" ref={ref}>
      {/* Only the vertical position comes from measuring; the width is the column's own (CSS), so the
          highlight widens in step with the rail instead of chasing it. */}
      <span className="nav-pill" aria-hidden="true" data-animate={animate ? 'true' : undefined}
        style={box ? { transform: `translate3d(0, ${box.y}px, 0)`, height: box.h } : { opacity: 0 }} />
      {groups.map((group, g) => (
        <NavGroupList key={group.id} group={group} start={starts[g] ?? 0} pathname={pathname} expand={expand} {...(onNavigate ? { onNavigate } : {})} />
      ))}
    </div>
  );
}

export function NavRail() {
  const { tr } = useApp();
  const [state, toggle] = useSidebarState();
  const expanded = state === 'expanded';
  const toggleLabel = expanded ? tr({ en: 'Collapse menu', fr: 'Réduire le menu' }) : tr({ en: 'Expand menu', fr: 'Développer le menu' });
  return (
    <nav id="sidebar" className="rail chrome" aria-label={tr({ en: 'Pages', fr: 'Pages' })} data-tour="rail">
      <div className="rail-scroll">
        <NavList withFooter expand />
      </div>
      <div className="rail-sep" aria-hidden="true" />
      <button type="button" className="rail-toggle" onClick={toggle} aria-controls="sidebar" aria-expanded={expanded} aria-label={toggleLabel} title={toggleLabel}>
        <ChevronsRight aria-hidden="true" size={18} strokeWidth={1.75} className="rail-toggle-icon" />
      </button>
    </nav>
  );
}
