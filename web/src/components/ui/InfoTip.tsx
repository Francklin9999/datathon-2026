'use client';
/** Viewport-clamped tooltip in a portal; hidden descriptions never participate in page layout. It fades in and out in place (components.css .info-bubble). */
import { Info } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { useApp } from '../../state/app';
import { portalTarget } from './popoverPlacement';

export function InfoTip({ text, label, align = 'center' }: { text: string; label?: string; align?: 'start' | 'center' | 'end' }) {
  const { tr } = useApp();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [position, setPosition] = useState({ left: 8, top: 8 });
  const root = useRef<HTMLSpanElement | null>(null);
  const bubble = useRef<HTMLSpanElement | null>(null);
  useEffect(() => setMounted(true), []);
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      if (!root.current || !bubble.current) return;
      const anchor = root.current.getBoundingClientRect();
      const note = bubble.current.getBoundingClientRect();
      const width = document.documentElement.clientWidth;
      const height = window.innerHeight;
      const desired = align === 'start' ? anchor.left - 8 : align === 'end' ? anchor.right - note.width + 8 : anchor.left + (anchor.width - note.width) / 2;
      setPosition({ left: Math.max(8, Math.min(desired, width - note.width - 8)),
        top: Math.max(8, Math.min(anchor.bottom + 8 + note.height > height - 8 ? anchor.top - note.height - 8 : anchor.bottom + 8, height - note.height - 8)) });
    };
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); };
  }, [open, align, text]);
  useEffect(() => {
    if (!open) return;
    const onDown = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('pointerdown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return (
    <span className="info-tip" ref={root} data-align={align}
      onPointerEnter={e => { if (e.pointerType !== 'touch') setOpen(true); }} onPointerLeave={() => setOpen(false)}>
      <button type="button" className="info-btn" aria-label={label ?? tr({ en: 'More information', fr: 'Plus d’informations' })}
        aria-describedby={id} aria-expanded={open} onFocus={e => { if (e.currentTarget.matches(':focus-visible')) setOpen(true); }} onBlur={() => setOpen(false)} onClick={() => setOpen(o => !o)}>
        <Info aria-hidden="true" size={13} strokeWidth={2} />
      </button>
      {mounted && createPortal(<span ref={bubble} className="info-bubble" role="tooltip" id={id}
        data-open={open ? '' : undefined} style={{ left: position.left, top: position.top }}>{text}</span>, portalTarget())}
    </span>
  );
}
