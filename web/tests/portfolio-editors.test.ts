/** Portfolio editors: no wasted goal reads, profile_creator gating (WEB-07) and conflict reload (portfolio.md). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { goalFundingKey } from '../src/lib/portfolioEditors';

const objective = { name: 'House', targetAmount: 100000 };

test('goal funding is requested only for profiles with stated objectives', () => {
  assert.equal(goalFundingKey('s|robert|v1|d', {}), null);
  assert.equal(goalFundingKey('s|robert|v1|d', { investorContext: null }), null);
  assert.equal(goalFundingKey('s|robert|v1|d', { investorContext: { objectives: [] } as never }), null);
  assert.equal(goalFundingKey(null, { investorContext: { objectives: [objective] } as never }), null);
  assert.equal(goalFundingKey('s|robert|v1|d', { investorContext: { objectives: [objective] } as never }), 'goals|s|robert|v1|d');
});

// Every client call below goes to a handler that starts with feature("profile_creator") (backend/aplomb/api/app.py).
const GATED_WRITES: Record<string, string[]> = {
  'Accounts.tsx': ['selectAccount', 'createAccount', 'refreshAccount', 'transferAccount'],
  'AccountEditor.tsx': ['editAccount'],
  'PositionQuantities.tsx': ['updatePortfolio'],
  'PrivateAssets.tsx': ['savePrivateAsset'],
  'ExposureLimits.tsx': ['addExposureLimit'],
  'ConditionalPolicies.tsx': ['addConditionRule', 'removeConditionRule'],
  'CustomPolicies.tsx': ['addCustomRule'],
};

for (const [file, calls] of Object.entries(GATED_WRITES)) {
  test(`${file} gates its profile_creator writes and offers a reload on conflict`, () => {
    const text = readFileSync(new URL(`../src/features/portfolio/${file}`, import.meta.url), 'utf8');
    for (const call of calls) assert.match(text, new RegExp(`getApiClient\\(\\)\\.${call}\\(`), `${file} no longer calls ${call}`);
    assert.match(text, /feature\('profile_creator'\)/, `${file} must hide its writes when profile_creator is off`);
    assert.match(text, /<ProfileWriteError /, `${file} must render write errors with ProfileWriteError`);
    assert.doesNotMatch(text, /<ErrorState /, `${file} shows a write error without the conflict reload`);
  });
}
