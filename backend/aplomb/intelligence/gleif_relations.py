"""GLEIF Level 2 ("who owns whom") capture for one exact LEI.

Only the official public endpoints under https://api.gleif.org/api/v1/lei-records are used
(CC0 data). Every returned record is inspected: a relationship row is kept only when its own
start/end node equals the LEI we asked about, whatever filter or path produced it. A missing
record (HTTP 404) is reported as "none published", which is not the same as "no parent": GLEIF
also publishes explicit reporting exceptions ("not reported: <reason>"), shown verbatim.

Availability is the capture time. The golden-copy publish date that GLEIF puts in each response
is kept as the documented publication time; neither is a claim about when a relationship was
first knowable before this capture.
"""
from __future__ import annotations

import hashlib
import json
import socket
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .entities import valid_lei
from .gleif import BASE, MAX_BYTES, TERMS, GLEIFError

LICENCE = 'CC0 1.0 (GLEIF LEI data)'
PAGE_SIZE = 100
NAME_CHUNK = 100
MAX_NAME_CHUNKS = 2
EXCEPTION_CATEGORIES = {'DIRECT_ACCOUNTING_CONSOLIDATION_PARENT', 'ULTIMATE_ACCOUNTING_CONSOLIDATION_PARENT'}
RELATION_TYPES = {'direct': 'IS_DIRECTLY_CONSOLIDATED_BY', 'ultimate': 'IS_ULTIMATELY_CONSOLIDATED_BY'}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_status(url: str) -> tuple[int, bytes]:
    """GET one GLEIF URL. Returns (200, body) or (404, b''); anything else is unavailable."""
    request = Request(url, headers={'Accept': 'application/vnd.api+json',
                                    'User-Agent': 'Aplomb research (GLEIF Level 2 reader)'})
    try:
        with build_opener(_NoRedirect).open(request, timeout=12) as response:
            if response.status != 200:
                raise GLEIFError('source_unavailable')
            if response.headers.get_content_type() not in ('application/vnd.api+json', 'application/json'):
                raise GLEIFError('unsupported_content_type')
            body = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 404:
            return 404, b''
        raise GLEIFError('source_unavailable') from exc
    except (URLError, OSError, socket.timeout) as exc:
        raise GLEIFError('source_unavailable') from exc
    if len(body) > MAX_BYTES:
        raise GLEIFError('response_too_large')
    return 200, body


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _text(value, limit: int = 300) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('invalid text field')
    return value


