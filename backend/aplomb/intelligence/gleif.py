"""Bounded read-only GLEIF API discovery, with captured provenance.

Names return candidates, never security/entity links. GLEIF access data is CC0; data revisions
and source availability are distinct from a record's legal registration date.
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

BASE = 'https://api.gleif.org/api/v1/lei-records'
TERMS = 'https://www.gleif.org/en/meta/lei-data-terms-of-use'
MAX_BYTES = 2_000_000


class GLEIFError(RuntimeError):
    """A bounded lookup failed; callers must return an explicit unavailable state."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(url: str) -> bytes:
    request = Request(url, headers={'Accept': 'application/vnd.api+json',
                                    'User-Agent': 'Aplomb research https://github.com/Francklin9999/datathon-2026'})
    try:
        with build_opener(_NoRedirect).open(request, timeout=12) as response:
            if response.status != 200:
                raise GLEIFError('source_unavailable')
            if response.headers.get_content_type() not in ('application/vnd.api+json', 'application/json'):
                raise GLEIFError('unsupported_content_type')
            body = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, OSError, socket.timeout) as exc:
        raise GLEIFError('source_unavailable') from exc
    if len(body) > MAX_BYTES:
        raise GLEIFError('response_too_large')
    return body


class GLEIFClient:
    def __init__(self, fetch=_fetch, clock=lambda: datetime.now(timezone.utc), capture=None):
        self.fetch = fetch
        self.clock = clock
        self.capture = capture

    def search(self, query: str, *, limit: int = 10) -> dict:
        query = query.strip()
        if not 2 <= len(query) <= 120 or any(ord(c) < 32 for c in query):
            raise ValueError('search text must contain 2–120 printable characters')
        if isinstance(limit, bool) or not 1 <= limit <= 20:
            raise ValueError('limit must be between 1 and 20')
        url = BASE + '?' + urlencode({'filter[entity.legalName]': query, 'page[size]': limit})
        payload = self.fetch(url)
        if len(payload) > MAX_BYTES:
            raise GLEIFError('response_too_large')
        try:
            body = json.loads(payload)
            records = body['data']
            if not isinstance(records, list) or len(records) > limit:
                raise ValueError('invalid result size')
            pagination = body['meta']['pagination']
            total = pagination['total']
            if type(total) is not int or total < len(records):
                raise ValueError('invalid pagination')
        except (ValueError, TypeError, KeyError) as exc:
            raise GLEIFError('invalid_response') from exc
        if self.capture is not None:
            self.capture(payload)
        captured_at = self.clock()
        if captured_at.tzinfo is None:
            raise ValueError('clock must be timezone-aware')
        captured_at = captured_at.astimezone(timezone.utc)
        results = []
        rejected = 0
        for row in records:
            try:
                lei = row['id']
                entity = row['attributes']['entity']
                name = entity['legalName']['name']
                jurisdiction = entity.get('jurisdiction')
                if not isinstance(lei, str) or not valid_lei(lei) or not isinstance(name, str) or not name.strip():
                    raise ValueError('invalid LEI or name')
                if jurisdiction is not None and (not isinstance(jurisdiction, str) or len(jurisdiction) > 20):
                    raise ValueError('invalid jurisdiction')
                results.append({'lei': lei, 'legal_name': name, 'jurisdiction': jurisdiction,
                                'entity_status': entity.get('status'),
                                'record_url': f'{BASE}/{lei}', 'match_status': 'candidate'})
            except (KeyError, TypeError, ValueError):
                rejected += 1
        return {'query': query, 'items': results, 'total': total, 'returned': len(results), 'rejected': rejected,
                'truncated': total > len(records), 'source': {'provider': 'GLEIF', 'url': url,
                    'retrieved_at': captured_at.isoformat().replace('+00:00', 'Z'),
                    'available_at': captured_at.isoformat().replace('+00:00', 'Z'),
                    'published_at': None, 'content_sha256': hashlib.sha256(payload).hexdigest(),
                    'licence': 'CC0 1.0', 'licence_url': TERMS},
                'limitations': ['Search names are candidates, not proof of a security-to-entity relationship.',
                                'GLEIF registration data may be revised; first-publication time is unknown.',
                                'Only one bounded page is returned.']}
