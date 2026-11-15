"""Exact-number public registry lookups, isolated to the caller session."""
from fastapi import APIRouter, Depends

from aplomb.api.errors import ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter

from .registries import RegistryError, capture


def registry_router(store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/intelligence/company-registry/{jurisdiction}/{number}')
    def lookup(jurisdiction: str, number: str, sid: str = Depends(session_dependency)):
        limiter.take(sid, 'company-registry', 4, 60)
        try:
            return capture(store, sid, jurisdiction, number)
        except RegistryError as exc:
            raise unavailable('Corporate registry source') from exc
        except ValueError as exc:
            raise ServiceError('validation_error', 'An exact numeric corporate registry number is required') from exc

    return router
