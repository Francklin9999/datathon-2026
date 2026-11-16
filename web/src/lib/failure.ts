/**
 * What a failed request means for the person in front of it: change the input, wait and retry, wait
 * for the newer API release, or something else. Built on ApiRequestError (api/errors.ts); pure, so
 * every page words the same failure the same way and tests can pin the mapping.
 *
 * Retry policy: a request may fail at most MAX_FAILED_ATTEMPTS times (the first try plus two retries)
 * before the page stops offering a bare Retry and explains instead.
 */
import { ApiRequestError, isAbort } from '../api/errors';
import type { I18NText } from '../contracts/types';
import { NEEDS_NEWER_API } from './apiCompat';
import { CLIENT_ERROR, ERROR_CODE } from './labels';

export type FailureKind = 'outdated-api' | 'edit' | 'retryable' | 'other';

export interface FailureDescription {
  kind: FailureKind;
  /** Short heading: the error-code label, or the newer-API notice. */
  title: I18NText;
  /** What happened and what to do next. Uses the server's bilingual `details.reason` when it sent one. */
  message: I18NText;
  /** The server's bilingual `details.reason`, when present (also folded into `message`). */
  reason: I18NText | null;
  /** The X-Request-Id to quote when reporting the failure; null when the API never answered. */
  requestId: string | null;
  /** The raw server message (English, written for operators): for a "Technical details" disclosure. */
  technical: string;
  /** Whether a bare Retry button still makes sense (retryable and fewer than MAX_FAILED_ATTEMPTS failures). */
  retry: boolean;
}

/** First try plus two retries. */
export const MAX_FAILED_ATTEMPTS = 3;

/** After `failureCount` failed attempts of the same request, is a bare Retry still worth offering? */
export function shouldOfferRetry(failureCount: number): boolean {
  return failureCount < MAX_FAILED_ATTEMPTS;
}

const t = (en: string, fr: string): I18NText => ({ en, fr });

/** A bilingual `{ en, fr }` value with both strings non-empty, else null. */
export function bilingualReason(value: unknown): I18NText | null {
  if (!value || typeof value !== 'object') return null;
  const { en, fr } = value as Record<string, unknown>;
  return typeof en === 'string' && en.trim() && typeof fr === 'string' && fr.trim() ? { en, fr } : null;
}

const RETRYABLE_CODES = new Set<string>(['network', 'upstream_unavailable', 'rate_limited', 'internal']);
const EDIT_CODES = new Set<string>(['validation_error', 'insufficient_data']);

function classify(error: ApiRequestError, olderApi: boolean): FailureKind {
  if (error.code === 'not_found' && olderApi) return 'outdated-api';
  if (EDIT_CODES.has(error.code)) return 'edit';
  if (RETRYABLE_CODES.has(error.code) || error.status >= 500) return 'retryable';
  return 'other';
}

function titleOf(error: ApiRequestError, kind: FailureKind): I18NText {
  if (kind === 'outdated-api') return NEEDS_NEWER_API;
  const code = error.code;
  if (code === 'network' || code === 'invalid_response' || code === 'aborted') return CLIENT_ERROR[code];
  return ERROR_CODE[code] ?? ERROR_CODE.internal;
}

function retryableMessage(error: ApiRequestError, exhausted: boolean): I18NText {
  if (exhausted) {
    return error.requestId
      ? t('Still unavailable after several tries. Try again later; if you report it, include the request ID.',
        'Toujours indisponible après plusieurs essais. Réessayez plus tard ; pour le signaler, joignez l’identifiant de requête.')
      : t('Still unavailable after several tries. Try again later.', 'Toujours indisponible après plusieurs essais. Réessayez plus tard.');
  }
  if (error.code === 'network') {
    return t('Could not reach the API. Check your connection, then try again.', 'Impossible de joindre l’API. Vérifiez votre connexion, puis réessayez.');
  }
  if (error.code === 'rate_limited') {
    const seconds = error.retryAfterMs && error.retryAfterMs > 0 ? Math.ceil(error.retryAfterMs / 1000) : null;
    return seconds
      ? t(`Too many requests in a short time. Wait about ${seconds} s, then try again.`, `Trop de requêtes en peu de temps. Patientez environ ${seconds} s, puis réessayez.`)
      : t('Too many requests in a short time. Wait a moment, then try again.', 'Trop de requêtes en peu de temps. Patientez un instant, puis réessayez.');
  }
  return t('The service is not responding right now. This is usually temporary; try again in a moment.',
    'Le service ne répond pas pour le moment. C’est généralement temporaire ; réessayez dans un instant.');
}

