/** Ticker coverage outside the move form (QA T5.1, T5.2, T4(b), 4.5c): lib/tickerCoverage.ts. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { fold } from '../src/lib/suggest';
import { universeComplete, universeMarkets } from '../src/lib/universe';
import {
  REPLAY_FIX_MOVE, checkTickers, instrumentCountLine, noMatchingInstrument, replayTickerIssue, showAllInstruments,
  targetLineTickers, type UniverseView,
} from '../src/lib/tickerCoverage';

const VERSION = 'snap-20261115-globalfx';
const ASSETS = [
  { ticker: 'TSLA', name: 'Tesla', market: 'NASDAQ', assetClass: 'equity' },
  { ticker: 'XIU.TO', name: 'iShares S&P/TSX 60', market: 'TSX', assetClass: 'etf' },
  { ticker: 'SPY', name: 'SPDR S&P 500', market: 'NYSE Arca', assetClass: 'etf' },
];
const READY: UniverseView = { ready: true, assets: ASSETS, total: 31, dataVersion: VERSION };
const LOADING: UniverseView = { ready: false, assets: [], total: 0, dataVersion: null };

test('universeComplete: a full page or a next cursor is never the whole universe', () => {
  // The API caps its matches at 500 before counting them, so total always equals the page at limit 500.
  const items = (n: number) => Array.from({ length: n }, () => ASSETS[0]!) as never[];
  assert.equal(universeComplete({ items: items(31), total: 31, nextCursor: null }, 500), true);
  assert.equal(universeComplete({ items: items(500), total: 500, nextCursor: null }, 500), false, 'capped page');
  assert.equal(universeComplete({ items: items(31), total: 31, nextCursor: '31' }, 500), false, 'more pages');
  assert.equal(universeComplete({ items: items(30), total: 31, nextCursor: null }, 500), false, 'fewer than total');
});

test('targetLineTickers: the first word of each non-empty TICKER PERCENT line, upper case', () => {
  assert.deepEqual(targetLineTickers('tsla 40\n\n  XIU.TO   60  \n7203.t\n'), ['TSLA', 'XIU.TO', '7203.T']);
  assert.deepEqual(targetLineTickers(''), []);
});

test('checkTickers: blocks an unsupported ticker when on-demand fetching is off, naming the snapshot', () => {
  const one = checkTickers(['7203.T'], READY, false);
  assert.equal(one.blocking, true);
  assert.deepEqual(one.unsupported, ['7203.T']);
  assert.deepEqual(one.message, {
    en: `7203.T is not one of the 31 supported instruments of snapshot ${VERSION}. Choose one from the list.`,
    fr: `7203.T ne fait pas partie des 31 instruments pris en charge de l’instantané ${VERSION}. Choisissez-en un dans la liste.`,
  });
  const many = checkTickers(targetLineTickers('TSLA 50\n7203.T 25\nzzz 25\n7203.t 0'), READY, false);
  assert.equal(many.blocking, true);
  assert.deepEqual(many.unsupported, ['7203.T', 'ZZZ']);
  assert.equal(many.message?.en, `Not supported in snapshot ${VERSION}: 7203.T, ZZZ. Use instruments from the list.`);
  assert.equal(many.message?.fr, `Non pris en charge dans l’instantané ${VERSION} : 7203.T, ZZZ. Utilisez des instruments de la liste.`);
});

test('checkTickers: supported, cash and case-insensitive tickers pass; on-demand only warns', () => {
  assert.deepEqual(checkTickers(['tsla', 'CASH.JPY', 'xiu.to', ''], READY, false), { unsupported: [], blocking: false, message: null });
  const hint = checkTickers(['7203.T'], READY, true);
  assert.equal(hint.blocking, false);
  assert.match(hint.message?.en ?? '', /^Not in snapshot snap-20261115-globalfx yet: 7203\.T\. .*Decide page/);
  assert.match(hint.message?.fr ?? '', /^Pas encore dans l’instantané snap-20261115-globalfx : 7203\.T\. .*page Décider/);
});

test('checkTickers: never blocks before the universe read has completed', () => {
  assert.deepEqual(checkTickers(['7203.T'], LOADING, false), { unsupported: [], blocking: false, message: null });
  assert.deepEqual(checkTickers(['7203.T'], { ...READY, dataVersion: null }, false).blocking, false);
});

test('replayTickerIssue: blocks Run for a ticker outside the snapshot, even with on-demand on', () => {
  const off = replayTickerIssue(' 7203.t ', READY, [], false);
  assert.equal(off?.field, 'ticker');
  assert.equal(off?.message.en, `7203.T is not one of the 31 supported instruments of snapshot ${VERSION}. Choose one from the list.`);
  const on = replayTickerIssue('7203.T', READY, [], true);
  assert.equal(on?.field, 'ticker');
  assert.match(on?.message.en ?? '', /a replay uses only instruments of the snapshot\. .*Decide page/);
  assert.match(on?.message.fr ?? '', /un rejeu n’utilise que les instruments de l’instantané\. .*page Décider/);
});

test('replayTickerIssue: nothing for listed, held, cash or empty tickers, or an unloaded universe', () => {
  assert.equal(replayTickerIssue('tsla', READY, [], false), null);
  assert.equal(replayTickerIssue('OLD.TO', READY, ['OLD.TO'], false), null);
  assert.equal(replayTickerIssue('CASH.USD', READY, [], false), null);
  // An empty ticker already has the move form's own "Choose an asset." issue: never a duplicate.
  assert.equal(replayTickerIssue('  ', READY, [], false), null);
  assert.equal(replayTickerIssue('7203.T', LOADING, [], false), null);
  assert.ok(REPLAY_FIX_MOVE.en && REPLAY_FIX_MOVE.fr);
});

test('Markets: the count line is words, not a bare ratio', () => {
  assert.deepEqual(instrumentCountLine(31, 31, VERSION), {
    en: `31 of 31 instruments · snapshot ${VERSION}`, fr: `31 sur 31 instruments · instantané ${VERSION}`,
  });
  assert.equal(instrumentCountLine(0, 31, VERSION).en, `0 of 31 instruments · snapshot ${VERSION}`);
  assert.equal(instrumentCountLine(1, 1, null).en, '1 of 1 instrument');
  assert.equal(instrumentCountLine(1, 1, null).fr, '1 sur 1 instrument');
});

test('Markets: a search with no match explains what the snapshot covers (markets from the data)', () => {
  // The page filters folded `ticker name market assetClass` text: nothing matches Toyota.
  const text = ASSETS.map(a => fold(`${a.ticker} ${a.name} ${a.market} ${a.assetClass}`));
  for (const query of ['7203.T', 'toyota']) assert.deepEqual(text.filter(t => t.includes(fold(query))), []);
  const markets = universeMarkets(ASSETS);
  assert.deepEqual(markets, ['NASDAQ', 'NYSE Arca', 'TSX']);
  assert.deepEqual(noMatchingInstrument(' toyota ', 31, VERSION, markets), {
    en: `No supported instrument matches “toyota”. Snapshot ${VERSION} covers 31 instruments on these markets: NASDAQ, NYSE Arca, TSX. Listings on other exchanges are not loaded.`,
    fr: `Aucun instrument pris en charge ne correspond à « toyota ». L’instantané ${VERSION} couvre 31 instruments sur ces marchés : NASDAQ, NYSE Arca, TSX. Les titres cotés sur d’autres bourses ne sont pas chargés.`,
  });
  assert.equal(noMatchingInstrument('x', 31, null, markets).en, 'No supported instrument matches “x”. Listings on other exchanges are not loaded.');
  assert.deepEqual(showAllInstruments(31), { en: 'Show all 31', fr: 'Tout afficher (31)' });
});
