/**
 * Contract 1.6.0 additions read by the web: the compare view's rule differences
 * (datastore-profiles-rules-strategies#4) and every holding's 1-year return (web-pages-core#1).
 * Both are optional, so an API before 1.6.0 (the deployed 1.4.0 one) keeps working.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { createApiClient } from '../src/api/client';
import { ApiRequestError } from '../src/api/errors';
import type { RuleCheck, RuleDifference } from '../src/contracts/types';
import { validateContract } from '../src/contracts/validate';
import { holdingReturnsOf } from '../src/lib/overviewReturns';
import { differenceRows } from '../src/lib/ruleDifferences';

function check(ruleId: string, over: Partial<RuleCheck> = {}): RuleCheck {
  return {
    ruleId, code: 'R1', status: 'pass', value: 10, threshold: 25, unit: 'pct', comparator: '<=', headroom: 15,
    worst: null, valueFactId: null, thresholdFactId: null, detail: { en: 'd', fr: 'd' }, neeReason: null, evidenceIds: [],
    ...over,
  };
}

function diff(ruleId: string, reason: RuleDifference['reason'], over: Partial<RuleDifference> = {}): RuleDifference {
  return { ruleId, reason, statusA: 'pass', statusB: 'pass', thresholdA: 25, thresholdB: 25, valueA: 10, valueB: 10, ...over };
}

test('differences: older API without the key shows no section', () => {
  assert.equal(differenceRows(undefined, [], [], 'Robert', 'Amira'), null);
  assert.deepEqual(differenceRows([diff('sim.only', 'same')], [check('sim.only')], [check('sim.only')], 'Robert', 'Amira'), []);
});

test('differences: rows name the rule, both profiles and the figures; status changes first', () => {
  const a = [check('cap.position', { status: 'conflict', value: 32.5, threshold: 15 }), check('cap.growth_assets'),
    check('limit.volatility', { value: 9, threshold: 12 }), check('flag.rate_cycle', { status: 'info', comparator: 'none', threshold: null, value: -0.02 })];
  const b = [check('cap.position', { status: 'tension', value: 25, threshold: 25 }), check('floor.diversifiers', { comparator: '>=' }),
    check('limit.volatility', { value: 10.5, threshold: 12 }), check('flag.rate_cycle', { status: 'info', comparator: 'none', threshold: null, value: 1.5 })];
  const rows = differenceRows([
    diff('limit.volatility', 'portfolio_differs', { thresholdA: 12, thresholdB: 12, valueA: 9, valueB: 10.5 }),
    diff('cap.position', 'threshold_differs', { statusA: 'conflict', statusB: 'tension', thresholdA: 15, thresholdB: 25, valueA: 32.5, valueB: 25 }),
    diff('flag.rate_cycle', 'portfolio_differs', { statusA: 'info', statusB: 'info', thresholdA: null, thresholdB: null, valueA: -0.02, valueB: 1.5 }),
    diff('cap.growth_assets', 'rule_only_in_a', { statusB: null, thresholdB: null, valueB: null }),
    diff('floor.diversifiers', 'rule_only_in_b', { statusA: null, thresholdA: null, valueA: null }),
    diff('sim.only', 'same'),
  ], a, b, 'Robert', 'Amira');
  assert.ok(rows);
  assert.deepEqual(rows.map(r => r.ruleId), ['cap.position', 'cap.growth_assets', 'floor.diversifiers', 'limit.volatility', 'flag.rate_cycle']);
  const [position, onlyA, onlyB, volatility, rateCycle] = rows;
  assert.equal(position!.name?.en, 'Single-asset limit');
  assert.equal(position!.sentence.en, 'Different thresholds: Robert 15.0%, Amira 25.0%. Measured value: Robert 32.5%, Amira 25.0%.');
  assert.match(position!.sentence.fr, /^Seuils différents : Robert 15,0 ?%, Amira 25,0 ?%\. Valeur mesurée : Robert 32,5 ?%, Amira 25,0 ?%\.$/u);
  assert.equal(onlyA!.sentence.en, 'Only Robert’s plan has this rule.');
  assert.equal(onlyB!.sentence.fr, 'Seul le plan du profil Amira comporte cette règle.');
  assert.equal(volatility!.sentence.en, 'Same threshold (12.0%), different portfolios: Robert 9.0%, Amira 10.5%.');
  // An informational return is signed with two decimals, as in the rule table.
  assert.match(rateCycle!.sentence.en, /^Different portfolios: Robert [−-]0\.02%, Amira \+1\.50%\.$/u);
  for (const row of rows) assert.ok(row.sentence.en && row.sentence.fr);
});

test('differences: unknown rule IDs keep the ID; equal values with another status say so', () => {
  const rows = differenceRows([diff('custom.xyz', 'portfolio_differs', { statusA: 'pass', statusB: 'nee' })],
    [check('custom.xyz')], [check('custom.xyz', { status: 'nee' })], 'A', 'B');
  assert.equal(rows![0]!.name, null);
  assert.equal(rows![0]!.sentence.en, 'Same threshold and measured value, different status.');
});

test('BatchCheckResponse validates with and without differences (1.6.0 additive)', () => {
  validateContract('BatchCheckResponse', { results: [] });
  validateContract('BatchCheckResponse', { results: [], differences: [diff('cap.position', 'threshold_differs')] });
  assert.throws(() => validateContract('BatchCheckResponse', { results: [], differences: [diff('cap.position', 'bogus' as never)] }));
});

test('holding returns: every holding from 1.6.0, the top five before', () => {
  const concentration = { hhi: 0.1, effectiveN: 10, topPositions: [
    { ticker: 'XBB.TO', name: 'Bonds', weightPct: 30, marketValue: 1, return1yPct: 4.2, assetClass: 'etf_bond' as const },
  ] };
  const old = holdingReturnsOf({ concentration });
  assert.deepEqual([...old], [['XBB.TO', { pct: 4.2, factId: null }]]);
  assert.equal(old.get('SPY'), undefined);  // the table shows "—" for it
  const current = holdingReturnsOf({ concentration, holdingReturns: [
    { ticker: 'XBB.TO', return1yPct: 4.2, return1yFactId: 'F-1' },
    { ticker: 'SPY', return1yPct: 12.5, return1yFactId: 'F-2' },
    { ticker: 'CASH.CAD', return1yPct: null, return1yFactId: null },
  ] });
  assert.deepEqual(current.get('SPY'), { pct: 12.5, factId: 'F-2' });
  assert.deepEqual(current.get('CASH.CAD'), { pct: null, factId: null });
});

// research#7 -----------------------------------------------------------------------------------------

function clientReturning(status: number, body: unknown, seen: string[]) {
  return createApiClient({
    baseUrl: 'http://api.test/v1', getSessionId: () => 's_00000000-0000-4000-8000-000000000001',
    fetchImpl: async input => { seen.push(String(input)); return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }); },
  });
}

test('research client methods: paths, queries and the snake_case connection rows of a 1.4.0 API', async () => {
  const seen: string[] = [];
  const rows = { providers: [
    // 1.4.0 chain row: no signup_url and no credential_variable.
    { id: 'alchemy', credential_present: true, rights_confirmed: true, supported_operation: 'head', documentation_url: 'https://d' },
    { id: 'tiingo', signup_url: 'https://s', credential_variable: 'T', credential_present: false, rights_confirmed: true, supported_operation: 'x' },
  ] };
  const connections = await clientReturning(200, rows, seen).marketConnections();
  assert.equal(connections.providers[0]?.credential_present, true);
  const observation = { status: 'available', provider: 'finnhub', observation: { company: { ticker: 'AAPL' } }, source_url: 'https://f',
    source_sha256: 'a'.repeat(64), retrieved_at: '2026-11-15T00:00:00+00:00', limitations: ['x'] };
  await clientReturning(200, observation, seen).marketObservation('twelve-data', { symbol: 'AAPL', mic: 'XNGS' });
  await clientReturning(200, { ...observation, provider: 'tiingo', sources: [] }, seen).tiingoHistory('AAPL', { start: '2026-10-01', end: '2026-11-01' });
  assert.deepEqual(seen.slice(0, 3), [
    'http://api.test/v1/research/market-connections',
    'http://api.test/v1/research/market-provider/twelve-data?symbol=AAPL&mic=XNGS',
    'http://api.test/v1/research/tiingo/AAPL?start=2026-10-01&end=2026-11-01',
  ]);
  // A body off the contract is an invalid_response error, not a silently wrong panel.
  const bad = await clientReturning(200, { status: 'available', provider: 'x' }, seen).marketObservation('finnhub', { symbol: 'AAPL' }).catch((e: unknown) => e);
  assert.ok(bad instanceof ApiRequestError && bad.code === 'invalid_response');
});

test('regional research client method validates both answer kinds', async () => {
  const seen: string[] = [];
  const frame = { region: 'KR', identifier: '00126380', identifierType: 'OpenDART corporate code', provider: 'OpenDART', kind: 'financials',
    mic: null, currency: null, retrievedAt: '2026-11-15T00:00:00Z', availableAt: '2026-11-15T00:00:00Z', publicationAt: null,
    sourceUrl: 'https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json', availabilityBasis: 'capture', historicalReplayEligibleBeforeCapture: false,
    requestedStart: '2026-10-01', requestedEnd: '2026-11-01', fiscalYear: '2025', reportCode: '11011', statementType: 'CFS',
    prices: [], filings: [], company: null, financials: [], ownership: [] };
  const client = clientReturning(200, { ...frame, status: 'unavailable', reason: 'provider_credentials_or_usage_rights_not_configured' }, seen);
  const result = await client.regionalResearch({ region: 'KR', identifier: '00126380', start: '2026-10-01', end: '2026-11-01', kind: 'financials',
    report_code: '11011', statement_type: 'CFS', fiscal_year: '2025' });
  assert.equal(result.status, 'unavailable');
  assert.equal(seen[0], 'http://api.test/v1/intelligence/regional?region=KR&identifier=00126380&start=2026-10-01&end=2026-11-01&kind=financials&report_code=11011&statement_type=CFS&fiscal_year=2025');
});
