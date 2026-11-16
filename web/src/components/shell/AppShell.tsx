'use client';
/**
 * AppShell (T13): ambient field, floating top bar (investor, Ask Aplomb, simulation note, help,
 * settings), floating navigation rail, one frosted page panel, the section dock, the phone menu
 * drawer and a polite live region. The simulation note in the top bar is the page's disclaimer.
 */
import Link from 'next/link';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useApp } from '../../state/app';
import { FIXTURE_BANNER } from '../../api/fixtures';
import { ErrorState, Loading } from '../common/States';
import { Drawer } from '../common/Drawer';
import { NavList, NavRail } from './NavRail';
import { CommandBar, Logo, MenuButton, PersonaSwitcher, SettingsMenu, SimPill } from './TopBar';
import { SectionDock } from './SectionDock';
import { TourProvider } from '../../features/tour/TourProvider';
import { HelpMenu } from '../../features/tour/HelpMenu';

/**
 * Gives both side groups of the top bar the content width of the wider one (--topbar-side), so Ask
 * Aplomb sits in the exact centre of the bar; the field absorbs the difference. Re-measured when a
 * side changes (investor name, language, window size).
 */
function useCentredCommand() {
  const ref = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const bar = ref.current;
    const sides = bar ? [...bar.querySelectorAll<HTMLElement>(':scope > .topbar-start, :scope > .topbar-end')] : [];
    if (!bar || sides.length !== 2 || typeof ResizeObserver === 'undefined') return undefined;
    const contentWidth = (side: HTMLElement) => {
      const items = [...side.children].filter((el): el is HTMLElement => el instanceof HTMLElement && el.offsetWidth > 0);
      const gap = parseFloat(getComputedStyle(side).columnGap) || 0;
      return items.reduce((sum, el) => sum + el.offsetWidth, 0) + gap * Math.max(0, items.length - 1);
    };
    const measure = () => bar.style.setProperty('--topbar-side', `${Math.ceil(Math.max(...sides.map(contentWidth)))}px`);
    const resized = new ResizeObserver(measure);
    // Side contents render as data arrives (investor, menus): watch every child, including new ones.
    const watch = () => { resized.disconnect(); resized.observe(bar); for (const side of sides) { resized.observe(side); for (const child of side.children) resized.observe(child); } measure(); };
    const added = new MutationObserver(watch);
    for (const side of sides) added.observe(side, { childList: true, subtree: true, characterData: true });
    watch();
    return () => { resized.disconnect(); added.disconnect(); };
  }, []);
  return ref;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { tr, phase, bootError, retryBoot, fixtures, announcement, feature } = useApp();
  const [menuOpen, setMenuOpen] = useState(false);
  const topbar = useCentredCommand();

  return (
    <TourProvider>
    <div className="shell">
      <div className="ambient" aria-hidden="true" />
      <a href="#main" className="skip-link">{tr({ en: 'Skip to content', fr: 'Aller au contenu' })}</a>

      <header className="topbar chrome" ref={topbar}>
        {/* Two side groups of equal flexible width keep Ask Aplomb centred in the bar. */}
        <div className="topbar-start">
          <MenuButton onOpen={() => setMenuOpen(true)} />
          <Logo />
          <span className="topbar-sep" aria-hidden="true" />
          <PersonaSwitcher />
        </div>
        <CommandBar />
        <div className="topbar-end">
          <SimPill />
          <HelpMenu />
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
    </TourProvider>
  );
}
