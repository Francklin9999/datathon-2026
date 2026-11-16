import assert from 'node:assert/strict';
import test from 'node:test';
import { createResearchFetch } from '../src/api/research';

test('13F comparison sends its strategy and window as JSON with the session', async () => {
  let received: { url: string; init: RequestInit | undefined } | undefined;
  const research = createResearchFetch({
    baseUrl: 'http://api.test/v1', getSessionId: () => 'session',
    fetchImpl: async (url, init) => { received = { url: String(url), init }; return new Response('{}'); },
  });
  const body = { filingId: 'filing-1', strategy: { kind: 'rebalance', trigger: 'calendar' }, window: { code: '1y' } };
  await research('/profiles/p1/strategies/compare-13f', { method: 'POST', body });
  assert.equal(received?.url, 'http://api.test/v1/profiles/p1/strategies/compare-13f');
  assert.equal(received?.init?.method, 'POST');
  assert.deepEqual(JSON.parse(String(received?.init?.body)), body);
  const headers = received?.init?.headers as Record<string, string>;
  assert.equal(headers['Content-Type'], 'application/json');
  assert.equal(headers['X-Aplomb-Session'], 'session');
});
