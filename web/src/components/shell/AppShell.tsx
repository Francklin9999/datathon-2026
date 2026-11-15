'use client';
/**
 * AppShell (T13): persistent navy sidebar, topbar with persona / window / language selectors,
 * persistent simulation disclaimer, development-fixture banner and a polite live region.
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, type ReactNode } from 'react';
import type { I18NText, WindowCode } from '../../contracts/types';
import { useApp, WINDOW_CODES } from '../../state/app';
import { RISK_LEVEL, WINDOW, labelOf } from '../../lib/labels';
import { fmtDate } from '../../lib/format';
import { FIXTURE_BANNER } from '../../api/fixtures';
import { ErrorState, Loading } from '../common/States';
import { Drawer } from '../common/Drawer';

interface NavItem { href: string; label: I18NText; flag?: string }

export const NAV: readonly NavItem[] = [
  { href: '/', label: { en: 'Home', fr: 'Accueil' } },
  { href: '/portfolio/', label: { en: 'Portfolio', fr: 'Portefeuille' } },
  { href: '/decision-desk/', label: { en: 'Decision Desk', fr: 'Pupitre de décision' } },
  { href: '/world-explorer/', label: { en: 'World Explorer', fr: 'Explorateur mondial' }, flag: 'world_explorer' },
  { href: '/evidence-audit/', label: { en: 'Evidence & Audit', fr: 'Preuves et audit' } },
  { href: '/time-machine/', label: { en: 'Time Machine', fr: 'Machine à remonter le temps' }, flag: 'time_machine' },
  { href: '/agents-system/', label: { en: 'Agents & System', fr: 'Agents et système' } },
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
      <svg width="22" height="30" viewBox="0 0 26 34" aria-hidden="true">
        <circle cx="13" cy="4" r="3" fill="none" stroke="#E3A53B" strokeWidth="2" />
        <line x1="13" y1="7" x2="13" y2="22" stroke="#E3A53B" strokeWidth="2" />
        <path d="M13 21 L20 28 L13 33 L6 28 Z" fill="#E3A53B" />
      </svg>
      <span className="serif logo-text">Aplomb</span>
    </Link>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname() ?? '/';
  const { tr, feature, meta } = useApp();
  return (
    <ul className="nav-list">
      {NAV.filter(item => !item.flag || !meta || feature(item.flag)).map(item => (
        <li key={item.href}>
          <Link href={item.href} className="nav-link" aria-current={isActive(pathname, item.href) ? 'page' : undefined}
            {...(onNavigate ? { onClick: onNavigate } : {})}>
            {tr(item.label)}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function PersonaSelect() {
  const { profiles, profile, selectProfile, tr, feature } = useApp();
  if (!profile) return null;
  return (
    <div className="topbar-field">
      <label htmlFor="persona-select" className="topbar-label">{tr({ en: 'Fictional investor', fr: 'Investisseur fictif' })}</label>
      <div className="persona-row">
        <span className="avatar" aria-hidden="true">{profile.initial}</span>
        <select id="persona-select" value={profile.profileId} onChange={e => selectProfile(e.target.value)}>
          {profiles.map(p => (
            <option key={p.profileId} value={p.profileId}>
              {p.name}{p.isDefault ? '' : ` (${tr({ en: 'custom', fr: 'personnalisé' })})`}
            </option>
          ))}
        </select>
        {feature('profile_creator') && (
          <Link href="/profiles/" className="topbar-link">{tr({ en: 'Profiles', fr: 'Profils' })}</Link>
        )}
      </div>
    </div>
  );
}

function WindowSelect() {
  const { windowCode, setWindow, tr, lang } = useApp();
  return (
    <div className="topbar-field">
      <label htmlFor="window-select" className="topbar-label">{tr({ en: 'Window', fr: 'Fenêtre' })}</label>
      <select id="window-select" value={windowCode} onChange={e => setWindow(e.target.value as WindowCode)}>
        {WINDOW_CODES.map(code => <option key={code} value={code}>{labelOf(WINDOW, code, lang)}</option>)}
      </select>
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
  const { tr, meta, phase, bootError, retryBoot, profile, lang, fixtures, announcement } = useApp();
  const [menuOpen, setMenuOpen] = useState(false);
  const disclaimer = meta?.disclaimer ?? FALLBACK_DISCLAIMER;

  return (
    <div className="shell">
      <a href="#main" className="skip-link">{tr({ en: 'Skip to content', fr: 'Aller au contenu' })}</a>
      <aside className="sidebar" aria-label={tr({ en: 'Primary', fr: 'Principal' })}>
        <Logo />
        <nav aria-label={tr({ en: 'Pages', fr: 'Pages' })}><NavList /></nav>
        <div className="sidebar-foot small">
          <Link href="/sources/" className="nav-link nav-link-sm">{tr({ en: 'Sources & data passports', fr: 'Sources et passeports' })}</Link>
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
        <header className="topbar">
          <button type="button" className="btn ghost btn-sm menu-btn" onClick={() => setMenuOpen(true)} aria-haspopup="dialog">
            {tr({ en: 'Menu', fr: 'Menu' })}
          </button>
          <div className="topbar-controls">
            <PersonaSelect />
            <WindowSelect />
            <LanguageSelect />
          </div>
          <div className="topbar-meta small">
            {meta && <span>{tr({ en: 'Data as of', fr: 'Données au' })} <strong>{fmtDate(meta.dataAsOf, lang)}</strong></span>}
            {profile && (
              <span>{profile.portfolio.currency} · {tr({ en: 'risk', fr: 'risque' })} {labelOf(RISK_LEVEL, profile.riskLevel, lang).toLowerCase()}</span>
            )}
          </div>
        </header>

        <p className="disclaimer" role="note"><span aria-hidden="true">⚠ </span>{tr(disclaimer)}</p>

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
          {meta && <span className="mono">{tr({ en: 'Contract', fr: 'Contrat' })} {meta.contractVersion} · {meta.environment}</span>}
        </footer>
      </div>

      <Drawer open={menuOpen} title={tr({ en: 'Menu', fr: 'Menu' })} onClose={() => setMenuOpen(false)} side="left">
        <nav aria-label={tr({ en: 'Pages', fr: 'Pages' })} className="mobile-nav">
          <NavList onNavigate={() => setMenuOpen(false)} />
          <Link href="/sources/" className="nav-link" onClick={() => setMenuOpen(false)}>{tr({ en: 'Sources', fr: 'Sources' })}</Link>
        </nav>
      </Drawer>

      <div className="sr-only" aria-live="polite" aria-atomic="true">{announcement}</div>
    </div>
  );
}
