'use client';
/**
 * AppShell (T13): floating glass sidebar with the fictional-investor switcher, glass topbar with
 * window / language / theme controls, persistent simulation disclaimer, development-fixture banner
 * and a polite live region. Presentation follows docs/superpowers/specs/2026-11-14-glass-ui-design.md.
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BookOpen, ChevronsUpDown, Cpu, Earth, History, LayoutDashboard, Menu, PieChart, Scale, ShieldCheck, UserRound,
  type LucideIcon,
} from 'lucide-react';
import { useEffect, useId, useState, type ReactNode } from 'react';
import type { I18NText, WindowCode } from '../../contracts/types';
import { useApp, WINDOW_CODES } from '../../state/app';
import { RISK_LEVEL, WINDOW, labelOf } from '../../lib/labels';
import { fmtDate } from '../../lib/format';
import { windowShortLabel } from '../../lib/ui/segmented';
import { FIXTURE_BANNER } from '../../api/fixtures';
import { ErrorState, Loading } from '../common/States';
import { Drawer } from '../common/Drawer';
import { SegmentedControl } from '../ui/SegmentedControl';
import { ThemeToggle } from '../ui/ThemeToggle';
import { pillStyle, useSlidingPill } from '../ui/useSlidingPill';

interface NavItem { href: string; label: I18NText; icon: LucideIcon; flag?: string }

export const NAV: readonly NavItem[] = [
  { href: '/', label: { en: 'Home', fr: 'Accueil' }, icon: LayoutDashboard },
  { href: '/portfolio/', label: { en: 'Portfolio', fr: 'Portefeuille' }, icon: PieChart },
  { href: '/decision-desk/', label: { en: 'Decision Desk', fr: 'Pupitre de décision' }, icon: Scale },
  { href: '/world-explorer/', label: { en: 'World Explorer', fr: 'Explorateur mondial' }, icon: Earth, flag: 'world_explorer' },
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

function Logo() {
  return (
    <Link href="/" className="logo" aria-label="Aplomb">
      <svg width="20" height="28" viewBox="0 0 26 34" aria-hidden="true">
        <circle cx="13" cy="4" r="3" fill="none" stroke="#E3A53B" strokeWidth="2" />
        <line x1="13" y1="7" x2="13" y2="22" stroke="#E3A53B" strokeWidth="2" />
        <path d="M13 21 L20 28 L13 33 L6 28 Z" fill="#E3A53B" />
      </svg>
      <span className="logo-text">Aplomb</span>
    </Link>
  );
}

/** Nav with one highlight that glides to the current page (positioned in list coordinates). */
function NavList({ onNavigate }: { onNavigate?: () => void }) {
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
          return (
            <li key={item.href}>
              <Link href={item.href} className="nav-link" aria-current={active ? 'page' : undefined}
                data-pill-target={active ? 'true' : undefined}
                {...(onNavigate ? { onClick: onNavigate } : {})}>
                <Icon className="nav-icon" aria-hidden="true" size={18} strokeWidth={1.75} />
                <span className="nav-text">{tr(item.label)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Investor switcher: the whole card is the hit area of a transparent native <select> laid over it,
 * so keyboard, screen readers and mobile pickers keep their native behaviour.
 */
function PersonaCard({ compact = false }: { compact?: boolean }) {
  const { profiles, profile, selectProfile, tr, feature } = useApp();
  const id = useId();
  // Chrome treats a clicked <select> as :focus-visible; remember the modality so the ring is keyboard-only.
  const [pointer, setPointer] = useState(false);
  if (!profile) return null;
  const caption = tr({ en: 'Fictional investor', fr: 'Investisseur fictif' });
  return (
    <div className={`persona${compact ? ' persona-compact' : ''}`}>
      <div className="persona-card" data-pointer={pointer ? 'true' : undefined}
        onPointerDown={() => setPointer(true)} onKeyDown={() => setPointer(false)} onBlur={() => setPointer(false)}>
        <span className="avatar" aria-hidden="true">{profile.initial}</span>
        <span className="persona-body" aria-hidden="true">
          <span className="persona-caption">{caption}</span>
          <span className="persona-name">{profile.name}</span>
        </span>
        <ChevronsUpDown aria-hidden="true" size={15} className="persona-chevron" />
        <label htmlFor={id} className="sr-only">{caption}</label>
        <select id={id} className="persona-native" value={profile.profileId} onChange={e => selectProfile(e.target.value)}>
          {profiles.map(p => (
            <option key={p.profileId} value={p.profileId}>
              {p.name}{p.isDefault ? '' : ` (${tr({ en: 'custom', fr: 'personnalisé' })})`}
            </option>
          ))}
        </select>
      </div>
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

export function AppShell({ children }: { children: ReactNode }) {
  const { tr, meta, phase, bootError, retryBoot, profile, lang, fixtures, announcement, feature } = useApp();
  const [menuOpen, setMenuOpen] = useState(false);
  const disclaimer = meta?.disclaimer ?? FALLBACK_DISCLAIMER;

  return (
    <div className="shell">
      <a href="#main" className="skip-link">{tr({ en: 'Skip to content', fr: 'Aller au contenu' })}</a>
      <aside className="sidebar glass" aria-label={tr({ en: 'Primary', fr: 'Principal' })}>
        <Logo />
        <PersonaCard />
        <nav aria-label={tr({ en: 'Pages', fr: 'Pages' })}><NavList /></nav>
        <div className="sidebar-foot">
          <Link href="/sources/" className="nav-link nav-link-sm">
            <BookOpen className="nav-icon" aria-hidden="true" size={16} strokeWidth={1.75} />
            <span className="nav-text">{tr({ en: 'Sources & data passports', fr: 'Sources et passeports' })}</span>
          </Link>
          {meta && <p className="sidebar-meta mono">{meta.dataVersion}</p>}
        </div>
      </aside>

      <div className="main-col">
        {fixtures && (
          <div className="banner banner-fixture" role="note">
            <strong>{FIXTURE_BANNER}</strong>{' '}
            {tr({ en: 'Only contract fixtures are served; every other call reports unavailable.', fr: 'Seuls les jeux d’essai du contrat sont servis ; tout autre appel est signalé indisponible.' })}
          </div>
        )}
        <header className="topbar glass">
          <button type="button" className="icon-btn menu-btn" onClick={() => setMenuOpen(true)} aria-haspopup="dialog"
            aria-label={tr({ en: 'Menu', fr: 'Menu' })}>
            <Menu aria-hidden="true" size={18} strokeWidth={1.75} />
          </button>
          <div className="topbar-persona"><PersonaCard compact /></div>
          <div className="topbar-meta small">
            {meta && <span className="meta-chip">{tr({ en: 'Data as of', fr: 'Données au' })} <strong>{fmtDate(meta.dataAsOf, lang)}</strong></span>}
            {profile && (
              <span className="meta-chip">{profile.portfolio.currency}, {tr({ en: 'risk', fr: 'risque' })} {labelOf(RISK_LEVEL, profile.riskLevel, lang).toLowerCase()}</span>
            )}
          </div>
          <div className="topbar-controls">
            <WindowControl />
            <LanguageSelect />
            <ThemeToggle />
          </div>
        </header>

        <p className="disclaimer" role="note">
          <span aria-hidden="true" className="disclaimer-mark">!</span>{tr(disclaimer)}
        </p>

        <main id="main" className="content" tabIndex={-1}>
          {phase === 'booting' && <Loading label={tr({ en: 'Connecting to the Aplomb API…', fr: 'Connexion à l’API Aplomb…' })} />}
          {phase === 'error' && bootError && (
            <ErrorState error={bootError} onRetry={retryBoot}
              title={tr({ en: 'The Aplomb API could not be reached. No figures are shown.', fr: 'L’API Aplomb est injoignable. Aucun chiffre n’est affiché.' })} />
          )}
          {phase === 'ready' && children}
        </main>

        <footer className="footer small">
          <span>{tr(disclaimer)}</span>
          <Link href="/sources/">{tr({ en: 'Sources', fr: 'Sources' })}</Link>
          {meta && <span className="mono">{tr({ en: 'Contract', fr: 'Contrat' })} {meta.contractVersion}, {meta.environment}</span>}
        </footer>
      </div>

      <Drawer open={menuOpen} title={tr({ en: 'Menu', fr: 'Menu' })} onClose={() => setMenuOpen(false)} side="left">
        <nav aria-label={tr({ en: 'Pages', fr: 'Pages' })} className="mobile-nav">
          <NavList onNavigate={() => setMenuOpen(false)} />
          <Link href="/sources/" className="nav-link" onClick={() => setMenuOpen(false)}>
            <BookOpen className="nav-icon" aria-hidden="true" size={18} strokeWidth={1.75} />
            <span className="nav-text">{tr({ en: 'Sources', fr: 'Sources' })}</span>
          </Link>
          {/* The sidebar (and its "Manage profiles" link) is hidden on phones: keep Profiles reachable. */}
          {feature('profile_creator') && (
            <Link href="/profiles/" className="nav-link" onClick={() => setMenuOpen(false)}>
              <UserRound className="nav-icon" aria-hidden="true" size={18} strokeWidth={1.75} />
              <span className="nav-text">{tr({ en: 'Profiles', fr: 'Profils' })}</span>
            </Link>
          )}
        </nav>
      </Drawer>

      <div className="sr-only" aria-live="polite" aria-atomic="true">{announcement}</div>
    </div>
  );
}
