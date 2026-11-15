'use client';
/**
 * Run polling (contracts/run-events.md §3, web/SPEC.md §3): 1 s while queued/running, 5 s while
 * waiting_input, delta fetches with the contiguous-completed watermark, one full fetch at terminal
 * status, pause while the tab is hidden and a full refetch when it is shown again, exponential
 * backoff on network/rate-limit failures. Nothing here fabricates progress.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Run } from '../contracts/types';
import { getApiClient } from '../api/index';
import { asApiError, isAbort, type ApiRequestError } from '../api/errors';
import { contiguousCompletedSeq, isTerminal, mergeRunDelta, nextPollDelay } from '../lib/runs';

export interface RunState {
  run: Run | null;
  error: ApiRequestError | null;
  /** Transient polling problem while a previous payload is still shown. */
  pollError: ApiRequestError | null;
  loading: boolean;
  reload: () => void;
}

const FATAL = new Set(['not_found', 'validation_error', 'feature_disabled', 'invalid_response']);

export function useRun(runId: string | null, onTerminal?: (run: Run) => void): RunState {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [pollError, setPollError] = useState<ApiRequestError | null>(null);
  const [loading, setLoading] = useState(false);
  const [nonce, setNonce] = useState(0);
  const onTerminalRef = useRef(onTerminal);
  useEffect(() => { onTerminalRef.current = onTerminal; });

  useEffect(() => {
    setRun(null); setError(null); setPollError(null);
    if (!runId) { setLoading(false); return undefined; }
    setLoading(true);
    const client = getApiClient();
    let current: Run | null = null;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;
    let stopped = false;

    const hidden = () => typeof document !== 'undefined' && document.visibilityState === 'hidden';

    const schedule = (delay: number | null) => {
      if (stopped || delay === null || hidden()) return;
      timer = setTimeout(() => { void tick(false); }, delay);
    };

    const tick = async (forceFull: boolean): Promise<void> => {
      if (stopped) return;
      controller?.abort();
      controller = new AbortController();
      const since = !forceFull && current ? contiguousCompletedSeq(current.steps) : 0;
      try {
        const payload = await client.run(runId, since > 0 ? since : null, controller.signal);
        if (stopped) return;
        failures = 0;
        setPollError(null);
        setError(null);
        const wasTerminal = current ? isTerminal(current.status) : false;
        const merged: Run = current && since > 0 ? mergeRunDelta(current, payload) : payload;
        if (isTerminal(merged.status) && since > 0) {
          // Terminal reached through a delta: fetch the complete run once before showing a signed result.
          current = merged;
          return tick(true);
        }
        current = merged;
        setRun(merged);
        setLoading(false);
        if (isTerminal(merged.status)) {
          if (!wasTerminal) onTerminalRef.current?.(merged);
          return;
        }
        schedule(nextPollDelay(merged.status, 0));
      } catch (caught) {
        if (stopped || isAbort(caught)) return;
        const apiError = asApiError(caught);
        if (FATAL.has(apiError.code)) {
          setError(apiError);
          setLoading(false);
          return;
        }
        if (current) setPollError(apiError);
        else { setError(apiError); setLoading(false); }
        failures += 1;
        schedule(nextPollDelay(current?.status ?? 'queued', failures, apiError.retryAfterMs));
      }
    };

    const onVisibility = () => {
      if (stopped) return;
      if (timer) clearTimeout(timer);
      timer = null;
      if (!hidden() && (!current || !isTerminal(current.status))) void tick(true);
    };

    document.addEventListener('visibilitychange', onVisibility);
    void tick(true);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      controller?.abort();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [runId, nonce]);

  const reload = useCallback(() => setNonce(n => n + 1), []);
  return { run, error, pollError, loading, reload };
}
