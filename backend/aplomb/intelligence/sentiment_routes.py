"""Session-scoped Alternative.me sentiment route."""
from fastapi import APIRouter, Depends

from aplomb.api.errors import unavailable
from aplomb.api.limiter import SessionLimiter

from .sentiment import SentimentError, capture


def sentiment_router(store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/intelligence/bitcoin-sentiment')
    def sentiment(sid: str = Depends(session_dependency)):
        limiter.take(sid, 'bitcoin-sentiment', 4, 60)
        try:
            return capture(store, sid)
        except SentimentError as exc:
            raise unavailable('Alternative.me Bitcoin sentiment') from exc

    return router
