/**
 * Client wiring that waited on web/src/api/client.ts: account valuations (api-core#17), the run
 * trace's budgets on Agents & System (api-core#6), drafts kept across a conflict reload
 * (web-pages-core#9) and the capabilities note (web-markets-risk-planning#12).
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { Profile, Run } from '../src/contracts/types';
import { createApiClient } from '../src/api/client';
import { ApiRequestError } from '../src/api/errors';
import { createFixtureFetch } from '../src/api/fixtures';
import { RUN_LIMITS, budgetLimits } from '../src/lib/system';
import { valuationLimitationText, valuationTotals } from '../src/lib/portfolioEditors';
import { DRAFT_TTL_MS, dropDraft, mergeDraftRows, peekDraft, stashDraft } from '../src/lib/draftStore';

const SESSION = 's_00000000-0000-4000-8000-000000000001';
interface Captured { url: string; init: RequestInit | undefined }

function clientFor(status: number, body: unknown, captured: Captured[] = []) {
  const fetchImpl: typeof fetch = async (input, init) => {
    captured.push({ url: String(input), init });
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', 'X-Request-Id': 'req_test' } });
  };
  return createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl });
}
const header = (init: RequestInit | undefined, name: string) => (init?.headers as Record<string, string> | undefined)?.[name];
async function failure(promise: Promise<unknown>): Promise<ApiRequestError> {
  const error = await promise.catch((e: unknown) => e);
  assert.ok(error instanceof ApiRequestError, 'expected an ApiRequestError');
  return error;
}

const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8');
const run = JSON.parse(read('../../contracts/fixtures/run.decision.robert-tsla-25.json')) as Run;

// The body account_valuation_summary returns (backend/aplomb/profiles/service.py), two accounts.
const valuations = {
  profileId: 'p_custom', currency: 'CAD', combinedValue: 16000,
  accounts: [
    { accountId: 'acct_a', name: 'TFSA', modeledTradedValue: 1000, privateValue: 5000, combinedValue: 6000 },
    { accountId: 'acct_b', name: 'RRSP', modeledTradedValue: 10000, privateValue: 0, combinedValue: 10000 },
  ],
  limitations: ['Private values are user or imported estimates, converted at the receipt date; they are excluded from traded portfolio weights, returns and risk. Do not also include the same assets in the traded portfolio.'],
};

test('accountValuations reads the session-owned route and validates the rows', async () => {
  const captured: Captured[] = [];
  const result = await clientFor(200, valuations, captured).accountValuations('p_custom');
  assert.equal(captured[0]?.url, 'http://api.test/v1/profiles/p_custom/account-valuations');
  assert.equal(captured[0]?.init?.method, 'GET');
  assert.equal(header(captured[0]?.init, 'X-Aplomb-Session'), SESSION);
  assert.equal(result.combinedValue, 16000);
  assert.deepEqual(result.accounts.map(row => row.accountId), ['acct_a', 'acct_b']);
  // The no-account "Primary" row has a null account id.
  const primary = await clientFor(200, { ...valuations, accounts: [{ accountId: null, name: 'Primary', modeledTradedValue: 5, privateValue: 0, combinedValue: 5 }] }).accountValuations('p_custom');
  assert.equal(primary.accounts[0]?.accountId, null);

  const bad = await failure(clientFor(200, { ...valuations, accounts: [{ accountId: 'a', name: 'x', modeledTradedValue: 'NaN', privateValue: 0, combinedValue: 0 }] }).accountValuations('p_custom'));
  assert.equal(bad.code, 'invalid_response');
  assert.equal(bad.requestId, 'req_test');
  const missing = await failure(clientFor(404, { error: { code: 'not_found', message: 'Not found', requestId: 'req_x' } }).accountValuations('p_other'));
  assert.equal(missing.code, 'not_found');
});

test('runTrace returns the run id and budgets, and rejects a malformed budget', async () => {
  const captured: Captured[] = [];
  const body = {
    runId: run.runId, kind: 'decision', status: 'succeeded', steps: [], claimAudit: [],
    budgets: [
      { name: 'llm_calls', used: 4, limit: 7 }, { name: 'research_calls', used: 2, limit: 5 },
      { name: 'revisions', used: 0, limit: 1 }, { name: 'rewrites', used: 0, limit: 1 },
      { name: 'scenarios', used: 1, limit: 6 }, { name: 'wall_clock_ms', used: 41000, limit: 120000 },
    ],
  };
  const trace = await clientFor(200, body, captured).runTrace(run.runId);
  assert.equal(captured[0]?.url, `http://api.test/v1/runs/${encodeURIComponent(run.runId)}/trace`);
  assert.equal(header(captured[0]?.init, 'X-Aplomb-Session'), SESSION);
  assert.deepEqual(Object.keys(trace).sort(), ['budgets', 'runId']);
  assert.equal(trace.budgets.length, 6);
  const bad = await failure(clientFor(200, { ...body, budgets: [{ name: 'llm_calls', used: 1 }] }).runTrace(run.runId));
  assert.equal(bad.code, 'invalid_response');
});

test('fixture mode answers both routes with a typed 503, so the pages fall back', async () => {
  const client = createApiClient({ baseUrl: 'http://fixture.local/v1', getSessionId: () => SESSION, fetchImpl: createFixtureFetch() });
  for (const promise of [client.runTrace(run.runId), client.accountValuations('robert')]) {
    const error = await failure(promise);
    assert.equal(error.status, 503);
    assert.equal(error.code, 'upstream_unavailable');
  }
});

test('budget limits come from the trace only when it is this run’s and complete', () => {
  const trace = { runId: 'run_1', budgets: [
    { name: 'llm_calls', limit: 7 }, { name: 'research_calls', limit: 5 }, { name: 'revisions', limit: 1 },
    { name: 'wall_clock_ms', limit: 120_000 }, { name: 'rewrites', limit: 1 },
  ] };
  assert.deepEqual(budgetLimits(trace, 'run_1'), {
    source: 'trace', llmCalls: 7, researchToolCalls: 5, reviseLoops: 1, wallClockTargetMs: 90_000, wallClockHardMs: 120_000,
  });
  const defaults = { source: 'default', ...RUN_LIMITS };
  assert.deepEqual(budgetLimits(null, 'run_1'), defaults);
  assert.deepEqual(budgetLimits(trace, 'run_2'), defaults, 'another run’s trace is never used');
  assert.deepEqual(budgetLimits({ runId: 'run_1', budgets: trace.budgets.filter(b => b.name !== 'revisions') }, 'run_1'), defaults,
    'a partial trace does not mix sources in one column');
  // A deployment may lower the hard limit below the 90 s target (settings.py: run_hard_seconds le=180).
  const short = budgetLimits({ runId: 'run_1', budgets: trace.budgets.map(b => (b.name === 'wall_clock_ms' ? { ...b, limit: 60_000 } : b)) }, 'run_1');
  assert.equal(short.wallClockTargetMs, 60_000);
  assert.equal(short.wallClockHardMs, 60_000);
});

test('Agents & System reads the limits through runTrace, not the hard-coded constants', () => {
  const page = read('../src/features/system/AgentsSystemPage.tsx');
  assert.match(page, /getApiClient\(\)\.runTrace\(run\.runId, signal\)/);
  assert.match(page, /budgetLimits\(trace\.data, run\.runId\)/);
  assert.doesNotMatch(page, /RUN_LIMITS\./);
});

const profile = {
  profileId: 'p_custom', reportingCurrency: 'CAD', portfolio: { totalValue: 999 },
  accounts: [
    { accountId: 'acct_a', name: 'TFSA', portfolio: { totalValue: 1000 }, privateAssets: [{ valuation: { conversion: { reportingValue: 5000 } } }] },
    { accountId: 'acct_b', name: 'RRSP', portfolio: { totalValue: 10000 }, privateAssets: [] },
  ],
} as unknown as Profile;

test('private-asset totals use the server summary, and the profile sums only as a fallback', () => {
  const server = valuationTotals(profile, valuations);
  assert.equal(server.source, 'server');
  assert.deepEqual([server.traded, server.privateValue, server.combined], [11000, 5000, 16000]);
  assert.equal(server.rows.length, 2);
  assert.equal(server.limitations.length, 1);

  const local = valuationTotals(profile, null);
  assert.equal(local.source, 'local');
  assert.deepEqual([local.traded, local.privateValue, local.combined], [11000, 5000, 16000]);
  assert.deepEqual(local.rows, []);
  assert.equal(valuationTotals(profile, { ...valuations, profileId: 'p_other' }).source, 'local', 'another profile’s summary is ignored');
  // Without accounts the traded value is the profile portfolio, and the server's "Primary" row is not listed per account.
  const bare = { ...profile, accounts: [] } as unknown as Profile;
  assert.equal(valuationTotals(bare, null).combined, 999);
  assert.deepEqual(valuationTotals(bare, { ...valuations, accounts: [{ accountId: null, name: 'Primary', modeledTradedValue: 999, privateValue: 0, combinedValue: 999 }], combinedValue: 999 }).rows, []);
});

/** The literals of the `limitations` list in account_valuation_summary, joined as Python joins them. */
function backendValuationLimitation(): string {
  const source = read('../../backend/aplomb/profiles/service.py');
  const block = /"limitations": \[((?:\s*"[^"]*")+)\]/.exec(source.slice(source.indexOf('def account_valuation_summary')));
  assert.ok(block?.[1], 'account_valuation_summary no longer returns a literal limitations list');
  return [...block[1].matchAll(/"([^"]*)"/g)].map(m => m[1]).join('');
}

test('the known valuation limitation matches the backend sentence and has a French text', () => {
  const sentence = backendValuationLimitation();
  const text = valuationLimitationText(sentence);
  assert.ok(text, 'the backend limitation changed: update KNOWN_VALUATION_LIMITATIONS');
  assert.equal(text.en, sentence);
  assert.notEqual(text.fr, sentence);
  assert.equal(valuationLimitationText('Some new sentence.'), null);
});

test('the Source availability note this build translates is the one the backend sends', () => {
  const backend = read('../../backend/aplomb/intelligence/capabilities.py');
  const note = /'note': '([^']+)'/.exec(backend)?.[1];
  assert.ok(note, 'capabilities() no longer returns a literal note');
  assert.ok(read('../src/features/markets/SourceAvailability.tsx').includes(`'${note}'`), 'update CAPABILITY_NOTE and its French');
});

