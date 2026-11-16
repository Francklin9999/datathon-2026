'use client';
/**
 * Styled single-select dropdown (WAI-ARIA listbox pattern). A button opens a popover list; arrows,
 * Home/End and typeahead move the active option, Enter/Space choose it, Escape or a click outside
 * closes and returns focus to the button. Used where the native list cannot be styled. An optional
 * footer (an action such as "Manage profiles") sits under the options, outside the listbox itself:
 * Tab moves to it, and leaving the popover closes it. The popover renders in a portal on
 * document.body, fixed under the button (above it when there is no room below), so no card, widget
 * or bar clips or covers it; it fades in and out (usePopover).
 */
import { Check } from 'lucide-react';
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { listboxNext, typeaheadIndex } from '../../lib/ui/listbox';
import { portalTarget } from './popoverPlacement';
import { usePopoverPosition, usePresence } from './usePopover';

export interface ListboxOption<T extends string> { value: T; label: string; meta?: string }

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Listbox<T extends string>({ label, value, options, onChange, renderTrigger, triggerClassName, popoverClassName, footer }: {
  /** Accessible name of the control (e.g. "Fictional investor"). */
  label: string;
  value: T;
  options: readonly ListboxOption<T>[];
  onChange: (value: T) => void;
  renderTrigger: (selected: ListboxOption<T> | undefined, open: boolean) => ReactNode;
  triggerClassName?: string;
  /** Extra class on the popover (it renders in a portal, so the trigger's parent cannot style it). */
  popoverClassName?: string;
  /** Rendered under the options; receives a function that closes the popover. */
  footer?: (close: () => void) => ReactNode;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement | null>(null);
  const button = useRef<HTMLButtonElement | null>(null);
  const list = useRef<HTMLUListElement | null>(null);
  // The popover element: the list itself, or the box holding the list and the footer.
  const pop = useRef<HTMLElement | null>(null);
  const typed = useRef({ text: '', at: 0 });
  const presence = usePresence(open, pop);
  const place = usePopoverPosition(presence.present, button, pop, { minWidth: 220 });
  // -1 when the value is not (yet) among the options, e.g. a stored benchmark before assets load.
  const selectedIndex = options.findIndex(o => o.value === value);
  const selected = selectedIndex >= 0 ? options[selectedIndex] : undefined;

  // Opened with the keyboard, the chosen option is active; opened with the pointer, nothing is until
  // the pointer is over an option (-1 = no active option), so only one row is ever highlighted.
  const openList = (withKeyboard: boolean) => { setActive(withKeyboard ? Math.max(0, selectedIndex) : -1); setOpen(true); };
  const close = (refocus: boolean) => { setOpen(false); if (refocus) button.current?.focus(); };
  const choose = (index: number) => {
    const option = options[index];
    if (option) onChange(option.value);
    close(true);
  };

  useEffect(() => {
    if (!open) return undefined;
    list.current?.focus({ preventScroll: true });
    const onDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!root.current?.contains(target) && !pop.current?.contains(target)) setOpen(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [open, active]);

  const onButtonKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) { event.preventDefault(); openList(true); }
  };

  const onListKey = (event: KeyboardEvent<HTMLUListElement>) => {
    const next = listboxNext(active, event.key, options.length);
    if (next !== null) { event.preventDefault(); setActive(next); return; }
    const typing = Date.now() - typed.current.at < 600 && typed.current.text.length > 0;
    if (event.key === 'Enter' || (event.key === ' ' && !typing)) { event.preventDefault(); choose(active); return; }
    // Closing the list must not also close a drawer or sheet around it.
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true); return; }
    if (event.key === 'Tab') {
      // The list sits at the end of the page (portal): focus goes back to the button first, so Tab
      // continues from there as if the list were still beside it. With a footer, Tab enters the footer.
      if (!footer || event.shiftKey) close(true);
      return;
    }
    if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const now = Date.now();
      typed.current = { text: now - typed.current.at < 600 ? typed.current.text + event.key : event.key, at: now };
      const hit = typeaheadIndex(options.map(o => o.label), typed.current.text, typed.current.text.length > 1 ? active - 1 : active);
      if (hit >= 0) setActive(hit);
    }
  };

  // Keys inside the footer: Escape closes; Shift+Tab from its first control returns to the list, Tab
  // from its last moves on past the button.
  const onPopoverKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.target === list.current || !pop.current) return;
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true); return; }
    if (event.key !== 'Tab') return;
    const items = [...pop.current.querySelectorAll<HTMLElement>(`.popover-footer :is(${FOCUSABLE})`)];
    if (event.shiftKey && event.target === items[0]) { event.preventDefault(); list.current?.focus(); return; }
    if (!event.shiftKey && event.target === items[items.length - 1]) close(true);
  };

  const portalClass = `popover popover-portal${popoverClassName ? ` ${popoverClassName}` : ''}`;
  const popProps = {
    style: place.style,
    'data-side': place.side,
    ...(presence.leaving ? { 'data-leaving': '', inert: true } : {}),
  };
  const items = (
    <ul ref={el => { list.current = el; if (!footer) pop.current = el; }} id={`${id}-list`} role="listbox" aria-label={label} tabIndex={-1}
      className={footer ? 'popover-list' : portalClass} {...(footer ? {} : popProps)}
      {...(active >= 0 ? { 'aria-activedescendant': `${id}-opt-${active}` } : {})} onKeyDown={onListKey}
      onPointerLeave={() => setActive(-1)}>
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

  return (
    <div className="listbox" ref={root}>
      <button ref={button} type="button" className={triggerClassName} aria-haspopup="listbox" aria-expanded={open}
        {...(open ? { 'aria-controls': `${id}-list` } : {})} aria-label={`${label}: ${selected?.label ?? value}`}
        onClick={() => (open ? close(false) : openList(false))} onKeyDown={onButtonKey}>
        {renderTrigger(selected, open)}
      </button>
      {presence.present && createPortal(footer ? (
        <div ref={el => { pop.current = el; }} className={portalClass} {...popProps} onKeyDown={onPopoverKey}
          onBlur={event => {
            const next = event.relatedTarget as Node | null;
            if (!next || (!root.current?.contains(next) && !pop.current?.contains(next))) setOpen(false);
          }}>
          {items}
          <div className="popover-footer">{footer(() => close(false))}</div>
        </div>
      ) : items, portalTarget())}
    </div>
  );
}