def _date(value) -> str | None:
    """GLEIF timestamps like 2023-05-17T00:00:00Z -> ISO date; anything else rejected."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('invalid date')
    return datetime.fromisoformat(value.replace('Z', '+00:00')).date().isoformat()


def _entity(row: dict) -> dict:
    lei = row['id']
    if not isinstance(lei, str) or not valid_lei(lei) or row.get('type') != 'lei-records':
        raise ValueError('invalid LEI record')
    attributes = row['attributes']
    entity, registration = attributes['entity'], attributes.get('registration') or {}
    if attributes.get('lei') not in (None, lei):
        raise ValueError('record id and lei differ')
    return {'lei': lei, 'legal_name': _text(entity['legalName']['name']),
            'jurisdiction': _text(entity.get('jurisdiction'), 20),
            'entity_status': _text(entity.get('status'), 40),
            'registration_status': _text(registration.get('status'), 40),
            'record_url': f'{BASE}/{lei}'}


def _relationship(row: dict, kind: str, *, start: str | None = None, end: str | None = None) -> dict:
    """Parse and check one relationship record against the node we asked about."""
    if row.get('type') != 'relationship-records':
        raise ValueError('not a relationship record')
    attributes = row['attributes']
    rel = attributes['relationship']
    start_node, end_node = rel['startNode'], rel['endNode']
    if start_node.get('type') != 'LEI' or end_node.get('type') != 'LEI':
        raise ValueError('non-LEI relationship node')
    child, parent = start_node['id'], end_node['id']
    if not (isinstance(child, str) and valid_lei(child) and isinstance(parent, str) and valid_lei(parent)):
        raise ValueError('invalid relationship LEI')
    if child == parent:
        raise ValueError('self relationship')
    if rel['type'] != RELATION_TYPES[kind]:
        raise ValueError('unexpected relationship type')
    if (start is not None and child != start) or (end is not None and parent != end):
        raise ValueError('relationship does not involve the requested LEI')
    periods = rel.get('periods') or []
    if not isinstance(periods, list) or len(periods) > 20:
        raise ValueError('invalid periods')
    relationship_period = next((p for p in periods if p.get('type') == 'RELATIONSHIP_PERIOD'), None)
    other_periods = [{'type': _text(p.get('type'), 60), 'start': _date(p.get('startDate')),
                      'end': _date(p.get('endDate'))} for p in periods if p is not relationship_period]
    registration = attributes.get('registration') or {}
    record_id = row.get('id')
    if not isinstance(record_id, str) or len(record_id) > 300:
        raise ValueError('invalid relationship record id')
    return {'record_id': record_id, 'kind': kind, 'gleif_type': rel['type'],
            'child_lei': child, 'parent_lei': parent,
            'relationship_status': _text(rel.get('status'), 40),
            'period_start': _date(relationship_period.get('startDate')) if relationship_period else None,
            'period_end': _date(relationship_period.get('endDate')) if relationship_period else None,
            'other_periods': other_periods,
            'record_valid_from': _date(attributes.get('validFrom')),
            'record_valid_to': _date(attributes.get('validTo')),
            'registration_status': _text(registration.get('status'), 40),
            'corroboration_level': _text(registration.get('corroborationLevel'), 60),
            'corroboration_documents': _text(registration.get('corroborationDocuments'), 80),
            'initial_registration_date': _date(registration.get('initialRegistrationDate')),
            'last_update_date': _date(registration.get('lastUpdateDate'))}


def _exception(row: dict, lei: str, category: str) -> dict:
    attributes = row['attributes']
    if row.get('type') != 'reporting-exceptions' or attributes.get('lei') != lei:
        raise ValueError('reporting exception for another LEI')
    if attributes.get('category') != category or category not in EXCEPTION_CATEGORIES:
        raise ValueError('unexpected exception category')
    reason = attributes.get('reason')
    if not isinstance(reason, str) or not reason or len(reason) > 80:
        raise ValueError('invalid exception reason')
    reference = attributes.get('reference')
    return {'category': category, 'reason': reason,
            'reference': _text(reference) if isinstance(reference, str) else None}


class L2Reader:
    """Bounded reader for one LEI; collects every raw payload it relied on."""

    def __init__(self, lei: str, *, fetch=fetch_status, max_pages: int = 2, now=None):
        lei = lei.strip().upper()
        if not valid_lei(lei):
            raise ValueError('A valid LEI checksum is required')
        if type(max_pages) is not int or not 1 <= max_pages <= 5:
            raise ValueError('max_pages must be between 1 and 5')
        stamp = now or datetime.now(timezone.utc)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError('clock must be timezone-aware')
        self.lei, self.fetch, self.max_pages = lei, fetch, max_pages
        self.retrieved_at = stamp.astimezone(timezone.utc)
        self.captures: list[dict] = []
        self.payloads: dict[str, bytes] = {}
        self.rejected = 0
        self.published_at: str | None = None

    def _get(self, path: str, params: dict | None = None) -> dict | None:
        url = (f'{BASE}/{path}' if path else BASE) + ('?' + urlencode(params) if params else '')
        status, payload = self.fetch(url)
        if status == 404:
            self.captures.append({'url': url, 'http_status': 404, 'sha256': None, 'bytes': 0})
            return None
        if status != 200 or len(payload) > MAX_BYTES:
            raise GLEIFError('source_unavailable')
        try:
            body = json.loads(payload)
            if not isinstance(body, dict) or 'data' not in body:
                raise ValueError('missing data')
        except ValueError as exc:
            raise GLEIFError('invalid_response') from exc
        digest = hashlib.sha256(payload).hexdigest()
        self.payloads[digest] = payload
        published = ((body.get('meta') or {}).get('goldenCopy') or {}).get('publishDate')
        if isinstance(published, str) and len(published) <= 40:
            self.published_at = self.published_at or published
        self.captures.append({'url': url, 'http_status': 200, 'sha256': digest, 'bytes': len(payload),
                              'golden_copy_published_at': published if isinstance(published, str) else None})
        return body

    def _provenance(self) -> dict:
        last = self.captures[-1]
        return {'source_url': last['url'], 'source_sha256': last['sha256'],
                'source_published_at': last.get('golden_copy_published_at')}

    def _single(self, path: str, parse):
        body = self._get(path)
        if body is None:
            return None
        try:
            return parse(body['data'])
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise GLEIFError('invalid_response') from exc

    def _parent(self, kind: str) -> dict:
        record = self._single(f'{self.lei}/{kind}-parent-relationship',
                              lambda d: _relationship(d, kind, start=self.lei))
        if record is not None:
            record.update(self._provenance())
            return {'state': 'reported', 'relationship': record, 'exception': None}
        category = f'{kind.upper()}_ACCOUNTING_CONSOLIDATION_PARENT'
        exception = self._single(f'{self.lei}/{kind}-parent-reporting-exception',
                                 lambda d: _exception(d, self.lei, category))
        if exception is not None:
            exception.update(self._provenance())
            return {'state': 'exception', 'relationship': None, 'exception': exception}
        return {'state': 'none_published', 'relationship': None, 'exception': None}

    def _children(self, kind: str) -> dict:
        items, total, pages = [], None, 0
        for page in range(1, self.max_pages + 1):
            body = self._get(f'{self.lei}/{kind}-child-relationships',
                             {'page[size]': PAGE_SIZE, 'page[number]': page})
            if body is None:
                total = 0
                break
            try:
                rows, meta = body['data'], body['meta']['pagination']
                if not isinstance(rows, list) or len(rows) > PAGE_SIZE or meta['currentPage'] != page:
                    raise ValueError('bad pagination')
                total, last = meta['total'], meta['lastPage']
                if type(total) is not int or type(last) is not int or total < 0:
                    raise ValueError('bad totals')
            except (KeyError, TypeError, ValueError) as exc:
                raise GLEIFError('invalid_response') from exc
            pages = page
            provenance = self._provenance()
            for row in rows:
                try:
                    items.append({**_relationship(row, kind, end=self.lei), **provenance})
                except (KeyError, TypeError, ValueError, AttributeError):
                    self.rejected += 1  # never trust that the path filtered to our LEI
            if page >= last:
                break
        unique = {r['record_id']: r for r in items}
        items = list(unique.values())
        return {'items': items, 'total_reported_by_source': total or 0, 'pages_inspected': pages,
                'truncated': bool(total and total > len(items))}

    def _names(self, leis: list[str]) -> dict[str, dict]:
        """Batch entity lookup; only rows whose id we asked for are accepted."""
        names: dict[str, dict] = {}
        wanted = list(dict.fromkeys(leis))[:NAME_CHUNK * MAX_NAME_CHUNKS]
        for start in range(0, len(wanted), NAME_CHUNK):
            chunk = wanted[start:start + NAME_CHUNK]
            body = self._get('', {'filter[lei]': ','.join(chunk), 'page[size]': NAME_CHUNK})
            rows = (body or {}).get('data') or []
            if not isinstance(rows, list):
                raise GLEIFError('invalid_response')
            for row in rows:
                try:
                    entity = _entity(row)
                except (KeyError, TypeError, ValueError, AttributeError):
                    self.rejected += 1
                    continue
                if entity['lei'] in chunk:
                    names[entity['lei']] = entity
                else:
                    self.rejected += 1
        return names

    def read(self) -> dict:
        subject = self._single(self.lei, _entity)
        if subject is None:
            return self._result({'status': 'lei_not_found', 'lei': self.lei, 'entity': None})
        if subject['lei'] != self.lei:
            raise GLEIFError('invalid_response')
        direct, ultimate = self._parent('direct'), self._parent('ultimate')
        direct_children, ultimate_children = self._children('direct'), self._children('ultimate')
        related = [p['relationship']['parent_lei'] for p in (direct, ultimate) if p['relationship']]
        related += [r['child_lei'] for r in direct_children['items'] + ultimate_children['items']]
        names = self._names(related) if related else {}
        for part in (direct, ultimate):
            if part['relationship']:
                part['parent'] = names.get(part['relationship']['parent_lei'])
        for group in (direct_children, ultimate_children):
            for item in group['items']:
                item['child'] = names.get(item['child_lei'])
        return self._result({'status': 'captured', 'lei': self.lei, 'entity': subject,
                             'direct_parent': direct, 'ultimate_parent': ultimate,
                             'direct_children': direct_children, 'ultimate_children': ultimate_children,
                             'names_resolved': len(names), 'names_requested': len(set(related))})

    def _result(self, body: dict) -> dict:
        retrieved = _iso(self.retrieved_at)
        limitations = [
            'Capture time is the earliest availability asserted; earlier knowability is not claimed.',
            'GLEIF Level 2 reports accounting consolidation, not economic ownership percentage or control.',
            'No published record (HTTP 404) does not prove that no parent or child exists.',
            f'Children are read up to {self.max_pages} page(s) of {PAGE_SIZE}; larger groups are marked truncated.',
        ]
        if body.get('names_requested', 0) > body.get('names_resolved', 0):
            limitations.append('Some related entity names were not fetched; their LEIs remain exact.')
        return {**body, 'rejected_rows': self.rejected,
                'source': {'provider': 'GLEIF', 'licence': LICENCE, 'licence_url': TERMS,
                           'retrieved_at': retrieved, 'available_at': retrieved,
                           'golden_copy_published_at': self.published_at,
                           'captures': self.captures},
                'limitations': limitations}


def read_l2(lei: str, *, fetch=fetch_status, max_pages: int = 2, now=None) -> tuple[dict, dict[str, bytes]]:
    reader = L2Reader(lei, fetch=fetch, max_pages=max_pages, now=now)
    result = reader.read()
    return result, reader.payloads


def capture_l2(store, session_id: str, lei: str, *, fetch=fetch_status, max_pages: int = 2, now=None) -> dict:
    """Read (or reuse today's) Level 2 capture and persist raw payloads immutably per session.

    A same-day capture already held by this session is reused instead of calling GLEIF again;
    the reused result keeps its original retrieval time and hashes.
    """
    from aplomb.api.errors import Conflict
    from aplomb.api.storage import Write

    lei = lei.strip().upper()
    if not valid_lei(lei):
        raise ValueError('A valid LEI checksum is required')
    owner = hashlib.sha256(session_id.encode()).hexdigest()
    pk = 'GLEIF_L2#' + owner
    day = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()
    bundle_sk = f'BUNDLE#{lei}#{max_pages}#{day}'
    existing = store.get('cache', pk, bundle_sk)
    if existing is not None and existing.get('sessionId') == session_id:
        _verify_bundle(store, session_id, existing['result'])
        return {**existing['result'], 'reused_capture': True}
    result, payloads = read_l2(lei, fetch=fetch, max_pages=max_pages, now=now)
    for digest, payload in payloads.items():
        record = {'revision': 1, 'sessionId': session_id, 'raw': payload.decode('utf-8'), 'sha256': digest}
        try:
            store.transact([Write('cache', pk, 'CAPTURE#' + digest, record, None)])
        except Conflict:
            old = store.get('cache', pk, 'CAPTURE#' + digest)
            if old is None or old.get('raw') != record['raw'] or old.get('sessionId') != session_id:
                raise
    try:
        store.transact([Write('cache', pk, bundle_sk,
                              {'revision': 1, 'sessionId': session_id, 'result': result}, None)])
    except Conflict:
        old = store.get('cache', pk, bundle_sk)
        if old is None or old.get('sessionId') != session_id:
            raise
        _verify_bundle(store, session_id, old['result'])
        return {**old['result'], 'reused_capture': True}
    return {**result, 'reused_capture': False}


def stored_payload(store, session_id: str, digest: str) -> bytes | None:
    """Return a raw payload this session captured, or None (no cross-session reads)."""
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        return None
    owner = hashlib.sha256(session_id.encode()).hexdigest()
    # Level 2 pages, then exact ISIN/LEI pair pages captured by exact.capture_pair.
    for partition in ('GLEIF_L2#', 'ENTITY_PAIR#'):
        item = store.get('cache', partition + owner, 'CAPTURE#' + digest)
        if item and item.get('sessionId') == session_id:
            raw = item['raw'].encode('utf-8')
            if hashlib.sha256(raw).hexdigest() == digest:
                return raw
    return None


def _verify_bundle(store, session_id, result):
    """A cached bundle is usable only while all its source payloads still match."""
    for capture in (result.get('source') or {}).get('captures', []):
        digest = capture.get('sha256')
        if digest and stored_payload(store, session_id, digest) is None:
            raise GLEIFError('capture_integrity_failure')


def captured_l2_as_of(store, session_id: str, lei: str, as_of):
    """Find the newest same-session captured bundle available by end-of-day UTC."""
    from datetime import time

    owner = hashlib.sha256(session_id.encode()).hexdigest()
    rows = store.query('cache', 'GLEIF_L2#' + owner)
    if len(rows) > 5000:
        raise GLEIFError('capture_limit_exceeded')
    cutoff = datetime.combine(as_of, time.max, tzinfo=timezone.utc)
    candidates = []
    for row in rows:
        if row.get('sessionId') != session_id:
            raise GLEIFError('capture_owner_mismatch')
        result = row.get('result')
        if not isinstance(result, dict) or result.get('lei') != lei:
            continue
        try:
            retrieved = datetime.fromisoformat(result['source']['retrieved_at'].replace('Z', '+00:00'))
            available = datetime.fromisoformat(result['source']['available_at'].replace('Z', '+00:00'))
            if retrieved.tzinfo is None or available.tzinfo is None:
                raise ValueError('timezone missing')
        except (KeyError, TypeError, ValueError) as exc:
            raise GLEIFError('invalid_capture_time') from exc
        if retrieved <= cutoff and available <= cutoff:
            _verify_bundle(store, session_id, result)
            candidates.append((retrieved, result))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def isin_candidates(isin: str, *, fetch=fetch_status, limit: int = 5) -> tuple[list[str], dict | None, bytes | None]:
    """LEIs GLEIF returns for an ISIN filter: candidates only, to be proven by an exact pair check."""
    from .entities import valid_isin

    isin = isin.strip().upper()
    if not valid_isin(isin):
        raise ValueError('A valid ISIN checksum is required')
    url = BASE + '?' + urlencode({'filter[isin]': isin, 'page[size]': limit})
    status, payload = fetch(url)
    if status == 404:
        return [], {'url': url, 'http_status': 404, 'sha256': None, 'bytes': 0}, None
    try:
        rows = json.loads(payload)['data']
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('invalid result size')
        leis = [r['id'] for r in rows if isinstance(r.get('id'), str) and valid_lei(r['id'])]
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise GLEIFError('invalid_response') from exc
    capture = {'url': url, 'http_status': 200, 'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}
    return list(dict.fromkeys(leis)), capture, payload
