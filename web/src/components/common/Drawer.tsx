'use client';
/**
 * Side drawer (near full-screen on mobile): focus moves in, Tab is trapped, Escape closes, focus
 * returns to the element that opened it (DESIGN.md, AUDUI-06; useDialogFocus). The glass sheet slides
 * in from its side and the backdrop fades (motion, on the one curve with the duration tokens; instant
 * when motion is off: useAnimationsAllowed). Rendered in a portal so a transformed ancestor never traps its fixed position.
 */
import { AnimatePresence, motion } from 'motion/react';
import { useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { useApp } from '../../state/app';
import { DUR, EASE, useAnimationsAllowed } from '../../lib/ui/theme';
import { useDialogFocus, useMounted } from '../ui/useDialogFocus';

/** The one curve: in at the entrance duration, out at the menu duration; instant when motion is off. */
const ENTER = { duration: DUR.enter, ease: EASE } as const;
const EXIT = { duration: DUR.menu, ease: EASE } as const;
const NONE = { duration: 0 } as const;

export function Drawer({ open, title, onClose, children, side = 'right' }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; side?: 'right' | 'left';
}) {
  const { tr } = useApp();
  const panel = useRef<HTMLDivElement | null>(null);
  const titleId = useId();
  useDialogFocus(open, panel, onClose);
  const mounted = useMounted();
  const animate = useAnimationsAllowed();

  if (!mounted) return null;
  const enter = animate ? ENTER : NONE;
  const exit = animate ? EXIT : NONE;
  const offset = side === 'right' ? 56 : -56;
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div key="backdrop" className="backdrop backdrop-drawer" onClick={onClose} aria-hidden="true"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: exit }} transition={animate ? EXIT : NONE} />
      )}
      {open && (
        <motion.div key="panel" className={`drawer drawer-${side}`} role="dialog" aria-modal="true" aria-labelledby={titleId}
          ref={panel} tabIndex={-1}
          initial={{ opacity: 0, x: offset, scale: 0.98 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: offset, scale: 0.98, transition: exit }}
          transition={enter}>
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
