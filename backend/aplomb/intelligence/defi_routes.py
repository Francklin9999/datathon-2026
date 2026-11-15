"""Selected DeFi observations under session and source-specific rights gates."""
from fastapi import APIRouter, Depends, Query

from aplomb.api.errors import ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter

from .defi_sources import DefiSourceError, pair, protocol, sources


def defi_router(store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/intelligence/defi/sources')
    def list_sources(sid: str = Depends(session_dependency)):
        return sources()

    @router.get('/v1/intelligence/defi/pair/{chain}/{pool}')
    def pool_detail(chain: str, pool: str, sid: str = Depends(session_dependency)):
        limiter.take(sid, 'defi-source', 6, 60)
        try:
            return pair(store, sid, chain, pool)
        except DefiSourceError as exc:
            if str(exc) == 'invalid_exact_pool_identity':
                raise ServiceError('validation_error', 'Invalid exact chain and pool address') from exc
            raise unavailable('DEX Screener source, capture or confirmed data rights') from exc

    @router.get('/v1/intelligence/defi/protocol/{slug}')
    def protocol_detail(slug: str, provider_id: str = Query(min_length=1, max_length=100),
                        sid: str = Depends(session_dependency)):
        limiter.take(sid, 'defi-source', 6, 60)
        try:
            return protocol(store, sid, slug, provider_id)
        except DefiSourceError as exc:
            if str(exc) == 'invalid_protocol_identity':
                raise ServiceError('validation_error', 'Invalid exact provider protocol identity') from exc
            raise unavailable('DefiLlama source, capture or written data rights') from exc

    return router
