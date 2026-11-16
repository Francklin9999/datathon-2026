"""Read-only source-capabilities shim for the current Markets page (see capabilities.py)."""
from fastapi import APIRouter, Depends

from .capabilities import capabilities


def capability_router(session_dependency):
    router = APIRouter()

    @router.get('/v1/intelligence/source-capabilities')
    def source_capabilities(_sid: str = Depends(session_dependency)):
        return capabilities()

    return router
