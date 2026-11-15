"""Small session-scoped HTTP boundary for Bitcoin network snapshots."""
from fastapi import APIRouter, Depends

from aplomb.api.errors import unavailable
from aplomb.api.limiter import SessionLimiter

from .chain_public import ChainError, capture


def chain_router(store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/intelligence/chains/bitcoin')
    def bitcoin_network(sid: str = Depends(session_dependency)):
        limiter.take(sid, 'bitcoin-network', 4, 60)
        try:
            return capture(store, sid)
        except ChainError as exc:
            raise unavailable('Bitcoin network source or confirmed reuse rights') from exc

    return router
