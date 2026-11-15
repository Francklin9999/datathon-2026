'use client';
/**
 * AppShell (T13): sidebar (expandable to labels or collapsed to an icon rail) with the
 * fictional-investor switcher, flat page header with data date, window, language and theme,
 * persistent simulation disclaimer, development-fixture banner and a polite live region.
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BookOpen, ChevronsUpDown, Cpu, Earth, History, Info, LayoutDashboard, Menu, PanelLeftClose, PanelLeftOpen, PieChart,
  Scale, ShieldCheck, UserRound, type LucideIcon,
} from 'lucide-react';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import type { I18NText, WindowCode } from '../../contracts/types';
import { useApp, WINDOW_CODES } from '../../state/app';
import { RISK_LEVEL, WINDOW, labelOf } from '../../lib/labels';
import { fmtDate } from '../../lib/format';
import { readPref, writePref } from '../../lib/session';
import { windowShortLabel } from '../../lib/ui/segmented';
import { SIDEBAR_PREF_KEY, isSidebarState, type SidebarState } from '../../lib/ui/theme';
import { FIXTURE_BANNER } from '../../api/fixtures';
import { ErrorState, Loading } from '../common/States';
import { Drawer } from '../common/Drawer';
import { Listbox } from '../ui/Listbox';
import { SegmentedControl } from '../ui/SegmentedControl';
import { ThemeToggle } from '../ui/ThemeToggle';
import { pillStyle, useSlidingPill } from '../ui/useSlidingPill';

interface NavItem { href: string; label: I18NText; icon: LucideIcon; flag?: string }

export const NAV: readonly NavItem[] = [
  { href: '/', label: { en: 'Home', fr: 'Accueil' }, icon: LayoutDashboard },
  { href: '/portfolio/', label: { en: 'Portfolio', fr: 'Portefeuille' }, icon: PieChart },
  { href: '/markets/', label: { en: 'Markets & Stocks', fr: 'Marchés et titres' }, icon: BookOpen },
  { href: '/decision-desk/', label: { en: 'Decision Desk', fr: 'Pupitre de décision' }, icon: Scale },
  { href: '/world-explorer/', label: { en: 'World Explorer', fr: 'Explorateur mondial' }, icon: Earth, flag: 'world_explorer' },
  { href: '/risk-intelligence/', label: { en: 'Risk Intelligence', fr: 'Analyse des risques' }, icon: ShieldCheck },
  { href: '/evidence-audit/', label: { en: 'Evidence & Audit', fr: 'Preuves et audit' }, icon: ShieldCheck },
  { href: '/time-machine/', label: { en: 'Time Machine', fr: 'Machine à remonter le temps' }, icon: History, flag: 'time_machine' },
  { href: '/agents-system/', label: { en: 'Agents & System', fr: 'Agents et système' }, icon: Cpu },
];

const FALLBACK_DISCLAIMER: I18NText = {
  en: 'Simulation only. Fictional profiles. Not financial advice.',
  fr: "Simulation uniquement. Profils fictifs. Ceci n'est pas un conseil financier.",
};

function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname.startsWith(href.replace(/\/$/, ''));
}

/** The plumb line: the product's own mark, one solid colour. */
function Logo() {
  return (
    <Link href="/" className="logo" aria-label="Aplomb">
      <svg className="logo-mark" width="16" height="22" viewBox="0 0 26 34" aria-hidden="true">
        <circle cx="13" cy="4" r="3" fill="none" stroke="currentColor" strokeWidth="2" />
        <line x1="13" y1="7" x2="13" y2="22" stroke="currentColor" strokeWidth="2" />
        <path d="M13 21 L20 28 L13 33 L6 28 Z" fill="currentColor" />
      </svg>
      <span className="logo-text">Aplomb</span>
    </Link>
  );
}

