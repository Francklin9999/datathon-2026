import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createLimitedFetch } from '../src/api/limit';

test('limited fetch: never more than max in flight, first come first served', async () => {
  let inFlight = 0;
  let peak = 0;
  const order: string[] = [];
  const inner = (async (input: RequestInfo | URL) => {
    inFlight += 1; peak = Math.max(peak, inFlight); order.push(String(input));
    await new Promise(r => setTimeout(r, 10));
    inFlight -= 1;
    return new Response('ok');
  }) as typeof fetch;
  const limited = createLimitedFetch(inner, 2);
  await Promise.all(['a', 'b', 'c', 'd', 'e'].map(u => limited(u)));
  assert.equal(peak, 2);
  assert.deepEqual(order, ['a', 'b', 'c', 'd', 'e']);
});

test('limited fetch: a request aborted before it starts never reaches the network', async () => {
  const sent: string[] = [];
  const inner = (async (input: RequestInfo | URL) => { sent.push(String(input)); return new Response('ok'); }) as typeof fetch;
  const limited = createLimitedFetch(inner, 4);
  const controller = new AbortController();
  const dropped = limited('dropped', { signal: controller.signal });
  controller.abort();
  await assert.rejects(dropped);
  await limited('kept');
  assert.deepEqual(sent, ['kept']);
});
