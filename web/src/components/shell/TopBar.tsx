'use client';
/**
 * Floating top bar: the fictional investor, "Ask Aplomb" (free text handed to Decision Desk, typed or
 * dictated), the simulation note (always visible), help and settings.
 */
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowUp, ChevronsUpDown, Info, Menu, Mic, Settings2, UserRound } from 'lucide-react';
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react';
import type { I18NText, WindowCode } from '../../contracts/types';
import { useApp, WINDOW_CODES } from '../../state/app';
import { useAssetUniverse } from '../../state/useAssetUniverse';
import { WINDOW, labelOf } from '../../lib/labels';
import { fmtDate } from '../../lib/format';
import { buildCompletionVocab, completeRequest } from '../../lib/completion';
import { withDictation } from '../../lib/dictation';
import { windowShortLabel } from '../../lib/ui/segmented';
import { ANIM_PREF_KEY, DEFAULT_ANIM, isAnimPref, type AnimPref, type ThemePref } from '../../lib/ui/theme';
import { readPref, writePref } from '../../lib/session';
import { Listbox } from '../ui/Listbox';
import { SegmentedControl } from '../ui/SegmentedControl';
import { useTheme } from '../ui/ThemeProvider';
import { useDictation } from '../ui/useDictation';

const FALLBACK_DISCLAIMER: I18NText = {
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
        triggerClassName="persona-trigger" popoverClassName="persona-pop"
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
            <span className="persona-body" aria-hidden="true" title={selected?.label ?? profile.name}>
              <span className="persona-caption">{caption}</span>
              <span className="persona-name">{selected?.label ?? profile.name}</span>
            </span>
            <ChevronsUpDown aria-hidden="true" size={16} strokeWidth={1.75} className="persona-chevron" />
          </>
        )} />
    </div>
  );
}

/** Longest request the bar accepts, typed or dictated. */
const ASK_MAX = 600;
/** A dictation error note stays this long unless the person acts first. */
const NOTE_MS = 8000;
/** The completion copies these from the field so its text lines up with what was typed. */
const GHOST_TYPE = ['font-family', 'font-size', 'font-weight', 'font-style', 'font-stretch', 'letter-spacing', 'word-spacing',
  'font-feature-settings', 'font-variation-settings', 'font-kerning', 'text-transform'] as const;

/**
 * "Ask Aplomb": typed or dictated requests open Decision Desk, which interprets them (nothing runs before
 * confirmation). Dictation only fills the field; the person checks the words and sends them. While the
 * person types (never for dictated words), the rest of a phrase, ticker or name shows in grey after the
 * caret: Tab or the right arrow accepts it, Escape hides it.
 */
