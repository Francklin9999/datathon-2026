"""Coin Metrics Community latest daily market observation, with explicit rights gating."""
from __future__ import annotations

import hashlib
import json
import os
import socket
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

BASE = 'https://community-api.coinmetrics.io/v4/timeseries/asset-metrics'
TERMS = 'https://docs.coinmetrics.io/service-and-support/coverage'


class CoinMetricsError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    try:
        request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Aplomb research'})
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            if response.status != 200 or response.headers.get_content_type() != 'application/json':
                raise CoinMetricsError('source_unavailable')
            body = response.read(250001)
    except (HTTPError, URLError, OSError, socket.timeout) as exc:
        raise CoinMetricsError('source_unavailable') from exc
    if len(body) > 250000:
        raise CoinMetricsError('source_too_large')
    return body


def latest(asset: str, *, get=fetch, now=None):
    # This explicit allowlist avoids guessing provider symbol identity.
    if asset not in ('btc', 'eth'):
        raise ValueError('supported Coin Metrics assets are btc and eth')
    url = BASE + '?' + urlencode({'assets': asset, 'metrics': 'PriceUSD', 'frequency': '1d', 'limit_per_asset': 1})
    payload = get(url)
    if len(payload) > 250000:
        raise CoinMetricsError('source_too_large')
    try:
        data = json.loads(payload)['data']
        if not isinstance(data, list) or len(data) != 1 or data[0]['asset'] != asset:
            raise ValueError('asset mismatch')
        value = Decimal(data[0]['PriceUSD'])
        if not value.is_finite() or value <= 0:
            raise ValueError('invalid price')
        observation = datetime.fromisoformat(data[0]['time'].replace('Z', '+00:00'))
        if observation.tzinfo is None:
            raise ValueError('missing timezone')
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise CoinMetricsError('invalid_response') from exc
    retrieved = now or datetime.now(timezone.utc)
    if retrieved.tzinfo is None or observation > retrieved:
        raise CoinMetricsError('invalid_source_time')
    # Observation is not a publication timestamp; only retrieval is proven availability.
    result = {'asset': asset, 'metric': 'PriceUSD', 'value': str(value), 'unit': 'USD',
              'observed_at': observation.isoformat(), 'available_at': retrieved.isoformat(),
              'retrieved_at': retrieved.isoformat(), 'published_at': None,
              'source_url': url, 'source_sha256': hashlib.sha256(payload).hexdigest(),
              'licence': 'Creative Commons BY-NC; Coin Metrics Community', 'licence_url': TERMS,
              'limitations': ['Daily provider aggregate, not an exchange execution price.',
                              'Availability before retrieval is unknown; revisions can occur.',
                              'Community data is noncommercial; permission required for commercial use.']}
    return result, payload


def capture(store, session_id: str, asset: str, *, get=fetch, permitted=None):
    if permitted is None:
        permitted = os.getenv('APLOMB_COINMETRICS_NONCOMMERCIAL') == '1'
    if not permitted:
        raise CoinMetricsError('licence_not_enabled')
    result, payload = latest(asset, get=get)
    owner = hashlib.sha256(session_id.encode()).hexdigest()
    pk, sk = 'COINMETRICS#' + owner, 'CAPTURE#' + result['source_sha256']
    record = {'revision': 1, 'sessionId': session_id, 'raw': payload.decode('utf-8'), 'result': result}
    try:
        store.transact([Write('cache', pk, sk, record, None)])
    except Conflict:
        old = store.get('cache', pk, sk)
        if old is None or old.get('raw') != record['raw'] or old.get('sessionId') != session_id:
            raise
        return old['result']
    return result
