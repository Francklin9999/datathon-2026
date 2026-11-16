'use client';
/**
 * Tabs (WAI-ARIA APG, automatic activation): one tab stop, arrows/Home/End move and select, and the
 * same gliding ink pill as SegmentedControl, so a page section switcher looks like every other
 * choice in the app. The caller renders the active panel with `tabPanelProps`. `useTabParam` keeps
 * the active tab in the URL (?tab=) without a navigation, so a link or a refresh lands on it.
 */
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { nextSegmentIndex } from '../../lib/ui/segmented';
import { pillStyle, useSlidingPill } from './useSlidingPill';

export interface TabItem<T extends string> { id: T; label: string; title?: string }

export function tabId(base: string, id: string): string { return `${base}-tab-${id}`; }
export function tabPanelId(base: string, id: string): string { return `${base}-panel-${id}`; }

/** Props for the active panel: labelled by its tab, focusable, and keyed so it fades in on change. */
export function tabPanelProps(base: string, id: string) {
  return { id: tabPanelId(base, id), role: 'tabpanel', 'aria-labelledby': tabId(base, id), tabIndex: 0, className: 'tab-panel', key: id } as const;
}

export function Tabs<T extends string>({ label, tabs, value, onChange, idBase }: {
  label: string;
  tabs: readonly TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  idBase: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const selected = Math.max(0, tabs.findIndex(t => t.id === value));
  const { ref, box } = useSlidingPill<HTMLDivElement>(`${value}|${tabs.map(t => t.label).join('|')}`);
  const [armed, setArmed] = useState(false);
  const arm = () => { if (!armed) setArmed(true); };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const next = nextSegmentIndex(selected, event.key, tabs.length);
    const tab = next === null ? undefined : tabs[next];
    if (next === null || !tab) return;
    event.preventDefault();
    onChange(tab.id);
    refs.current[next]?.focus();
  };

  return (
    <div ref={ref} role="tablist" aria-label={label} className="segmented segmented-md tabs" onKeyDown={onKeyDown}
      onPointerEnter={arm} onFocus={arm}>
      <span className="segment-pill" aria-hidden="true" data-animate={armed ? 'true' : undefined} style={pillStyle(box)} />
      {tabs.map((tab, i) => {
        const active = i === selected;
        return (
          <button key={tab.id} ref={el => { refs.current[i] = el; }} type="button" role="tab" id={tabId(idBase, tab.id)}
            aria-selected={active} aria-controls={tabPanelId(idBase, tab.id)} tabIndex={active ? 0 : -1} className="segment"
            data-pill-target={active ? 'true' : undefined} {...(tab.title ? { title: tab.title } : {})}
            onClick={() => onChange(tab.id)}>
            <span className="segment-label">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** The value of `?{param}=` when it is one of `allowed`; otherwise `fallback`. Pure, for tests. */
export function readTabParam<T extends string>(search: string, param: string, allowed: readonly T[], fallback: T): T {
  const raw = new URLSearchParams(search).get(param);
  return raw !== null && (allowed as readonly string[]).includes(raw) ? (raw as T) : fallback;
}

/** Active tab kept in `?{param}=` with history.replaceState (no navigation, no scroll jump). */
export function useTabParam<T extends string>(param: string, allowed: readonly T[], fallback: T): [T, (next: T) => void] {
  const [value, setValue] = useState<T>(fallback);
  const allowedKey = allowed.join('|');
  useEffect(() => {
    setValue(readTabParam(window.location.search, param, allowed, fallback));
    // `allowed` is compared by content (allowedKey).
  }, [param, allowedKey, fallback]);
  const select = useCallback((next: T) => {
    setValue(next);
    const url = new URL(window.location.href);
    if (next === fallback) url.searchParams.delete(param); else url.searchParams.set(param, next);
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
  }, [param, fallback]);
  return [value, select];
}
