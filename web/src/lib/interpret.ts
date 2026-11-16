/**
 * One Decision Desk interpretation (POST /requests/parse) with a Cancel and a client deadline.
 * Framework-free so the outcomes can be tested with injected timers.
 *
 * Cancelling or timing out only drops the browser's connection: the server finishes (and pays for)
 * its model call anyway, so the page never says the server stopped.
 */
import { asApiError, type ApiRequestError } from '../api/errors';

/** How long the page waits for an interpretation before it stops waiting (one constant). */
export const INTERPRET_TIMEOUT_MS = 90_000;

export type InterpretOutcome<T> =
  | { status: 'ok'; value: T }
  /** The user cancelled. */
  | { status: 'cancelled' }
  /** No answer within the deadline; the request was abandoned. */
  | { status: 'timeout' }
  | { status: 'error'; error: ApiRequestError };

export interface InterpretHandle<T> {
  /** Always resolves (never rejects), exactly once. */
  promise: Promise<InterpretOutcome<T>>;
  /** Abandon the request; the outcome becomes `cancelled` unless it already settled. */
  cancel: () => void;
}

export interface InterpretOptions {
  timeoutMs?: number | undefined;
  setTimer?: ((fn: () => void, ms: number) => unknown) | undefined;
  clearTimer?: ((handle: unknown) => void) | undefined;
}

export function startInterpret<T>(call: (signal: AbortSignal) => Promise<T>, options: InterpretOptions = {}): InterpretHandle<T> {
  const setTimer = options.setTimer ?? ((fn: () => void, ms: number): unknown => setTimeout(fn, ms));
  const clearTimer = options.clearTimer ?? ((handle: unknown) => clearTimeout(handle as ReturnType<typeof setTimeout>));
  const controller = new AbortController();
  let settled = false;
  let resolveOutcome: (outcome: InterpretOutcome<T>) => void = () => undefined;
  const promise = new Promise<InterpretOutcome<T>>(resolve => { resolveOutcome = resolve; });
  const finish = (outcome: InterpretOutcome<T>) => {
    if (settled) return;
    settled = true;
    clearTimer(timer);
    resolveOutcome(outcome);
  };
  const timer = setTimer(() => {
    if (settled) return;
    finish({ status: 'timeout' });
    controller.abort();
  }, options.timeoutMs ?? INTERPRET_TIMEOUT_MS);
  call(controller.signal).then(
    value => finish({ status: 'ok', value }),
    error => finish({ status: 'error', error: asApiError(error) }),
  );
  return {
    promise,
    cancel: () => {
      if (settled) return;
      finish({ status: 'cancelled' });
      controller.abort();
    },
  };
}
