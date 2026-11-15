"""Session-owned acquisition and inspection of permitted anonymous financial feeds."""
import base64
import binascii
import csv
import hashlib
import time
import zipfile
from datetime import date
from typing import Annotated
from xml.etree.ElementTree import ParseError

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from aplomb.api.errors import Conflict, NotFound, ServiceError
from aplomb.api.storage import Write, canonical

from .errors import IngestionError
from .financial_connectors import DEFERRED_PROVIDERS, PROVIDERS, acquire, provider_status


class CaptureRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    as_of: date = Field(alias='asOf')
    symbol: Annotated[str, Field(pattern=r'^[A-Z0-9.\-]{1,30}$')] = 'SPY'
    sheet: Annotated[str, Field(max_length=80)] = ''
    limit: Annotated[int, Field(strict=True, ge=1, le=200)] = 100


def make_router(store, session_dependency) -> APIRouter:
    router = APIRouter()
    session = Annotated[str, Depends(session_dependency)]

    def checked_capture(partition: str, capture_id: str, owner: str) -> dict | None:
        # Store.get_owned is for run records with run.sessionId, not generic cache rows.
        record = store.get('cache', partition, capture_id)
        if not record or record.get('sessionId') != owner:
            return None
        try:
            response = record['response']
            raw = base64.b64decode(record['rawBase64'], validate=True)
            valid = (hashlib.sha256(raw).hexdigest() == response['source']['rawSha256']
                     and hashlib.sha256(canonical(response)).hexdigest() == record['responseSha256'])
        except (KeyError, ValueError, TypeError, binascii.Error):
            valid = False
        if not valid:
            raise ServiceError('upstream_unavailable', 'Stored financial capture failed its integrity check')
        return record

    def permitted(provider_id: str) -> None:
        # Check on every read; revoking permission must not leak cached data.
        status = provider_status(PROVIDERS[provider_id])
        if status['status'] != 'configured':
            raise ServiceError('upstream_unavailable', f"{status['name']}: {status['status']}",
                               {'provider': provider_id, 'termsUrl': status['terms']})

    @router.get('/v1/risk/providers')
    def providers(sid: session):
        return {'providers': [provider_status(p) for p in PROVIDERS.values()],
                'setAside': [provider_status(p) for p in DEFERRED_PROVIDERS.values()],
                'scope': 'Free anonymous-access feeds only. Paid sources excluded; login/API-key sources set aside.',
                'limitations': ['Provider terms remain applicable. Availability is not a redistribution grant.',
                                'Configured is not a successful live capture.']}

    @router.post('/v1/risk/providers/{provider_id}/capture')
    def capture(provider_id: str, body: CaptureRequest, sid: session):
        if provider_id in DEFERRED_PROVIDERS:
            raise ServiceError('upstream_unavailable', 'Source set aside: paid plan, login or API key required')
        if provider_id not in PROVIDERS:
            raise NotFound('Unknown financial provider')
        permitted(provider_id)
        owner = hashlib.sha256(sid.encode()).hexdigest()
        query = body.model_dump(mode='json', by_alias=True)
        query_hash = hashlib.sha256(canonical(query)).hexdigest()
        partition = f'FINANCIAL#{owner}#{provider_id}'
        pointer_key = 'QUERY#' + query_hash
        pointer = store.get('cache', partition, pointer_key)
        now = time.time()
        if pointer and pointer['expiresAt'] > now:
            saved = checked_capture(partition, pointer['captureId'], sid)
            if saved:
                return saved['response']
        try:
            response, raw = acquire(provider_id, day=body.as_of, symbol=body.symbol,
                                    sheet=body.sheet, limit=body.limit)
        except (ValueError, KeyError, TypeError, UnicodeError, IndexError, OverflowError, ParseError, zipfile.BadZipFile, csv.Error, IngestionError) as exc:
            raise ServiceError('upstream_unavailable', 'Provider data failed validation',
                               {'provider': provider_id, 'reason': str(exc)[:200]}) from None
        # Capture bytes remain session private; only normalized records and checksums leave this API.
        capture_id = 'capture_' + hashlib.sha256(canonical({'source': response['source'], 'query': query})).hexdigest()
        response['captureId'] = capture_id
        response['query'] = query
        response['storage'] = 'Session-owned immutable capture in existing application storage'
        record = {'revision': 1, 'sessionId': sid, 'rawBase64': base64.b64encode(raw).decode(),
                  'response': response, 'responseSha256': hashlib.sha256(canonical(response)).hexdigest()}
        new_pointer = {'revision': (pointer['revision'] if pointer else 0) + 1,
                       'captureId': capture_id, 'expiresAt': int(now) + 3600}
        existing = checked_capture(partition, capture_id, sid)
        if existing and existing != record:
            raise ServiceError('upstream_unavailable', 'Financial capture identity collision')
        writes = [] if existing else [Write('cache', partition, capture_id, record, None)]
        writes.append(Write('cache', partition, pointer_key, new_pointer, pointer['revision'] if pointer else None))
        try:
            store.transact(writes)
        except Conflict:
            if not checked_capture(partition, capture_id, sid):
                raise Conflict('Concurrent source capture changed; retry the request') from None
        return response

    @router.get('/v1/risk/providers/{provider_id}/captures/{capture_id}')
    def captured(provider_id: str, capture_id: str, sid: session,
                 known_at: Annotated[date | None, Header(alias='X-Aplomb-Known-Date')] = None):
        if provider_id not in PROVIDERS:
            raise NotFound('Unknown financial provider')
        permitted(provider_id)
        owner = hashlib.sha256(sid.encode()).hexdigest()
        record = checked_capture(f'FINANCIAL#{owner}#{provider_id}', capture_id, sid)
        if record is None:
            raise NotFound('Capture not found in this session')
        response = record['response']
        if known_at and response['availableAt'][:10] > known_at.isoformat():
            raise ServiceError('insufficient_data', 'Capture was not available by the requested historical date')
        return response

    return router
