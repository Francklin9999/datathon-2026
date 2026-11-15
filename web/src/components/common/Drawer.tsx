'use client';
/**
 * Side drawer (near full-screen on mobile): focus moves in, Tab is trapped, Escape closes, focus
 * returns to the element that opened it (DESIGN.md, AUDUI-06; useDialogFocus). The glass sheet slides
 * in from its side and the backdrop fades (motion; transforms are dropped under reduced motion by
 * MotionConfig). Rendered in a portal so a transformed ancestor never traps its fixed position.
 */
import { AnimatePresence, motion } from 'motion/react';
import { useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { useApp } from '../../state/app';
import { useDialogFocus, useMounted } from '../ui/useDialogFocus';

const SMOOTH = { type: 'spring', visualDuration: 0.42, bounce: 0.08 } as const;
const EXIT = { duration: 0.2, ease: [0.32, 0.72, 0, 1] } as const;

export function Drawer({ open, title, onClose, children, side = 'right' }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; side?: 'right' | 'left';
}) {
  const { tr } = useApp();
  const panel = useRef<HTMLDivElement | null>(null);
  const titleId = useId();
  useDialogFocus(open, panel, onClose);
  const mounted = useMounted();

  if (!mounted) return null;
  const offset = side === 'right' ? 56 : -56;
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div key="backdrop" className="backdrop backdrop-drawer" onClick={onClose} aria-hidden="true"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: EXIT }} transition={{ duration: 0.2 }} />
      )}
      {open && (
        <motion.div key="panel" className={`drawer drawer-${side}`} role="dialog" aria-modal="true" aria-labelledby={titleId}
          ref={panel} tabIndex={-1}
          initial={{ opacity: 0, x: offset, scale: 0.98 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: offset, scale: 0.98, transition: EXIT }}
          transition={SMOOTH}>
          <div className="drawer-head">
            <h2 id={titleId} className="drawer-title">{title}</h2>
            <button type="button" className="icon-btn icon-btn-sm" onClick={onClose} aria-label={tr({ en: 'Close', fr: 'Fermer' })} title={tr({ en: 'Close', fr: 'Fermer' })}>
              <X aria-hidden="true" size={16} strokeWidth={2} />
            </button>
          </div>
          {children}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
