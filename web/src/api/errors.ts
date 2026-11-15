import type { ErrorCode } from '../contracts/types';

/** Client-side failure kinds that never come from the server body. */
export type ClientErrorCode = 'network' | 'invalid_response' | 'aborted';

/**
 * Every failed call surfaces as one of these. `code` is the server `ApiError.error.code`
 * when the body was a valid ApiError, otherwise a client-side code.
 */
export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: ErrorCode | ClientErrorCode;
  readonly requestId: string | null;
  readonly details: Record<string, unknown> | null;
  readonly retryAfterMs: number | null;

  constructor(init: {
    status: number;
    code: ErrorCode | ClientErrorCode;
    message: string;
    requestId?: string | null;
    details?: Record<string, unknown> | null;
    retryAfterMs?: number | null;
  }) {
    super(init.message);
    this.name = 'ApiRequestError';
    this.status = init.status;
    this.code = init.code;
    this.requestId = init.requestId ?? null;
    this.details = init.details ?? null;
    this.retryAfterMs = init.retryAfterMs ?? null;
  }
}

export function isAbort(error: unknown): boolean {
  return (error instanceof ApiRequestError && error.code === 'aborted')
    || (typeof DOMException !== 'undefined' && error instanceof DOMException && error.name === 'AbortError');
}

export function asApiError(error: unknown): ApiRequestError {
  if (error instanceof ApiRequestError) return error;
  if (isAbort(error)) {
    return new ApiRequestError({ status: 0, code: 'aborted', message: 'Request cancelled' });
  }
  const message = error instanceof Error ? error.message : String(error);
  return new ApiRequestError({ status: 0, code: 'network', message });
}
