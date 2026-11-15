"""Venue-exact crypto exchange market data with explicit rights gating.

Each venue adapter returns its own symbol identity (venue + venue symbol + explicit
base/quote). A stablecoin quote such as USDT or USDC is never treated as USD, and
quotes from different venues are never consolidated into one price. Every upstream
response is stored as an immutable, session-owned raw capture keyed by its sha256.

Rights status was reviewed on 2026-11-15 (see docs/parallel/reports/agent-2/
CONT-crypto-exchanges.md). Venues whose published terms forbid this use are listed
as blocked and have no adapter. Built venues stay disabled until the operator sets
the venue's noncommercial acknowledgement flag.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import socket
import threading
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

MAX_JSON = 1_000_000
MAX_ZIP = 2_000_000
MAX_CHECKSUM = 1_000
MAX_DEPTH = 20
MAX_CANDLES = 60
MIN_SPACING_SECONDS = 0.25

COMPARISON_NOTE = ('Venue quotes differ; no consolidated price is computed. Rows are only compared '
                   'within the same quote currency, and stablecoin quotes (USDT, USDC) are not USD.')


class CryptoMarketError(RuntimeError):
    """Raised with a stable reason code only; upstream text is never surfaced."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# ---------------------------------------------------------------- venue registry

VENUES = {
    'binance': {
        'name': 'Binance (public market data REST)', 'source_id': 'SRC-068',
        'docs_url': 'https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints',
        'terms_url': 'https://www.binance.com/en/about-legal/terms',
        'flag': 'APLOMB_BINANCE_PUBLIC_NONCOMMERCIAL', 'status': 'gated',
        'licence': 'Binance Terms of Use (operator review required; noncommercial research use only)',
        'limitations': [
            'Binance Terms of Use text could not be retrieved by an automated client on 2026-11-15; '
            'the operator flag records a human terms review.',
            '24h figures are a rolling window ending at the venue close time, not a calendar day.',
            'Order book depth response carries an update id but no venue timestamp.'],
    },
    'bitstamp': {
        'name': 'Bitstamp (public API v2)', 'source_id': 'SRC-072',
        'docs_url': 'https://www.bitstamp.net/api/',
        'terms_url': 'https://www.bitstamp.net/api/#section/Commercial-Use-of-Bitstamp\'s-Exchange-Data',
        'flag': 'APLOMB_BITSTAMP_NONCOMMERCIAL', 'status': 'gated',
        'licence': 'Bitstamp exchange data; commercial use requires a Data License Agreement',
        'limitations': [
            'Commercial use requires a signed Bitstamp Data License Agreement (partners@bitstamp.net).',
            'Ticker volume is base-asset volume over the last 24 hours; no quote volume is published.',
            'The single-market ticker response does not echo the market symbol.'],
    },
    'binance_vision': {
        'name': 'Binance Vision historical data', 'source_id': 'SRC-069',
        'docs_url': 'https://github.com/binance/binance-public-data',
        'terms_url': 'https://data.binance.vision/terms-of-use.html',
        'flag': 'APLOMB_BINANCE_VISION_NONCOMMERCIAL', 'status': 'gated',
        'licence': 'CC BY-NC-SA 4.0 under the Binance Vision Dataset Terms; attribution: Binance Vision',
        'limitations': [
            'Noncommercial academic/research use only; commercial use needs a separate enterprise licence.',
            'Daily files are published after the day closes; the original publication time is unknown.',
            'Spot timestamps from 2025-01-01 are microseconds; earlier files use milliseconds.'],
    },
}

BLOCKED = {
    'coinbase': {'name': 'Coinbase Exchange public API', 'source_id': 'SRC-070',
                 'terms_url': 'https://www.coinbase.com/legal/market_data',
                 'reason': 'Market Data Terms of Use forbid display to third parties, end-user applications '
                           'and use in automated or AI agent systems without written consent.'},
    'kraken': {'name': 'Kraken REST public endpoints', 'source_id': 'SRC-071',
               'terms_url': 'https://www.kraken.com/legal/global-terms',
               'reason': 'Global terms section 9 forbids automation, data extraction and third-party '
                         'applications without prior written consent.'},
    'coinlore': {'name': 'CoinLore API', 'source_id': 'SRC-063',
                 'terms_url': 'https://www.coinlore.com/terms-of-use',
                 'reason': 'Site terms forbid automated bots/data mining and redistribution without '
                           'express written consent.'},
}

