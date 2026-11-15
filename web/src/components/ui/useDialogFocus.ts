'use client';
/**
 * Modal focus handling shared by Drawer and Sheet: focus moves into the panel, Tab is trapped,
 * Escape closes, focus returns to the element that opened it, and the page does not scroll behind.
 * Open dialogs form a stack: only the top one reacts to keys, so a source drawer opened from a
 * details sheet closes alone on Escape and returns focus inside the sheet.
 */
import { useEffect, useRef, useState, type RefObject } from 'react';

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const stack: symbol[] = [];

export function useDialogFocus(open: boolean, panel: RefObject<HTMLElement | null>, onClose: () => void): void {
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; });

  useEffect(() => {
    if (!open) return undefined;
    const token = Symbol('dialog');
    stack.push(token);
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (stack[stack.length - 1] !== token) return;
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
      const at = stack.indexOf(token);
      if (at >= 0) stack.splice(at, 1);
      document.body.style.overflow = overflow;
      if (previous && document.contains(previous)) previous.focus();
    };
  }, [open, panel]);
}

/** False during the static render and hydration, true after mount: portals target document.body only then. */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);
  return mounted;
}
