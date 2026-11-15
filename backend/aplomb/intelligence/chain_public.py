"""Bounded Bitcoin network observations from the documented Mempool REST API.

No exchange prices, wallet addresses, or instructions to transact are involved.
Hosted output reuse terms have not been established; the operator must confirm
rights before fetching or persisting data. The upstream software licence does not
establish rights to hosted API output.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import socket
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

SOURCE = 'https://mempool.space/docs/api/rest'
ENDPOINTS = {
    'fees': ('https://mempool.space/api/v1/fees/recommended', 'application/json'),
    'mempool': ('https://mempool.space/api/mempool', 'application/json'),
    'height': ('https://mempool.space/api/blocks/tip/height', 'text/plain'),
}
MAX_BYTES = 65536


class ChainError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url: str, expected_type: str) -> bytes:
    if (url, expected_type) not in ENDPOINTS.values():
        raise ChainError('endpoint_not_allowed')
    try:
        request = Request(url, headers={'Accept': expected_type, 'User-Agent': 'Aplomb network research'})
        with build_opener(NoRedirect).open(request, timeout=8) as response:
            if response.status != 200 or response.headers.get_content_type() != expected_type:
                raise ChainError('source_unavailable')
            body = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 429:
            raise ChainError('rate_limited') from exc
        raise ChainError('source_unavailable') from exc
    except (URLError, OSError, socket.timeout) as exc:
        raise ChainError('source_unavailable') from exc
    if len(body) > MAX_BYTES:
        raise ChainError('response_too_large')
    return body


def strict_json(payload: bytes):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    def invalid(_value):
        raise ValueError('non-finite JSON')
    try:
        return json.loads(payload, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError) as exc:
        raise ChainError('invalid_response') from exc


def _integer(data, key, *, maximum=10**16):
    number = data.get(key)
    if type(number) is not int or number < 0 or number > maximum:
        raise ChainError('invalid_response')
    return number


def normalize(kind: str, payload: bytes) -> dict:
    if not isinstance(payload, bytes) or len(payload) > MAX_BYTES:
        raise ChainError('response_too_large')
    if kind == 'height':
        try:
            height = payload.decode('ascii').strip()
            if not height.isascii() or not height.isdecimal() or len(height) > 12:
                raise ValueError('invalid height')
            return {'block_height': int(height), 'unit': 'blocks', 'confirmations': 'tip can reorganize'}
        except (ValueError, UnicodeError) as exc:
            raise ChainError('invalid_response') from exc
    data = strict_json(payload)
    if not isinstance(data, dict):
        raise ChainError('invalid_response')
    if kind == 'fees':
        keys = ('fastestFee', 'halfHourFee', 'hourFee', 'economyFee', 'minimumFee')
        values = {}
        for key in keys:
            value = data.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10**9:
                raise ChainError('invalid_response')
            values[key] = value
        return {'provider_estimates': values, 'unit': 'satoshi per virtual byte',
                'scope': 'provider estimate, no confirmation guarantee'}
    if kind == 'mempool':
        histogram = data.get('fee_histogram')
        if not isinstance(histogram, list) or len(histogram) > 5000:
            raise ChainError('invalid_response')
        for row in histogram:
            if not isinstance(row, list) or len(row) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in row
            ):
                raise ChainError('invalid_response')
        return {'transaction_count': _integer(data, 'count'), 'virtual_size': _integer(data, 'vsize'),
                'total_fees': _integer(data, 'total_fee'), 'virtual_size_unit': 'virtual bytes',
                'total_fees_unit': 'satoshis', 'scope': 'one node’s unconfirmed transaction pool'}
    raise ChainError('unsupported_observation')


def capture(store, session_id: str, *, get=fetch, permitted=None, clock=None):
    if permitted is None:
        permitted = os.getenv('APLOMB_MEMPOOL_REUSE_CONFIRMED') == '1'
    if not permitted:
        raise ChainError('reuse_rights_unconfirmed')
    if not isinstance(session_id, str) or not session_id:
        raise ChainError('invalid_session')
    clock = clock or (lambda: datetime.now(timezone.utc))
    owner = 'CHAIN#' + hashlib.sha256(session_id.encode()).hexdigest()
    rows, errors = {}, {}
    for kind, (url, media) in ENDPOINTS.items():
        try:
            raw = get(url, media)
            data = normalize(kind, raw)
            captured = clock()
            if captured.tzinfo is None or captured.utcoffset() is None:
                raise ChainError('invalid_capture_time')
            stamp = captured.astimezone(timezone.utc).isoformat()
            digest = hashlib.sha256(raw).hexdigest()
            item = {'revision': 1, 'sessionId': session_id, 'raw': raw.decode('utf-8'),
                    'observation': {'kind': kind, 'data': data, 'chain': 'Bitcoin mainnet',
                                    'source_url': url, 'source_sha256': digest,
                                    'dataset_version': 'mempool-' + digest[:16],
                                    'observed_at': None, 'published_at': None,
                                    'available_at': stamp, 'retrieved_at': stamp,
                                    'licence': 'Hosted API output reuse rights operator-confirmed; see source terms',
                                    'documentation_url': SOURCE}}
            sk = 'CAPTURE#' + hashlib.sha256((kind + ':' + digest).encode()).hexdigest()
            try:
                store.transact([Write('cache', owner, sk, item, None)])
            except Conflict:
                prior = store.get('cache', owner, sk)
                if (not prior or prior.get('sessionId') != session_id or prior['raw'] != item['raw']
                        or prior['observation']['source_url'] != url):
                    raise ChainError('capture_integrity_failure')
                item = prior
            rows[kind] = item['observation']
        except (ChainError, ValueError, UnicodeError) as exc:
            errors[kind] = str(exc) if isinstance(exc, ChainError) else 'invalid_response'
    return {'status': 'available' if not errors else 'partial' if rows else 'unavailable',
            'observations': rows, 'errors': errors,
            'limitations': ['The endpoint is live; historical values cannot be reconstructed from observation dates.',
                            'Reuse rights are an operator assertion. Rate limits apply; no automatic retries.',
                            'Network conditions are not security prices, liquidity estimates, or a trade signal.']}
