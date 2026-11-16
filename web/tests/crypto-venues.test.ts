import assert from 'node:assert/strict';
import test from 'node:test';
import { VISION_FALLBACK_SYMBOLS, visionVenue } from '../src/lib/cryptoVenues';

const market = (venue_symbol: string) => ({ venue: 'binance', venue_symbol, base: 'BTC', quote: 'USDT', quote_kind: 'stablecoin', identity: `binance_vision:${venue_symbol}` });

test('crypto history reads its market list, licence and limitations from the venue catalogue', () => {
  const body = { venues: [{ venue: 'binance_vision', status: 'enabled', licence: 'CC BY-NC-SA 4.0', limitations: ['Noncommercial only.'],
    markets: [market('BTCUSDT'), market('ETHEUR'), market('BTCUSDT')] }], assets: ['BTC'], intervals: ['1d'], note: 'n' };
  assert.deepEqual(visionVenue(body), { symbols: ['BTCUSDT', 'ETHEUR'], licence: 'CC BY-NC-SA 4.0', limitations: ['Noncommercial only.'] });
});

test('a missing or malformed catalogue leaves the fallback list in place', () => {
  const ok = { venue: 'binance_vision', licence: 'L', limitations: [], markets: [market('BTCUSDT')] };
  for (const body of [null, {}, { venues: [] }, { venues: [{ ...ok, venue: 'binance' }] }, { venues: [{ ...ok, markets: [] }] },
    { venues: [{ ...ok, markets: [{ venue_symbol: 3 }] }] }, { venues: [{ ...ok, licence: undefined }] },
    { venues: [{ ...ok, limitations: [1] }] }]) assert.equal(visionVenue(body), null, JSON.stringify(body));
  assert.ok(VISION_FALLBACK_SYMBOLS.includes('BTCUSDT'));
});
