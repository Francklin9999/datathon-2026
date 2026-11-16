"""Selected DeFi observations under session and source-specific rights gates."""
from fastapi import APIRouter, Depends

from aplomb.api.errors import ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter

from .defi_sources import DefiSourceError, pair, sources


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

    return router
