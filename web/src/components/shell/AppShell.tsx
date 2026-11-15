'use client';
/**
 * AppShell (T13): ambient field, floating top bar (investor, Ask Aplomb, simulation note, help,
 * settings), floating navigation rail, one frosted page panel, the section dock, the phone menu
 * drawer and a polite live region. The simulation note in the top bar is the page's disclaimer.
 */
import Link from 'next/link';
import { useState, type ReactNode } from 'react';
import { useApp } from '../../state/app';
import { FIXTURE_BANNER } from '../../api/fixtures';
import { ErrorState, Loading } from '../common/States';
import { Drawer } from '../common/Drawer';
import { NavList, NavRail } from './NavRail';
import { CommandBar, Logo, MenuButton, PersonaSwitcher, SettingsMenu, SimPill } from './TopBar';
import { SectionDock } from './SectionDock';

export { NAV } from './NavRail';

export function AppShell({ children, help }: { children: ReactNode; help?: ReactNode }) {
  const { tr, phase, bootError, retryBoot, fixtures, announcement, feature } = useApp();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="shell">
      <div className="ambient" aria-hidden="true" />
      <a href="#main" className="skip-link">{tr({ en: 'Skip to content', fr: 'Aller au contenu' })}</a>

      <header className="topbar chrome">
        <MenuButton onOpen={() => setMenuOpen(true)} />
        <Logo />
        <span className="topbar-sep" aria-hidden="true" />
        <PersonaSwitcher />
        <CommandBar />
        <div className="topbar-end">
          <SimPill />
          {help}
          <SettingsMenu />
        </div>
      </header>

      <NavRail />

      {fixtures && <div className="banner banner-fixture" role="note"><strong>{FIXTURE_BANNER}</strong></div>}

      <main id="main" className="page glass" tabIndex={-1}>
        <div className="content">
          {phase === 'booting' && <Loading label={tr({ en: 'Loading…', fr: 'Chargement…' })} />}
          {phase === 'error' && bootError && (
            <ErrorState error={bootError} onRetry={retryBoot}
              title={tr({ en: 'Aplomb could not be reached. No figures are shown.', fr: 'Aplomb est injoignable. Aucun chiffre n’est affiché.' })} />
          )}
          {phase === 'ready' && children}
        </div>
      </main>

      {phase === 'ready' && <SectionDock />}

      <Drawer open={menuOpen} title={tr({ en: 'Menu', fr: 'Menu' })} onClose={() => setMenuOpen(false)} side="left">
        <nav aria-label={tr({ en: 'Pages', fr: 'Pages' })} className="mobile-nav">
          <NavList onNavigate={() => setMenuOpen(false)} withSources />
          {feature('profile_creator') && (
            <Link href="/profiles/" className="nav-link" onClick={() => setMenuOpen(false)}>
              <span className="nav-text">{tr({ en: 'Manage profiles', fr: 'Gérer les profils' })}</span>
            </Link>
          )}
        </nav>
      </Drawer>

      <div className="sr-only" aria-live="polite" aria-atomic="true">{announcement}</div>
    </div>
  );
}
