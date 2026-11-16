/** Shared helpers: API contract compatibility, failure classification, supported-universe checks. */
import assert from 'node:assert/strict';
import test from 'node:test';
import schema from '../../contracts/generated/schema.json' with { type: 'json' };
import { ApiRequestError } from '../src/api/errors';
import {
  FEATURE_MIN_CONTRACT, NEEDS_NEWER_API, WEB_CONTRACT_VERSION, apiCompatibility, apiSupports, apiVersionLine,
  compareContractVersions, parseContractVersion,
} from '../src/lib/apiCompat';
import { MAX_FAILED_ATTEMPTS, bilingualReason, describeFailure, shouldOfferRetry } from '../src/lib/failure';
import {
  isCashTicker, isSupportedTicker, normalizeTicker, onDemandTickerHint, supportedCountLabel, supportedUniverseHint,
  universeMarkets, unsupportedTickerMessage, unsupportedTickers, unsupportedTickersMessage,
} from '../src/lib/universe';

const meta = (contractVersion: string) => ({ contractVersion });
const err = (init: ConstructorParameters<typeof ApiRequestError>[0]) => new ApiRequestError(init);

test('apiCompat: the web contract version is the generated schema version', () => {
  assert.equal(WEB_CONTRACT_VERSION, schema['x-contract-version']);
  assert.ok(parseContractVersion(WEB_CONTRACT_VERSION));
  // The site must itself serve every feature it gates.
  for (const minimum of Object.values(FEATURE_MIN_CONTRACT)) assert.equal(apiSupports(meta(WEB_CONTRACT_VERSION), minimum), true);
});

test('apiCompat: semantic comparison, not string comparison', () => {
  assert.deepEqual(parseContractVersion('1.5.0'), { major: 1, minor: 5, patch: 0 });
  assert.deepEqual(parseContractVersion('v2.10.3-rc.1'), { major: 2, minor: 10, patch: 3 });
  assert.equal(parseContractVersion('1.5'), null);
  assert.equal(parseContractVersion(''), null);
  assert.equal(parseContractVersion(null), null);
  const v = (s: string) => parseContractVersion(s)!;
  assert.ok(compareContractVersions(v('1.10.0'), v('1.9.9')) > 0);
  assert.ok(compareContractVersions(v('1.5.0'), v('1.5.1')) < 0);
  assert.equal(compareContractVersions(v('1.5.0'), v('1.5.0')), 0);
});

test('apiCompat: strategies need contract 1.5.0; the deployed 1.4.0 API is older', () => {
  const min = FEATURE_MIN_CONTRACT.strategies;
  assert.equal(min, '1.5.0');
  assert.equal(apiCompatibility(meta('1.4.0'), min), 'older');
  assert.equal(apiSupports(meta('1.4.0'), min), false);
  assert.equal(apiCompatibility(meta('1.5.0'), min), 'supported');
  assert.equal(apiCompatibility(meta('1.10.0'), min), 'supported');
  assert.equal(apiCompatibility(meta('1.5.2'), min), 'supported');
  assert.equal(apiCompatibility(meta('2.0.0'), min), 'incompatible');
  assert.equal(apiCompatibility(meta('0.9.0'), min), 'incompatible');
  assert.equal(apiCompatibility(meta('garbage'), min), 'incompatible');
  assert.equal(apiCompatibility(null, min), 'unknown');
  assert.equal(apiSupports(undefined, min), false);
});

test('apiCompat: notice strings are bilingual and name both versions', () => {
  assert.ok(NEEDS_NEWER_API.en && NEEDS_NEWER_API.fr);
  const line = apiVersionLine('1.5.0', '1.4.0');
  for (const text of [line.en, line.fr]) { assert.match(text, /1\.5\.0/); assert.match(text, /1\.4\.0/); }
  assert.match(apiVersionLine('1.5.0', null).en, /reports —/);
});