/** Nav with one highlight that glides to the current page (positioned in list coordinates). */
function NavList({ onNavigate, tooltips = false }: { onNavigate?: () => void; tooltips?: boolean }) {
  const pathname = usePathname() ?? '/';
  const { tr, feature, meta } = useApp();
  const items = NAV.filter(item => !item.flag || !meta || feature(item.flag));
  const { ref, box } = useSlidingPill<HTMLDivElement>(`${pathname}|${items.length}`);
  // Glide only after the first placement, so the highlight never slides in on page load.
  const [animate, setAnimate] = useState(false);
  useEffect(() => { if (box && !animate) setAnimate(true); }, [box, animate]);
  return (
    <div className="nav-wrap" ref={ref}>
      <span className="nav-pill" aria-hidden="true" data-animate={animate ? 'true' : undefined} style={pillStyle(box)} />
      <ul className="nav-list">
        {items.map(item => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          const label = tr(item.label);
          return (
            <li key={item.href}>
              <Link href={item.href} className="nav-link" aria-current={active ? 'page' : undefined} {...(tooltips ? { title: label } : {})}
                data-pill-target={active ? 'true' : undefined}
                {...(onNavigate ? { onClick: onNavigate } : {})}>
                <Icon className="nav-icon" aria-hidden="true" size={18} strokeWidth={1.5} />
                <span className="nav-text">{label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Investor switcher: a styled listbox (the native list cannot be themed in every browser). */
function PersonaSwitcher({ compact = false }: { compact?: boolean }) {
  const { profiles, profile, selectProfile, tr, feature } = useApp();
  if (!profile) return null;
  const caption = tr({ en: 'Fictional investor', fr: 'Investisseur fictif' });
  const options = profiles.map(p => ({
    value: p.profileId,
    label: p.name,
    ...(p.isDefault ? {} : { meta: tr({ en: 'custom', fr: 'personnalisé' }) }),
  }));
  return (
    <div className={`persona${compact ? ' persona-compact' : ''}`}>
      <Listbox label={caption} value={profile.profileId} options={options} onChange={selectProfile}
        triggerClassName="persona-trigger"
        renderTrigger={selected => (
          <>
            <span className="avatar" aria-hidden="true">{profile.initial}</span>
            <span className="persona-body" aria-hidden="true">
              <span className="persona-caption">{caption}</span>
              <span className="persona-name">{selected?.label ?? profile.name}</span>
            </span>
            <ChevronsUpDown aria-hidden="true" size={16} strokeWidth={1.5} className="persona-chevron" />
          </>
        )} />
      {!compact && feature('profile_creator') && (
        <Link href="/profiles/" className="persona-link">{tr({ en: 'Manage profiles', fr: 'Gérer les profils' })}</Link>
      )}
    </div>
  );
}

function WindowControl() {
  const { windowCode, setWindow, tr, lang } = useApp();
  return (
    <div className="topbar-window">
      <span className="topbar-label" aria-hidden="true">{tr({ en: 'Window', fr: 'Fenêtre' })}</span>
      <SegmentedControl<WindowCode>
        label={tr({ en: 'Analysis window', fr: 'Fenêtre d’analyse' })}
        value={windowCode}
        onChange={setWindow}
        options={WINDOW_CODES.map(code => ({ value: code, label: windowShortLabel(code, lang), title: labelOf(WINDOW, code, lang) }))}
      />
    </div>
  );
}

function LanguageSelect() {
  const { lang, setLang, meta } = useApp();
  if (meta && meta.features.bilingual === false) return null;
  return (
    <div className="lang-toggle" role="group" aria-label="Language / Langue">
      <button type="button" aria-pressed={lang === 'en'} onClick={() => setLang('en')} lang="en">EN</button>
      <button type="button" aria-pressed={lang === 'fr'} onClick={() => setLang('fr')} lang="fr">FR</button>
    </div>
  );
}

/** Expanded / collapsed sidebar, stored as a UI preference; the boot script applied it before paint. */
function useSidebarState(): [SidebarState, () => void] {
  const [state, setState] = useState<SidebarState>('expanded');
  useEffect(() => {
    const stored = readPref(SIDEBAR_PREF_KEY);
    if (isSidebarState(stored)) setState(stored);
  }, []);
  const toggle = useCallback(() => {
    setState(current => {
      const next: SidebarState = current === 'collapsed' ? 'expanded' : 'collapsed';
      writePref(SIDEBAR_PREF_KEY, next);
      if (next === 'collapsed') document.documentElement.dataset.sidebar = 'collapsed';
      else delete document.documentElement.dataset.sidebar;
      return next;
    });
  }, []);
  return [state, toggle];
}

export function AppShell({ children }: { children: ReactNode }) {
  const { tr, meta, phase, bootError, retryBoot, profile, lang, fixtures, announcement, feature } = useApp();
  const pathname = usePathname() ?? '/';
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebar, toggleSidebar] = useSidebarState();
  const collapsed = sidebar === 'collapsed';
  const disclaimer = meta?.disclaimer ?? FALLBACK_DISCLAIMER;
  // Home carries its own scope bar (window, period and dashboard criteria); other pages use this one.
  const showWindow = pathname !== '/';

  return (
    <div className="shell">
      <a href="#main" className="skip-link">{tr({ en: 'Skip to content', fr: 'Aller au contenu' })}</a>
      <aside id="sidebar" className="sidebar" aria-label={tr({ en: 'Primary', fr: 'Principal' })}>
        <div className="sidebar-head">
          <Logo />
          <button type="button" className="icon-btn collapse-btn" onClick={toggleSidebar}
            aria-controls="sidebar" aria-expanded={!collapsed}
            aria-label={collapsed ? tr({ en: 'Expand sidebar', fr: 'Déplier la barre latérale' }) : tr({ en: 'Collapse sidebar', fr: 'Replier la barre latérale' })}
            title={collapsed ? tr({ en: 'Expand sidebar', fr: 'Déplier la barre latérale' }) : tr({ en: 'Collapse sidebar', fr: 'Replier la barre latérale' })}>
            {collapsed ? <PanelLeftOpen aria-hidden="true" size={18} strokeWidth={1.5} /> : <PanelLeftClose aria-hidden="true" size={18} strokeWidth={1.5} />}
          </button>
        </div>
        <PersonaSwitcher />
        <nav aria-label={tr({ en: 'Pages', fr: 'Pages' })}><NavList tooltips={collapsed} /></nav>
        <div className="sidebar-foot">
          <Link href="/sources/" className="nav-link nav-link-sm" {...(collapsed ? { title: tr({ en: 'Sources & data passports', fr: 'Sources et passeports' }) } : {})}>
            <BookOpen className="nav-icon" aria-hidden="true" size={16} strokeWidth={1.5} />
            <span className="nav-text">{tr({ en: 'Sources & data passports', fr: 'Sources et passeports' })}</span>
          </Link>
          {meta && <p className="sidebar-meta">{meta.dataVersion}</p>}
        </div>
      </aside>

      <div className="main-col">
        {fixtures && (
          <div className="banner banner-fixture" role="note">
            <strong>{FIXTURE_BANNER}</strong>{' '}
            {tr({ en: 'Only contract fixtures are served; every other call reports unavailable.', fr: 'Seuls les jeux d’essai du contrat sont servis ; tout autre appel est signalé indisponible.' })}
          </div>
        )}
        <header className="topbar">
          <button type="button" className="icon-btn menu-btn" onClick={() => setMenuOpen(true)} aria-haspopup="dialog"
            aria-label={tr({ en: 'Menu', fr: 'Menu' })}>
            <Menu aria-hidden="true" size={18} strokeWidth={1.5} />
          </button>
          <div className="topbar-persona"><PersonaSwitcher compact /></div>
          <div className="topbar-meta">
            {meta && <span className="meta-chip">{tr({ en: 'Data as of', fr: 'Données au' })} <strong>{fmtDate(meta.dataAsOf, lang)}</strong></span>}
            {profile && (
              <span className="meta-chip">{profile.portfolio.currency}, {tr({ en: 'risk', fr: 'risque' })} {labelOf(RISK_LEVEL, profile.riskLevel, lang).toLowerCase()}</span>
            )}
          </div>
          <div className="topbar-controls">
            {showWindow && <WindowControl />}
            <LanguageSelect />
            <ThemeToggle />
          </div>
        </header>

        <p className="disclaimer" role="note">
          <Info aria-hidden="true" size={14} strokeWidth={1.5} className="disclaimer-mark" />{tr(disclaimer)}
        </p>

        <main id="main" className="content" tabIndex={-1}>
          {phase === 'booting' && <Loading label={tr({ en: 'Connecting to the Aplomb API…', fr: 'Connexion à l’API Aplomb…' })} />}
          {phase === 'error' && bootError && (
            <ErrorState error={bootError} onRetry={retryBoot}
              title={tr({ en: 'The Aplomb API could not be reached. No figures are shown.', fr: 'L’API Aplomb est injoignable. Aucun chiffre n’est affiché.' })} />
          )}
          {phase === 'ready' && children}
        </main>

        <footer className="footer">
          <span>{tr(disclaimer)}</span>
          <Link href="/sources/">{tr({ en: 'Sources', fr: 'Sources' })}</Link>
          {meta && <span className="mono">{tr({ en: 'Contract', fr: 'Contrat' })} {meta.contractVersion}, {meta.environment}</span>}
        </footer>
      </div>

      <Drawer open={menuOpen} title={tr({ en: 'Menu', fr: 'Menu' })} onClose={() => setMenuOpen(false)} side="left">
        <nav aria-label={tr({ en: 'Pages', fr: 'Pages' })} className="mobile-nav">
          <NavList onNavigate={() => setMenuOpen(false)} />
          <Link href="/sources/" className="nav-link" onClick={() => setMenuOpen(false)}>
            <BookOpen className="nav-icon" aria-hidden="true" size={18} strokeWidth={1.5} />
            <span className="nav-text">{tr({ en: 'Sources', fr: 'Sources' })}</span>
          </Link>
          {/* The sidebar (and its "Manage profiles" link) is hidden on phones: keep Profiles reachable. */}
          {feature('profile_creator') && (
            <Link href="/profiles/" className="nav-link" onClick={() => setMenuOpen(false)}>
              <UserRound className="nav-icon" aria-hidden="true" size={18} strokeWidth={1.5} />
              <span className="nav-text">{tr({ en: 'Profiles', fr: 'Profils' })}</span>
            </Link>
          )}
        </nav>
      </Drawer>

      <div className="sr-only" aria-live="polite" aria-atomic="true">{announcement}</div>
    </div>
  );
}
