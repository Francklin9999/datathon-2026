"""Alternative.me Bitcoin Fear & Greed observations, not forecasts or trade signals.

The provider permits reuse including commercial display when attribution is prominent
next to the data. The timestamp labels a provider index day; it is not proof of the
publication time of a historical vintage. Only capture time proves availability here.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

SOURCE = 'https://api.alternative.me/fng/?limit=30'
TERMS = 'https://alternative.me/crypto/fear-and-greed-index/'
MAX_BYTES = 100_000
CLASSES = frozenset({'Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed'})


class SentimentError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch():
    request = Request(SOURCE, headers={'Accept': 'application/json', 'User-Agent': 'Aplomb Research'})
    try:
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            if response.status != 200 or response.headers.get_content_type() != 'application/json':
                raise SentimentError('source_unavailable')
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise SentimentError('source_unavailable') from exc
    if len(raw) > MAX_BYTES:
        raise SentimentError('source_too_large')
    return raw


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def normalize(raw: bytes, now: datetime):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES or now.tzinfo is None:
        raise SentimentError('invalid_response')
    try:
        payload = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if payload['name'] != 'Fear and Greed Index' or payload['metadata']['error'] is not None:
            raise ValueError('unexpected provider metadata')
        rows = payload['data']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 30:
            raise ValueError('unexpected rows')
        result, seen = [], set()
        for row in rows:
            val, timestamp, classification = row['value'], row['timestamp'], row['value_classification']
            if not isinstance(val, str) or not re.fullmatch(r'(?:0|[1-9][0-9]?|100)', val):
                raise ValueError('invalid score')
            if not isinstance(timestamp, str) or not re.fullmatch(r'[0-9]{1,11}', timestamp):
                raise ValueError('invalid timestamp')
            if classification not in CLASSES:
                raise ValueError('invalid classification')
            observed = datetime.fromtimestamp(int(timestamp), timezone.utc)
            if observed > now or observed in seen:
                raise ValueError('future or duplicate index day')
            seen.add(observed)
            result.append({'value': int(val), 'unit': 'index points (0–100)',
                           'classification': classification, 'observed_at': observed.isoformat()})
        result.sort(key=lambda row: row['observed_at'], reverse=True)
        return result
    except (ValueError, OverflowError, OSError, TypeError, KeyError, UnicodeError) as exc:
        raise SentimentError('invalid_response') from exc


def capture(store, session_id: str, *, get=fetch, clock=lambda: datetime.now(timezone.utc)):
    raw = get()
    retrieved = clock()
    observations = normalize(raw, retrieved)
    digest = hashlib.sha256(raw).hexdigest()
    owner = hashlib.sha256(session_id.encode()).hexdigest()
    source = {'url': SOURCE, 'sha256': digest, 'retrieved_at': retrieved.isoformat(),
              'available_at': retrieved.isoformat(), 'published_at': None,
              'dataset_version': 'sentiment-' + digest[:20], 'provider': 'Alternative.me',
              'terms_url': TERMS, 'attribution': 'Data from Alternative.me — Crypto Fear & Greed Index',
              'licence': 'Provider API reuse terms; prominent adjacent attribution required'}
    result = {'status': 'available', 'asset': 'BTC', 'observations': observations, 'source': source,
              'limitations': ['Provider sentiment index and methodology, not a forecast or recommendation.',
                              'The provider describes its current index as Bitcoin-only.',
                              'Historical rows were captured today; original publication and revision times are unknown.']}
    item = {'revision': 1, 'sessionId': session_id, 'raw': raw.decode('utf-8'), 'result': result}
    pk, sk = 'SENTIMENT#' + owner, 'CAPTURE#' + digest
    try:
        store.transact([Write('cache', pk, sk, item, None)])
    except Conflict:
        saved = store.get('cache', pk, sk)
        if not saved or saved.get('sessionId') != session_id or saved.get('raw') != item['raw']:
            raise SentimentError('capture_integrity_failure')
        return saved['result']
    return result
