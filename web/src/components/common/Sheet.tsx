'use client';
/**
 * Details sheet: a centred glass panel (bottom sheet on phones) holding what a dashboard widget has
 * no room for. It grows out of the control that opened it (a short scale and drift from that side),
 * like an iOS card expanding, and shrinks back on close. Modal: focus moves in, Tab is trapped,
 * Escape and the backdrop close it, focus returns to the opener (useDialogFocus). Content renders only
 * while open, in a portal that keeps React context (fact scopes stay valid inside).
 */
import { AnimatePresence, motion } from 'motion/react';
import { useId, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { useApp } from '../../state/app';
import { useDialogFocus, useMounted } from '../ui/useDialogFocus';

const SPRING = { type: 'spring', visualDuration: 0.45, bounce: 0.12 } as const;
const EXIT = { duration: 0.22, ease: [0.32, 0.72, 0, 1] } as const;

/** Drift toward the opener as a fraction of its distance from the viewport centre. */
function driftFrom(origin: DOMRect | null): { x: number; y: number } {
  if (!origin || typeof window === 'undefined') return { x: 0, y: 24 };
  const k = 0.18;
  return {
    x: (origin.left + origin.width / 2 - window.innerWidth / 2) * k,
    y: (origin.top + origin.height / 2 - window.innerHeight / 2) * k,
  };
}

export function Sheet({ open, title, onClose, origin, children }: {
  open: boolean; title: string; onClose: () => void;
  /** Bounding box of the control that opened the sheet. */
  origin: DOMRect | null;
  children: ReactNode;
}) {
  const { tr } = useApp();
  const panel = useRef<HTMLDivElement | null>(null);
  const titleId = useId();
  useDialogFocus(open, panel, onClose);
  const mounted = useMounted();
  if (!mounted) return null;
  const drift = driftFrom(origin);
  const hidden = { opacity: 0, scale: 0.9, x: drift.x, y: drift.y };
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div key="backdrop" className="backdrop" onClick={onClose} aria-hidden="true"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: EXIT }} transition={{ duration: 0.22 }} />
      )}
      {open && (
        <div key="layer" className="sheet-layer">
          <motion.div className="sheet" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={panel} tabIndex={-1}
            initial={hidden} animate={{ opacity: 1, scale: 1, x: 0, y: 0 }} exit={{ ...hidden, transition: EXIT }} transition={SPRING}>
            <div className="sheet-head">
              <h2 id={titleId} className="sheet-title">{title}</h2>
              <button type="button" className="icon-btn icon-btn-sm sheet-close" onClick={onClose}
                aria-label={tr({ en: 'Close', fr: 'Fermer' })} title={tr({ en: 'Close', fr: 'Fermer' })}>
                <X aria-hidden="true" size={16} strokeWidth={2} />
              </button>
            </div>
            <div className="sheet-body">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** Open state plus the opener's box, for a button that opens a Sheet. */
export function useSheet(): { open: boolean; origin: DOMRect | null; show: (from: HTMLElement) => void; hide: () => void } {
  const [state, setState] = useState<{ open: boolean; origin: DOMRect | null }>({ open: false, origin: null });
  return {
    ...state,
    show: from => setState({ open: true, origin: from.getBoundingClientRect() }),
    hide: () => setState(s => ({ ...s, open: false })),
  };
}

/** A titled block inside a sheet. */
export function SheetSection({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="sheet-section">
      {title && <h3 className="eyebrow">{title}</h3>}
      {children}
    </section>
  );
}
