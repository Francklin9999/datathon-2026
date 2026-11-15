"""No-key exact ISIN-to-FIGI mapping. No ticker search or licensed CUSIP requests.

Official docs allow unauthenticated access (25 mapping requests/minute); the local
route is stricter. FIGIs and descriptions are provider assertions, not issuer proof.
"""

import hashlib
import json
import re
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import APIRouter, Depends, Query

from aplomb.api.errors import Conflict, ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter
from aplomb.api.storage import Write

from .entities import Evidence, valid_isin
from .master import IdentifierAssertion
from .master_repository import InstrumentRepository

ENDPOINT = 'https://api.openfigi.com/v3/mapping'
DOCS = 'https://www.openfigi.com/api/documentation'
TERMS = 'https://www.openfigi.com/docs/terms-of-service'
MAX_BYTES = 750_000
_lock = threading.Lock()
_last_request = 0.0


class OpenFIGIError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_job(isin, mic=None):
    if not isinstance(isin, str) or not valid_isin(isin):
        raise ValueError('Valid exact ISIN checksum required')
    if mic is not None and (not isinstance(mic, str) or not re.fullmatch(r'[A-Z0-9]{4}', mic)):
        raise ValueError('MIC must have four uppercase alphanumeric characters')
    job = {'idType': 'ID_ISIN', 'idValue': isin, 'includeUnlistedEquities': True}
    if mic:
        job['micCode'] = mic
    return job


