'use client';
/**
 * A small "i" that reveals a note on hover, keyboard focus or tap. The note is also the button's
 * description for assistive technology, so folding it away hides nothing from screen readers.
 */
import { Info } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import { useApp } from '../../state/app';

export function InfoTip({ text, label, align = 'center' }: { text: string; label?: string; align?: 'start' | 'center' | 'end' }) {
  const { tr } = useApp();
  const id = useId();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLSpanElement | null>(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event: PointerEvent) => { if (root.current && !root.current.contains(event.target as Node)) setOpen(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('pointerdown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return (
    <span className="info-tip" ref={root} data-align={align} {...(open ? { 'data-open': '' } : {})}>
      <button type="button" className="info-btn" aria-label={label ?? tr({ en: 'More information', fr: 'Plus d’informations' })}
        aria-describedby={id} aria-expanded={open} onClick={() => setOpen(o => !o)}>
        <Info aria-hidden="true" size={13} strokeWidth={2} />
      </button>
      <span className="info-bubble" role="tooltip" id={id}>{text}</span>
    </span>
  );
}
