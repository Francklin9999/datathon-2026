import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { flags } from '../src/stack.mjs';

test('deployed feature keys match the shared contract catalog', () => {
  const schema = JSON.parse(readFileSync(new URL('../../contracts/generated/schema.json', import.meta.url)));
  assert.deepEqual([...flags].sort(), [...schema.$defs.FeatureFlag.enum].sort());
});