function otherMessage(error: ApiRequestError): I18NText {
  switch (error.code) {
    case 'not_found':
      return t('The requested item was not found. Check what you entered, or reload the page if it was removed.',
        'L’élément demandé est introuvable. Vérifiez votre saisie, ou rechargez la page s’il a été supprimé.');
    case 'conflict':
      return t('The request conflicts with the current version of the data. Reload, then try again.',
        'La requête est en conflit avec la version actuelle des données. Rechargez, puis réessayez.');
    case 'forbidden_action':
      return t('This is a simulation: no orders are placed, so this action is not available.',
        'Ceci est une simulation : aucun ordre n’est passé, cette action n’est donc pas disponible.');
    case 'feature_disabled':
      return t('This feature is turned off in this deployment.', 'Cette fonction est désactivée dans ce déploiement.');
    case 'invalid_response':
      return t('The API answered in an unexpected format. The site and the API may be on different releases; reload the page later.',
        'L’API a répondu dans un format inattendu. Le site et l’API ne sont peut-être pas à la même version ; rechargez la page plus tard.');
    case 'aborted':
      return t('The request was cancelled.', 'La requête a été annulée.');
    default:
      return t('The request failed.', 'La requête a échoué.');
  }
}

function messageOf(error: ApiRequestError, kind: FailureKind, reason: I18NText | null, exhausted: boolean): I18NText {
  switch (kind) {
    case 'outdated-api':
      return t('The connected API does not offer this feature yet. It will work once the API is updated to the newer release.',
        'L’API connectée ne propose pas encore cette fonction. Elle fonctionnera dès que l’API sera mise à jour.');
    case 'edit':
      if (reason) return reason;
      return error.code === 'insufficient_data'
        ? t('There is not enough data for this calculation. Change the period or the selection, then try again.',
          'Les données sont insuffisantes pour ce calcul. Modifiez la période ou la sélection, puis réessayez.')
        : t('The request was not accepted as entered. Change the input, then try again; sending it unchanged will fail the same way.',
          'La requête n’a pas été acceptée telle quelle. Modifiez la saisie, puis réessayez ; l’envoyer sans changement échouera de la même façon.');
    case 'retryable':
      return retryableMessage(error, exhausted);
    default:
      return reason ?? otherMessage(error);
  }
}

/**
 * Describe a failed call. `olderApi`: the API reports a contract older than the feature needs
 * (apiCompat.apiCompatibility(...) === 'older'), so its `not_found` means "route not there yet".
 * `failures`: how many times this same request has failed so far (default 1); from
 * MAX_FAILED_ATTEMPTS on, a retryable failure says so instead of offering Retry.
 * A value that is not an ApiRequestError (a bug in the page, not a failed call) is `other`.
 */
export function describeFailure(error: unknown, options: { olderApi?: boolean | undefined; failures?: number | undefined } = {}): FailureDescription {
  const failures = options.failures ?? 1;
  if (!(error instanceof ApiRequestError)) {
    const aborted = isAbort(error);
    return {
      kind: 'other',
      title: aborted ? CLIENT_ERROR.aborted : t('Something went wrong on this page', 'Un problème est survenu sur cette page'),
      message: aborted ? t('The request was cancelled.', 'La requête a été annulée.') : t('Reload the page, then try again.', 'Rechargez la page, puis réessayez.'),
      reason: null,
      requestId: null,
      technical: error instanceof Error ? error.message : String(error),
      retry: false,
    };
  }
  const kind = classify(error, options.olderApi === true);
  const reason = bilingualReason(error.details?.reason);
  const exhausted = !shouldOfferRetry(failures);
  return {
    kind,
    title: titleOf(error, kind),
    message: messageOf(error, kind, reason, exhausted),
    reason,
    requestId: error.requestId,
    technical: error.message,
    retry: kind === 'retryable' && !exhausted,
  };
}
