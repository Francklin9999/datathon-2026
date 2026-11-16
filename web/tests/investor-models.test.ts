import assert from 'node:assert/strict';
import test from 'node:test';
import { parseModelInput } from '../src/api/investorModels';

test('model imports are bounded JSON objects and cannot execute user text', () => {
  assert.deepEqual(parseModelInput('{"names":["market"],"returns":[]}'), { names: ['market'], returns: [] });
  assert.throws(() => parseModelInput('[]'));
  assert.throws(() => parseModelInput('({ code: process.exit() })'));
  assert.throws(() => parseModelInput(JSON.stringify({ text: 'é'.repeat(120_001) })));
});
