'use client';
/**
 * Minimal keyed query hook. Keys must include session/profile version/data version/window/lang
 * (web/SPEC.md §2). A key change aborts the previous request and clears stale data immediately,
 * so a persona switch never shows the previous persona's numbers or prose.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { asApiError, isAbort, type ApiRequestError } from '../api/errors';

const cache = new Map<string, unknown>();
/** Reads already on their way (see prefetchQuery): a query with the same key waits for them. */
const inflight = new Map<string, Promise<unknown>>();

/** Start a read before the component that shows it mounts; its result lands in the cache. */
export function prefetchQuery<T>(key: string | null, fetcher: (signal: AbortSignal) => Promise<T>): void {
  if (!key || cache.has(key) || inflight.has(key)) return;
  const promise = fetcher(new AbortController().signal)
    .then(data => { cache.set(key, data); return data; })
    .finally(() => inflight.delete(key));
  promise.catch(() => { /* the component's own query reports errors */ });
  inflight.set(key, promise);
}

/** Delays before retrying a read that failed for a transient reason. */
const READ_RETRIES = [800, 2000] as const;

export function isTransient(error: ApiRequestError): boolean {
  return error.code === 'network' || error.status === 502 || error.status === 503 || error.status === 504;
}

export function invalidateQueries(predicate: (key: string) => boolean): void {
  for (const key of [...cache.keys()]) if (predicate(key)) cache.delete(key);
}

export interface QueryState<T> {
  data: T | null;
  error: ApiRequestError | null;
  loading: boolean;
  reload: () => void;
}

interface InternalState<T> { key: string | null; data: T | null; error: ApiRequestError | null; loading: boolean }

export function useQuery<T>(key: string | null, fetcher: (signal: AbortSignal) => Promise<T>): QueryState<T> {
  const [state, setState] = useState<InternalState<T>>(() => ({
    key, data: key && cache.has(key) ? (cache.get(key) as T) : null, error: null, loading: key !== null && !cache.has(key),
  }));
  const [nonce, setNonce] = useState(0);
  const fetcherRef = useRef(fetcher);
  useEffect(() => { fetcherRef.current = fetcher; });

  useEffect(() => {
    if (key === null) {
      setState({ key, data: null, error: null, loading: false });
      return undefined;
    }
    if (cache.has(key)) {
      setState({ key, data: cache.get(key) as T, error: null, loading: false });
      return undefined;
    }
    const controller = new AbortController();
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    setState(prev => ({ key, data: prev.key === key ? prev.data : null, error: null, loading: true }));
    const attempt = (n: number) => {
      fetcherRef.current(controller.signal).then(
        data => {
          if (controller.signal.aborted) return;
          cache.set(key, data);
          setState({ key, data, error: null, loading: false });
        },
        error => {
          if (controller.signal.aborted || isAbort(error)) return;
          const apiError = asApiError(error);
          // A cold or briefly overloaded API can fail a read (network or 502–504): try again quietly.
          if (n < READ_RETRIES.length && isTransient(apiError)) {
            retryTimer = setTimeout(() => attempt(n + 1), READ_RETRIES[n]);
            return;
          }
          setState({ key, data: null, error: apiError, loading: false });
        },
      );
    };
    const pending = inflight.get(key);
    if (pending) {
      pending.then(
        data => { if (!controller.signal.aborted) setState({ key, data: data as T, error: null, loading: false }); },
        () => { if (!controller.signal.aborted) attempt(0); },
      );
    } else {
      attempt(0);
    }
    return () => { controller.abort(); if (retryTimer) clearTimeout(retryTimer); };
  }, [key, nonce]);

  const reload = useCallback(() => {
    if (key) cache.delete(key);
    setNonce(n => n + 1);
  }, [key]);

  // Never expose data that belongs to a previous key.
  const current = state.key === key;
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: current ? state.loading : key !== null,
    reload,
  };
}
