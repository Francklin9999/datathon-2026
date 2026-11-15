"""Wikidata candidate discovery with bounded per-session access."""
from fastapi import APIRouter, Depends, Query

from aplomb.api.errors import ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter

from .wikidata import WikidataError, capture, source_contact


def wikidata_router(settings, store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/intelligence/wikidata-candidates')
    def discover(isin: str = Query(min_length=12, max_length=12),
                 sid: str = Depends(session_dependency)):
        limiter.take(sid, 'wikidata-candidates', 4, 60)
        contact = source_contact(settings)
        if not contact:
            raise unavailable('Wikidata descriptive source contact configuration')
        try:
            return capture(store, sid, isin, contact=contact)
        except WikidataError as exc:
            raise unavailable('Wikidata candidate lookup') from exc
        except ValueError as exc:
            raise ServiceError('validation_error', 'Invalid exact ISIN') from exc

    return router
