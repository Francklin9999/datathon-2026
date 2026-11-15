"""Exact ISIN discovery in Wikidata: candidate assertions, not identity proof.

The query template is code-owned. External input never supplies SPARQL, labels,
URLs, redirect targets or headers. Current capture time is the sole supported
availability bound; community assertions may be wrong or outdated.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

from .entities import valid_isin

ENDPOINT = 'https://query.wikidata.org/sparql'
MAX_BYTES = 250_000
MAX_RESULTS = 20
TERMS = 'https://www.wikidata.org/wiki/Wikidata:Licensing'
PROJECT_CONTACT = 'Aplomb/0.1 (https://github.com/Francklin9999/datathon-2026)'


def source_contact(settings):
    """Use the real public project URL for local exploration when no contact is configured."""
    return settings.source_user_agent or (PROJECT_CONTACT if settings.environment == 'local' else None)


class WikidataError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def query_for_isin(isin: str) -> str:
    if not isinstance(isin, str) or not valid_isin(isin):
        raise ValueError('Valid exact ISIN with checksum required')
    # The checksum and structure validation prohibit quotes or SPARQL punctuation.
    return ('SELECT DISTINCT ?item ?isin WHERE { ?item <http://www.wikidata.org/prop/direct/P946> ?isin . '
            f'FILTER(?isin = "{isin}") }} LIMIT {MAX_RESULTS + 1}')


def fetch(url: str, *, contact: str) -> bytes:
    if not contact or len(contact) < 15 or not ('@' in contact or 'https://' in contact):
        raise WikidataError('contact_not_configured')
    try:
        request = Request(url, headers={'Accept': 'application/sparql-results+json',
                                       'User-Agent': contact, 'Accept-Encoding': 'identity'})
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            if response.status != 200 or response.headers.get_content_type() not in (
                'application/sparql-results+json', 'application/json'
            ):
                raise WikidataError('source_unavailable')
            payload = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        # Do not retry 429 or bypass service restrictions.
        raise WikidataError('rate_limited' if exc.code == 429 else 'source_unavailable') from exc
    except (URLError, OSError, TimeoutError) as exc:
        raise WikidataError('source_unavailable') from exc
    if len(payload) > MAX_BYTES:
        raise WikidataError('source_too_large')
    return payload


def candidates(isin: str, *, get=fetch, contact: str, now=None):
    query = query_for_isin(isin)
    url = ENDPOINT + '?' + urlencode({'query': query, 'format': 'json'})
    payload = get(url, contact=contact)
    if not isinstance(payload, bytes) or len(payload) > MAX_BYTES:
        raise WikidataError('invalid_response')
    try:
        body = json.loads(payload)
        rows = body['results']['bindings']
        if not isinstance(rows, list) or len(rows) > MAX_RESULTS + 1:
            raise ValueError('row bound')
        items, seen = [], set()
        for row in rows:
            item = row['item']
            binding = row['isin']
            uri = item['value']
            if (item['type'] != 'uri' or not re.fullmatch(r'http://www\.wikidata\.org/entity/Q[1-9][0-9]*', uri)
                or binding['type'] != 'literal' or binding['value'] != isin):
                raise ValueError('mismatched response')
            qid = uri.rsplit('/', 1)[-1]
            if qid in seen:
                raise ValueError('duplicate item')
            seen.add(qid)
            items.append({'item_id': qid, 'url': 'https://www.wikidata.org/wiki/' + qid,
                          'asserted_isin': isin, 'evidence_class': 'candidate'})
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise WikidataError('invalid_response') from exc
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('clock must be timezone-aware')
    stamp = stamp.astimezone(timezone.utc).isoformat()
    digest = hashlib.sha256(payload).hexdigest()
    return {'status': 'results' if items else 'no_results', 'isin': isin,
            'items': items[:MAX_RESULTS], 'partial': len(items) > MAX_RESULTS,
            'source_url': url, 'source_sha256': digest, 'dataset_version': 'sha256:' + digest,
            'licence': 'CC0 1.0 structured data', 'licence_url': TERMS,
            'published_at': None, 'available_at': stamp, 'retrieved_at': stamp,
            'limitations': ['Wikidata community assertions are candidates, not proven issuer or security identities.',
                            'Availability before this capture and completeness of coverage are unknown.',
                            'Independent primary-source checks are required before financial use.']}, payload


def capture(store, session_id: str, isin: str, *, contact: str, get=fetch, now=None):
    result, payload = candidates(isin, contact=contact, get=get, now=now)
    owner = hashlib.sha256(session_id.encode()).hexdigest()
    pk = 'WIKIDATA#' + owner
    # Source parameters and content are both part of the capture identity.
    sk = 'CAPTURE#' + hashlib.sha256((isin + result['source_sha256']).encode()).hexdigest()
    record = {'revision': 1, 'sessionId': session_id, 'raw': payload.decode('utf-8'), 'result': result}
    try:
        store.transact([Write('cache', pk, sk, record, None)])
    except Conflict:
        old = store.get('cache', pk, sk)
        if old is None or old.get('raw') != record['raw'] or old.get('sessionId') != session_id or old['result']['isin'] != isin:
            raise WikidataError('capture_integrity_error')
        return old['result']
    return result
