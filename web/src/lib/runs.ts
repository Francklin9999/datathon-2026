/** Pure polling/merge rules from contracts/run-events.md §3 and web/SPEC.md §3. */
import type { Run, RunStatus, Step } from '../contracts/types';

const ACTIVE_POLL_MS = 1_000;
const WAITING_POLL_MS = 5_000;
const MAX_BACKOFF_MS = 30_000;

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

/*
 * Live elapsed time (no fake progress): computed from timestamps the server wrote. `clientNow` is
 * Date.now(); the server's last write (`updatedAt`) is a floor, so a client clock running behind
 * never shows a time earlier than the payload. A client clock running ahead can still overstate.
 */

function parsedMs(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : null;
}

/** Best estimate of "now" on the server's clock. */
export function serverNowMs(run: Pick<Run, 'updatedAt'>, clientNow: number): number {
  const updated = parsedMs(run.updatedAt);
  return updated === null ? clientNow : Math.max(clientNow, updated);
}

/** A finished step's recorded duration; for a running step, the time since it started (never negative). */
export function stepElapsedMs(step: Pick<Step, 'durationMs' | 'startedAt'>, run: Pick<Run, 'updatedAt'>, clientNow: number): number | null {
  if (step.durationMs !== null) return step.durationMs;
  const started = parsedMs(step.startedAt);
  return started === null ? null : Math.max(0, serverNowMs(run, clientNow) - started);
}

/** Whole run: the recorded total once terminal; otherwise the time since the request was accepted (queue included). */
export function runElapsedMs(run: Pick<Run, 'status' | 'usage' | 'createdAt' | 'updatedAt'>, clientNow: number): number | null {
  if (isTerminal(run.status)) return run.usage.durationMs;
  const created = parsedMs(run.createdAt);
  return created === null ? null : Math.max(0, serverNowMs(run, clientNow) - created);
}

/** Time since the first step started (the basis of the server's hard budget); null before any step. */
export function workerElapsedMs(run: Pick<Run, 'steps' | 'updatedAt'>, clientNow: number): number | null {
  const first = [...run.steps].sort((a, b) => a.seq - b.seq)[0];
  const started = parsedMs(first?.startedAt);
  return started === null ? null : Math.max(0, serverNowMs(run, clientNow) - started);
}

/** A running analysis that has worked longer than `targetMs` (the run-events.md §4 target; not a server deadline). */
export function pastRunTarget(run: Pick<Run, 'status' | 'steps' | 'updatedAt'>, clientNow: number, targetMs: number): boolean {
  if (run.status !== 'running') return false;
  const worked = workerElapsedMs(run, clientNow);
  return worked !== null && worked > targetMs;
}

/**
 * The summary the worker writes when a step starts (backend agents/workflow.py: "Running: plan." /
 * "En cours : plan."), replaced when the step ends. It only repeats the step's label and status.
 */
export function isRunningPlaceholder(step: Pick<Step, 'type' | 'summary'>): boolean {
  return step.summary.en === `Running: ${step.type}.` && step.summary.fr === `En cours : ${step.type}.`;
}

/** Delay before the next poll, or null to stop polling. */
export function nextPollDelay(status: RunStatus, consecutiveFailures: number, retryAfterMs: number | null = null): number | null {
  if (isTerminal(status)) return null;
  const base = status === 'waiting_input' ? WAITING_POLL_MS : ACTIVE_POLL_MS;
  if (consecutiveFailures <= 0) return base;
  const backoff = Math.min(MAX_BACKOFF_MS, base * 2 ** consecutiveFailures);
  return Math.max(backoff, retryAfterMs ?? 0);
}