export function CommandBar() {
  const { tr, lang, profile } = useApp();
  const router = useRouter();
  const [text, setText] = useState('');
  const form = useRef<HTMLFormElement | null>(null);
  const input = useRef<HTMLInputElement | null>(null);
  const ghost = useRef<HTMLSpanElement | null>(null);
  const typed = useRef('');
  const id = useId();
  const hintId = useId();
  // Completion state: the last change was typed, the caret is at the end, no IME composition is open.
  const [typing, setTyping] = useState(false);
  const [focused, setFocused] = useState(false);
  const [atEnd, setAtEnd] = useState(true);
  const [composing, setComposing] = useState(false);
  const [fits, setFits] = useState(true);
  // The universe is read once the bar is first used, then shared with the other search fields.
  const [used, setUsed] = useState(false);
  const { assets } = useAssetUniverse(used);
  const positions = profile?.portfolio.positions;
  const vocab = useMemo(() => buildCompletionVocab(lang,
    [...(positions ?? []).map(p => p.ticker), ...assets.map(a => a.ticker)], assets.map(a => a.name)), [lang, positions, assets]);
  const dictation = useDictation(lang, heard => { setTyping(false); setText(withDictation(typed.current, heard, ASK_MAX)); }, () => {
    // Back to the field to check and send, unless focus went elsewhere meanwhile (or never came: iOS taps).
    const field = input.current;
    if (!field || !field.value || !form.current?.contains(document.activeElement)) return;
    field.focus();
    field.setSelectionRange(field.value.length, field.value.length);
  });
  const { message, dismiss } = dictation;
  const completion = useMemo(() => (typing && focused && atEnd && !composing && !dictation.listening ? completeRequest(text, vocab) : null),
    [typing, focused, atEnd, composing, dictation.listening, text, vocab]);
  const shownCompletion = completion && fits ? completion : null;

  useLayoutEffect(() => {
    // Same type as the field, and hidden when the text and the completion no longer fit in view.
    const field = input.current;
    const rest = ghost.current;
    if (!field || !rest) return;
    const style = getComputedStyle(field);
    for (const property of GHOST_TYPE) rest.style.setProperty(property, style.getPropertyValue(property));
    setFits(field.scrollLeft === 0 && rest.scrollWidth <= rest.clientWidth);
  }, [completion, text]);

  const acceptCompletion = () => {
    if (!shownCompletion) return;
    setText(shownCompletion.accepted.slice(0, ASK_MAX));
    setAtEnd(true);
  };

  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(dismiss, NOTE_MS);
    return () => clearTimeout(timer);
  }, [message, dismiss]);

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
    dictation.cancel();
    dismiss();
    setTyping(false);
    const value = text.trim();
    if (!value) return;
    router.push(`/decision-desk/?q=${encodeURIComponent(value.slice(0, ASK_MAX))}`);
    setText('');
    input.current?.blur();
  };

  const toggleDictation = () => {
    if (dictation.listening) { dictation.stop(); return; }
    typed.current = text;
    dictation.start();
  };

  const onKeyDown = (event: ReactKeyboardEvent) => {
    if (event.key !== 'Escape' || (!dictation.listening && !message)) return;
    event.preventDefault();
    dictation.cancel();
    dismiss();
  };

  const onFieldKey = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (!shownCompletion || event.nativeEvent.isComposing) return;
    const plain = !event.shiftKey && !event.altKey && !event.ctrlKey && !event.metaKey;
    if (plain && (event.key === 'Tab' || event.key === 'ArrowRight')) {
      event.preventDefault();
      acceptCompletion();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      setTyping(false);
    }
  };

  const trackCaret = (field: HTMLInputElement) => setAtEnd(field.selectionStart === field.value.length && field.selectionEnd === field.value.length);

  return (
    <form ref={form} className="command" role="search" onSubmit={submit} onKeyDown={onKeyDown} data-tour="command">
      <label htmlFor={id} className="sr-only">{tr({ en: 'Ask Aplomb to test a move', fr: 'Demander à Aplomb de tester un mouvement' })}</label>
      <div className="command-field" data-listening={dictation.listening || undefined}>
        <span className="command-orb" aria-hidden="true" />
        <span className="command-input-wrap">
          <input ref={input} id={id} className="command-input" type="text" value={text} maxLength={ASK_MAX} autoComplete="off"
            placeholder={dictation.listening
              ? tr({ en: 'Listening… say a move, then check it', fr: 'À l’écoute… dites un mouvement, puis vérifiez-le' })
              : tr({ en: 'Ask: add 5% of NVDA, funded from bonds', fr: 'Demander : ajouter 5 % de NVDA, financé par les obligations' })}
            {...(shownCompletion ? { 'aria-describedby': hintId } : {})}
            onChange={event => {
              // Typing takes over from dictation, and only typing offers a completion.
              dictation.cancel();
              dismiss();
              setTyping(true);
              trackCaret(event.target);
              setText(event.target.value);
            }}
            onSelect={event => trackCaret(event.currentTarget)}
            onKeyDown={onFieldKey}
            onFocus={() => { setFocused(true); setUsed(true); }}
            onBlur={() => setFocused(false)}
            onCompositionStart={() => setComposing(true)}
            onCompositionEnd={() => setComposing(false)} />
          {completion && (
            <span ref={ghost} className="command-ghost" data-fits={fits ? undefined : 'false'} aria-hidden="true">
              <span className="command-ghost-typed">{text}</span>
              <span className="command-ghost-rest" onPointerDown={event => { event.preventDefault(); acceptCompletion(); }}>{completion.ghost}</span>
            </span>
          )}
        </span>
        {shownCompletion && (
          <span id={hintId} className="sr-only">
            {tr({ en: `Suggestion: ${shownCompletion.accepted}. Tab accepts it.`, fr: `Suggestion : ${shownCompletion.accepted}. Tab l’accepte.` })}
          </span>
        )}
        <kbd className="command-kbd" aria-hidden="true">/</kbd>
        {dictation.supported && (
          <button type="button" className="command-mic" aria-pressed={dictation.listening} onClick={toggleDictation}
            aria-label={tr({ en: 'Dictate a request', fr: 'Dicter une demande' })}
            title={dictation.listening
              ? tr({ en: 'Stop dictation', fr: 'Arrêter la dictée' })
              : tr({ en: 'Dictate a request. Your browser’s speech service turns your voice into text', fr: 'Dicter une demande. Le service vocal de votre navigateur transcrit votre voix' })}>
            <Mic aria-hidden="true" size={17} strokeWidth={1.9} />
          </button>
        )}
        <button type="submit" className="command-submit" disabled={!text.trim()} aria-label={tr({ en: 'Send to Decide', fr: 'Envoyer vers Décider' })}
          title={tr({ en: 'Send to Decide', fr: 'Envoyer vers Décider' })}>
          <ArrowUp aria-hidden="true" size={18} strokeWidth={2} />
        </button>
      </div>
      {message && <p className="command-note glass-pop" aria-hidden="true">{tr(message)}</p>}
      <span className="sr-only" role="status">{message ? tr(message) : ''}</span>
    </form>
  );
}