test('failure: retry is offered for the first try and two retries, then stops', () => {
  assert.equal(MAX_FAILED_ATTEMPTS, 3);
  assert.deepEqual([0, 1, 2, 3, 4].map(shouldOfferRetry), [true, true, true, false, false]);
});

test('failure: not_found from an older API is outdated-api; from a current API it is not', () => {
  const e = err({ status: 404, code: 'not_found', message: 'Resource not found', requestId: 'req_1' });
  const old = describeFailure(e, { olderApi: true });
  assert.equal(old.kind, 'outdated-api');
  assert.deepEqual(old.title, NEEDS_NEWER_API);
  assert.equal(old.requestId, 'req_1');
  assert.equal(old.retry, false);
  assert.equal(old.technical, 'Resource not found');
  const current = describeFailure(e);
  assert.equal(current.kind, 'other');
  assert.equal(current.retry, false);
});

test('failure: validation and insufficient data ask for an edit and prefer the bilingual reason', () => {
  const reason = { en: 'Cash positions total 0.00 points, less than the 10 points needed.', fr: 'L’encaisse totalise 0,00 points, moins que les 10,0 points requis.' };
  const withReason = describeFailure(err({ status: 422, code: 'validation_error', message: reason.en, details: { fields: ['move.funding'], reason } }));
  assert.equal(withReason.kind, 'edit');
  assert.deepEqual(withReason.message, reason);
  assert.deepEqual(withReason.reason, reason);
  assert.equal(withReason.retry, false);
  const plain = describeFailure(err({ status: 422, code: 'validation_error', message: 'Unknown tickers: 7203.T', details: { unknown: ['7203.T'] } }));
  assert.equal(plain.kind, 'edit');
  assert.equal(plain.reason, null);
  assert.notEqual(plain.message.fr, plain.message.en);
  assert.equal(plain.technical, 'Unknown tickers: 7203.T');
  assert.equal(describeFailure(err({ status: 422, code: 'insufficient_data', message: 'x' })).kind, 'edit');
  // Even an older API's validation error is an edit, not a version notice.
  assert.equal(describeFailure(err({ status: 422, code: 'validation_error', message: 'x' }), { olderApi: true }).kind, 'edit');
});

test('failure: network, 5xx, upstream_unavailable and rate_limited are retryable until the third failure', () => {
  const cases = [
    err({ status: 0, code: 'network', message: 'Failed to fetch' }),
    err({ status: 503, code: 'upstream_unavailable', message: 'Model gateway down', requestId: 'req_2' }),
    err({ status: 500, code: 'internal', message: 'boom' }),
    err({ status: 429, code: 'rate_limited', message: 'slow down', retryAfterMs: 2500 }),
    err({ status: 502, code: 'invalid_response', message: 'not json' }),
  ];
  for (const e of cases) {
    const first = describeFailure(e);
    assert.equal(first.kind, 'retryable', e.code);
    assert.equal(first.retry, true, e.code);
    assert.equal(describeFailure(e, { failures: 2 }).retry, true, e.code);
    const third = describeFailure(e, { failures: 3 });
    assert.equal(third.retry, false, e.code);
    assert.match(third.message.en, /Still unavailable after several tries/);
    assert.match(third.message.fr, /Toujours indisponible/);
  }
  assert.match(describeFailure(cases[3]!).message.en, /about 3 s/);
  assert.match(describeFailure(cases[1]!, { failures: 3 }).message.en, /request ID/);
  assert.doesNotMatch(describeFailure(cases[0]!, { failures: 3 }).message.en, /request ID/);
});

test('failure: conflict, forbidden, disabled, invalid shape, aborts and page bugs are other', () => {
  for (const code of ['conflict', 'forbidden_action', 'feature_disabled'] as const) {
    const d = describeFailure(err({ status: 409, code, message: 'm' }));
    assert.equal(d.kind, 'other', code);
    assert.equal(d.retry, false);
    assert.ok(d.title.en && d.title.fr && d.message.en && d.message.fr);
  }
  assert.equal(describeFailure(err({ status: 200, code: 'invalid_response', message: 'm' })).kind, 'other');
  assert.equal(describeFailure(err({ status: 0, code: 'aborted', message: 'Request cancelled' })).kind, 'other');
  const bug = describeFailure(new TypeError('x is undefined'));
  assert.equal(bug.kind, 'other');
  assert.equal(bug.requestId, null);
  assert.equal(bug.technical, 'x is undefined');
});

