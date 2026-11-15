/** Saved strategies and their configuration (web/src/lib/strategies.ts). */
import assert from 'node:assert/strict';
import test from 'node:test';
import type { StrategyConfig } from '../src/contracts/types';
import { validateContract } from '../src/contracts/validate';
import {
  MAX_STRATEGIES, STRATEGY_KINDS, configIssues, defaultConfig, describe, newStrategy, readStrategies, wireConfig, writeStrategies,
  type SavedStrategy,
} from '../src/lib/strategies';

const en = (t: { en: string }) => t.en;
const money = (n: number) => `${n} CAD`;

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
