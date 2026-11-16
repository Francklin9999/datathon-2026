'use client';
/**
 * How many times the same request has failed in a row, for lib/failure.ts (describeFailure's
 * `failures`, shouldOfferRetry). Each new error object counts once (useQuery and the run hooks create
 * one per failed attempt); a change of `resetKey` (the request changed: other settings, profile or
 * window) or a success starts again from zero.
 */
import { useState } from 'react';

interface Tally { key: string | null; error: unknown; count: number }

export function useFailureCount(error: unknown, resetKey: string | null, succeeded = false): number {
  const [tally, setTally] = useState<Tally>({ key: resetKey, error: null, count: 0 });
  let next = tally;
  if (next.key !== resetKey) next = { key: resetKey, error: null, count: 0 };
  if (succeeded && next.count > 0) next = { ...next, error: null, count: 0 };
  if (error && error !== next.error) next = { ...next, error, count: next.count + 1 };
  // Adjusting state while rendering (React's documented pattern for state derived from props):
  // React re-renders at once with the new tally, before the effects of this render run.
  if (next !== tally) setTally(next);
  return next.count;
}
