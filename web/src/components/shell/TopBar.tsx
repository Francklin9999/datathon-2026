'use client';
/**
 * Floating top bar: the fictional investor, "Ask Aplomb" (free text handed to Decision Desk), the
 * simulation note (always visible), help and settings.
 */
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowUp, ChevronsUpDown, Info, Menu, Settings2, UserRound } from 'lucide-react';
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import type { I18NText, WindowCode } from '../../contracts/types';
import { useApp, WINDOW_CODES } from '../../state/app';
import { WINDOW, labelOf } from '../../lib/labels';
import { fmtDate } from '../../lib/format';
import { windowShortLabel } from '../../lib/ui/segmented';
import { ANIM_PREF_KEY, DEFAULT_ANIM, isAnimPref, type AnimPref, type ThemePref } from '../../lib/ui/theme';
import { readPref, writePref } from '../../lib/session';
import { Listbox } from '../ui/Listbox';
import { SegmentedControl } from '../ui/SegmentedControl';
import { useTheme } from '../ui/ThemeProvider';

export const FALLBACK_DISCLAIMER: I18NText = {
  en: 'Simulation only. Fictional profiles. Not financial advice.',
  fr: "Simulation uniquement. Profils fictifs. Ceci n'est pas un conseil financier.",
};

/** The plumb line: the product's own mark. */
export function Logo() {
  return (
    <Link href="/" className="logo" aria-label="Aplomb">
      <svg className="logo-mark" width="18" height="24" viewBox="0 0 26 34" aria-hidden="true">
        <circle cx="13" cy="4" r="3" fill="none" stroke="currentColor" strokeWidth="2" />
        <line x1="13" y1="7" x2="13" y2="22" stroke="currentColor" strokeWidth="2" />
        <path d="M13 21 L20 28 L13 33 L6 28 Z" fill="currentColor" />
      </svg>
      <span className="logo-text">Aplomb</span>
    </Link>
  );
}

/** Investor switcher: a styled listbox, with "Manage profiles" under the investors. */
export function PersonaSwitcher() {
  const { profiles, profile, selectProfile, tr, feature } = useApp();
  if (!profile) return null;
  const caption = tr({ en: 'Fictional investor', fr: 'Investisseur fictif' });
  const options = profiles.map(p => ({
    value: p.profileId,
    label: p.name,
    ...(p.isDefault ? {} : { meta: tr({ en: 'custom', fr: 'personnalisé' }) }),
  }));
  return (
    <div className="persona" data-tour="persona">
      <Listbox label={caption} value={profile.profileId} options={options} onChange={selectProfile}
        triggerClassName="persona-trigger"
        {...(feature('profile_creator') ? {
          footer: (close: () => void) => (
            <Link href="/profiles/" className="popover-action" onClick={close}>
              <UserRound aria-hidden="true" size={16} strokeWidth={1.75} />{tr({ en: 'Manage profiles', fr: 'Gérer les profils' })}
            </Link>
          ),
        } : {})}
        renderTrigger={selected => (
          <>
            <span className="avatar" aria-hidden="true">{profile.initial}</span>
            <span className="persona-body" aria-hidden="true">
              <span className="persona-caption">{caption}</span>
              <span className="persona-name">{selected?.label ?? profile.name}</span>
            </span>
            <ChevronsUpDown aria-hidden="true" size={16} strokeWidth={1.75} className="persona-chevron" />
          </>
        )} />
    </div>
  );
}

/** "Ask Aplomb": typed requests open Decision Desk, which interprets them (nothing runs before confirmation). */
export function CommandBar() {
  const { tr } = useApp();
  const router = useRouter();
  const [text, setText] = useState('');
  const input = useRef<HTMLInputElement | null>(null);
  const id = useId();

  useEffect(() => {
    // "/" focuses the bar from anywhere, except while typing in another field.
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))) return;
      event.preventDefault();
      input.current?.focus();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = text.trim();
    if (!value) return;
    router.push(`/decision-desk/?q=${encodeURIComponent(value.slice(0, 600))}`);
    setText('');
    input.current?.blur();
  };

  return (
    <form className="command" role="search" onSubmit={submit} data-tour="command">
      <label htmlFor={id} className="sr-only">{tr({ en: 'Ask Aplomb to test a move', fr: 'Demander à Aplomb de tester un mouvement' })}</label>
      <div className="command-field">
        <span className="command-orb" aria-hidden="true" />
        <input ref={input} id={id} className="command-input" type="text" value={text} maxLength={600} autoComplete="off"
          placeholder={tr({ en: 'Ask: add 5% of NVDA, funded from bonds', fr: 'Demander : ajouter 5 % de NVDA, financé par les obligations' })}
          onChange={event => setText(event.target.value)} />
        <kbd className="command-kbd" aria-hidden="true">/</kbd>
        <button type="submit" className="command-submit" disabled={!text.trim()} aria-label={tr({ en: 'Send to Decide', fr: 'Envoyer vers Décider' })}>
          <ArrowUp aria-hidden="true" size={18} strokeWidth={2} />
        </button>
      </div>
    </form>
  );
}

/** The simulation note: short on the bar, the full disclaimer for assistive technology and on hover. */
export function SimPill() {
  const { tr, meta } = useApp();
  const full = tr(meta?.disclaimer ?? FALLBACK_DISCLAIMER);
  return (
    <p className="sim-pill" role="note" title={full} data-tour="disclaimer">
      <Info aria-hidden="true" size={14} strokeWidth={1.75} />
      <span className="sim-text" aria-hidden="true">{tr({ en: 'Simulation, not advice', fr: 'Simulation, pas un conseil' })}</span>
      <span className="sr-only">{full}</span>
    </p>
  );
}

