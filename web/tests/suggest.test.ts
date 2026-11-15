/** Search-field suggestions: folding, de-duplication, ranking order, limits, emphasis, ticker lists. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { browseSuggestions, buildSuggestIndex, fold, matchSpan, rankSuggestions, tickerSuggestions, type Suggestion } from '../src/lib/suggest';

const values = (items: readonly Suggestion[]) => items.map(item => item.value);

const UNIVERSE = [
  { ticker: 'AAPL', name: 'Apple Inc.' },
  { ticker: 'NVDA', name: 'NVIDIA Corporation' },
  { ticker: 'TSLA', name: 'Tesla, Inc.' },
  { ticker: 'RY.TO', name: 'Royal Bank of Canada' },
  { ticker: 'XBB.TO', name: 'iShares Core Canadian Universe Bond Index ETF' },
  { ticker: 'GLE.PA', name: 'Société Générale' },
];

test('suggest: folding ignores case and accents and keeps the length of composed text', () => {
  assert.equal(fold('Société Générale'), 'societe generale');
  assert.equal(fold('ÉLAN'), 'elan');
  assert.equal(fold('Société').length, 'Société'.length);
});

test('suggest: a value listed twice keeps its first row (a holding before the universe)', () => {
  const index = buildSuggestIndex([{ value: 'NVDA', label: '', meta: 'Held' }, { value: 'NVDA', label: 'NVIDIA Corporation' }, { value: '', label: 'blank' }]);
  assert.equal(index.entries.length, 1);
  assert.equal(rankSuggestions(index, 'nv', 5)[0]?.meta, 'Held');
});

test('suggest: exact, then value prefix, then a word of the label, then anywhere; ties keep list order', () => {
  const index = buildSuggestIndex([
    { value: 'TDX', label: 'Contains td in value' },
    { value: 'ATD.TO', label: 'Alimentation Couche-Tard' },
    { value: 'TD.TO', label: 'Toronto-Dominion Bank' },
    { value: 'ZZZ', label: 'Tdot holdings' },
    { value: 'TD', label: 'Exact' },
    { value: 'QQQ', label: 'Fund with xtd inside' },
  ]);
  assert.deepEqual(values(rankSuggestions(index, 'td', 10)), ['TD', 'TDX', 'TD.TO', 'ZZZ', 'ATD.TO', 'QQQ']);
});

test('suggest: names find their ticker, accents optional, and the limit holds', () => {
  const index = buildSuggestIndex(tickerSuggestions(UNIVERSE, [], 'Held'));
  assert.deepEqual(values(rankSuggestions(index, 'tes', 8)), ['TSLA']);
  assert.deepEqual(values(rankSuggestions(index, 'royal bank', 8)), ['RY.TO']);
  assert.deepEqual(values(rankSuggestions(index, 'generale', 8)), ['GLE.PA']);
  assert.deepEqual(values(rankSuggestions(index, 'nv', 8)), ['NVDA']);
  assert.equal(rankSuggestions(index, 'a', 2).length, 2);
  assert.deepEqual(values(rankSuggestions(index, 'zzz', 8)), []);
});

test('suggest: an empty query lists the first rows in order', () => {
  const index = buildSuggestIndex(tickerSuggestions(UNIVERSE, ['TSLA', 'XBB.TO'], 'Held'));
  assert.deepEqual(values(rankSuggestions(index, '  ', 3)), ['TSLA', 'XBB.TO', 'AAPL']);
});

test('suggest: holdings come first, named from the universe and marked; unknown holdings stay', () => {
  const rows = tickerSuggestions(UNIVERSE, ['TSLA', 'CASH.X'], 'Held');
  assert.deepEqual(rows.slice(0, 2), [
    { value: 'TSLA', label: 'Tesla, Inc.', meta: 'Held' },
    { value: 'CASH.X', label: '', meta: 'Held' },
  ]);
  assert.equal(rows.length, 2 + UNIVERSE.length);
});

test('suggest: opening a field on one of its values lists everything, that value first', () => {
  const index = buildSuggestIndex([{ value: 'CAD', label: 'Canadian dollar' }, { value: 'USD', label: 'US dollar' }, { value: 'EUR', label: 'Euro' }]);
  assert.deepEqual(values(browseSuggestions(index, 'usd', 50) ?? []), ['USD', 'CAD', 'EUR']);
  assert.equal(browseSuggestions(index, 'US', 50), null);
  assert.equal(browseSuggestions(index, '  ', 50), null);
  assert.equal(browseSuggestions(index, 'cad', 2)?.length, 2);
});

test('suggest: the typed part is found for emphasis, case-insensitively', () => {
  assert.deepEqual(matchSpan('NVIDIA Corporation', 'corp'), [7, 11]);
  assert.deepEqual(matchSpan('TSLA', 'ts'), [0, 2]);
  assert.equal(matchSpan('Tesla', ''), null);
  assert.equal(matchSpan('Tesla', 'xyz'), null);
});
