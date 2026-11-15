import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { Profile } from '../src/contracts/types';
import { validateContract } from '../src/contracts/validate';
import { formFromProfile, formPositions, toCreateRequest, validateProfileForm } from '../src/lib/profileForm';
import { blendFinalTargets, parseFinalTargets } from '../src/lib/targetAllocation';

const fixtures = JSON.parse(readFileSync(new URL('../../contracts/fixtures/profiles.json', import.meta.url), 'utf8'));
const close = (a: number, b: number) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);

test('complete targets support additions, full exits, capitalization, and reject invalid financing weights', () => {
  assert.deepEqual(parseFinalTargets('  spy  15.25\n\n xbb.to 84.75\n'), [
    { ticker: 'SPY', weightPct: 15.25 }, { ticker: 'XBB.TO', weightPct: 84.75 },
  ]);
  assert.deepEqual(parseFinalTargets('SPY 0\nQQQ 100'), [
    { ticker: 'SPY', weightPct: 0 }, { ticker: 'QQQ', weightPct: 100 },
  ]);
  for (const input of ['', 'SPY', 'SPY 100 extra', 'SPY NaN', 'SPY Infinity', 'SPY -1\nQQQ 101',
    'SPY 51\nQQQ 50', 'spy 50\nSPY 50', 'SPY;DROP 100']) assert.throws(() => parseFinalTargets(input));
  const tooMany = Array.from({ length: 41 }, (_, i) => `T${i} ${i === 0 ? 100 : 0}`).join('\n');
  assert.throws(() => parseFinalTargets(tooMany), /invalid_target_sum/);
});

test('target slider blends the final allocation deterministically without treating a point as a compatibility bound', () => {
  const before = [{ ticker: 'A', weightPct: 60 }, { ticker: 'B', weightPct: 40 }];
  const target = [{ ticker: 'A', weightPct: 25 }, { ticker: 'C', weightPct: 75 }];
  assert.deepEqual(blendFinalTargets(before, target, 0), before);
  assert.deepEqual(blendFinalTargets(before, target, 100), target);
  assert.deepEqual(blendFinalTargets(before, target, 50), [
    { ticker: 'A', weightPct: 42.5 }, { ticker: 'B', weightPct: 20 }, { ticker: 'C', weightPct: 37.5 },
  ]);
  for (const point of [0, 12.5, 33, 50, 100]) {
    const result = blendFinalTargets(before, target, point);
    close(result.reduce((sum, position) => sum + position.weightPct, 0), 100);
    assert.ok(result.every(position => position.weightPct > 0));
    assert.deepEqual(result, blendFinalTargets(before, target, point));
  }
  for (const invalid of [-1, 101, NaN, Infinity]) assert.throws(() => blendFinalTargets(before, target, invalid), /invalid_progress/);
  assert.throws(() => blendFinalTargets([{ ticker: 'A', weightPct: 80 }], target, 0), /invalid_weight_sum/);
  // Invalid endpoints must be rejected even when interpolation would hide the issue.
  assert.throws(() => blendFinalTargets(before, [{ ticker: 'A', weightPct: -10 }, { ticker: 'B', weightPct: 110 }], 0), /invalid_positions/);
  assert.throws(() => blendFinalTargets(before, [{ ticker: 'A', weightPct: 50 }, { ticker: 'A', weightPct: 50 }], 0), /invalid_positions/);
  assert.throws(() => blendFinalTargets(before, [{ ticker: 'A', weightPct: NaN }], 0), /invalid_positions/);
  assert.throws(() => blendFinalTargets(before, [{ ticker: 'A', weightPct: 70 }], 0), /invalid_weight_sum/);
  const fortyBefore = Array.from({ length: 40 }, (_, i) => ({ ticker: `A${i}`, weightPct: 2.5 }));
  assert.throws(() => blendFinalTargets(fortyBefore, [{ ticker: 'B', weightPct: 100 }], 50), /too_many_blended_holdings/);
});

test('position quantity provenance survives unchanged edit and is removed for a replacement ticker', () => {
  const profile = structuredClone(fixtures.items[0]) as Profile;
  profile.portfolio.positions = [
    { ticker: 'SPY', weightPct: 60, quantity: 7, quantityAsOf: '2026-11-12', quantityOrigin: 'imported', quantitySource: 'Custodian statement' },
    { ticker: 'XBB.TO', weightPct: 40 },
  ];
  const form = formFromProfile(profile);
  const initial = toCreateRequest(form, null);
  validateContract('CreateProfileRequest', initial);
  assert.deepEqual(initial.portfolio!.positions, profile.portfolio.positions);
  form.positions[0]!.weightPct = '55';
  form.positions[1]!.weightPct = '45';
  assert.deepEqual(formPositions(form)[0], { ...profile.portfolio.positions[0], weightPct: 55 });
  form.positions[0]!.ticker = ' qqq ';
  assert.deepEqual(formPositions(form)[0], { ticker: 'QQQ', weightPct: 55 });
  assert.equal(profile.portfolio.positions[0]!.quantity, 7);
});

test('country, dates, source provenance and independent objectives round-trip without sharing state', () => {
  const profile = structuredClone(fixtures.items[0]) as Profile;
  profile.reportingCurrency = 'EUR';
  profile.investorContext = {
    country: 'JP', investorType: 'university endowment', language: 'fr', riskCapacity: 'low',
    riskCapacityOrigin: 'imported', riskToleranceOrigin: 'user', inputOrigins: { reportingCurrency: 'imported' },
    horizons: [{ name: 'Grant', startDate: '2027-01-01', deadline: '2030-06-01', origin: 'assumption', sourceUrl: 'https://example.org/horizon' }],
    objectives: [{ name: 'Tuition', horizonYears: 3, priority: 1, targetAmount: 10000, origin: 'imported', sourceUrl: 'https://example.org/goal' },
      { name: 'Later', horizonYears: 10, priority: 2, origin: 'user' }],
    requirements: [{ name: 'Expense', kind: 'spending', amount: 1200, dueDate: '2027-06-01', frequency: 'annual', origin: 'imported', sourceUrl: 'https://example.org/expense' }],
    targetAllocations: [{ dimension: 'position', key: 'SPY', targetPct: 25, origin: 'user' }],
    rebalancing: { frequency: 'quarterly', driftThresholdPct: 5, origin: 'assumption' },
  };
  const form = formFromProfile(profile);
  assert.deepEqual(validateProfileForm(form), []);
  const saved = toCreateRequest(form, null);
  validateContract('CreateProfileRequest', saved);
  assert.equal(saved.reportingCurrency, 'EUR');
  assert.deepEqual(saved.investorContext, profile.investorContext);
  form.investorContext!.requirements![0]!.amount = 1500;
  assert.equal(profile.investorContext.requirements![0]!.amount, 1200);
  assert.equal(saved.investorContext!.requirements![0]!.amount, 1200);
  form.investorContext!.horizons![0]!.endDate = '2026-01-01';
  assert.ok(validateProfileForm(form).some(issue => issue.field === 'investorContext'));
});
