'use client';
/** Loading / error / unavailable / empty states shared by every page (web/SPEC.md §6). */
import type { ReactNode } from 'react';
import type { ApiRequestError } from '../../api/errors';
import type { Lang } from '../../contracts/types';
import { CLIENT_ERROR, ERROR_CODE, labelOf } from '../../lib/labels';
import { useApp } from '../../state/app';
import { Skeleton } from '../ui/Skeleton';

export function Loading({ label, variant = 'inline' }: { label?: string; variant?: 'inline' | 'skeleton' }) {
  const { tr } = useApp();
  const text = label ?? tr({ en: 'Loading…', fr: 'Chargement…' });
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
    <div className="state state-loading" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}

export function errorTitle(error: ApiRequestError, lang: Lang): string {
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
  return (
    <div className={`state ${disabled ? 'state-unavailable' : 'state-error'}`} role="alert">
      <p className="state-title">{title ?? errorTitle(error, lang)}</p>
      <p className="muted small">{error.message}</p>
      {error.requestId && (
        <details className="tech-details">
          <summary>{tr({ en: 'Technical details', fr: 'Détails techniques' })}</summary>
          <p className="mono break">{tr({ en: 'Request', fr: 'Requête' })} {error.requestId}</p>
        </details>
      )}
      {children}
      {onRetry && !disabled && (
        <button type="button" className="btn ghost" onClick={onRetry}>{tr({ en: 'Retry', fr: 'Réessayer' })}</button>
      )}
    </div>
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
