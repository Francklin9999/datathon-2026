'use client';
/**
 * A destructive action in two steps: the first press turns the button into "Confirm …" next to a
 * Cancel; the second press acts. It returns to rest after a few seconds, on Escape or when focus
 * leaves both buttons, so nothing is deleted by a stray click.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useApp } from '../../state/app';

const ARMED_MS = 5000;

export function ConfirmButton({ label, confirmLabel, onConfirm, icon, disabled = false, small = true, ariaLabel }: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
  icon?: ReactNode;
  disabled?: boolean;
  small?: boolean;
  /** Accessible name of the resting button when `label` alone is ambiguous (e.g. "Delete Robert"). */
  ariaLabel?: string;
}) {
  const { tr } = useApp();
  const [armed, setArmed] = useState(false);
  const group = useRef<HTMLSpanElement | null>(null);
  const confirmRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!armed) return undefined;
    confirmRef.current?.focus();
    const timer = setTimeout(() => setArmed(false), ARMED_MS);
    return () => clearTimeout(timer);
  }, [armed]);

  const size = small ? ' btn-sm' : '';
  if (!armed) {
    return (
      <button type="button" className={`btn danger${size}`} disabled={disabled} onClick={() => setArmed(true)}
        {...(ariaLabel ? { 'aria-label': ariaLabel } : {})}>
        {icon}{label}
      </button>
    );
  }
  return (
    <span ref={group} className="confirm-group" role="group" aria-label={confirmLabel}
      onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); setArmed(false); } }}
      onBlur={event => { if (!group.current?.contains(event.relatedTarget as Node | null)) setArmed(false); }}>
      <button ref={confirmRef} type="button" className={`btn danger${size}`} onClick={() => { setArmed(false); onConfirm(); }}>
        {icon}{confirmLabel}
      </button>
      <button type="button" className={`btn ghost${size}`} onClick={() => setArmed(false)}>
        {tr({ en: 'Cancel', fr: 'Annuler' })}
      </button>
    </span>
  );
}
