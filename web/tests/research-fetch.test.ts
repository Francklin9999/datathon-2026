/** Research routes go through the client's fetch: fixture adapter, in-flight limit, session header, error mapping. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiRequestError } from '../src/api/errors';
import { createFixtureFetch } from '../src/api/fixtures';
import { getApiClient, researchFetch } from '../src/api/index';
import { API_MAX_IN_FLIGHT } from '../src/api/limit';
import { createResearchFetch, researchJson } from '../src/api/research';
import { ensureSessionId } from '../src/lib/session';

const SESSION = 's_00000000-0000-4000-8000-000000000001';

function reply(status: number, body: string, headers: Record<string, string> = {}): typeof fetch {
  return async () => new Response(body, { status, headers: { 'Content-Type': 'application/json', ...headers } });
}

test('research fetch prefixes the base URL and sends the session header', async () => {
  const seen: { url: string; init: RequestInit | undefined }[] = [];
  const research = createResearchFetch({
    baseUrl: 'http://api.test/v1', getSessionId: () => SESSION,
    fetchImpl: async (input, init) => { seen.push({ url: String(input), init }); return new Response('{}'); },
  });
  await research('/intelligence/gleif-golden/delta/X', { method: 'POST' });
  assert.equal(seen[0]?.url, 'http://api.test/v1/intelligence/gleif-golden/delta/X');
  assert.equal(seen[0]?.init?.method, 'POST');
  assert.equal((seen[0]?.init?.headers as Record<string, string>)['X-Aplomb-Session'], SESSION);
});

test('in fixture mode research routes get the adapter’s typed 503, never the live API', async () => {
  const research = createResearchFetch({ baseUrl: 'http://fixture.local/v1', getSessionId: () => SESSION, fetchImpl: createFixtureFetch() });
  const path = '/intelligence/source-capabilities';
  const response = await research(path);
  assert.equal(response.status, 503);
  const error = await researchJson(response, path).catch((e: unknown) => e);
  assert.ok(error instanceof ApiRequestError);
  assert.equal(error.code, 'upstream_unavailable');
  assert.equal(error.status, 503);
});

test('researchJson keeps the server error code instead of reporting a network failure', async () => {
  const body = JSON.stringify({ error: { code: 'rate_limited', message: 'Slow down', requestId: 'req_9' } });
  const response = await reply(429, body, { 'Retry-After': '2' })('x');
  const error = await researchJson(response, '/intelligence/source-capabilities').catch((e: unknown) => e);
  assert.ok(error instanceof ApiRequestError);
  assert.equal(error.code, 'rate_limited');
  assert.equal(error.status, 429);
  assert.equal(error.requestId, 'req_9');
  assert.equal(error.retryAfterMs, 2000);
});

test('researchJson reports a non-JSON gateway page as invalid_response, and returns OK bodies', async () => {
  const gateway = await researchJson(await reply(502, '<html>Bad gateway</html>', { 'X-Request-Id': 'req_gw' })('x'), '/p').catch((e: unknown) => e);
  assert.ok(gateway instanceof ApiRequestError);
  assert.equal(gateway.code, 'invalid_response');
  assert.equal(gateway.status, 502);
  assert.equal(gateway.requestId, 'req_gw');
  const plain = await researchJson(await reply(500, JSON.stringify({ detail: 'x' }))('x'), '/p').catch((e: unknown) => e);
  assert.ok(plain instanceof ApiRequestError);
  assert.equal(plain.code, 'invalid_response');
  assert.deepEqual(await researchJson(await reply(200, '{"families":[]}')('x'), '/p'), { families: [] });
});

test('typed and research calls share one in-flight limit', async () => {
  ensureSessionId();
  const original = globalThis.fetch;
  let inFlight = 0;
  let peak = 0;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    inFlight += 1; peak = Math.max(peak, inFlight);
    await new Promise(resolve => setTimeout(resolve, 10));
    inFlight -= 1;
    const health = String(input).endsWith('/health');
    return new Response(JSON.stringify(health ? { status: 'ok', time: new Date().toISOString() } : {}), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
  try {
    const client = getApiClient();
    await Promise.all([
      ...Array.from({ length: 3 }, () => client.health()),
      ...Array.from({ length: 3 }, () => researchFetch('/intelligence/source-capabilities')),
    ]);
  } finally { globalThis.fetch = original; }
  assert.equal(peak, API_MAX_IN_FLIGHT);
});
