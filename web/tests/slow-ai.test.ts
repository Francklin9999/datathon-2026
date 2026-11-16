/**
 * Slow AI calls (QA 3a-3c): an interpretation with Cancel and a 90 s deadline, live elapsed times
 * computed from the server's timestamps, and a per-request deadline on run polling.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import type { Run, Step } from '../src/contracts/types';
import { ApiRequestError } from '../src/api/errors';
import { INTERPRET_TIMEOUT_MS, startInterpret } from '../src/lib/interpret';
import {
  isRunningPlaceholder, pastRunTarget, runElapsedMs, serverNowMs, stepElapsedMs, workerElapsedMs,
} from '../src/lib/runs';
import { POLL_TIMEOUT_MS, createRunPoller, type RunPollerView } from '../src/lib/runPoller';

/** Manual timers: `fire(ms)` runs every pending timer armed with that delay. */
function fakeTimers() {
  let next = 1;
  const pending = new Map<number, { fn: () => void; ms: number }>();
  return {
    setTimer: (fn: () => void, ms: number): unknown => { const id = next++; pending.set(id, { fn, ms }); return id; },
    clearTimer: (handle: unknown) => { pending.delete(handle as number); },
    delays: () => [...pending.values()].map(t => t.ms),
    fire(ms: number) {
      for (const [id, t] of [...pending]) if (t.ms === ms) { pending.delete(id); t.fn(); }
    },
    /** Run only the oldest pending timer armed with `ms`. */
    fireOldest(ms: number) {
      const found = [...pending].find(([, t]) => t.ms === ms);
      if (found) { pending.delete(found[0]); found[1].fn(); }
    },
  };
}

const flush = () => new Promise(resolve => setImmediate(resolve));

test('the interpretation deadline is one 90 s constant', () => {
  assert.equal(INTERPRET_TIMEOUT_MS, 90_000);
});

test('an interpretation that never answers times out at the deadline and aborts the request', async () => {
  const timers = fakeTimers();
  const seen: AbortSignal[] = [];
  const handle = startInterpret(signal => { seen.push(signal); return new Promise<string>(() => undefined); }, timers);
  assert.deepEqual(timers.delays(), [INTERPRET_TIMEOUT_MS]);
  timers.fire(INTERPRET_TIMEOUT_MS);
  assert.deepEqual(await handle.promise, { status: 'timeout' });
  assert.equal(seen[0]?.aborted, true);
});

test('Cancel resolves as cancelled, aborts the request and disarms the deadline', async () => {
  const timers = fakeTimers();
  const seen: AbortSignal[] = [];
  const handle = startInterpret(signal => {
    seen.push(signal);
    return new Promise<string>((_, reject) => signal.addEventListener('abort', () => reject(new ApiRequestError({ status: 0, code: 'aborted', message: 'Request cancelled' }))));
  }, timers);
  handle.cancel();
  assert.deepEqual(await handle.promise, { status: 'cancelled' });
  assert.equal(seen[0]?.aborted, true);
  assert.deepEqual(timers.delays(), []);
});

test('a result clears the deadline; a server error is reported as is', async () => {
  const timers = fakeTimers();
  const ok = startInterpret(async () => 'parsed', timers);
  assert.deepEqual(await ok.promise, { status: 'ok', value: 'parsed' });
  assert.deepEqual(timers.delays(), []);
  ok.cancel(); // after settling: no effect
  assert.deepEqual(await ok.promise, { status: 'ok', value: 'parsed' });

  const failing = startInterpret(async () => { throw new ApiRequestError({ status: 503, code: 'upstream_unavailable', message: 'Request parser model is unavailable' }); }, timers);
  const outcome = await failing.promise;
  assert.equal(outcome.status, 'error');
  assert.equal(outcome.status === 'error' && outcome.error.code, 'upstream_unavailable');
  assert.deepEqual(timers.delays(), []);
});

// Shape captured in-process (investigation s3-slow-ai 3b): a running plan step, endedAt and durationMs null.
const runningStep = (patch: Partial<Step> = {}): Step => ({
  seq: 1, type: 'plan', iteration: 1, agent: 'planner', actor: 'llm', status: 'running',
  startedAt: '2026-11-15T22:49:17.801Z', endedAt: null, durationMs: null,
  summary: { en: 'Running: plan.', fr: 'En cours : plan.' }, model: null, usage: null,
  toolCalls: [], factIds: [], evidenceIds: [], ...patch,
} as Step);

const run = (patch: Partial<Run> = {}): Run => ({
  status: 'running', createdAt: '2026-11-15T22:49:16.000Z', updatedAt: '2026-11-15T22:49:17.801Z',
  usage: { llmCalls: 0, toolCalls: 0, durationMs: 2.86 }, steps: [runningStep()], ...patch,
} as Run);

const at = (iso: string) => Date.parse(iso);

test('a running step counts from its start; a finished step keeps its recorded duration', () => {
  const now = at('2026-11-15T22:49:29.801Z');
  assert.equal(stepElapsedMs(runningStep(), run(), now), 12_000);
  assert.equal(stepElapsedMs(runningStep({ status: 'done', durationMs: 9400 }), run(), now), 9400);
  assert.equal(stepElapsedMs(runningStep({ status: 'failed', durationMs: 120 }), run(), now), 120);
});

