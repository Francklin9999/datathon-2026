'use client';
/**
 * Run polling (contracts/run-events.md §3, web/SPEC.md §3): 1 s while queued/running, 5 s while
 * waiting_input, delta fetches with the contiguous-completed watermark, one full fetch at terminal
 * status (retried with backoff, then reported as an error), pause while the tab is hidden and a
 * full refetch when it is shown again, exponential backoff on network/rate-limit failures.
 * The rules live in lib/runPoller.ts; nothing here fabricates progress.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Run } from '../contracts/types';
import { getApiClient } from '../api/index';
import type { ApiRequestError } from '../api/errors';
import { createRunPoller, type RunPollerView } from '../lib/runPoller';

export interface RunState {
  run: Run | null;
  /** The run cannot be read, or its complete terminal payload could not be fetched; `reload` retries. */
  error: ApiRequestError | null;
  /** Transient polling problem while a previous payload is still shown; a retry is scheduled. */
  pollError: ApiRequestError | null;
  loading: boolean;
  reload: () => void;
}

const IDLE: RunPollerView = { run: null, error: null, pollError: null, loading: false };
const LOADING: RunPollerView = { run: null, error: null, pollError: null, loading: true };

interface Internal { runId: string | null; nonce: number; view: RunPollerView }

/**
 * `onTerminal` is called once per run ID, when the complete terminal run is shown (also when the
 * run was already finished on the first fetch). A reload of the same run does not call it again.
 */
export function useRun(runId: string | null, onTerminal?: (run: Run) => void): RunState {
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState<Internal>(() => ({ runId, nonce: 0, view: runId ? LOADING : IDLE }));
  const onTerminalRef = useRef(onTerminal);
  useEffect(() => { onTerminalRef.current = onTerminal; });
  const announcedFor = useRef<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setState(prev => (prev.runId === null && prev.view === IDLE ? prev : { runId: null, nonce, view: IDLE }));
      return undefined;
    }
    setState({ runId, nonce, view: LOADING });
    const client = getApiClient();
    const poller = createRunPoller({
      fetchRun: (since, signal) => client.run(runId, since, signal),
      onChange: view => setState({ runId, nonce, view }),
      onTerminal: finished => {
        if (announcedFor.current === runId) return;
        announcedFor.current = runId;
        onTerminalRef.current?.(finished);
      },
      isHidden: () => typeof document !== 'undefined' && document.visibilityState === 'hidden',
    });
    const onVisibility = () => poller.visibilityChanged();
    document.addEventListener('visibilitychange', onVisibility);
    poller.start();
    return () => {
      poller.stop();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [runId, nonce]);

  const reload = useCallback(() => setNonce(n => n + 1), []);
  // Never expose a payload that belongs to a previous run ID (or to a request being reloaded).
  const view = state.runId === runId && (runId === null || state.nonce === nonce) ? state.view : (runId ? LOADING : IDLE);
  return { run: view.run, error: view.error, pollError: view.pollError, loading: view.loading, reload };
}
