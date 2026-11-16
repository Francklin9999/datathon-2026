/**
 * The app's pages, grouped and in navigation order: the rail, the phone menu and the 404 page list the
 * same groups, filtered the same way. Icons are named here (one per page, never shared) and drawn by
 * the rail (components/shell/NavRail.tsx); the World entry shows the mini globe instead of its icon.
 */
import type { I18NText } from '../../contracts/types';

/** lucide-react icon of a page, by component name (NavRail.tsx maps the name to the component). */
export type NavIconName =
  | 'LayoutDashboard' | 'PieChart' | 'Scale' | 'Repeat' | 'History' | 'Earth' | 'BadgeCheck' | 'Cpu' | 'Database' | 'FlaskConical';

export interface NavEntry { href: string; label: I18NText; icon: NavIconName; flag?: string; tour: string }

export type NavGroupId = 'overview' | 'plan' | 'explore' | 'trust' | 'footer';

export interface NavGroup {
  id: NavGroupId;
  /** Visible heading in the expanded rail and the phone menu; null for the footer (a divider only). */
  heading: I18NText | null;
  /** Accessible name of the group's list. */
  name: I18NText;
  entries: readonly NavEntry[];
}

export const SOURCES_ENTRY: NavEntry = { href: '/sources/', label: { en: 'Sources', fr: 'Sources' }, icon: 'Database', tour: 'nav-sources' };
export const LABS_ENTRY: NavEntry = { href: '/labs/', label: { en: 'Labs', fr: 'Labos' }, icon: 'FlaskConical', tour: 'nav-labs' };

export const NAV_GROUPS: readonly NavGroup[] = [
  {
    id: 'overview', heading: { en: 'Overview', fr: 'Vue d’ensemble' }, name: { en: 'Overview', fr: 'Vue d’ensemble' },
    entries: [
      { href: '/', label: { en: 'Home', fr: 'Accueil' }, icon: 'LayoutDashboard', tour: 'nav-home' },
    ],
  },
  {
    id: 'plan', heading: { en: 'Plan', fr: 'Plan' }, name: { en: 'Plan', fr: 'Plan' },
    entries: [
      { href: '/portfolio/', label: { en: 'Portfolio', fr: 'Portefeuille' }, icon: 'PieChart', tour: 'nav-portfolio' },
      { href: '/decision-desk/', label: { en: 'Decide', fr: 'Décider' }, icon: 'Scale', tour: 'nav-decide' },
      { href: '/strategies/', label: { en: 'Strategies', fr: 'Stratégies' }, icon: 'Repeat', tour: 'nav-strategies' },
      { href: '/time-machine/', label: { en: 'Replay', fr: 'Rejouer' }, icon: 'History', flag: 'time_machine', tour: 'nav-replay' },
    ],
  },
  {
    id: 'explore', heading: { en: 'Explore', fr: 'Explorer' }, name: { en: 'Explore', fr: 'Explorer' },
    entries: [
      { href: '/world-explorer/', label: { en: 'World', fr: 'Monde' }, icon: 'Earth', flag: 'world_explorer', tour: 'nav-world' },
    ],
  },
  {
    id: 'trust', heading: { en: 'Trust', fr: 'Confiance' }, name: { en: 'Trust', fr: 'Confiance' },
    entries: [
      { href: '/evidence-audit/', label: { en: 'Evidence', fr: 'Preuves' }, icon: 'BadgeCheck', tour: 'nav-evidence' },
      { href: '/agents-system/', label: { en: 'System', fr: 'Système' }, icon: 'Cpu', tour: 'nav-system' },
    ],
  },
  {
    id: 'footer', heading: null, name: { en: 'Data and labs', fr: 'Données et labos' },
    entries: [SOURCES_ENTRY, LABS_ENTRY],
  },
];

/** The main pages (every group but the footer), in order. */
export const NAV_ENTRIES: readonly NavEntry[] = NAV_GROUPS.filter(group => group.id !== 'footer').flatMap(group => group.entries);

/** Sources and Labs, listed under the main pages. */
export const FOOTER_ENTRIES: readonly NavEntry[] = NAV_GROUPS.find(group => group.id === 'footer')?.entries ?? [];

/** Whether `href` is the current page (or a page under it). Home matches only itself. */
export function isActivePath(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname.startsWith(href.replace(/\/$/, ''));
}

interface NavFilter { metaLoaded: boolean; feature: (flag: string) => boolean; withFooter?: boolean }

/** A flagged page is hidden only once /meta has loaded and reports its flag off, so the list does not jump while the app boots. */
function shown({ metaLoaded, feature }: NavFilter) {
  return (entry: NavEntry) => !entry.flag || !metaLoaded || feature(entry.flag);
}

/** The groups to show, each with its visible entries; empty groups are dropped. */
export function visibleNavGroups(filter: NavFilter): NavGroup[] {
  const keep = shown(filter);
  return NAV_GROUPS
    .filter(group => filter.withFooter || group.id !== 'footer')
    .map(group => ({ ...group, entries: group.entries.filter(keep) }))
    .filter(group => group.entries.length > 0);
}

/** The entries to show, flat (the 404 page). */
export function visibleNavEntries(filter: NavFilter): NavEntry[] {
  return visibleNavGroups(filter).flatMap(group => group.entries);
}
