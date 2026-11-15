"""Exact-LEI regulatory disclosure and registry lookup."""
from fastapi import APIRouter, Depends, Query

from aplomb.api.errors import ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter

from .eu_registers import EURegisterError, eba_market_risk, esma_entities


def eu_router(store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/intelligence/eu/eba-market-risk/{lei}')
    def bank_market_risk(lei: str, period: str = Query(default='202506'),
                         sid: str = Depends(session_dependency)):
        limiter.take(sid, 'eu-registry', 6, 60)
        try:
            return eba_market_risk(store, sid, lei, period)
        except EURegisterError as exc:
            if str(exc) in ('invalid_lei', 'unsupported_period'):
                raise ServiceError('validation_error', 'Invalid LEI or unsupported reporting period') from exc
            raise unavailable('EBA market-risk dataset') from exc

    @router.get('/v1/intelligence/eu/esma-entity/{lei}')
    def entity_records(lei: str, sid: str = Depends(session_dependency)):
        limiter.take(sid, 'eu-registry', 6, 60)
        try:
            return esma_entities(store, sid, lei)
        except EURegisterError as exc:
            if str(exc) == 'invalid_lei':
                raise ServiceError('validation_error', 'Invalid LEI') from exc
            raise unavailable('ESMA registry') from exc

    return router