# Exact venue symbols verified against each venue's own market listing on 2026-11-15
# (Bitstamp /api/v2/markets/, Binance /api/v3/exchangeInfo). Never derived from a ticker string.
MARKETS = {
    'binance': {
        'BTCUSDT': ('BTC', 'USDT'), 'BTCUSDC': ('BTC', 'USDC'), 'BTCEUR': ('BTC', 'EUR'),
        'ETHUSDT': ('ETH', 'USDT'), 'ETHUSDC': ('ETH', 'USDC'), 'ETHEUR': ('ETH', 'EUR'),
        'SOLUSDT': ('SOL', 'USDT'), 'SOLUSDC': ('SOL', 'USDC'),
    },
    'bitstamp': {
        'btcusd': ('BTC', 'USD'), 'btceur': ('BTC', 'EUR'), 'btcusdt': ('BTC', 'USDT'),
        'btcusdc': ('BTC', 'USDC'), 'ethusd': ('ETH', 'USD'), 'etheur': ('ETH', 'EUR'),
        'ethusdt': ('ETH', 'USDT'), 'ethusdc': ('ETH', 'USDC'), 'solusd': ('SOL', 'USD'),
        'soleur': ('SOL', 'EUR'), 'solusdc': ('SOL', 'USDC'),
    },
}
MARKETS['binance_vision'] = MARKETS['binance']

QUOTE_KIND = {'USD': 'fiat', 'EUR': 'fiat', 'USDT': 'stablecoin', 'USDC': 'stablecoin'}
ASSETS = ('BTC', 'ETH', 'SOL')
INTERVALS = {'1h': 3600, '4h': 14400, '1d': 86400}


def permitted(venue: str) -> bool:
    return venue == 'binance_vision' and os.getenv(VENUES[venue]['flag']) == '1'


def market_identity(venue: str, symbol: str) -> dict:
    if venue not in MARKETS:
        raise ValueError('unsupported venue')
    pair = MARKETS[venue].get(symbol)
    if pair is None:
        raise ValueError('unsupported venue symbol')
    base, quote = pair
    return {'venue': 'binance' if venue == 'binance_vision' else venue, 'venue_symbol': symbol,
            'base': base, 'quote': quote, 'quote_kind': QUOTE_KIND[quote],
            'identity': f'{venue}:{symbol}'}


def venue_catalog() -> dict:
    venues = []
    for key, info in VENUES.items():
        if key != 'binance_vision':
            continue
        venues.append({'venue': key, 'name': info['name'], 'source_id': info['source_id'],
                       'status': 'enabled' if permitted(key) else 'licence_not_enabled',
                       'docs_url': info['docs_url'], 'terms_url': info['terms_url'],
                       'licence': info['licence'], 'limitations': info['limitations'],
                       'markets': [market_identity(key, s) for s in MARKETS[key]]})
    blocked = []  # Other pending venues were excluded by the owner.
    return {'venues': venues, 'blocked': blocked, 'assets': list(ASSETS),
            'intervals': list(INTERVALS), 'note': COMPARISON_NOTE}


# ---------------------------------------------------------------- bounded transport

_spacing_lock = threading.Lock()
_last_call: dict[str, float] = {}


def _pace(host: str) -> None:
    # Bounded, sequential access per host; never parallel bursts against a venue.
    with _spacing_lock:
        wait = _last_call.get(host, 0.0) + MIN_SPACING_SECONDS - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


def fetch(url: str, *, accept: tuple[str, ...] = ('application/json',), limit: int = MAX_JSON):
    host = url.split('/')[2]
    _pace(host)
    try:
        request = Request(url, headers={'Accept': ', '.join(accept), 'User-Agent': 'Aplomb research'})
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            if response.status != 200 or response.headers.get_content_type() not in accept:
                raise CryptoMarketError('source_unavailable')
            body = response.read(limit + 1)
            modified = response.headers.get('Last-Modified')
    except (HTTPError, URLError, OSError, socket.timeout) as exc:
        raise CryptoMarketError('source_unavailable') from exc
    if len(body) > limit:
        raise CryptoMarketError('source_too_large')
    return body, modified


def _json_get(url: str, get) -> tuple[object, bytes]:
    body, _ = get(url)
    try:
        return json.loads(body), body
    except (ValueError, UnicodeDecodeError) as exc:
        raise CryptoMarketError('invalid_response') from exc


