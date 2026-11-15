import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { Profile } from '../src/contracts/types';
import { validateContract, ContractValidationError } from '../src/contracts/validate';
import { formFromProfile, toCreateRequest, validateProfileForm } from '../src/lib/profileForm';

const fixtures = JSON.parse(readFileSync(new URL('../../contracts/fixtures/profiles.json', import.meta.url), 'utf8'));

test('multiple objectives and fractional horizons survive profile copy/edit without sharing mutable context', () => {
  const profile = structuredClone(fixtures.items[0]) as Profile;
  profile.investorContext = { country: 'GB', investorType: 'endowment', objectives: [
    { name: 'Liquidity', horizonYears: .25, priority: 1 }, { name: 'Capital', horizonYears: 30, priority: 2 },
  ] };
  const form = formFromProfile(profile);
  const body = toCreateRequest(form, null);
  validateContract('CreateProfileRequest', body);
  assert.deepEqual(body.investorContext, profile.investorContext);
  assert.equal(validateProfileForm(form).length, 0);
  form.investorContext!.objectives![0]!.name = 'Changed copy';
  assert.equal(profile.investorContext!.objectives![0]!.name, 'Liquidity');
  assert.ok(validateProfileForm({ ...form, investorContext: { country: 'BAD' } }).some(x => x.field === 'investorContext'));
  assert.throws(() => validateContract('InvestorContext', { objectives: Array(21).fill({ name: 'Goal', horizonYears: 1, priority: 1 }) }), ContractValidationError);
});

test('goal statements remain inputs and do not overwrite deterministic rule thresholds', () => {
  const profile = structuredClone(fixtures.items[0]) as Profile;
  const before = structuredClone(profile.rules);
  const form = formFromProfile(profile);
  form.investorContext = { objectives: [{ name: 'Aggressive target', horizonYears: 1, priority: 1, targetAmount: 1000000 }] };
  assert.deepEqual(profile.rules, before);
  assert.equal(toCreateRequest(form, null).rules, null);
});
