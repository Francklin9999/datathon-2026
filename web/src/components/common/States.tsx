'use client';
/** Loading / error / unavailable / empty states shared by every page (web/SPEC.md §6). */
import { useEffect, useState, type ReactNode } from 'react';
import type { ApiRequestError } from '../../api/errors';
import type { Lang } from '../../contracts/types';
import { CLIENT_ERROR, ERROR_CODE, labelOf } from '../../lib/labels';
import { useApp } from '../../state/app';
import { Skeleton } from '../ui/Skeleton';

/** A load that ends within this many milliseconds never shows its spinner (no flicker). */
const SPINNER_DELAY_MS = 150;

export function Loading({ label, variant = 'inline' }: { label?: string; variant?: 'inline' | 'skeleton' }) {
  const { tr } = useApp();
  const text = label ?? tr({ en: 'Loading…', fr: 'Chargement…' });
  // The box keeps its place from the start (no layout shift); its spinner and words appear after the delay.
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setShown(true), SPINNER_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, []);
  if (variant === 'skeleton') {
    return (
      <div className="skeleton-tile" role="status">
        <span className="sr-only">{text}</span>
        <Skeleton width="38%" height={12} />
        <Skeleton width="72%" height={22} />
        <Skeleton width="56%" height={12} />
      </div>
    );
  }
  return (
    <div className="state state-loading" role="status" {...(shown ? {} : { 'data-pending': '' })}>
      <span className="spinner" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}

function errorTitle(error: ApiRequestError, lang: Lang): string {
  if (error.code === 'network' || error.code === 'invalid_response' || error.code === 'aborted') {
    return labelOf(CLIENT_ERROR, error.code, lang);
  }
  return labelOf(ERROR_CODE, error.code, lang);
}

export function ErrorState({ error, onRetry, title, children }: {
  error: ApiRequestError; onRetry?: (() => void) | undefined; title?: string; children?: ReactNode;
}) {
  const { tr, lang } = useApp();
  const disabled = error.code === 'feature_disabled';
  const serviceDown = error.code === 'upstream_unavailable';
  return (
    <div className={`state ${disabled ? 'state-unavailable' : 'state-error'}`} role="alert">
      <p className="state-title">{title ?? errorTitle(error, lang)}</p>
      {/* A service outage message is written for operators: it goes with the technical details. */}
      {!serviceDown && <p className="muted small">{error.message}</p>}
      {(error.requestId || serviceDown) && (
        <details className="tech-details">
          <summary>{tr({ en: 'Technical details', fr: 'Détails techniques' })}</summary>
          {serviceDown && <p className="break">{error.message}</p>}
          {error.requestId && <p className="mono break">{tr({ en: 'Request', fr: 'Requête' })} {error.requestId}</p>}
        </details>
      )}
      {children}
      {onRetry && !disabled && (
        <button type="button" className="btn ghost" onClick={onRetry}>{tr({ en: 'Retry', fr: 'Réessayer' })}</button>
      )}
    </div>
  );
}

/**
 * A rejected profile write. On a 409 conflict (the profile changed elsewhere, e.g. in another tab, or the
 * edit is not allowed) it offers to reload the profiles, as Profiles does (web/page-specs/portfolio.md).
 * `onReload` runs first, so an editor can stash its unsaved input (lib/draftStore.ts) before the
 * reload remounts it.
 */
export function ProfileWriteError({ error, onReload }: { error: ApiRequestError; onReload?: () => void }) {
  const { tr, reloadProfiles } = useApp();
  return (
    <ErrorState error={error}>
      {error.code === 'conflict' && (
        <button type="button" className="btn ghost btn-sm" onClick={() => { onReload?.(); reloadProfiles(); }}>{tr({ en: 'Reload profiles', fr: 'Recharger les profils' })}</button>
      )}
    </ErrorState>
  );
}

/** Shown by an editor that restored the input it stashed before a conflict reload. */
export function DraftRestoredNote() {
  const { tr } = useApp();
  return (
    <p className="small" role="status">
      {tr({ en: 'Your unsaved entries were kept after the reload. Check them against the reloaded profile before saving.', fr: 'Vos saisies non enregistrées ont été conservées après le rechargement. Vérifiez-les par rapport au profil rechargé avant d’enregistrer.' })}
    </p>
  );
}

export function Unavailable({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state-unavailable" role="status">
      <p className="state-title">{title}</p>
      {children && <div className="muted small">{children}</div>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state state-empty"><p className="muted">{children}</p></div>;
}