def fetch(job):
    global _last_request
    # Accountless service limit is IP-scoped. Space this process's requests; HTTP 429
    # is reported without retry. Distributed quotas remain the provider's authority.
    with _lock:
        if time.monotonic() - _last_request < 3:
            raise OpenFIGIError('local_rate_limited')
        _last_request = time.monotonic()
    body = json.dumps([job], separators=(',', ':')).encode()
    req = Request(ENDPOINT, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': 'Aplomb exact identifier research'})
    try:
        with build_opener(NoRedirect).open(req, timeout=12) as response:
            if response.status != 200 or response.headers.get_content_type() != 'application/json':
                raise OpenFIGIError('source_unavailable')
            raw = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        code = 'rate_limited' if exc.code == 429 else 'source_access_denied' if exc.code in (401, 403) else 'source_unavailable'
        raise OpenFIGIError(code) from exc
    except (URLError, OSError, TimeoutError) as exc:
        raise OpenFIGIError('source_unavailable') from exc
    if len(raw) > MAX_BYTES:
        raise OpenFIGIError('source_too_large')
    return raw


def valid_figi(value):
    if not isinstance(value, str) or not re.fullmatch(r'[B-DF-HJ-NP-TV-Z]{2}G[B-DF-HJ-NP-TV-Z0-9]{8}[0-9]', value):
        return False
    total = 0
    for index, character in enumerate(value[:11]):
        number = int(character) if character.isdigit() else ord(character) - 55
        number *= 2 if index % 2 else 1
        total += number // 10 + number % 10
    return (-total) % 10 == int(value[-1])


def parse(payload):
    if not isinstance(payload, bytes) or len(payload) > MAX_BYTES:
        raise OpenFIGIError('source_too_large')
    try:
        data = json.loads(payload)
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise ValueError()
        job = data[0]
        if 'error' in job:
            raise OpenFIGIError('mapping_job_error')
        if 'warning' in job and 'data' not in job:
            return []
        rows = job['data']
        if not isinstance(rows, list) or len(rows) > 1000:
            raise ValueError()
        result, seen = [], set()
        for row in rows:
            if not isinstance(row, dict) or not valid_figi(row.get('figi')) or row['figi'] in seen:
                raise ValueError()
            seen.add(row['figi'])
            item = {'figi': row['figi']}
            for key in ('shareClassFIGI', 'compositeFIGI'):
                value = row.get(key)
                if value is not None and not valid_figi(value):
                    raise ValueError()
                item[key] = value
            for key in ('ticker', 'name', 'exchCode', 'securityType', 'securityType2', 'marketSector', 'securityDescription'):
                value = row.get(key)
                if value is not None and (not isinstance(value, str) or len(value) > 500):
                    raise ValueError()
                item[key] = value
            result.append(item)
        return result
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        if isinstance(exc, OpenFIGIError):
            raise
        raise OpenFIGIError('invalid_source_response') from exc


def capture(store, sid, isin, mic=None, *, get=fetch, now=None):
    job = request_job(isin, mic)
    raw = get(job)
    rows = parse(raw)
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError('Timezone-aware capture timestamp required')
    digest = hashlib.sha256(raw).hexdigest()
    query_hash = hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()
    owner = 'OPENFIGI#' + hashlib.sha256(sid.encode()).hexdigest()
    key = 'CAPTURE#' + query_hash + '#' + digest
    result = {'status': 'available' if rows else 'no_mapping_in_response', 'isin': isin,
              'requested_mic_filter': mic, 'mappings': rows, 'source_url': ENDPOINT,
              'source_sha256': digest, 'dataset_version': 'openfigi-' + query_hash[:12] + '-' + digest[:12],
              'observed_at': None, 'published_at': None, 'available_at': stamp.isoformat(),
              'retrieved_at': stamp.isoformat(), 'documentation_url': DOCS, 'terms_url': TERMS,
              'licence': 'FIGI identifiers public-domain dedication; associated metadata MIT per OpenFIGI',
              'limitations': ['Exact provider mapping, not issuer ownership or economic exposure.',
                              'One ISIN can return multiple instrument, composite and share-class FIGIs.',
                              'Provider exchange codes are not automatically ISO MICs.',
                              'Availability before capture and original listing lifecycle are unknown.',
                              'No CUSIP inputs or licensed CUSIP crosswalks are used.']}
    record = {'revision': 1, 'sessionId': sid, 'request': job, 'raw': raw.decode('utf-8'), 'result': result}
    try:
        store.transact([Write('cache', owner, key, record, None)])
    except Conflict:
        prior = store.get('cache', owner, key)
        if not prior or prior.get('raw') != record['raw'] or prior.get('request') != job or prior.get('sessionId') != sid:
            raise OpenFIGIError('capture_integrity_failure') from None
        result = prior['result']
    evidence = Evidence(source_id='security_openfigi_mapping', url=ENDPOINT,
                        content_sha256=digest,
                        available_at=datetime.fromisoformat(result['available_at']),
                        retrieved_at=datetime.fromisoformat(result['retrieved_at']),
                        licence=result['licence'], limitations=tuple(result['limitations']))
    assertions = [IdentifierAssertion(subject='isin:' + isin, scheme='provider_asset_id',
                                     value='openfigi:' + row['figi'], role='provider_asset',
                                     evidence_class='direct', origin='openfigi_exact_isin_mapping', evidence=evidence)
                  for row in rows]
    repository = InstrumentRepository(store, sid)
    published = []
    for offset in range(0, len(assertions), 200):
        published.extend(repository.publish_assertions(assertions[offset:offset + 200], source_bytes=raw, rights_confirmed=True))
    return {**result, 'published_assertion_ids': published}


def openfigi_router(store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/intelligence/openfigi')
    def mapping(isin: str = Query(min_length=12, max_length=12),
                mic: str | None = Query(default=None, min_length=4, max_length=4),
                sid: str = Depends(session_dependency)):
        try:
            request_job(isin, mic)
            limiter.take(sid, 'openfigi', 4, 60)
            return capture(store, sid, isin, mic)
        except OpenFIGIError as exc:
            raise unavailable('OpenFIGI mapping (' + str(exc) + ')') from exc
        except ValueError as exc:
            raise ServiceError('validation_error', 'Valid exact ISIN and optional MIC required') from exc

    return router
