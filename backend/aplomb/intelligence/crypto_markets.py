"""Venue-exact Binance Vision daily history with explicit rights gating.

Every market keeps its own symbol identity (venue + venue symbol + explicit base/quote).
A stablecoin quote such as USDT or USDC is never treated as USD. Every upstream file is
stored as an immutable, session-owned raw capture keyed by its sha256.

Rights status was reviewed on 2026-11-15; dispositions are recorded in
data/source_dispositions.json. Only Binance Vision history is offered, and it stays
disabled until the operator sets its noncommercial acknowledgement flag. The owner
excluded the live Binance and Bitstamp venues; their adapters and the compare/market
routes were removed (wiring audit, intelligence#5).
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import os
import re
import socket
import threading
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

MAX_JSON = 1_000_000
MAX_ZIP = 2_000_000
MAX_CHECKSUM = 1_000
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

# Exact Binance spot symbols verified against Binance /api/v3/exchangeInfo on 2026-11-15.
# Binance Vision files use the same symbols. Never derived from a ticker string.
MARKETS = {
    'binance_vision': {
        'BTCUSDT': ('BTC', 'USDT'), 'BTCUSDC': ('BTC', 'USDC'), 'BTCEUR': ('BTC', 'EUR'),
        'ETHUSDT': ('ETH', 'USDT'), 'ETHUSDC': ('ETH', 'USDC'), 'ETHEUR': ('ETH', 'EUR'),
        'SOLUSDT': ('SOL', 'USDT'), 'SOLUSDC': ('SOL', 'USDC'),
    },
}

QUOTE_KIND = {'USD': 'fiat', 'EUR': 'fiat', 'USDT': 'stablecoin', 'USDC': 'stablecoin'}
ASSETS = ('BTC', 'ETH', 'SOL')
INTERVALS = {'1h': 3600, '4h': 14400, '1d': 86400}


def permitted(venue: str) -> bool:
    return venue in VENUES and os.getenv(VENUES[venue]['flag']) == '1'


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
        venues.append({'venue': key, 'name': info['name'], 'source_id': info['source_id'],
                       'status': 'enabled' if permitted(key) else 'licence_not_enabled',
                       'docs_url': info['docs_url'], 'terms_url': info['terms_url'],
                       'licence': info['licence'], 'limitations': info['limitations'],
                       'markets': [market_identity(key, s) for s in MARKETS[key]]})
    return {'venues': venues, 'assets': list(ASSETS),
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


# ---------------------------------------------------------------- kline parsing

def _binance_kline(row, unit: str) -> dict:
    if not isinstance(row, list) or len(row) < 11:
        raise CryptoMarketError('invalid_response')
    open_, high, low, close = (dec(row[i], positive=True) for i in (1, 2, 3, 4))
    if high < max(open_, close, low) or low > min(open_, close):
        raise CryptoMarketError('invalid_response')
    return {'open_time': epoch(row[0], unit), 'close_time': epoch(row[6], unit),
            'open': text(open_), 'high': text(high), 'low': text(low), 'close': text(close),
            'volume': text(dec(row[5])), 'quote_volume': text(dec(row[7])), 'trades': _int(row[8])}


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


def _require(venue: str, allowed) -> None:
    if venue not in VENUES:
        raise ValueError('unsupported venue')
    ok = allowed(venue) if callable(allowed) else permitted(venue) if allowed is None else allowed
    if not ok:
        raise CryptoMarketError('licence_not_enabled')


# ---------------------------------------------------------------- public operations

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
