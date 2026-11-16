"""Current Golden Copy metadata and narrowly scoped delta acquisition.

Stored entity records reach the UI through GET /v1/intelligence/relationships
(relationship_graph uses golden_copy.latest_entity); there is no separate entity route.
"""
from fastapi import APIRouter, Depends

from aplomb.api.errors import ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter

from .golden_copy import GoldenCopyError, discover, ingest_delta


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

    return router
