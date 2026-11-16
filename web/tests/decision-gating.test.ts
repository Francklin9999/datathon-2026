/**
 * Decision Desk pre-submit gating (QA t4 a/b, T5.2): funding feasibility mirrors backend
 * quant/funding.py, unsupported tickers are blocked only with a loaded universe and on-demand off,
 * and a refusal received from the instant check gates "Analyze evidence".
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiRequestError } from '../src/api/errors';
import { previewRefusal, unlistedMoveTicker, validateMoveForm, type MoveForm, type MoveUniverse } from '../src/lib/move';

const form = (patch: Partial<MoveForm> = {}): MoveForm => ({ ticker: 'TSLA', sizePct: 10, fundingMode: 'auto', fromTickers: [], ...patch });
const noCash = [{ ticker: 'SPY', weightPct: 60 }, { ticker: 'XBB.TO', weightPct: 40 }];
const someCash = [{ ticker: 'SPY', weightPct: 55 }, { ticker: 'XBB.TO', weightPct: 40 }, { ticker: 'CASH.CAD', weightPct: 5 }];
const fields = (patch: Partial<MoveForm>, positions: { ticker: string; weightPct: number }[]) =>
  validateMoveForm(form(patch), 0, { positions }).map(i => i.field);

test('from_cash with no cash is refused before the check (backend insufficient_cash)', () => {
  const issues = validateMoveForm(form({ fundingMode: 'from_cash' }), 0, { positions: noCash });
  assert.deepEqual(issues.map(i => i.field), ['fundingMode']);
  assert.match(issues[0]!.message.en, /holds no cash/);
  assert.match(issues[0]!.message.fr, /aucune liquidité/);
});

test('from_cash boundaries match the server: 5 of 5 passes, 5.1 does not', () => {
  assert.deepEqual(fields({ fundingMode: 'from_cash', sizePct: 5 }, someCash), []);
  const issues = validateMoveForm(form({ fundingMode: 'from_cash', sizePct: 5.1 }), 0, { positions: someCash });
  assert.deepEqual(issues.map(i => i.field), ['fundingMode']);
  assert.equal(issues[0]!.message.en, 'Cash holdings total 5.0 points, less than the 5.1 points this move needs. Choose another funding mode or a smaller size.');
  assert.match(issues[0]!.message.fr, /5,0 points, moins que les 5,1 points/);
});

test('the target cash line does not fund itself', () => {
  assert.deepEqual(fields({ ticker: 'CASH.CAD', fundingMode: 'from_cash', sizePct: 1 }, someCash), ['fundingMode']);
});

test('auto, pro_rata and new_money are never blocked for funding', () => {
  assert.deepEqual(fields({ fundingMode: 'auto' }, noCash), []);
  assert.deepEqual(fields({ fundingMode: 'pro_rata' }, noCash), []);
  assert.deepEqual(fields({ fundingMode: 'new_money' }, noCash), []);
});

test('named holdings must cover the size (backend insufficient_donors)', () => {
  assert.deepEqual(fields({ fundingMode: 'from_holdings', fromTickers: ['XBB.TO'], sizePct: 41 }, noCash), ['fromTickers']);
  assert.deepEqual(fields({ fundingMode: 'from_holdings', fromTickers: ['XBB.TO'], sizePct: 40 }, noCash), []);
  // No donor named: only the existing message, never two for the same field.
  assert.deepEqual(fields({ fundingMode: 'from_holdings', fromTickers: [] }, noCash), ['fromTickers']);
});

test('without context, validation is unchanged', () => {
  assert.deepEqual(validateMoveForm(form({ fundingMode: 'from_cash' }), 0), []);
});

const universe = (onDemand: boolean): MoveUniverse => ({ assets: [{ ticker: 'TSLA' }, { ticker: 'SPY' }], total: 31, dataVersion: 'snap-x', onDemand });

test('an unsupported ticker is blocked only with a loaded universe and on-demand off', () => {
  const issues = validateMoveForm(form({ ticker: '7203.T' }), 0, { positions: [], universe: universe(false) });
  assert.deepEqual(issues.map(i => i.field), ['ticker']);
  assert.equal(issues[0]!.message.en, '7203.T is not one of the 31 supported instruments of snapshot snap-x. Choose one from the list.');
  assert.match(issues[0]!.message.fr, /ne fait pas partie des 31 instruments/);
  assert.deepEqual(validateMoveForm(form({ ticker: '7203.T' }), 0, { positions: [], universe: universe(true) }), []);
  assert.deepEqual(validateMoveForm(form({ ticker: '7203.T' }), 0, { positions: [], universe: null }), []);
});

test('listed, cash, held and empty tickers are not reported as unsupported', () => {
  const ctx = { positions: [{ ticker: 'OLD.X', weightPct: 100 }], universe: universe(false) };
  assert.deepEqual(validateMoveForm(form({ ticker: 'tsla' }), 0, ctx), []);
  assert.deepEqual(validateMoveForm(form({ ticker: 'CASH.USD' }), 0, ctx), []);
  assert.deepEqual(validateMoveForm(form({ ticker: 'OLD.X' }), 0, ctx), []);
  assert.deepEqual(validateMoveForm(form({ ticker: '' }), 0, ctx).map(i => i.message.en), ['Choose an asset.']);
  assert.equal(unlistedMoveTicker(form({ ticker: ' 7203.t ' }), ctx), '7203.T');
  assert.equal(unlistedMoveTicker(form({ ticker: '7203.T' }), { universe: { ...universe(false), assets: [] } }), null);
});

const reason = { en: 'Cash positions total 0.00 points, less than the 10 points needed.', fr: 'L’encaisse totalise 0,00 points, moins que les 10,0 points requis.' };

test('a received funding refusal names its field and keeps the bilingual reason', () => {
  const error = new ApiRequestError({ status: 422, code: 'validation_error', message: reason.en, details: { fields: ['move.funding'], code: 'insufficient_cash', reason } });
  assert.deepEqual(previewRefusal(error), { field: 'fundingMode', reason });
  const donors = new ApiRequestError({ status: 422, code: 'validation_error', message: 'x', details: { fields: ['move.funding.fromTickers'] } });
  assert.equal(previewRefusal(donors)?.field, 'fromTickers');
  const pydantic = new ApiRequestError({ status: 422, code: 'validation_error', message: 'Request validation failed', details: { fields: [{ path: 'body.move.sizePct', problem: 'x' }] } });
  assert.deepEqual(previewRefusal(pydantic), { field: 'sizePct', reason: null });
});

test('an unknown ticker refusal points at the ticker', () => {
  const error = new ApiRequestError({ status: 404, code: 'not_found', message: 'Unknown ticker 7203.T' });
  assert.deepEqual(previewRefusal(error), { field: 'ticker', reason: null });
});

test('transient failures never gate Analyze', () => {
  for (const code of ['network', 'upstream_unavailable', 'rate_limited', 'insufficient_data', 'internal', 'aborted'] as const) {
    assert.equal(previewRefusal(new ApiRequestError({ status: code === 'network' ? 0 : 503, code, message: 'x' })), null, code);
  }
  assert.equal(previewRefusal(null), null);
});
