/**
 * The app's pages, in navigation order: the rail, the phone menu and the 404 page list the same
 * entries, filtered the same way. Icons are attached by the rail (components/shell/NavRail.tsx).
 */
import type { I18NText } from '../../contracts/types';

export interface NavEntry { href: string; label: I18NText; flag?: string; tour: string }

export const NAV_ENTRIES: readonly NavEntry[] = [
  { href: '/', label: { en: 'Home', fr: 'Accueil' }, tour: 'nav-home' },
  { href: '/portfolio/', label: { en: 'Portfolio', fr: 'Portefeuille' }, tour: 'nav-portfolio' },
  { href: '/markets/', label: { en: 'Markets', fr: 'Marchés' }, tour: 'nav-markets' },
  { href: '/risk-intelligence/', label: { en: 'Risk', fr: 'Risques' }, tour: 'nav-risk' },
  { href: '/decision-desk/', label: { en: 'Decide', fr: 'Décider' }, tour: 'nav-decide' },
  { href: '/strategies/', label: { en: 'Strategies', fr: 'Stratégies' }, tour: 'nav-strategies' },
  { href: '/world-explorer/', label: { en: 'World', fr: 'Monde' }, flag: 'world_explorer', tour: 'nav-world' },
  { href: '/evidence-audit/', label: { en: 'Evidence', fr: 'Preuves' }, tour: 'nav-evidence' },
  { href: '/time-machine/', label: { en: 'Replay', fr: 'Rejouer' }, flag: 'time_machine', tour: 'nav-replay' },
  { href: '/agents-system/', label: { en: 'System', fr: 'Système' }, tour: 'nav-system' },
];

export const SOURCES_ENTRY: NavEntry = { href: '/sources/', label: { en: 'Sources', fr: 'Sources' }, tour: 'nav-sources' };

/** Whether `href` is the current page (or a page under it). Home matches only itself. */
export function isActivePath(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname.startsWith(href.replace(/\/$/, ''));
}

/**
 * The entries to show. A flagged page is hidden only once /meta has loaded and reports its flag off,
 * so the list does not jump while the app boots.
 */
export function visibleNavEntries({ metaLoaded, feature, withSources = false }: {
  metaLoaded: boolean; feature: (flag: string) => boolean; withSources?: boolean;
}): NavEntry[] {
  const items = NAV_ENTRIES.filter(item => !item.flag || !metaLoaded || feature(item.flag));
  return withSources ? [...items, SOURCES_ENTRY] : items;
}
