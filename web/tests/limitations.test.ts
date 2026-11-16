/** QA 4.5b: notes written for code are not shown as limitations; the reader-facing ones stay. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { splitLimitations } from '../src/lib/limitations';

test('the fact-ID notes the deployed API still sends move out of the visible limitations', () => {
  // The exact strings of API 1.4.0 (quant/candidates.py and quant/expanded_api.py before QA 4.5b).
  const focus = [
    'Local fact IDs must be remapped into the run ledger before claim creation.',
    'Goal figures are nominal scenarios from user assumptions, not forecasts.',
    'No model, independent review or recommendation has run.',
  ];
  assert.deepEqual(splitLimitations(focus), {
    shown: focus.slice(1),
    technical: [focus[0]],
  });
  const compare = ['Private appraisals, actual transactions, tax and costs are excluded; values are modeled.',
    'Local fact IDs are per portfolio; never combine their ledgers without remapping.'];
  assert.deepEqual(splitLimitations(compare).shown, [compare[0]]);
});

test('without a code note every limitation stays visible, in order', () => {
  const lines = ['Goal figures are nominal scenarios from user assumptions, not forecasts.', 'Facts are calculations only.'];
  assert.deepEqual(splitLimitations(lines), { shown: lines, technical: [] });
  assert.deepEqual(splitLimitations([]), { shown: [], technical: [] });
});
