'use client';
/**
 * Minimal keyed query hook. Keys must include session/profile version/data version/window/lang
 * (web/SPEC.md §2). A key change aborts the previous request and clears stale data immediately,
 * so a persona switch never shows the previous persona's numbers or prose.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { asApiError, isAbort, type ApiRequestError } from '../api/errors';

const cache = new Map<string, unknown>();

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
    setState(prev => ({ key, data: prev.key === key ? prev.data : null, error: null, loading: true }));
    fetcherRef.current(controller.signal).then(
      data => {
        if (controller.signal.aborted) return;
        cache.set(key, data);
        setState({ key, data, error: null, loading: false });
      },
      error => {
        if (controller.signal.aborted || isAbort(error)) return;
        setState({ key, data: null, error: asApiError(error), loading: false });
      },
    );
    return () => controller.abort();
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