/** A round chrome button that opens a small popover; Escape or a click outside closes it. */
export function ChromeMenu({ label, icon, tour, children, wide = false }: {
  label: string; icon: ReactNode; tour: string; children: (close: () => void) => ReactNode; wide?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement | null>(null);
  const button = useRef<HTMLButtonElement | null>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event: PointerEvent) => { if (root.current && !root.current.contains(event.target as Node)) setOpen(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); button.current?.focus(); } };
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('pointerdown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return (
    <div className="menu-anchor" ref={root}>
      <button ref={button} type="button" className="chrome-btn" aria-expanded={open} aria-controls={id} aria-label={label} title={label}
        onClick={() => setOpen(o => !o)} data-tour={tour}>
        {icon}
      </button>
      {open && (
        <div id={id} className={`settings-pop glass-pop${wide ? ' help-pop' : ''}`} role="dialog" aria-label={label}>
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

const THEME_OPTIONS: readonly { value: ThemePref; label: I18NText }[] = [
  { value: 'light', label: { en: 'Light', fr: 'Clair' } },
  { value: 'dark', label: { en: 'Dark', fr: 'Sombre' } },
  { value: 'system', label: { en: 'Auto', fr: 'Auto' } },
];

const ANIM_OPTIONS: readonly { value: AnimPref; label: I18NText }[] = [
  { value: 'auto', label: { en: 'Auto', fr: 'Auto' } },
  { value: 'on', label: { en: 'On', fr: 'Activées' } },
  { value: 'off', label: { en: 'Off', fr: 'Désactivées' } },
];

/** Animation preference, stored and applied to <html> (the boot script applied it before paint). */
function useAnimPref(): [AnimPref, (pref: AnimPref) => void] {
  const [anim, setAnimState] = useState<AnimPref>(DEFAULT_ANIM);
  useEffect(() => { const stored = readPref(ANIM_PREF_KEY); if (isAnimPref(stored)) setAnimState(stored); }, []);
  const setAnim = (next: AnimPref) => {
    setAnimState(next);
    writePref(ANIM_PREF_KEY, next);
    if (next === 'auto') delete document.documentElement.dataset.anim;
    else document.documentElement.dataset.anim = next;
  };
  return [anim, setAnim];
}

export function SettingsMenu() {
  const { tr, lang, setLang, meta } = useApp();
  const { pref, setPref } = useTheme();
  const [anim, setAnim] = useAnimPref();
  const bilingual = !(meta && meta.features.bilingual === false);
  return (
    <ChromeMenu label={tr({ en: 'Settings', fr: 'Réglages' })} icon={<Settings2 aria-hidden="true" size={18} strokeWidth={1.75} />} tour="settings">
      {() => (
        <>
          {bilingual && (
            <div className="settings-row">
              <span className="settings-label" aria-hidden="true">{tr({ en: 'Language', fr: 'Langue' })}</span>
              <SegmentedControl<'en' | 'fr'> label={tr({ en: 'Language', fr: 'Langue' })} value={lang} onChange={setLang}
                options={[{ value: 'en', label: 'English' }, { value: 'fr', label: 'Français' }]} />
            </div>
          )}
          <div className="settings-row">
            <span className="settings-label" aria-hidden="true">{tr({ en: 'Theme', fr: 'Thème' })}</span>
            <SegmentedControl<ThemePref> label={tr({ en: 'Theme', fr: 'Thème' })} value={pref} onChange={setPref}
              options={THEME_OPTIONS.map(o => ({ value: o.value, label: tr(o.label) }))} />
          </div>
          <div className="settings-row">
            <span className="settings-label" aria-hidden="true">{tr({ en: 'Animations', fr: 'Animations' })}</span>
            <SegmentedControl<AnimPref> label={tr({ en: 'Animations', fr: 'Animations' })} value={anim} onChange={setAnim}
              options={ANIM_OPTIONS.map(o => ({ value: o.value, label: tr(o.label) }))} />
          </div>
          {meta && (
            <p className="settings-meta">
              <span>{tr({ en: 'Data as of', fr: 'Données au' })}</span>
              <strong>{fmtDate(meta.dataAsOf, lang)}</strong>
            </p>
          )}
        </>
      )}
    </ChromeMenu>
  );
}

export function MenuButton({ onOpen }: { onOpen: () => void }) {
  const { tr } = useApp();
  return (
    <button type="button" className="chrome-btn menu-btn" onClick={onOpen} aria-haspopup="dialog" aria-label={tr({ en: 'Menu', fr: 'Menu' })}>
      <Menu aria-hidden="true" size={18} strokeWidth={1.75} />
    </button>
  );
}

/** Analysis period for pages that read the global window (Portfolio, Decide); sits in their page header. */
export function WindowControl() {
  const { windowCode, setWindow, tr, lang } = useApp();
  return (
    <div data-tour="window">
      <SegmentedControl<WindowCode>
        label={tr({ en: 'Analysis period', fr: 'Période d’analyse' })}
        value={windowCode}
        onChange={setWindow}
        options={WINDOW_CODES.map(code => ({ value: code, label: windowShortLabel(code, lang), title: labelOf(WINDOW, code, lang) }))}
      />
    </div>
  );
}
