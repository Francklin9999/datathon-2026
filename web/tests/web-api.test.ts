/** T13 API client and development fixture adapter (web/SPEC.md §2–§5, WEB-03/WEB-09). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { createApiClient } from '../src/api/client';
import { ApiRequestError } from '../src/api/errors';
import { createFixtureFetch } from '../src/api/fixtures';
import { isSessionId, newSessionId } from '../src/lib/session';

const SESSION = 's_00000000-0000-4000-8000-000000000001';

interface Captured { url: string; init: RequestInit | undefined }

function fakeFetch(status: number, body: unknown, captured: Captured[], headers: Record<string, string> = {}): typeof fetch {
  return async (input, init) => {
    captured.push({ url: String(input), init });
    return new Response(body === null ? null : JSON.stringify(body), {
      status, headers: { 'Content-Type': 'application/json', 'X-Request-Id': 'req_test', ...headers },
    });
  };
}

const header = (init: RequestInit | undefined, name: string) => (init?.headers as Record<string, string> | undefined)?.[name];
const apiError = (code: string) => ({ error: { code, message: 'x', requestId: 'req_1' } });

test('session IDs are s_ + UUIDv4', () => {
  const id = newSessionId();
  assert.ok(isSessionId(id), id);
  assert.ok(!isSessionId('s_not-a-uuid'));
});

test('protected calls carry the session header; Content-Type only with a body', async () => {
  const captured: Captured[] = [];
  const profiles = JSON.parse(readFileSync(new URL('../../contracts/fixtures/profiles.json', import.meta.url), 'utf8'));
  const client = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl: fakeFetch(200, profiles, captured) });
  const response = await client.profiles();
  assert.equal(response.items[0]?.profileId, 'robert');
  assert.equal(captured[0]?.url, 'http://api.test/v1/profiles');
  assert.equal(header(captured[0]?.init, 'X-Aplomb-Session'), SESSION);
  assert.equal(header(captured[0]?.init, 'Content-Type'), undefined);
});

test('/health and /meta are anonymous', async () => {
  const captured: Captured[] = [];
  const client = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl: fakeFetch(200, { status: 'ok', time: '2026-11-14T20:25:00Z' }, captured) });
  await client.health();
  assert.equal(header(captured[0]?.init, 'X-Aplomb-Session'), undefined);
});

test('POST bodies are JSON; window, since and lang go in the query string', async () => {
  const captured: Captured[] = [];
  const client = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl: fakeFetch(503, apiError('upstream_unavailable'), captured) });
  await assert.rejects(client.check({ profileId: 'robert', move: null, window: { code: 'full' } }));
  assert.equal(header(captured[0]?.init, 'Content-Type'), 'application/json');
  assert.deepEqual(JSON.parse(String(captured[0]?.init?.body)), { profileId: 'robert', move: null, window: { code: 'full' } });
  await assert.rejects(client.overview('robert', '1y'));
  assert.equal(captured[1]?.url, 'http://api.test/v1/profiles/robert/overview?window=1y');
  await assert.rejects(client.run('run_x', null));
  assert.equal(captured[2]?.url, 'http://api.test/v1/runs/run_x');
  await assert.rejects(client.run('run_x', 3));
  assert.equal(captured[3]?.url, 'http://api.test/v1/runs/run_x?since=3');
  await assert.rejects(client.brief('robert', 'fr'));
  assert.equal(captured[4]?.url, 'http://api.test/v1/profiles/robert/brief?lang=fr');
});

test('ApiError bodies become typed errors with code, status, request id and Retry-After', async () => {
  const client = createApiClient({
    baseUrl: 'http://api.test/v1', getSessionId: () => SESSION,
    fetchImpl: fakeFetch(429, { error: { code: 'rate_limited', message: 'slow down', requestId: 'req_9' } }, [], { 'Retry-After': '3' }),
  });
  const error = await client.profiles().catch((e: unknown) => e);
  assert.ok(error instanceof ApiRequestError);
  assert.equal(error.code, 'rate_limited');
  assert.equal(error.status, 429);
  assert.equal(error.requestId, 'req_9');
  assert.equal(error.retryAfterMs, 3000);
});

test('a 200 body that breaks the contract is rejected, never passed to the UI', async () => {
  const client = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl: fakeFetch(200, { items: [{ profileId: 42 }] }, []) });
  const error = await client.profiles().catch((e: unknown) => e);
  assert.ok(error instanceof ApiRequestError);
  assert.equal(error.code, 'invalid_response');
});

test('network failures and missing sessions are typed', async () => {
  const offline = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl: async () => { throw new TypeError('fetch failed'); } });
  const networkError = await offline.profiles().catch((e: unknown) => e);
  assert.ok(networkError instanceof ApiRequestError);
  assert.equal(networkError.code, 'network');
  const noSession = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => null, fetchImpl: fakeFetch(200, {}, []) });
  const sessionError = await noSession.profiles().catch((e: unknown) => e);
  assert.ok(sessionError instanceof ApiRequestError);
  assert.equal(sessionError.code, 'invalid_response');
});

test('POST /runs: 202 queued and 200 cached both validate; Idempotency-Key forwarded', async () => {
  const captured: Captured[] = [];
  const queued = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl: fakeFetch(202, { runId: 'run_01JCQ000000000000000000009', status: 'queued', pollAfterMs: 1000 }, captured) });
  const created = await queued.createRun({ kind: 'portfolio_brief', profileId: 'robert', lang: 'en' }, 'key-1');
  assert.equal(created.status, 'queued');
  assert.equal(header(captured[0]?.init, 'Idempotency-Key'), 'key-1');
  const cached = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl: fakeFetch(200, { runId: 'run_01JCQ000000000000000000009', status: 'succeeded' }, []) });
  assert.equal((await cached.createRun({ kind: 'portfolio_brief', profileId: 'robert', lang: 'en' })).status, 'succeeded');
});

test('DELETE 204 resolves without a body', async () => {
  const client = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl: async () => new Response(null, { status: 204 }) });
  await client.deleteProfile('p_abcdefghij');
});

const fixtureClient = () => createApiClient({ baseUrl: 'http://fixture.local/v1', getSessionId: () => SESSION, fetchImpl: createFixtureFetch() });

test('fixture adapter serves only what contract fixtures contain', async () => {
  const client = fixtureClient();
  const meta = await client.meta();
  assert.equal(meta.environment, 'local');
  assert.deepEqual(Object.entries(meta.features).filter(([, on]) => on).map(([flag]) => flag), ['bilingual'], 'no P1 capability is claimed');
  assert.deepEqual((await client.profiles()).items.map(p => p.profileId), ['robert', 'amira', 'mateo']);
  const run = await client.run('run_01JCQ000000000000000000001', null);
  assert.equal(run.flags.fixture, true);
  const fact = await client.fact(run.runId, 'F-004');
  assert.ok(fact.usedBy.sentenceIds.includes('S-01'));
  const missingFact = await client.fact(run.runId, 'F-999').catch((e: unknown) => e);
  assert.ok(missingFact instanceof ApiRequestError);
  assert.equal(missingFact.code, 'not_found');
  assert.equal((await client.runs({})).items.length, 1);
  assert.equal((await client.profile('robert')).profileId, 'robert');
  const missingProfile = await client.profile('p_abcdefghij').catch((e: unknown) => e);
  assert.ok(missingProfile instanceof ApiRequestError);
  assert.equal(missingProfile.code, 'not_found');
});

test('fixture /meta reports the contract version of the generated schema', async () => {
  const schema = JSON.parse(readFileSync(new URL('../../contracts/generated/schema.json', import.meta.url), 'utf8'));
  assert.equal((await fixtureClient().meta()).contractVersion, schema['x-contract-version']);
});

test('fixture adapter never invents data for endpoints without fixtures', async () => {
  const client = fixtureClient();
  const calls: (() => Promise<unknown>)[] = [
    () => client.overview('robert', 'full'),
    () => client.check({ profileId: 'robert', move: null }),
    () => client.datasets(),
    () => client.brief('robert', 'en'),
    () => client.archivedProfiles(),
  ];
  for (const call of calls) {
    const error = await call().catch((e: unknown) => e);
    assert.ok(error instanceof ApiRequestError);
    assert.equal(error.code, 'upstream_unavailable');
    assert.equal(error.status, 503);
  }
});
