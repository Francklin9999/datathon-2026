import assert from 'node:assert/strict';
import test from 'node:test';
import { gatePassportHref } from '../src/lib/replay';

test('replay gate passport links keep the run data version so Sources can flag drift (SRC-04)', () => {
  const href = gatePassportHref('prices_daily', 'snap-20261113-starter');
  assert.equal(href, '/sources/?datasetId=prices_daily&dataVersion=snap-20261113-starter');
  const params = new URLSearchParams(gatePassportHref('a&b', 'v 1/2').split('?')[1]);
  assert.equal(params.get('datasetId'), 'a&b');
  assert.equal(params.get('dataVersion'), 'v 1/2');
});
