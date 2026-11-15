"""Current Golden Copy metadata and narrowly scoped delta acquisition."""
from datetime import date

from fastapi import APIRouter, Depends, Query

from aplomb.api.errors import ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter

from .golden_copy import GoldenCopyError, discover, ingest_delta, latest_entity


def golden_router(store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/intelligence/gleif-golden/metadata')
    def latest_metadata(sid: str = Depends(session_dependency)):
        limiter.take(sid, 'gleif-golden-metadata', 4, 60)
        try:
            result, _ = discover(store, sid)
            return result
        except GoldenCopyError as exc:
            raise unavailable('GLEIF Golden Copy metadata') from exc

    @router.post('/v1/intelligence/gleif-golden/delta/{lei}')
    def delta_lookup(lei: str, sid: str = Depends(session_dependency)):
        limiter.take(sid, 'gleif-golden-delta', 2, 60)
        try:
            return ingest_delta(store, sid, lei.upper())
        except GoldenCopyError as exc:
            raise unavailable('Bounded GLEIF intraday delta') from exc
        except ValueError as exc:
            raise ServiceError('validation_error', 'Valid LEI checksum required') from exc

    @router.get('/v1/intelligence/gleif-golden/entity/{lei}')
    def stored_entity(lei: str, sid: str = Depends(session_dependency), as_of: str | None = Query(default=None)):
        try:
            cutoff = date.fromisoformat(as_of) if as_of else None
            item = latest_entity(store, sid, lei.upper(), cutoff)
        except GoldenCopyError as exc:
            raise unavailable('Stored GLEIF Golden Copy record') from exc
        except ValueError as exc:
            raise ServiceError('validation_error', 'Valid LEI and ISO date required') from exc
        return {'status': 'captured' if item else 'not_captured',
                'entity': item['entity'] if item else None, 'source': item['source'] if item else None}

    return router