/**
 * A popover anchored to a button: Escape closes it and returns focus to the button, a click outside
 * closes it. Shared by the simulation note and the round chrome menus.
 */
function usePopover() {
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
  return { open, setOpen, root, button, id };
}

/** The simulation note: short on the bar; a press opens the full disclaimer. */
export function SimPill() {
  const { tr, meta } = useApp();
  const full = tr(meta?.disclaimer ?? FALLBACK_DISCLAIMER);
  const short = tr({ en: 'Simulation, not advice', fr: 'Simulation, pas un conseil' });
  const { open, setOpen, root, button, id } = usePopover();
  return (
    <div className="menu-anchor sim-anchor" ref={root}>
      <button ref={button} type="button" className="sim-pill" aria-expanded={open} aria-controls={id} title={short}
        onClick={() => setOpen(o => !o)} data-tour="disclaimer">
        <Info aria-hidden="true" size={14} strokeWidth={1.75} />
        <span className="sim-text">{short}</span>
      </button>
      {open && (
        <div id={id} className="settings-pop sim-pop glass-pop" role="dialog" aria-label={tr({ en: 'About this simulation', fr: 'À propos de cette simulation' })}>
          <p className="sim-pop-title">{tr({ en: 'About this simulation', fr: 'À propos de cette simulation' })}</p>
          <p className="sim-pop-body">{full}</p>
        </div>
      )}
    </div>
  );
}

/** A round chrome button that opens a small popover; Escape or a click outside closes it. */
export function ChromeMenu({ label, icon, tour, children, wide = false }: {
  label: string; icon: ReactNode; tour: string; children: (close: () => void) => ReactNode; wide?: boolean;
}) {
  const { open, setOpen, root, button, id } = usePopover();
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
    <button type="button" className="chrome-btn menu-btn" onClick={onOpen} aria-haspopup="dialog" aria-label={tr({ en: 'Menu', fr: 'Menu' })} title={tr({ en: 'Menu', fr: 'Menu' })}>
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