test('failure: bilingual reason requires both non-empty strings', () => {
  assert.deepEqual(bilingualReason({ en: 'a', fr: 'b', extra: 1 }), { en: 'a', fr: 'b' });
  assert.equal(bilingualReason({ en: 'a' }), null);
  assert.equal(bilingualReason({ en: 'a', fr: ' ' }), null);
  assert.equal(bilingualReason('a'), null);
  assert.equal(bilingualReason(null), null);
});

const UNIVERSE = [
  { ticker: 'AAPL', market: 'NASDAQ' },
  { ticker: 'XBB.TO', market: 'TSX' },
  { ticker: 'SPY', market: 'NYSE Arca' },
  { ticker: 'RY.TO', market: 'TSX' },
];

test('universe: supported tickers are listed ones and cash pseudo-assets, case-insensitive', () => {
  assert.equal(normalizeTicker(' xbb.to '), 'XBB.TO');
  assert.equal(isSupportedTicker(UNIVERSE, 'aapl'), true);
  assert.equal(isSupportedTicker(UNIVERSE, ' XBB.TO'), true);
  assert.equal(isSupportedTicker(UNIVERSE, '7203.T'), false);
  assert.equal(isSupportedTicker(UNIVERSE, ''), false);
  assert.equal(isSupportedTicker(UNIVERSE, 'CASH.CAD'), true);
  assert.equal(isCashTicker('cash.usd'), true);
  assert.equal(isCashTicker('CASH.CA'), false);
});

test('universe: unsupported tickers are normalized, de-duplicated and never block on an unloaded universe', () => {
  assert.deepEqual(unsupportedTickers(['AAPL', '7203.t', '', 'CASH.CAD', '7203.T', 'toyota'], UNIVERSE), ['7203.T', 'TOYOTA']);
  assert.deepEqual(unsupportedTickers(['7203.T'], []), []);
  assert.deepEqual(unsupportedTickers([], UNIVERSE), []);
});

test('universe: markets come from the data, unique and sorted', () => {
  assert.deepEqual(universeMarkets(UNIVERSE), ['NASDAQ', 'NYSE Arca', 'TSX']);
  assert.deepEqual(universeMarkets([]), []);
});

test('universe: messages name the ticker, the count and the snapshot in both languages', () => {
  const one = unsupportedTickerMessage('7203.t', 31, 'snap-20261115-globalfx');
  for (const text of [one.en, one.fr]) {
    assert.match(text, /7203\.T/);
    assert.match(text, /31/);
    assert.match(text, /snap-20261115-globalfx/);
  }
  assert.notEqual(one.en, one.fr);
  const many = unsupportedTickersMessage(['7203.T', 'toyota'], 'snap-x');
  assert.match(many.en, /7203\.T, TOYOTA/);
  assert.match(many.fr, /instantané snap-x/);
  assert.match(onDemandTickerHint('nflx', 'snap-x').fr, /NFLX/);
  assert.deepEqual(supportedCountLabel(31), { en: '31 supported instruments', fr: '31 instruments pris en charge' });
  assert.deepEqual(supportedCountLabel(1), { en: '1 supported instrument', fr: '1 instrument pris en charge' });
  assert.equal(supportedUniverseHint(31, 'snap-x', ['NASDAQ', 'TSX']).en, 'Supported: the 31 instruments of snapshot snap-x (NASDAQ, TSX).');
  assert.equal(supportedUniverseHint(31, 'snap-x', []).fr, 'Pris en charge : les 31 instruments de l’instantané snap-x.');
});
