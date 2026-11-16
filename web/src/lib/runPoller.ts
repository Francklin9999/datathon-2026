/**
 * Framework-free run poller behind `useRun` (contracts/run-events.md §3, web/SPEC.md §3).
 *
 * 1 s while queued/running, 5 s while waiting_input, delta fetches with the contiguous-completed
 * watermark, pause while the tab is hidden and a full refetch when it is shown again, exponential
 * backoff on network/rate-limit failures.
 *
 * Terminal status: a terminal status seen through a delta is never shown. The complete run is
 * fetched first; that fetch is retried with backoff, and after `TERMINAL_FETCH_ATTEMPTS`
 * consecutive failures the poller stops and reports an error (the last non-terminal payload stays
 * visible, nothing is fabricated). `onTerminal` fires once, when the complete terminal run is shown.
 *
 * Each poll request has a deadline (POLL_TIMEOUT_MS): one that never answers counts as a lost
 * connection, so the view says so and the next poll is scheduled with backoff.
 */
import type { Run } from '../contracts/types';
import { ApiRequestError, asApiError, isAbort } from '../api/errors';
import { contiguousCompletedSeq, isTerminal, mergeRunDelta, nextPollDelay } from './runs';

export interface RunPollerView {
  run: Run | null;
  /** The run cannot be read (fatal code), or the complete terminal run could not be fetched. */
  error: ApiRequestError | null;
  /** Transient polling problem while a previous payload is still shown; a retry is scheduled. */
  pollError: ApiRequestError | null;
  loading: boolean;
}

/** Attempts at the complete terminal run (the first one included) before an error is reported. */
const TERMINAL_FETCH_ATTEMPTS = 5;

const FATAL: ReadonlySet<string> = new Set(['not_found', 'validation_error', 'feature_disabled', 'invalid_response']);

/**
 * Deadline for one poll request. A GET that never answers is abandoned and handled like a lost
 * connection (pollError, backoff, retry), instead of freezing the view with no further poll.
 */
export const POLL_TIMEOUT_MS = 20_000;

export interface RunPollerOptions {
  /** `since` is the completed-step watermark for a delta, or null for the complete run. */
  fetchRun: (since: number | null, signal: AbortSignal) => Promise<Run>;
  /** Default POLL_TIMEOUT_MS. */
  pollTimeoutMs?: number | undefined;
  onChange: (view: RunPollerView) => void;
  /** Called at most once per poller, with the complete terminal run. */
  onTerminal?: ((run: Run) => void) | undefined;
  isHidden?: (() => boolean) | undefined;
  setTimer?: ((fn: () => void, ms: number) => unknown) | undefined;
  clearTimer?: ((handle: unknown) => void) | undefined;
}

export interface RunPoller {
  start: () => void;
  stop: () => void;
  /** Call on `visibilitychange`: pauses while hidden, refetches the complete run when shown. */
  visibilityChanged: () => void;
}

export function createRunPoller(options: RunPollerOptions): RunPoller {
  const isHidden = options.isHidden ?? (() => false);
  const setTimer = options.setTimer ?? ((fn: () => void, ms: number): unknown => setTimeout(fn, ms));
  const clearTimer = options.clearTimer ?? ((handle: unknown) => clearTimeout(handle as ReturnType<typeof setTimeout>));
  const pollTimeoutMs = options.pollTimeoutMs ?? POLL_TIMEOUT_MS;

  /** Last payload shown. Never a terminal status that came from a delta. */
  let current: Run | null = null;
  /** A delta reported a terminal status; the complete run is still to be fetched. */
  let awaitingFull = false;
  let failures = 0;
  let timer: unknown = null;
  let controller: AbortController | null = null;
  let stopped = false;
  let announced = false;
  let view: RunPollerView = { run: null, error: null, pollError: null, loading: true };

  const emit = (patch: Partial<RunPollerView>) => {
    view = { ...view, ...patch };
    options.onChange(view);
  };

  const cancelTimer = () => {
    if (timer !== null) clearTimer(timer);
    timer = null;
  };

  const schedule = (delay: number | null) => {
    if (stopped || delay === null || isHidden()) return;
    cancelTimer();
    timer = setTimer(() => { timer = null; void tick(false); }, delay);
  };

  const tick = async (forceFull: boolean): Promise<void> => {
    if (stopped) return;
    cancelTimer();
    controller?.abort();
    const mine = new AbortController();
    controller = mine;
    const previous = current;
    const since = !forceFull && !awaitingFull && previous ? contiguousCompletedSeq(previous.steps) : 0;
    let payload: Run;
    let timedOut = false;
    let deadline: unknown = null;
    // Settles on its own, even if the abandoned request never rejects (e.g. still queued in the limiter).
    const expired = new Promise<never>((_, reject) => {
      deadline = setTimer(() => {
        timedOut = true;
        reject(new ApiRequestError({ status: 0, code: 'network', message: `Run poll timed out after ${Math.round(pollTimeoutMs / 1000)} s` }));
        mine.abort();
      }, pollTimeoutMs);
    });
    try {
      payload = await Promise.race([options.fetchRun(since > 0 ? since : null, mine.signal), expired]);
    } catch (caught) {
      clearTimer(deadline);
      // Superseded by a newer tick, or stopped: say nothing. A timed-out poll is a lost connection;
      // any other abort means superseded or stopped.
      if (stopped || controller !== mine) return;
      if (!timedOut && (mine.signal.aborted || isAbort(caught))) return;
      const apiError = asApiError(caught);
      if (FATAL.has(apiError.code)) {
        emit({ error: apiError, pollError: null, loading: false });
        return;
      }
      failures += 1;
      if (awaitingFull && failures >= TERMINAL_FETCH_ATTEMPTS) {
        // The run is finished but its complete payload cannot be read: stop and say so.
        emit({ error: apiError, pollError: null, loading: false });
        return;
      }
      if (previous) emit({ pollError: apiError });
      else emit({ error: apiError, loading: false });
      const status = previous && !isTerminal(previous.status) ? previous.status : 'queued';
      schedule(nextPollDelay(status, failures, apiError.retryAfterMs));
      return;
    }
    clearTimer(deadline);
    if (stopped || mine.signal.aborted) return;
    failures = 0;
    const merged: Run = previous && since > 0 ? mergeRunDelta(previous, payload) : payload;
    if (since > 0 && isTerminal(merged.status)) {
      // Terminal reached through a delta: fetch the complete run before showing a signed result.
      awaitingFull = true;
      emit({ error: null, pollError: null });
      return tick(true);
    }
    awaitingFull = false;
    current = merged;
    emit({ run: merged, error: null, pollError: null, loading: false });
    if (isTerminal(merged.status)) {
      if (!announced) {
        announced = true;
        options.onTerminal?.(merged);
      }
      return;
    }
    schedule(nextPollDelay(merged.status, 0));
  };

  return {
    start: () => { void tick(true); },
    stop: () => {
      stopped = true;
      cancelTimer();
      controller?.abort();
    },
    visibilityChanged: () => {
      if (stopped) return;
      cancelTimer();
      if (!isHidden() && (!current || !isTerminal(current.status))) void tick(true);
    },
  };
}
