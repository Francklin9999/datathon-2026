/** Saved strategies and their configuration (web/src/lib/strategies.ts). */
import assert from 'node:assert/strict';
import test from 'node:test';
import type { StrategyConfig } from '../src/contracts/types';
import { validateContract } from '../src/contracts/validate';
import { createApiClient } from '../src/api/client';
import { ApiRequestError } from '../src/api/errors';
import { WEB_CONTRACT_VERSION } from '../src/lib/apiCompat';
import {
  MAX_STRATEGIES, STRATEGY_KINDS, UNDO_DELETE_MS, automationState, configIssues, defaultConfig, describe, moveFocusFromExpiredUndo,
  newStrategy, readStrategies,
  removeStrategy, restoreStrategy, simulationRequest, strategiesCompatibility, strategiesUnavailable, strategyFailure, wireConfig,
  writeStrategies, type SavedStrategy,
} from '../src/lib/strategies';

const en = (t: { en: string }) => t.en;
const money = (n: number) => `${n} CAD`;
const bilingual = (t: { en: string; fr: string } | null | undefined, label: string) => {
  assert.ok(t && t.en.trim() && t.fr.trim(), `${label}: both languages`);
};

test('every default configuration is valid and accepted by the contract', () => {
  for (const kind of STRATEGY_KINDS) {
    const config = defaultConfig(kind);
    assert.deepEqual(configIssues(config), [], kind);
    validateContract('StrategySimulateRequest', { strategy: wireConfig(config), window: { code: 'full' } });
  }
});

test('the request carries only the fields of the chosen trigger', () => {
  const calendar = wireConfig({ kind: 'rebalance', trigger: 'calendar', frequency: 'monthly', bandPts: 7, costBps: 5 });
  assert.deepEqual(calendar, { kind: 'rebalance', trigger: 'calendar', frequency: 'monthly', costBps: 5 });
  const band = wireConfig({ kind: 'rebalance', trigger: 'band', frequency: 'monthly', bandPts: 7, costBps: 5 });
  assert.deepEqual(band, { kind: 'rebalance', trigger: 'band', bandPts: 7, costBps: 5 });
  const guard = wireConfig({ ...defaultConfig('risk_guard'), safeTicker: null } as StrategyConfig);
  assert.equal('safeTicker' in guard, false, 'no safe asset chosen: the server picks one');
});

test('form problems are reported before anything is sent', () => {
  assert.equal(configIssues({ kind: 'contribute', amount: 0, frequency: 'monthly', allocation: 'target' }).length, 1);
  assert.equal(configIssues({ kind: 'rebalance', trigger: 'band', bandPts: Number.NaN }).length, 1);
  const guard = configIssues({ kind: 'risk_guard', triggerDrawdownPct: 5, shiftPct: 50, reentryDrawdownPct: 5 });
  assert.match(guard[0]!.en, /below the trigger/);
  assert.equal(configIssues({ ...defaultConfig('rebalance'), costBps: 101 }).length, 1);
});

test('Home widget: saved invalid settings are reported, not left on "Simulating…"', () => {
  // An emptied field is saved as NaN, which JSON stores as null; readStrategies keeps the strategy.
  const store = new Map<string, string>();
  const strategy = newStrategy('contribute', [], en, 'st_x');
  writeStrategies('robert', [{ ...strategy, config: { ...strategy.config, amount: Number.NaN } as StrategyConfig }], (k, v) => { store.set(k, v); });
  const [saved] = readStrategies('robert', k => store.get(k) ?? null);
  assert.ok(saved);
  assert.equal(automationState(saved.config, false, false), 'invalid');
  const valid = defaultConfig('contribute');
  assert.equal(automationState(valid, false, false), 'pending');
  assert.equal(automationState(valid, true, false), 'next');
  assert.equal(automationState(valid, false, true), 'unavailable');
});

test('descriptions name what the automation does', () => {
  assert.equal(describe(defaultConfig('rebalance'), en, money), 'Rebalance, quarterly, 10 bps per trade');
  assert.equal(describe({ kind: 'rebalance', trigger: 'band', bandPts: 5 }, en, money), 'Rebalance past a 5-pt drift');
  assert.equal(describe(defaultConfig('contribute'), en, money), '500 CAD monthly, to the most underweight');
  assert.match(describe(defaultConfig('risk_guard'), en, money), /^At −8% from the peak, move 50% of growth to safety/);
});

