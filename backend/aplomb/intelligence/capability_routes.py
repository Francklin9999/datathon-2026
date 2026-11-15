"""Read-only source capability inventory; contains no account or credential values."""
from fastapi import APIRouter, Depends

from .capabilities import capabilities


def capability_router(settings, session_dependency):
    router = APIRouter()

    @router.get('/v1/intelligence/source-capabilities')
    def source_capabilities(_sid: str = Depends(session_dependency)):
        return capabilities(settings)

    return router
