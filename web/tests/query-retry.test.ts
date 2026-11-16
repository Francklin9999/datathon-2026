/** Read retries in useQuery: transient failures and 429 rate_limited, honouring Retry-After. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiRequestError } from '../src/api/errors';
import { readRetryDelay } from '../src/state/useQuery';

const error = (status: number, code: ApiRequestError['code'], retryAfterMs: number | null = null) =>
  new ApiRequestError({ status, code, message: code, retryAfterMs });

test('transient read failures are retried twice with the fixed delays', () => {
  for (const failure of [error(0, 'network'), error(502, 'internal'), error(503, 'upstream_unavailable'), error(504, 'internal')]) {
    assert.equal(readRetryDelay(failure, 0), 800);
    assert.equal(readRetryDelay(failure, 1), 2000);
    assert.equal(readRetryDelay(failure, 2), null);
  }
});

test('a 429 read is retried and waits at least its Retry-After', () => {
  assert.equal(readRetryDelay(error(429, 'rate_limited'), 0), 800);
  assert.equal(readRetryDelay(error(429, 'rate_limited', 3000), 0), 3000);
  assert.equal(readRetryDelay(error(429, 'rate_limited', 1000), 1), 2000);
  assert.equal(readRetryDelay(error(429, 'rate_limited', 3000), 2), null, 'retries are bounded');
  assert.equal(readRetryDelay(error(429, 'rate_limited', 60_000), 0), null, 'a long server wait shows the error instead');
});

test('other errors are not retried', () => {
  for (const failure of [error(404, 'not_found'), error(422, 'validation_error'), error(409, 'conflict'), error(500, 'internal')]) {
    assert.equal(readRetryDelay(failure, 0), null);
  }
});