test('saved strategies: at most three per profile, garbage dropped, names kept unique', () => {
  const store = new Map<string, string>();
  const read = (k: string) => store.get(k) ?? null;
  const write = (k: string, v: string) => { store.set(k, v); };
  const list: SavedStrategy[] = [];
  for (let i = 0; i < 5; i++) list.push(newStrategy('rebalance', list, en, `st_${i}`));
  assert.deepEqual(list.slice(0, 3).map(s => s.name), ['Rebalancing', 'Rebalancing 2', 'Rebalancing 3']);
  writeStrategies('robert', list, write);
  assert.equal(readStrategies('robert', read).length, MAX_STRATEGIES);
  assert.deepEqual(readStrategies('amira', read), [], 'each profile has its own list');
  store.set('strategies.v1.robert', '{"not":"a list"}');
  assert.deepEqual(readStrategies('robert', read), []);
  store.set('strategies.v1.robert', JSON.stringify([{ id: 'x', name: 'ok', active: true, config: { kind: 'nope' } }, null, { id: 'y', name: 'B', config: defaultConfig('contribute') }]));
  const kept = readStrategies('robert', read);
  assert.deepEqual(kept.map(s => [s.id, s.active]), [['y', false]]);
});

test('the default bodies are the ones the backend tests simulate in every window', () => {
  // Same literals as WEB_STRATEGY_BODIES in backend/tests/integration/test_domain_http.py.
  assert.deepEqual(wireConfig(defaultConfig('rebalance')), { kind: 'rebalance', trigger: 'calendar', costBps: 10, frequency: 'quarterly' });
  assert.deepEqual(wireConfig({ ...defaultConfig('rebalance'), trigger: 'band' } as StrategyConfig), { kind: 'rebalance', trigger: 'band', costBps: 10, bandPts: 5 });
  assert.deepEqual(wireConfig(defaultConfig('contribute')), { kind: 'contribute', amount: 500, frequency: 'monthly', allocation: 'underweight', costBps: 0 });
  assert.deepEqual(wireConfig(defaultConfig('risk_guard')), { kind: 'risk_guard', triggerDrawdownPct: 8, shiftPct: 50, reentryDrawdownPct: 3, costBps: 10 });
});

test('an API older than contract 1.5.0 is never asked to simulate', () => {
  assert.equal(strategiesCompatibility({ contractVersion: '1.4.0' }), 'older');
  assert.equal(strategiesCompatibility({ contractVersion: '1.5.0' }), 'supported');
  assert.equal(strategiesCompatibility({ contractVersion: '1.6.2' }), 'supported');
  assert.equal(strategiesCompatibility({ contractVersion: '2.0.0' }), 'incompatible');
  assert.equal(strategiesCompatibility(null), 'unknown');
  assert.equal(strategiesCompatibility({ contractVersion: WEB_CONTRACT_VERSION }), 'supported', 'the site never gates itself out');

  const config = defaultConfig('rebalance');
  const base = 's_x|robert|v1|snap';
  assert.equal(simulationRequest('older', base, '1y', config), null);
  assert.equal(simulationRequest('incompatible', base, '1y', config), null);
  assert.equal(simulationRequest('unknown', base, '1y', config), null);
  assert.equal(simulationRequest('supported', null, '1y', config), null, 'no session/profile key yet');
  assert.equal(simulationRequest('supported', base, '1y', { ...defaultConfig('contribute'), amount: 0 } as StrategyConfig), null, 'invalid settings');
  const request = simulationRequest('supported', base, '1y', config);
  assert.deepEqual(request?.body, wireConfig(config));
  assert.equal(request?.key, `strategy|${base}|1y|${JSON.stringify(wireConfig(config))}`);
});

test('the version-skew notice: Strategies page, strategy cards, creation cards, Home', () => {
  assert.equal(strategiesUnavailable('supported', '1.5.0'), null);
  assert.equal(strategiesUnavailable('unknown', null), null, 'nothing shown while /meta loads');
  const older = strategiesUnavailable('older', '1.4.0');
  assert.ok(older);
  for (const [name, text] of Object.entries(older)) bilingual(text, `older.${name}`);
  assert.equal(older.badge.en, 'Needs the newer API release');
  assert.match(older.version.en, /1\.5\.0 or later; the connected API reports 1\.4\.0\./);
  assert.match(older.version.fr, /1\.5\.0 ou plus récent ; l’API connectée indique 1\.4\.0\./);
  assert.match(older.body.en, /edit and delete/, 'saved strategies stay editable and deletable');
  const incompatible = strategiesUnavailable('incompatible', '2.0.0');
  assert.ok(incompatible);
  for (const [name, text] of Object.entries(incompatible)) bilingual(text, `incompatible.${name}`);
  assert.doesNotMatch(incompatible.title.en, /newer/, 'a different major is not "older"');

  const valid = defaultConfig('contribute');
  assert.equal(automationState(valid, false, false, 'older'), 'outdated');
  assert.equal(automationState(valid, false, false, 'incompatible'), 'outdated');
  assert.equal(automationState(valid, false, false, 'unknown'), 'pending');
  assert.equal(automationState(valid, true, false, 'supported'), 'next');
});

const SESSION = 's_00000000-0000-4000-8000-000000000001';

async function simulateFailure(status: number, error: Record<string, unknown>): Promise<ApiRequestError> {
  const fetchImpl: typeof fetch = async () => new Response(JSON.stringify({ error: { requestId: 'req_x', ...error } }), {
    status, headers: { 'Content-Type': 'application/json', 'X-Request-Id': 'req_x' },
  });
  const client = createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl });
  try {
    await client.simulateStrategy('robert', { strategy: wireConfig(defaultConfig('rebalance')), window: { code: 'full' } });
  } catch (e) {
    assert.ok(e instanceof ApiRequestError);
    return e;
  }
  throw new Error('expected a failure');
}

