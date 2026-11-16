"""HTTP boundary for the Time Machine ALFRED rights gate.

Read-only and separate from replay runs: nothing it returns is added to a run's inputs, ledger or
signed result. The SEC point-in-time reconstruction and its three routes were removed with the
owner's removal of the SEC sources (see intelligence/capabilities.py, family ``sec``).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .vintages import alfred_access


def point_in_time_router(session_dependency, feature):
    router = APIRouter()

    @router.get("/v1/timemachine/vintages/status")
    def vintages_status(sid: str = Depends(session_dependency)):
        feature("time_machine")
        return alfred_access()

    return router