test('a stashed draft is restored only on a newer profile version and only once used', () => {
  const key = 'test|p_custom';
  const now = 1_000_000;
  stashDraft(key, 3, { name: 'typed' }, now);
  assert.equal(peekDraft(key, 3, now + 10), null, 'same version: the editor did not remount, nothing to restore');
  assert.deepEqual(peekDraft(key, 4, now + 10), { name: 'typed' });
  assert.deepEqual(peekDraft(key, 4, now + 20), { name: 'typed' }, 'peeking does not consume (state initializers may run twice)');
  dropDraft(key);
  assert.equal(peekDraft(key, 4, now + 30), null);

  stashDraft(key, 3, { name: 'old' }, now);
  assert.equal(peekDraft(key, 4, now + DRAFT_TTL_MS + 1), null, 'an old stash is not restored');
  assert.equal(peekDraft(key, 5, now + 1), null, 'and it was removed');
});

test('per-holding drafts keep typed rows that still exist and start new rows from the profile', () => {
  const fresh = { AAPL: { quantity: '' }, MSFT: { quantity: '3' } };
  const draft = { AAPL: { quantity: '10' }, TSLA: { quantity: '2' } };
  assert.deepEqual(mergeDraftRows(fresh, draft), { AAPL: { quantity: '10' }, MSFT: { quantity: '3' } });
  assert.equal(mergeDraftRows(fresh, null), fresh);
});

test('every keyed portfolio editor stashes its draft before the conflict reload and restores it', () => {
  for (const file of ['Accounts.tsx', 'AccountEditor.tsx', 'PositionQuantities.tsx', 'PrivateAssets.tsx', 'ConditionalPolicies.tsx', 'CustomPolicies.tsx']) {
    const text = read(`../src/features/portfolio/${file}`);
    assert.match(text, /<ProfileWriteError error=\{error\} onReload=/, `${file} reloads without keeping its input`);
    assert.match(text, /useRestoredDraft</, `${file} does not read a stashed draft back`);
    assert.match(text, /<DraftRestoredNote ?\/>/, `${file} restores input without saying so`);
    assert.match(text, /dropDraft\(draftKey\)/, `${file} keeps a stashed draft after a successful save`);
  }
});
