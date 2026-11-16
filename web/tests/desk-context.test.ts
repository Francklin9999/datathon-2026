/** Decision Desk investigation context from a shared World link (web/src/lib/deskContext.ts). */
import assert from 'node:assert/strict';
import test from 'node:test';
import { deskContext, prefillTicker } from '../src/lib/deskContext';

const linked = { eventId: 'evt_a', ticker: 'CNQ.TO', sourceRunId: 'run_1' };
const saved = { eventId: 'evt_saved', ticker: 'XOM' };

test('a link for this persona is used and shown', () => {
  assert.deepEqual(deskContext(linked, 'p_robert', 'p_robert', null), { context: linked, shown: linked, foreign: false });
  assert.deepEqual(deskContext(linked, null, 'p_robert', saved), { context: linked, shown: linked, foreign: false });
});

test('a link for another persona is shown as foreign but never used', () => {
  assert.deepEqual(deskContext(linked, 'p_amira', 'p_robert', null), { context: null, shown: linked, foreign: true });
});

test('a restored run context of this persona wins over a foreign link', () => {
  assert.deepEqual(deskContext(linked, 'p_amira', 'p_robert', saved), { context: saved, shown: saved, foreign: false });
});

test('no context at all', () => {
  assert.deepEqual(deskContext(null, 'p_amira', 'p_robert', null), { context: null, shown: null, foreign: false });
});

test('a ?ticker= link pre-fills a plausible ticker only', () => {
  assert.equal(prefillTicker('aapl'), 'AAPL');
  assert.equal(prefillTicker(' CNQ.TO '), 'CNQ.TO');
  assert.equal(prefillTicker('BRK-B'), 'BRK-B');
  assert.equal(prefillTicker(null), '');
  assert.equal(prefillTicker(''), '');
  assert.equal(prefillTicker('<script>'), '');
  assert.equal(prefillTicker('A'.repeat(21)), '');
});
