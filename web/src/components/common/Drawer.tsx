'use client';
/**
 * Right-side drawer (full-width modal on mobile): focus moves in, Tab is trapped, Escape closes,
 * focus returns to the element that opened it (DESIGN.md, AUDUI-06). The sheet slides in from its
 * side and the backdrop fades (motion; transforms are dropped under reduced motion by MotionConfig).
 */
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useId, useRef, type ReactNode } from 'react';
import { useApp } from '../../state/app';

const SMOOTH = { type: 'spring', visualDuration: 0.4, bounce: 0 } as const;
const EXIT = { duration: 0.18, ease: [0.7, 0, 0.84, 0] } as const;

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Drawer({ open, title, onClose, children, side = 'right' }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; side?: 'right' | 'left';
}) {
  const { tr } = useApp();
  const panel = useRef<HTMLDivElement | null>(null);
  const titleId = useId();
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; });

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onCloseRef.current(); return; }
      if (event.key !== 'Tab' || !panel.current) return;
      const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (items.length === 0) { event.preventDefault(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) {
        event.preventDefault(); last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      if (previous && document.contains(previous)) previous.focus();
    };
  }, [open]);

  const offset = side === 'right' ? 48 : -48;
  return (
    <AnimatePresence>
      {open && (
        <motion.div key="backdrop" className="backdrop" onClick={onClose} aria-hidden="true"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: EXIT }} transition={{ duration: 0.16 }} />
      )}
      {open && (
        <motion.div key="panel" className={`drawer drawer-${side}`} role="dialog" aria-modal="true" aria-labelledby={titleId}
          ref={panel} tabIndex={-1}
          initial={{ opacity: 0, x: offset }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: offset, transition: EXIT }}
          transition={SMOOTH}>
          <div className="drawer-head">
            <h2 id={titleId} className="serif drawer-title">{title}</h2>
            <button type="button" className="btn ghost btn-sm" onClick={onClose}>
              {tr({ en: 'Close', fr: 'Fermer' })}
            </button>
          </div>
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
