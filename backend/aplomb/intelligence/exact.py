"""Bounded GLEIF exact ISIN/LEI proof; names and search results cannot establish links."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from .entities import Evidence, Relationship, valid_isin, valid_lei
from .gleif import BASE, MAX_BYTES, GLEIFError, _fetch


def exact_pair(isin: str, lei: str, *, fetch=_fetch, max_pages: int = 5, now=None):
    """Return a direct, current captured relationship only after inspecting the exact pair.

    GLEIF's related-resource endpoint can ignore the ISIN filter, so pagination is
    deliberate and bounded. An incomplete search never asserts the pair does not exist.
    The capture date is the earliest supported availability, not first publication.
    """
    if not valid_isin(isin) or not valid_lei(lei):
        raise ValueError('Valid ISIN and LEI checksums are required')
    if type(max_pages) is not int or not 1 <= max_pages <= 5:
        raise ValueError('max_pages must be between 1 and 5')
    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError('clock must be timezone-aware')
    for page in range(1, max_pages + 1):
        url = f'{BASE}/{lei}/isins?' + urlencode({'page[size]': 200, 'page[number]': page})
        payload = fetch(url)
        if len(payload) > MAX_BYTES:
            raise GLEIFError('response_too_large')
        try:
            body = json.loads(payload)
            rows, meta = body['data'], body['meta']['pagination']
            if not isinstance(rows, list) or len(rows) > 200 or meta['currentPage'] != page:
                raise ValueError('bad pagination')
            last = meta['lastPage']
            if type(last) is not int or last < 1:
                raise ValueError('bad page count')
            matches = [r for r in rows if r['attributes']['isin'] == isin
                       and r['attributes']['lei'] == lei]
        except (ValueError, KeyError, TypeError) as exc:
            raise GLEIFError('invalid_response') from exc
        if matches:
            stamp = now or datetime.now(timezone.utc)
            evidence = Evidence(source_id='entity_gleif_isin_lei', url=url,
                content_sha256=hashlib.sha256(payload).hexdigest(), available_at=stamp,
                retrieved_at=stamp, licence='GLEIF data terms; ANNA mapping limitations apply',
                limitations=('Capture time is not the first publication date.',
                             'ISIN/LEI is issuer mapping, not listing, ownership or financial exposure.'))
            relation = Relationship(subject_id='isin:' + isin, relation='SECURITY_ISSUED_BY',
                object_id='lei:' + lei, evidence_class='direct', valid_from=stamp.date(), evidence=evidence)
            return {'status': 'verified_pair', 'relationship': relation.model_dump(mode='json'),
                    'pages_inspected': page}, payload
        if page >= last:
            return {'status': 'not_found_in_capture', 'pages_inspected': page,
                    'limitations': ['A missing row does not prove that no relationship exists.']}, None
    return {'status': 'search_incomplete', 'pages_inspected': max_pages,
            'limitations': ['Page limit reached; relationship remains unknown.']}, None


def capture_pair(store, session_id: str, isin: str, lei: str, *, fetch=_fetch):
    """Persist the verified raw page immutably under a session-owned partition."""
    from aplomb.api.errors import Conflict
    from aplomb.api.storage import Write

    result, payload = exact_pair(isin, lei, fetch=fetch)
    if payload is not None:
        owner = hashlib.sha256(session_id.encode()).hexdigest()
        pk = 'ENTITY_PAIR#' + owner
        digest = hashlib.sha256(payload).hexdigest()
        sk = 'CAPTURE#' + digest
        record = {'revision': 1, 'sessionId': session_id, 'raw': payload.decode('utf-8'),
                  'relationship': result['relationship']}
        try:
            store.transact([Write('cache', pk, sk, record, None)])
        except Conflict:
            old = store.get('cache', pk, sk)
            # Same source payload may be re-observed later; keep first immutable capture.
            if old is None or old.get('raw') != record['raw'] or old.get('sessionId') != session_id:
                raise
            result['relationship'] = old['relationship']
    return result


def captured_pairs_as_of(store, session_id: str, isin: str, as_of, *, lei=None):
    """Only inspect same-session verified pair pages captured by the requested date."""
    from datetime import time

    owner = hashlib.sha256(session_id.encode()).hexdigest()
    records = store.query('cache', 'ENTITY_PAIR#' + owner)
    if len(records) > 5000:
        raise GLEIFError('capture_limit_exceeded')
    cutoff = datetime.combine(as_of, time.max, tzinfo=timezone.utc)
    result = []
    for item in records:
        if item.get('sessionId') != session_id:
            raise GLEIFError('capture_owner_mismatch')
        try:
            rel = Relationship.model_validate(item['relationship'])
            raw = item['raw'].encode('utf-8')
            if hashlib.sha256(raw).hexdigest() != rel.evidence.content_sha256:
                raise ValueError('source hash mismatch')
            rows = json.loads(raw)['data']
            if not isinstance(rows, list) or not any(
                row.get('attributes', {}).get('isin') == rel.subject_id.removeprefix('isin:')
                and row.get('attributes', {}).get('lei') == rel.object_id.removeprefix('lei:')
                for row in rows if isinstance(row, dict)
            ):
                raise ValueError('captured source does not support pair')
        except (KeyError, TypeError, ValueError) as exc:
            raise GLEIFError('capture_integrity_failure') from exc
        if (rel.subject_id == 'isin:' + isin and rel.evidence.available_at <= cutoff
                and rel.evidence.retrieved_at <= cutoff and (not lei or rel.object_id == 'lei:' + lei)):
            result.append(rel)
    return result
