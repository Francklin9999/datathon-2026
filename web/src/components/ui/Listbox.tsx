'use client';
/**
 * Styled single-select dropdown (WAI-ARIA listbox pattern). A button opens a popover list; arrows,
 * Home/End and typeahead move the active option, Enter/Space choose it, Escape or a click outside
 * closes and returns focus to the button. Used where the native list cannot be styled. An optional
 * footer (an action such as "Manage profiles") sits under the options, outside the listbox itself:
 * Tab moves to it, and leaving the popover closes it.
 */
import { Check } from 'lucide-react';
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { listboxNext, typeaheadIndex } from '../../lib/ui/listbox';

export interface ListboxOption<T extends string> { value: T; label: string; meta?: string }

export function Listbox<T extends string>({ label, value, options, onChange, renderTrigger, triggerClassName, className, footer }: {
  /** Accessible name of the control (e.g. "Fictional investor"). */
  label: string;
  value: T;
  options: readonly ListboxOption<T>[];
  onChange: (value: T) => void;
  renderTrigger: (selected: ListboxOption<T> | undefined, open: boolean) => ReactNode;
  triggerClassName?: string;
  className?: string;
  /** Rendered under the options; receives a function that closes the popover. */
  footer?: (close: () => void) => ReactNode;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement | null>(null);
  const button = useRef<HTMLButtonElement | null>(null);
  const list = useRef<HTMLUListElement | null>(null);
  const typed = useRef({ text: '', at: 0 });
  // -1 when the value is not (yet) among the options, e.g. a stored benchmark before assets load.
  const selectedIndex = options.findIndex(o => o.value === value);
  const selected = selectedIndex >= 0 ? options[selectedIndex] : undefined;

  const openList = () => { setActive(Math.max(0, selectedIndex)); setOpen(true); };
  const close = (refocus: boolean) => { setOpen(false); if (refocus) button.current?.focus(); };
  const choose = (index: number) => {
    const option = options[index];
    if (option) onChange(option.value);
    close(true);
  };

  useEffect(() => {
    if (!open) return undefined;
    list.current?.focus();
    const onDown = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [open, active]);

  const onButtonKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) { event.preventDefault(); openList(); }
  };

  const onListKey = (event: KeyboardEvent<HTMLUListElement>) => {
    const next = listboxNext(active, event.key, options.length);
    if (next !== null) { event.preventDefault(); setActive(next); return; }
    const typing = Date.now() - typed.current.at < 600 && typed.current.text.length > 0;
    if (event.key === 'Enter' || (event.key === ' ' && !typing)) { event.preventDefault(); choose(active); return; }
    if (event.key === 'Escape') { event.preventDefault(); close(true); return; }
    if (event.key === 'Tab') { if (!footer || event.shiftKey) close(false); return; }
    if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const now = Date.now();
      typed.current = { text: now - typed.current.at < 600 ? typed.current.text + event.key : event.key, at: now };
      const hit = typeaheadIndex(options.map(o => o.label), typed.current.text, typed.current.text.length > 1 ? active - 1 : active);
      if (hit >= 0) setActive(hit);
    }
  };

  return (
    <div className={`listbox${className ? ` ${className}` : ''}`} ref={root}>
      <button ref={button} type="button" className={triggerClassName} aria-haspopup="listbox" aria-expanded={open}
        {...(open ? { 'aria-controls': `${id}-list` } : {})} aria-label={`${label}: ${selected?.label ?? value}`}
        onClick={() => (open ? close(false) : openList())} onKeyDown={onButtonKey}>
        {renderTrigger(selected, open)}
      </button>
      {open && (() => {
        const items = (
          <ul ref={list} id={`${id}-list`} role="listbox" aria-label={label} tabIndex={-1} className={footer ? 'popover-list' : 'popover'}
            aria-activedescendant={`${id}-opt-${active}`} onKeyDown={onListKey}>
            {options.map((option, i) => (
              <li key={option.value} id={`${id}-opt-${i}`} role="option" aria-selected={i === selectedIndex} data-index={i}
                data-active={i === active ? 'true' : undefined} className="option"
                onPointerEnter={() => setActive(i)} onClick={() => choose(i)}>
                <span>{option.label}</span>
                {option.meta && <span className="option-meta">{option.meta}</span>}
                {i === selectedIndex && <Check className="option-check" aria-hidden="true" size={16} strokeWidth={1.5} />}
              </li>
            ))}
          </ul>
        );
        if (!footer) return items;
        return (
          <div className="popover"
            onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); close(true); } }}
            onBlur={event => { if (!root.current?.contains(event.relatedTarget as Node | null)) setOpen(false); }}>
            {items}
            <div className="popover-footer">{footer(() => close(false))}</div>
          </div>
        );
      })()}
    </div>
  );
}
