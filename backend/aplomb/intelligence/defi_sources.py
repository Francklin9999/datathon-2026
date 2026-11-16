"""Bounded DeFi pool observations by exact provider identity; rights gates default closed.

The endpoints expose selected DEX Screener pool observations, not raw feeds. A capture
time is the only proven availability time. No reported liquidity is investment value.
The DefiLlama protocol (TVL) lookup was removed with that provider (wiring audit,
intelligence#2).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import socket
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

EVM = frozenset({'ethereum', 'base', 'arbitrum', 'optimism', 'bsc', 'polygon', 'avalanche'})
MAX_BYTES = 1_000_000


class DefiSourceError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Aplomb research'})
    try:
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            if response.status != 200 or response.headers.get_content_type() != 'application/json':
                raise DefiSourceError('source_unavailable')
            raw = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        raise DefiSourceError('rate_limited' if exc.code == 429 else 'source_unavailable') from exc
    except (OSError, URLError, socket.timeout) as exc:
        raise DefiSourceError('source_unavailable') from exc
    if len(raw) > MAX_BYTES:
        raise DefiSourceError('source_too_large')
    return raw


def address(chain, value):
    if chain in EVM and re.fullmatch(r'0x[0-9a-fA-F]{40}', value or ''):
        return value.lower()
    if chain == 'solana' and re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]{32,44}', value or ''):
        return value
    raise DefiSourceError('invalid_exact_pool_identity')


def decimal_value(value, *, allow_negative=False):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise DefiSourceError('invalid_source_number')
    try:
        n = Decimal(str(value))
    except InvalidOperation as exc:
        raise DefiSourceError('invalid_source_number') from exc
    if not n.is_finite() or (n < 0 and not allow_negative):
        raise DefiSourceError('invalid_source_number')
    return str(n)


def strict_load(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise DefiSourceError('source_too_large')
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise DefiSourceError('duplicate_source_key')
            out[key] = value
        return out
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise DefiSourceError('invalid_source_json') from exc


def parse_pair(raw, chain, pool):
    identity = address(chain, pool)
    body = strict_load(raw)
    rows = body.get('pairs') if isinstance(body, dict) else None
    if rows is None:
        return None
    if not isinstance(rows, list) or len(rows) > 2:
        raise DefiSourceError('invalid_source_response')
    if not rows:
        return None
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise DefiSourceError('ambiguous_source_identity')
    row = rows[0]
    if row.get('chainId') != chain or address(chain, row.get('pairAddress')) != identity:
        raise DefiSourceError('source_identity_mismatch')
    base, quote = row.get('baseToken'), row.get('quoteToken')
    if not isinstance(base, dict) or not isinstance(quote, dict):
        raise DefiSourceError('missing_token_identity')
    base_id, quote_id = address(chain, base.get('address')), address(chain, quote.get('address'))
    def label(token, field):
        item = token.get(field)
        return item[:120] if isinstance(item, str) and item else None
    def optional_object(key):
        value = row.get(key)
        if value is not None and not isinstance(value, dict):
            raise DefiSourceError('invalid_source_response')
        return value or {}
    created = row.get('pairCreatedAt')
    if created is not None and (type(created) is not int or not 0 <= created <= 253402300799999):
        raise DefiSourceError('invalid_source_timestamp')
    if not isinstance(row.get('dexId'), str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', row['dexId']):
        raise DefiSourceError('invalid_source_response')
    return {'chain': chain, 'pool_address': identity, 'dex_id': row['dexId'],
            'base': {'address': base_id, 'symbol': label(base, 'symbol'), 'name': label(base, 'name')},
            'quote': {'address': quote_id, 'symbol': label(quote, 'symbol'), 'name': label(quote, 'name')},
            'price_usd': decimal_value(row.get('priceUsd')),
            'price_native': decimal_value(row.get('priceNative')),
            'liquidity_usd': decimal_value(optional_object('liquidity').get('usd')),
            'volume_24h_usd': decimal_value(optional_object('volume').get('h24')),
            'price_change_24h_pct': decimal_value(optional_object('priceChange').get('h24'), allow_negative=True),
            'fully_diluted_valuation_usd': decimal_value(row.get('fdv')),
            'market_cap_usd': decimal_value(row.get('marketCap')),
            'pool_created_at': datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if created else None}


def _capture(store, sid, provider, url, raw, observation, captured_at):
    digest = hashlib.sha256(raw).hexdigest()
    owner = 'DEFI#' + hashlib.sha256(sid.encode()).hexdigest()
    key = 'CAPTURE#' + hashlib.sha256((provider + url + digest).encode()).hexdigest()
    result = {'status': 'available' if observation is not None else 'not_found',
              'provider': provider, 'source_url': url, 'source_sha256': digest,
              'dataset_version': provider + '-' + digest[:16],
              'retrieved_at': captured_at.isoformat(), 'available_at': captured_at.isoformat(),
              'published_at': None, 'observation': observation,
              'limitations': ['Provider-reported estimates, not verified on-chain or an executable price.',
                              'Availability before capture and later revisions are unknown.',
                              'Token symbols are labels, not security or issuer identities.']}
    item = {'revision': 1, 'sessionId': sid, 'source': url, 'raw': raw.decode('utf-8'), 'result': result}
    try:
        store.transact([Write('cache', owner, key, item, None)])
    except Conflict:
        prior = store.get('cache', owner, key)
        if not prior or prior.get('sessionId') != sid or prior.get('source') != url or prior.get('raw') != item['raw']:
            raise DefiSourceError('capture_integrity_failure')
        return prior['result']
    return result


def pair(store, sid, chain, pool, *, get=fetch, rights=None, now=None):
    if rights is None:
        rights = os.getenv('APLOMB_DEXSCREENER_RIGHTS_CONFIRMED') == 'true'
    if not rights:
        raise DefiSourceError('rights_not_confirmed')
    identity = address(chain, pool)
    url = f'https://api.dexscreener.com/latest/dex/pairs/{chain}/{identity}'
    raw = get(url)
    observation = parse_pair(raw, chain, identity)
    captured = now or datetime.now(timezone.utc)
    if captured.tzinfo is None or not math.isfinite(captured.timestamp()):
        raise DefiSourceError('invalid_capture_time')
    result = _capture(store, sid, 'dexscreener', url, raw, observation, captured)
    result['terms_url'] = 'https://docs.dexscreener.com/api/api-terms-and-conditions'
    result['docs_url'] = 'https://docs.dexscreener.com/api/reference'
    return result


def sources():
    return {'providers': [
        {'id': 'dexscreener', 'source_id': 'SRC-064', 'status': 'configured' if os.getenv('APLOMB_DEXSCREENER_RIGHTS_CONFIRMED') == 'true' else 'rights_not_confirmed',
         'docs_url': 'https://docs.dexscreener.com/api/reference', 'terms_url': 'https://docs.dexscreener.com/api/api-terms-and-conditions'},
    ]}
