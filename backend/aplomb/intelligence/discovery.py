"""Session-isolated, immutable GLEIF captures in the existing application store.

The cache is only a pointer to an already validated response. Raw public source payload,
normalized candidates, source checksum and retrieval metadata are retained together. DynamoStore
uses its existing S3 spill mechanism for large records; no new database is required.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Callable

from aplomb.api.errors import Conflict
from aplomb.api.storage import Store, Write, canonical
from aplomb.contracts.api import EntitySearchResponse

from .gleif import GLEIFClient


class DiscoveryStorageError(RuntimeError):
    pass


class EntityDiscovery:
    def __init__(self, store: Store, client_factory=GLEIFClient, clock: Callable[[], float] = time.time):
        self.store, self.client_factory, self.clock = store, client_factory, clock

    def search(self, session_id: str, query: str, *, limit: int = 10) -> EntitySearchResponse:
        query = query.strip()
        if not 2 <= len(query) <= 120 or any(ord(c) < 32 for c in query) or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError('Search requires 2–120 printable characters and a limit from 1 to 20')
        owner = hashlib.sha256(session_id.encode()).hexdigest()
        pk = 'ENTITY#' + owner + '#' + hashlib.sha256(canonical({'q': query, 'limit': limit})).hexdigest()
        try:
            cached = self.store.get('cache', pk, 'CURRENT')
            if cached and cached['expiresAt'] > self.clock():
                captured = self.store.get('cache', pk, cached['captureKey'])
                if captured and captured['sessionId'] == session_id:
                    self._validate_capture(captured)
                    return EntitySearchResponse.model_validate(captured['response'])
        except Exception as exc:
            raise DiscoveryStorageError('Unable to read validated entity capture') from exc
        payloads = []
        response = EntitySearchResponse.model_validate(self.client_factory(capture=payloads.append).search(query, limit=limit))
        if len(payloads) != 1:
            raise DiscoveryStorageError('Provider did not capture exactly one source response')
        payload = payloads[0]
        capture_key = 'CAPTURE#' + response.source.retrieved_at + '#' + response.source.content_sha256
        record = {'revision': 1, 'sessionId': session_id, 'raw': payload.decode('utf-8'),
                  'response': response.to_wire()}
        self._validate_capture(record)
        old_revision = cached['revision'] if cached else None
        pointer = {'revision': (old_revision or 0) + 1, 'captureKey': capture_key,
                   'expiresAt': int(self.clock()) + 3600}
        try:
            self.store.transact([Write('cache', pk, capture_key, record, None),
                                 Write('cache', pk, 'CURRENT', pointer, old_revision)])
        except Conflict:
            # A concurrent capture may win the pointer update. Preserve this validated source
            # independently; never overwrite its original payload or return a partial write.
            try:
                existing = self.store.get('cache', pk, capture_key)
                if existing is None:
                    self.store.transact([Write('cache', pk, capture_key, record, None)])
                elif existing != record:
                    raise DiscoveryStorageError('Entity capture identity collision')
            except Exception as exc:
                raise DiscoveryStorageError('Unable to retain entity capture') from exc
        except Exception as exc:
            raise DiscoveryStorageError('Unable to retain entity capture') from exc
        return response

    @staticmethod
    def _validate_capture(record):
        body = EntitySearchResponse.model_validate(record['response'])
        if hashlib.sha256(record['raw'].encode()).hexdigest() != body.source.content_sha256:
            raise DiscoveryStorageError('Entity source checksum mismatch')
        json.loads(record['raw'])
