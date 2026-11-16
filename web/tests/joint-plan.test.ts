import assert from 'node:assert/strict';
import test from 'node:test';
import { CASHFLOW_DESCRIPTION_MAX, parseJointCashflows } from '../src/lib/jointPlan';

test('joint-plan cash flows keep an optional description so the backend can flag duplicate withdrawals', () => {
  assert.deepEqual(parseJointCashflows(''), []);
  assert.deepEqual(parseJointCashflows('  2027-06-01   -20   Rent  \n\n2027-07-01 150'), [
    { date: '2027-06-01', amount: -20, origin: 'user', description: 'Rent' },
    { date: '2027-07-01', amount: 150, origin: 'user' },
  ]);
  assert.deepEqual(parseJointCashflows('2027-06-01 -20 Summer   school fees'), [
    { date: '2027-06-01', amount: -20, origin: 'user', description: 'Summer school fees' },
  ]);
  assert.deepEqual(parseJointCashflows(`2027-06-01 -1 ${'x'.repeat(CASHFLOW_DESCRIPTION_MAX)}`)?.[0]?.description?.length, CASHFLOW_DESCRIPTION_MAX);
  for (const input of ['2027-06-01', '2027/06/01 10', '2027-06-01 ten', '2027-06-01 Infinity', '2027-06-01 NaN rent',
    `2027-06-01 -1 ${'x'.repeat(CASHFLOW_DESCRIPTION_MAX + 1)}`]) assert.equal(parseJointCashflows(input), null, input);
});