test('a client clock behind the server never gives a negative or earlier time', () => {
  const behind = at('2026-11-15T22:49:00.000Z');
  assert.equal(serverNowMs(run(), behind), at('2026-11-15T22:49:17.801Z'));
  assert.equal(stepElapsedMs(runningStep(), run(), behind), 0);
});

test('the whole run counts from the request while active, and shows its total once finished', () => {
  const now = at('2026-11-15T22:49:46.000Z');
  assert.equal(runElapsedMs(run(), now), 30_000);
  assert.equal(runElapsedMs(run({ status: 'succeeded', usage: { inputTokens: 0, outputTokens: 0, llmCalls: 3, toolCalls: 2, durationMs: 2243.8 } }), now), 2243.8);
  assert.equal(workerElapsedMs(run({ steps: [] }), now), null);
  assert.equal(workerElapsedMs(run(), now), at('2026-11-15T22:49:46.000Z') - at('2026-11-15T22:49:17.801Z'));
});

test('the over-target note is only for a running analysis past the target', () => {
  const started = at('2026-11-15T22:49:17.801Z');
  assert.equal(pastRunTarget(run(), started + 90_000, 90_000), false);
  assert.equal(pastRunTarget(run(), started + 90_001, 90_000), true);
  assert.equal(pastRunTarget(run({ status: 'succeeded' }), started + 120_000, 90_000), false);
  assert.equal(pastRunTarget(run({ status: 'waiting_input' }), started + 120_000, 90_000), false);
  assert.equal(pastRunTarget(run({ steps: [] }), started + 120_000, 90_000), false);
});

test('the server placeholder summary of a running step is recognised exactly', () => {
  assert.equal(isRunningPlaceholder(runningStep()), true);
  assert.equal(isRunningPlaceholder(runningStep({ summary: { en: 'Plan ready.', fr: 'Plan prêt.' } })), false);
  assert.equal(isRunningPlaceholder(runningStep({ type: 'write' })), false);
});

const polledRun = (status: Run['status'] = 'running'): Run => ({
  runId: 'run_1', status, steps: [], facts: {}, evidence: {}, createdAt: '2026-11-15T22:49:16.000Z', updatedAt: '2026-11-15T22:49:17.000Z',
  usage: { llmCalls: 0, toolCalls: 0, durationMs: 0 },
} as unknown as Run);

test('a poll that never answers becomes a lost connection with backoff, then recovers', async () => {
  const timers = fakeTimers();
  const views: RunPollerView[] = [];
  const signals: AbortSignal[] = [];
  let call = 0;
  const poller = createRunPoller({
    fetchRun: (_since, signal) => {
      call += 1;
      signals.push(signal);
      if (call === 2) return new Promise<Run>(() => undefined); // hangs and ignores the abort
      return Promise.resolve(polledRun());
    },
    onChange: view => views.push(view),
    ...timers,
  });
  poller.start();
  await flush();
  assert.equal(views.at(-1)?.run?.status, 'running');
  assert.deepEqual(timers.delays(), [1000]);
  timers.fire(1000); // second poll: hangs
  await flush();
  assert.deepEqual(timers.delays(), [POLL_TIMEOUT_MS]);
  timers.fire(POLL_TIMEOUT_MS);
  await flush();
  const lost = views.at(-1)!;
  assert.equal(lost.pollError?.code, 'network');
  assert.equal(lost.run?.status, 'running', 'the previous payload stays visible');
  assert.equal(signals[1]!.aborted, true);
  assert.deepEqual(timers.delays(), [2000], 'retry with backoff (nextPollDelay running, 1 failure)');
  timers.fire(2000);
  await flush();
  assert.equal(views.at(-1)?.pollError, null);
  poller.stop();
});

test('stop() during a pending poll reports nothing, and a superseded poll never times out', async () => {
  const timers = fakeTimers();
  const views: RunPollerView[] = [];
  const poller = createRunPoller({
    fetchRun: () => new Promise<Run>(() => undefined),
    onChange: view => views.push(view),
    ...timers,
  });
  poller.start();
  await flush();
  poller.stop();
  timers.fire(POLL_TIMEOUT_MS);
  await flush();
  assert.deepEqual(views, []);

  const timers2 = fakeTimers();
  const views2: RunPollerView[] = [];
  const poller2 = createRunPoller({
    fetchRun: () => new Promise<Run>(() => undefined), // both polls hang and ignore the abort
    onChange: view => views2.push(view),
    ...timers2,
  });
  poller2.start();
  await flush();
  poller2.visibilityChanged(); // shown again: a new full fetch supersedes the first one
  await flush();
  assert.deepEqual(timers2.delays(), [POLL_TIMEOUT_MS, POLL_TIMEOUT_MS]);
  timers2.fireOldest(POLL_TIMEOUT_MS); // the superseded poll's deadline
  await flush();
  assert.equal(views2.length, 0, 'a superseded poll stays silent');
  timers2.fireOldest(POLL_TIMEOUT_MS); // the current poll's deadline
  await flush();
  assert.equal(views2.at(-1)?.error?.code, 'network', 'no payload yet, so the first-read error is shown');
  poller2.stop();
});