# ---------------------------------------------------------------- value helpers

def dec(value, *, positive: bool = False, allow_zero: bool = True) -> Decimal:
    try:
        number = Decimal(str(value)) if not isinstance(value, Decimal) else value
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CryptoMarketError('invalid_response') from exc
    if not number.is_finite() or number < 0 or (positive and number == 0) or (not allow_zero and number == 0):
        raise CryptoMarketError('invalid_response')
    return number


def text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, 'f')


def epoch(value, unit: str) -> str:
    number = _int(value)
    scale = {'s': 1, 'ms': 1_000, 'us': 1_000_000}[unit]
    seconds, remainder = divmod(number, scale)
    moment = datetime.fromtimestamp(seconds, timezone.utc) + timedelta(microseconds=remainder * 1_000_000 // scale)
    return moment.isoformat()


def _int(value) -> int:
    try:
        return int(str(value))
    except ValueError as exc:
        raise CryptoMarketError('invalid_response') from exc


def spread(bid: Decimal | None, ask: Decimal | None) -> dict:
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        return {'absolute': None, 'bps_of_mid': None, 'mid': None, 'crossed': None}
    absolute = ask - bid
    mid = (ask + bid) / 2
    bps = (absolute / mid * 10000).quantize(Decimal('0.01'))
    return {'absolute': text(absolute), 'bps_of_mid': text(bps), 'mid': text(mid), 'crossed': ask < bid}


def _levels(rows, depth: int) -> list[dict]:
    if not isinstance(rows, list):
        raise CryptoMarketError('invalid_response')
    levels = []
    for row in rows[:depth]:
        if not isinstance(row, list) or len(row) < 2:
            raise CryptoMarketError('invalid_response')
        levels.append({'price': text(dec(row[0], positive=True)), 'size': text(dec(row[1]))})
    return levels


def _check_order(levels: list[dict], descending: bool) -> None:
    prices = [Decimal(level['price']) for level in levels]
    if prices != sorted(prices, reverse=descending):
        raise CryptoMarketError('invalid_response')


def candle_summary(candles: list[dict]) -> dict | None:
    if not candles:
        return None
    opens = Decimal(candles[0]['open'])
    closes = Decimal(candles[-1]['close'])
    change = ((closes - opens) / opens * 100).quantize(Decimal('0.01')) if opens > 0 else None
    return {'count': len(candles), 'first_open_time': candles[0]['open_time'],
            'last_open_time': candles[-1]['open_time'], 'first_open': text(opens), 'last_close': text(closes),
            'high': text(max(Decimal(c['high']) for c in candles)),
            'low': text(min(Decimal(c['low']) for c in candles)),
            'change_pct': text(change),
            'base_volume_total': text(sum((Decimal(c['volume']) for c in candles), Decimal(0)))}


# ---------------------------------------------------------------- adapters

class BinanceAdapter:
    venue = 'binance'
    base = 'https://data-api.binance.vision/api/v3/'

    def __init__(self, get=fetch):
        self.get = get

    def ticker(self, symbol: str) -> tuple[dict, list[tuple[str, bytes]]]:
        url = self.base + 'ticker/24hr?' + urlencode({'symbol': symbol})
        data, raw = _json_get(url, self.get)
        if not isinstance(data, dict) or data.get('symbol') != symbol:
            raise CryptoMarketError('identity_mismatch')
        bid, ask = dec(data.get('bidPrice')), dec(data.get('askPrice'))
        return {'last': text(dec(data.get('lastPrice'), positive=True)),
                'bid': text(bid), 'ask': text(ask),
                'bid_size': text(dec(data.get('bidQty'))), 'ask_size': text(dec(data.get('askQty'))),
                'open_24h': text(dec(data.get('openPrice'))), 'high_24h': text(dec(data.get('highPrice'))),
                'low_24h': text(dec(data.get('lowPrice'))),
                'volume_base_24h': text(dec(data.get('volume'))),
                'volume_quote_24h': text(dec(data.get('quoteVolume'))),
                'window': 'rolling 24h', 'window_start': epoch(data.get('openTime'), 'ms'),
                'venue_time': epoch(data.get('closeTime'), 'ms'), 'venue_time_field': 'closeTime',
                'spread': spread(bid if bid > 0 else None, ask if ask > 0 else None)}, [(url, raw)]

    def candles(self, symbol: str, interval: str, limit: int) -> tuple[list[dict], list[tuple[str, bytes]]]:
        url = self.base + 'klines?' + urlencode({'symbol': symbol, 'interval': interval, 'limit': limit})
        data, raw = _json_get(url, self.get)
        if not isinstance(data, list) or len(data) > limit:
            raise CryptoMarketError('invalid_response')
        return [_binance_kline(row, 'ms') for row in data], [(url, raw)]

    def book(self, symbol: str, depth: int) -> tuple[dict, list[tuple[str, bytes]]]:
        limit = 5 if depth <= 5 else 10 if depth <= 10 else 20
        url = self.base + 'depth?' + urlencode({'symbol': symbol, 'limit': limit})
        data, raw = _json_get(url, self.get)
        if not isinstance(data, dict) or not isinstance(data.get('lastUpdateId'), int):
            raise CryptoMarketError('invalid_response')
        bids, asks = _levels(data.get('bids'), depth), _levels(data.get('asks'), depth)
        _check_order(bids, True)
        _check_order(asks, False)
        return {'bids': bids, 'asks': asks, 'venue_time': None, 'venue_sequence': str(data['lastUpdateId']),
                'aggregation': 'aggregated by price level'}, [(url, raw)]


def _binance_kline(row, unit: str) -> dict:
    if not isinstance(row, list) or len(row) < 11:
        raise CryptoMarketError('invalid_response')
    open_, high, low, close = (dec(row[i], positive=True) for i in (1, 2, 3, 4))
    if high < max(open_, close, low) or low > min(open_, close):
        raise CryptoMarketError('invalid_response')
    return {'open_time': epoch(row[0], unit), 'close_time': epoch(row[6], unit),
            'open': text(open_), 'high': text(high), 'low': text(low), 'close': text(close),
            'volume': text(dec(row[5])), 'quote_volume': text(dec(row[7])), 'trades': _int(row[8])}


class BitstampAdapter:
    venue = 'bitstamp'
    base = 'https://www.bitstamp.net/api/v2/'

    def __init__(self, get=fetch):
        self.get = get

    def ticker(self, symbol: str) -> tuple[dict, list[tuple[str, bytes]]]:
        url = f'{self.base}ticker/{symbol}/'
        data, raw = _json_get(url, self.get)
        if not isinstance(data, dict) or data.get('market_type') not in (None, 'SPOT'):
            raise CryptoMarketError('identity_mismatch')
        bid, ask = dec(data.get('bid')), dec(data.get('ask'))
        return {'last': text(dec(data.get('last'), positive=True)), 'bid': text(bid), 'ask': text(ask),
                'bid_size': None, 'ask_size': None,
                'open_24h': text(dec(data.get('open_24', data.get('open')))),
                'high_24h': text(dec(data.get('high'))), 'low_24h': text(dec(data.get('low'))),
                'volume_base_24h': text(dec(data.get('volume'))), 'volume_quote_24h': None,
                'vwap_24h': text(dec(data.get('vwap'))),
                'window': 'last 24 hours', 'window_start': None,
                'venue_time': epoch(data.get('timestamp'), 's'), 'venue_time_field': 'timestamp',
                'spread': spread(bid if bid > 0 else None, ask if ask > 0 else None)}, [(url, raw)]

    def candles(self, symbol: str, interval: str, limit: int) -> tuple[list[dict], list[tuple[str, bytes]]]:
        url = f'{self.base}ohlc/{symbol}/?' + urlencode({'step': INTERVALS[interval], 'limit': limit})
        data, raw = _json_get(url, self.get)
        try:
            body = data['data']
            pair = body['pair']
            rows = body['ohlc']
        except (KeyError, TypeError) as exc:
            raise CryptoMarketError('invalid_response') from exc
        base, quote = MARKETS['bitstamp'][symbol]
        if pair != f'{base}/{quote}':
            raise CryptoMarketError('identity_mismatch')
        if not isinstance(rows, list) or len(rows) > limit:
            raise CryptoMarketError('invalid_response')
        step = INTERVALS[interval]
        candles = []
        for row in rows:
            if not isinstance(row, dict):
                raise CryptoMarketError('invalid_response')
            open_, high, low, close = (dec(row.get(k), positive=True) for k in ('open', 'high', 'low', 'close'))
            if high < max(open_, close, low) or low > min(open_, close):
                raise CryptoMarketError('invalid_response')
            start = _int(row.get('timestamp'))
            candles.append({'open_time': epoch(start, 's'), 'close_time': epoch(start + step, 's'),
                            'open': text(open_), 'high': text(high), 'low': text(low), 'close': text(close),
                            'volume': text(dec(row.get('volume'))), 'quote_volume': None, 'trades': None})
        return candles, [(url, raw)]

    def book(self, symbol: str, depth: int) -> tuple[dict, list[tuple[str, bytes]]]:
        url = f'{self.base}order_book/{symbol}/?' + urlencode({'group': 1})
        data, raw = _json_get(url, self.get)
        if not isinstance(data, dict):
            raise CryptoMarketError('invalid_response')
        bids, asks = _levels(data.get('bids'), depth), _levels(data.get('asks'), depth)
        _check_order(bids, True)
        _check_order(asks, False)
        micro = data.get('microtimestamp')
        venue_time = epoch(micro, 'us') if micro is not None else epoch(data.get('timestamp'), 's')
        return {'bids': bids, 'asks': asks, 'venue_time': venue_time, 'venue_sequence': None,
                'aggregation': 'grouped at same price (group=1)'}, [(url, raw)]


ADAPTERS = {'binance': BinanceAdapter, 'bitstamp': BitstampAdapter}


# ---------------------------------------------------------------- capture storage

def _owner(session_id: str) -> str:
    if not isinstance(session_id, str) or not session_id:
        raise CryptoMarketError('invalid_session')
    return hashlib.sha256(session_id.encode()).hexdigest()


def store_raw(store, session_id: str, venue: str, kind: str, url: str, payload: bytes,
              retrieved: datetime, *, binary: bool = False, extra: dict | None = None) -> dict:
    digest = hashlib.sha256(payload).hexdigest()
    pk, sk = 'CRYPTOMKT#' + _owner(session_id), f'CAPTURE#{venue}#{kind}#{digest}'
    meta = {'capture_id': f'{venue}:{kind}:{digest}', 'venue': venue, 'kind': kind, 'source_url': url,
            'sha256': digest, 'bytes': len(payload), 'retrieved_at': retrieved.isoformat(), **(extra or {})}
    raw = base64.b64encode(payload).decode() if binary else payload.decode('utf-8')
    record = {'revision': 1, 'sessionId': session_id, 'encoding': 'base64' if binary else 'utf-8',
              'raw': raw, 'meta': meta}
    try:
        store.transact([Write('cache', pk, sk, record, None)])
    except Conflict:
        old = store.get('cache', pk, sk)
        if old is None or old.get('raw') != raw or old.get('sessionId') != session_id:
            raise CryptoMarketError('capture_conflict') from None
        # Identical bytes already captured in this session: keep the first retrieval time.
        return old['meta']
    return meta


def _captured(store, session_id, venue, kind, pairs, retrieved) -> list[dict]:
    return [store_raw(store, session_id, venue, kind, url, raw, retrieved) for url, raw in pairs]


def _provenance(venue: str, captures: list[dict], retrieved: datetime) -> dict:
    info = VENUES[venue]
    return {'source_id': info['source_id'], 'docs_url': info['docs_url'], 'terms_url': info['terms_url'],
            'licence': info['licence'], 'limitations': info['limitations'], 'captures': captures,
            'retrieved_at': retrieved.isoformat(), 'available_at': retrieved.isoformat(),
            'availability_basis': 'capture time; earlier venue publication is not proven'}


def _require(venue: str, allowed) -> None:
    if venue not in VENUES:
        raise ValueError('unsupported venue')
    ok = allowed(venue) if callable(allowed) else permitted(venue) if allowed is None else allowed
    if not ok:
        raise CryptoMarketError('licence_not_enabled')


# ---------------------------------------------------------------- public operations

def market_detail(store, session_id: str, venue: str, symbol: str, *, interval: str = '1d',
                  limit: int = 30, depth: int = 10, get=fetch, allowed=None, now=None) -> dict:
    if venue not in ADAPTERS:
        raise ValueError('unsupported venue')
    identity = market_identity(venue, symbol)
    if interval not in INTERVALS:
        raise ValueError('interval must be one of 1h, 4h, 1d')
    if not 1 <= limit <= MAX_CANDLES:
        raise ValueError(f'limit must be between 1 and {MAX_CANDLES}')
    if not 1 <= depth <= MAX_DEPTH:
        raise ValueError(f'depth must be between 1 and {MAX_DEPTH}')
    _require(venue, allowed)
    adapter = ADAPTERS[venue](get)
    retrieved = now or datetime.now(timezone.utc)
    ticker, t_raw = adapter.ticker(symbol)
    candles, c_raw = adapter.candles(symbol, interval, limit)
    book, b_raw = adapter.book(symbol, depth)
    captures = (_captured(store, session_id, venue, 'ticker', t_raw, retrieved)
                + _captured(store, session_id, venue, 'candles', c_raw, retrieved)
                + _captured(store, session_id, venue, 'book', b_raw, retrieved))
    best_bid = Decimal(book['bids'][0]['price']) if book['bids'] else None
    best_ask = Decimal(book['asks'][0]['price']) if book['asks'] else None
    book['best_bid'], book['best_ask'] = text(best_bid), text(best_ask)
    book['spread'] = spread(best_bid, best_ask)
    book['bid_size_total'] = text(sum((Decimal(x['size']) for x in book['bids']), Decimal(0)))
    book['ask_size_total'] = text(sum((Decimal(x['size']) for x in book['asks']), Decimal(0)))
    return {'market': identity, 'ticker': ticker,
            'candles': {'interval': interval, 'items': candles, 'summary': candle_summary(candles),
                        'note': 'Most recent candle may still be open at capture time.'},
            'book': book, 'provenance': _provenance(venue, captures, retrieved), 'note': COMPARISON_NOTE}


def compare(store, session_id: str, asset: str, *, venues=None, get=fetch, allowed=None, now=None) -> dict:
    asset = asset.upper()
    if asset not in ASSETS:
        raise ValueError('supported assets are BTC, ETH and SOL')
    selected = list(ADAPTERS) if not venues else list(dict.fromkeys(venues))
    for venue in selected:
        if venue not in ADAPTERS:
            raise ValueError('unsupported venue')
    retrieved = now or datetime.now(timezone.utc)
    rows, unavailable, captures = [], [], []
    for venue in selected:
        try:
            _require(venue, allowed)
        except CryptoMarketError as exc:
            unavailable.append({'venue': venue, 'reason': str(exc), 'terms_url': VENUES[venue]['terms_url']})
            continue
        adapter = ADAPTERS[venue](get)
        for symbol, (base, _quote) in MARKETS[venue].items():
            if base != asset:
                continue
            try:
                ticker, raw = adapter.ticker(symbol)
                meta = _captured(store, session_id, venue, 'ticker', raw, retrieved)
            except CryptoMarketError as exc:
                unavailable.append({'venue': venue, 'venue_symbol': symbol, 'reason': str(exc)})
                continue
            captures += meta
            rows.append({'market': market_identity(venue, symbol), 'last': ticker['last'],
                         'bid': ticker['bid'], 'ask': ticker['ask'], 'spread': ticker['spread'],
                         'volume_base_24h': ticker['volume_base_24h'],
                         'volume_quote_24h': ticker['volume_quote_24h'], 'window': ticker['window'],
                         'venue_time': ticker['venue_time'], 'capture_id': meta[0]['capture_id']})
    groups = []
    for quote in sorted({r['market']['quote'] for r in rows}):
        members = [r for r in rows if r['market']['quote'] == quote]
        group = {'quote': quote, 'quote_kind': QUOTE_KIND[quote], 'venues': [r['market']['identity'] for r in members],
                 'last_range': None}
        if len({r['market']['venue'] for r in members}) >= 2:
            lasts = [Decimal(r['last']) for r in members]
            low, high = min(lasts), max(lasts)
            group['last_range'] = {'low': text(low), 'high': text(high), 'difference': text(high - low),
                                   'difference_bps_of_low': text(((high - low) / low * 10000).quantize(Decimal('0.01')))}
        groups.append(group)
    return {'asset': asset, 'rows': rows, 'quote_groups': groups, 'unavailable': unavailable,
            'retrieved_at': retrieved.isoformat(), 'available_at': retrieved.isoformat(),
            'captures': captures, 'note': COMPARISON_NOTE,
            'sources': [{'venue': v, 'docs_url': VENUES[v]['docs_url'], 'terms_url': VENUES[v]['terms_url'],
                         'licence': VENUES[v]['licence']} for v in selected]}


VISION_BASE = 'https://data.binance.vision/data/spot/daily/klines/'
VISION_FIRST = date(2017, 8, 17)
MICROSECOND_FROM = date(2025, 1, 1)
_CHECKSUM = re.compile(r'^([0-9a-f]{64})\s+\*?([A-Za-z0-9._-]+)\s*$')


def vision_daily(store, session_id: str, symbol: str, day: date, *, interval: str = '1d',
                 get=fetch, allowed=None, now=None) -> dict:
    identity = market_identity('binance_vision', symbol)
    if interval not in INTERVALS:
        raise ValueError('interval must be one of 1h, 4h, 1d')
    retrieved = now or datetime.now(timezone.utc)
    if day < VISION_FIRST or day >= retrieved.date():
        raise ValueError('date must be a completed UTC day on or after 2017-08-17')
    _require('binance_vision', allowed)
    name = f'{symbol}-{interval}-{day.isoformat()}.zip'
    url = f'{VISION_BASE}{symbol}/{interval}/{name}'
    archive, modified = get(url, accept=('application/zip',), limit=MAX_ZIP)
    checksum, _ = get(url + '.CHECKSUM', accept=('application/zip', 'text/plain', 'application/octet-stream'),
                      limit=MAX_CHECKSUM)
    try:
        match = _CHECKSUM.match(checksum.decode('ascii').strip())
    except UnicodeDecodeError as exc:
        raise CryptoMarketError('invalid_checksum') from exc
    digest = hashlib.sha256(archive).hexdigest()
    if not match or match.group(2) != name:
        raise CryptoMarketError('invalid_checksum')
    if match.group(1) != digest:
        raise CryptoMarketError('checksum_mismatch')
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            members = zf.infolist()
            if len(members) != 1 or members[0].filename != name[:-4] + '.csv' or members[0].file_size > 5_000_000:
                raise CryptoMarketError('invalid_archive')
            body = zf.read(members[0]).decode('ascii')
    except (zipfile.BadZipFile, UnicodeDecodeError, KeyError) as exc:
        raise CryptoMarketError('invalid_archive') from exc
    unit = 'us' if day >= MICROSECOND_FROM else 'ms'
    rows = [row for row in csv.reader(io.StringIO(body)) if row]
    if rows and not rows[0][0].isdigit():
        rows = rows[1:]  # tolerate a header line
    candles = [_binance_kline(row, unit) for row in rows]
    expected = 86400 // INTERVALS[interval]
    seen = set()
    for candle in candles:
        opened = datetime.fromisoformat(candle['open_time'])
        closed = datetime.fromisoformat(candle['close_time'])
        offset = opened.hour * 3600 + opened.minute * 60 + opened.second
        if (opened.date() != day or opened.microsecond or offset % INTERVALS[interval]
                or offset in seen or closed < opened
                or closed >= opened + timedelta(seconds=INTERVALS[interval])):
            raise CryptoMarketError('invalid_archive')
        seen.add(offset)
    candles.sort(key=lambda candle: candle['open_time'])
    complete = seen == set(range(0, 86400, INTERVALS[interval]))
    extra = {'checksum_verified': True, 'source_last_modified': modified, 'timestamp_unit': unit}
    archive_meta = store_raw(store, session_id, 'binance_vision', f'klines-{interval}', url, archive, retrieved,
                             binary=True, extra=extra)
    checksum_meta = store_raw(store, session_id, 'binance_vision', f'checksum-{interval}', url + '.CHECKSUM',
                              checksum, retrieved)
    info = VENUES['binance_vision']
    return {'market': identity, 'date': day.isoformat(), 'interval': interval, 'candles': candles,
            'expected_candles': expected, 'complete': complete,
            'summary': candle_summary(candles),
            'checksum': {'sha256': digest, 'published': match.group(1), 'verified': True},
            'provenance': {'source_id': info['source_id'], 'docs_url': info['docs_url'],
                           'terms_url': info['terms_url'], 'licence': info['licence'],
                           'attribution': 'Data: Binance Vision (data.binance.vision), CC BY-NC-SA 4.0',
                           'limitations': info['limitations'], 'captures': [archive_meta, checksum_meta],
                           'source_last_modified': modified,
                           'retrieved_at': retrieved.isoformat(), 'available_at': retrieved.isoformat(),
                           'availability_basis': 'capture time; HTTP Last-Modified is reported, not proven publication'}}
