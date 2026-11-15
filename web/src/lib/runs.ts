/** Pure polling/merge rules from contracts/run-events.md §3 and web/SPEC.md §3. */
import type { Run, RunStatus, Step } from '../contracts/types';

export const ACTIVE_POLL_MS = 1_000;
export const WAITING_POLL_MS = 5_000;
export const MAX_BACKOFF_MS = 30_000;

export function isTerminal(status: RunStatus): boolean {
  return status === 'succeeded' || status === 'failed' || status === 'cancelled';
}

/**
 * Highest seq such that every step 1..seq is present and `done` or `failed`.
 * Never the highest running seq (run-events.md §3).
 */
export function contiguousCompletedSeq(steps: readonly Step[]): number {
  const bySeq = new Map(steps.map(step => [step.seq, step]));
  let seq = 0;
  for (;;) {
    const next = bySeq.get(seq + 1);
    if (!next || next.status === 'running') return seq;
    seq += 1;
  }
}

/** Upsert steps by seq, merge fact/evidence maps by ID, take top-level fields from the newer payload. */
export function mergeRunDelta(previous: Run, delta: Run): Run {
  if (previous.runId !== delta.runId) return delta;
  const steps = new Map(previous.steps.map(step => [step.seq, step]));
  for (const step of delta.steps) steps.set(step.seq, step);
  return {
    ...delta,
    steps: [...steps.values()].sort((a, b) => a.seq - b.seq),
    facts: { ...previous.facts, ...delta.facts },
    evidence: { ...previous.evidence, ...delta.evidence },
  };
}

/** Delay before the next poll, or null to stop polling. */
export function nextPollDelay(status: RunStatus, consecutiveFailures: number, retryAfterMs: number | null = null): number | null {
  if (isTerminal(status)) return null;
  const base = status === 'waiting_input' ? WAITING_POLL_MS : ACTIVE_POLL_MS;
  if (consecutiveFailures <= 0) return base;
  const backoff = Math.min(MAX_BACKOFF_MS, base * 2 ** consecutiveFailures);
  return Math.max(backoff, retryAfterMs ?? 0);
}
