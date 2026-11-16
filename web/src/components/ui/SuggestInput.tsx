'use client';
/**
 * Text field with suggestions: the WAI-ARIA APG editable combobox with list autocomplete and manual
 * selection. Suggestions are ranked locally (lib/suggest.ts) on every keystroke, so they keep up with
 * typing. Down opens and moves, Up moves back, Enter takes the highlighted row, Escape closes. The
 * typed text stays as typed unless a row is chosen, so free text (an on-demand ticker) still works.
 * The list renders in a portal on document.body, fixed under the field (above it when there is no
 * room below), so no card, widget or drawer clips it; focus never leaves the field.
 */
import { useEffect, useMemo, useRef, useState, type InputHTMLAttributes, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { browseSuggestions, buildSuggestIndex, matchSpan, rankSuggestions, type Suggestion } from '../../lib/suggest';
import { portalTarget } from './popoverPlacement';
import { usePopoverPosition, usePresence } from './usePopover';

/** Rows listed for typed text. */
const SUGGEST_LIMIT = 8;
/** Rows listed when browsing a field's whole list (the popover scrolls past about eight). */
const BROWSE_LIMIT = 50;

type FieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'value' | 'onChange' | 'type' | 'role' | 'list' | 'autoComplete'>;

export function SuggestInput({ id, value, onChange, suggestions, listLabel, onPick, type = 'text', ...field }: FieldProps & {
  id: string;
  value: string;
  onChange: (value: string) => void;
  suggestions: readonly Suggestion[];
  /** Accessible name of the list of suggestions. */
  listLabel: string;
  /** Instead of filling the field, act on the chosen row (open a country, for instance). */
  onPick?: (item: Suggestion) => void;
  type?: 'text' | 'search';
}) {
  const index = useMemo(() => buildSuggestIndex(suggestions), [suggestions]);
  const [open, setOpen] = useState(false);
  // Opened by a click or Down while empty or on a value it already holds: list everything, like a
  // select (a currency list must not stop at eight and hide USD).
  const [browse, setBrowse] = useState(false);
  const browsed = useMemo(() => {
    if (!browse) return null;
    return value.trim() ? browseSuggestions(index, value, BROWSE_LIMIT) : rankSuggestions(index, '', BROWSE_LIMIT);
  }, [browse, index, value]);
  const results = useMemo(() => browsed ?? rankSuggestions(index, value, SUGGEST_LIMIT), [browsed, index, value]);
  const marked = browsed ? '' : value;
  const [active, setActive] = useState(-1);
  const [byKeys, setByKeys] = useState(false);
  const input = useRef<HTMLInputElement | null>(null);
  const list = useRef<HTMLUListElement | null>(null);
  const listId = `${id}-suggestions`;
  const shown = open && results.length > 0;
  const current = active < results.length ? active : -1;
  const presence = usePresence(shown, list);
  const place = usePopoverPosition(presence.present, input, list, { minWidth: 240, exactWidth: true });

  useEffect(() => {
    if (shown && current >= 0) list.current?.querySelector<HTMLElement>(`[data-index="${current}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [shown, current]);

  const close = () => { setOpen(false); setActive(-1); setBrowse(false); };
  const choose = (item: Suggestion) => { if (onPick) onPick(item); else onChange(item.value); close(); };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    field.onKeyDown?.(event);
    if (event.defaultPrevented || event.nativeEvent.isComposing) return;
    if (event.key === 'ArrowDown' && results.length > 0) {
      event.preventDefault();
      setByKeys(true);
      if (!shown) { setOpen(true); setBrowse(true); setActive(event.altKey ? -1 : 0); } else setActive(Math.min(results.length - 1, current + 1));
    } else if (event.key === 'ArrowUp' && shown) {
      event.preventDefault();
      setByKeys(true);
      setActive(Math.max(-1, current - 1));
    } else if (event.key === 'Enter' && shown && current >= 0) {
      const item = results[current];
      if (item) { event.preventDefault(); choose(item); }
    } else if (event.key === 'Escape' && shown) {
      // Closing the list must not also close a drawer or tour around the field.
      event.preventDefault();
      event.stopPropagation();
      close();
    } else if (event.key === 'Tab') {
      close();
    }
  };

  return (
    <div className="suggest">
      <input {...field} ref={input} id={id} type={type} role="combobox" autoComplete="off" spellCheck={false} value={value}
        aria-autocomplete="list" aria-expanded={shown}
        {...(shown ? { 'aria-controls': listId } : {})}
        {...(shown && current >= 0 ? { 'aria-activedescendant': `${listId}-${current}` } : {})}
        onChange={event => { onChange(event.target.value); setOpen(true); setBrowse(false); setActive(-1); }}
        onKeyDown={onKeyDown}
        onClick={event => { field.onClick?.(event); setOpen(true); setBrowse(true); }}
        onBlur={event => { field.onBlur?.(event); close(); }} />
      {presence.present && results.length > 0 && createPortal(
        <ul ref={list} id={listId} role="listbox" aria-label={listLabel} className="popover popover-portal suggest-list"
          style={place.style} data-side={place.side} {...(presence.leaving ? { 'data-leaving': '', inert: true } : {})}
          data-keys={byKeys ? 'true' : undefined} onMouseDown={event => event.preventDefault()}>
          {results.map((item, i) => (
            <li key={item.value} id={`${listId}-${i}`} role="option" aria-selected={i === current} data-index={i}
              data-active={i === current ? 'true' : undefined} className="option"
              onPointerEnter={() => { setByKeys(false); setActive(i); }} onClick={() => choose(item)}>
              <span className="suggest-value"><Marked text={item.value} query={marked} /></span>
              {item.label && <span className="suggest-label"><Marked text={item.label} query={marked} /></span>}
              {item.meta && <span className="option-meta">{item.meta}</span>}
            </li>
          ))}
        </ul>,
        portalTarget(),
      )}
    </div>
  );
}

/** The text with the typed part emphasized, when it appears as typed. */
function Marked({ text, query }: { text: string; query: string }) {
  const span = matchSpan(text, query);
  if (!span) return <>{text}</>;
  return <>{text.slice(0, span[0])}<mark className="suggest-mark">{text.slice(span[0], span[1])}</mark>{text.slice(span[1])}</>;
}