test('a failed simulation says what to do, keeps the request ID and stops offering Retry after three failures', async () => {
  // A 404 from an API that does advertise 1.5.0 (e.g. the profile is gone): no endless Retry.
  const notFound = strategyFailure(await simulateFailure(404, { code: 'not_found', message: 'Resource not found' }), 1);
  assert.equal(notFound.kind, 'other');
  assert.equal(notFound.retry, false);
  assert.equal(notFound.requestId, 'req_x');
  assert.equal(notFound.technical, 'Resource not found', 'the raw server text goes to Technical details');
  assert.notEqual(notFound.message.en, 'Resource not found');

  const invalid = strategyFailure(await simulateFailure(422, { code: 'validation_error', message: 'bad', details: { fields: ['strategy.safeTicker'] } }), 1);
  assert.equal(invalid.kind, 'edit');
  assert.equal(invalid.retry, false);
  assert.match(invalid.message.en, /Change them above/);
  bilingual(invalid.message, 'validation_error');

  const short = strategyFailure(await simulateFailure(422, { code: 'insufficient_data', message: 'short', details: { reason: 'short_history' } }), 1);
  assert.equal(short.kind, 'edit');
  assert.match(short.message.en, /longer period, such as 1Y or All/);
  assert.match(short.message.fr, /1A ou Tout/);

  const reason = { en: 'Pick a later start.', fr: 'Choisissez un début plus tardif.' };
  assert.deepEqual(strategyFailure(await simulateFailure(422, { code: 'insufficient_data', message: 'x', details: { reason } }), 1).message, reason,
    'a bilingual server reason wins');

  const down = await simulateFailure(503, { code: 'upstream_unavailable', message: 'Pricing store down' });
  assert.equal(strategyFailure(down, 1).retry, true);
  assert.equal(strategyFailure(down, 2).retry, true);
  const exhausted = strategyFailure(down, 3);
  assert.equal(exhausted.retry, false);
  assert.match(exhausted.message.en, /^Still unavailable after several tries\..*request ID/);
  bilingual(exhausted.message, 'exhausted');

  const offline = strategyFailure(new ApiRequestError({ status: 0, code: 'network', message: 'fetch failed' }), 1);
  assert.equal(offline.kind, 'retryable');
  assert.equal(offline.retry, true);
  assert.equal(offline.requestId, null);
});

test('delete keeps what Undo needs; Undo puts the strategy back where it was', () => {
  const store = new Map<string, string>();
  const read = (k: string) => store.get(k) ?? null;
  const write = (k: string, v: string) => { store.set(k, v); };
  const list: SavedStrategy[] = [];
  for (const [i, kind] of STRATEGY_KINDS.entries()) list.push(newStrategy(kind, list, en, `st_${i}`));
  writeStrategies('robert', list, write);

  const out = removeStrategy(list, 'st_1');
  assert.ok(out);
  assert.deepEqual(out.next.map(s => s.id), ['st_0', 'st_2']);
  assert.deepEqual(out.removed, { strategy: list[1], index: 1 });
  writeStrategies('robert', out.next, write);
  assert.equal(readStrategies('robert', read).length, 2, 'the delete is saved at once');

  const back = restoreStrategy(readStrategies('robert', read), out.removed);
  assert.ok(back);
  writeStrategies('robert', back, write);
  assert.deepEqual(readStrategies('robert', read), list, 'original order restored and saved');

  assert.equal(removeStrategy(list, 'nope'), null);
  assert.deepEqual(restoreStrategy([], { strategy: list[2]!, index: 2 })?.map(s => s.id), ['st_2'], 'an index past the end appends');
  assert.equal(restoreStrategy(list, out.removed), null, 'already present');
  const others = [0, 1, 2].map(i => ({ ...list[i]!, id: `other_${i}` }));
  assert.equal(restoreStrategy(others, out.removed), null, 'list full');
  assert.equal(UNDO_DELETE_MS, 10_000);
});

test('an expiring Undo notice hands focus to a control still on the page, only when Undo holds it', () => {
  const focused: string[] = [];
  const control = (name: string) => ({ focus: () => { focused.push(name); } });
  const undo = control('undo');
  const item = control('item');
  const add = control('add');
  assert.equal(moveFocusFromExpiredUndo(undo, undo, [null, item, add]), true);
  assert.deepEqual(focused, ['item'], 'first present candidate');
  assert.equal(moveFocusFromExpiredUndo(add, undo, [item]), false, 'focus elsewhere is left alone');
  assert.equal(moveFocusFromExpiredUndo(null, null, [item]), false, 'no Undo button (list was full)');
  assert.equal(moveFocusFromExpiredUndo(undo, undo, [null, undefined]), false);
  assert.deepEqual(focused, ['item']);
});
