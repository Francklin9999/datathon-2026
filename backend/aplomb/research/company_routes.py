"""Small additive SEC research HTTP boundary; current captures only."""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from aplomb.api.errors import ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter

from .company_detail import CompanyResearch, cik_id
from .core import PublicHTTP, ResearchService


class StatusRecordingTransport:
    """Records upstream HTTP status per URL so a 403 is reported as access denied, never retried
    or bypassed. Only the status integer is kept; bodies and headers are not logged."""

    def __init__(self, inner):
        self.inner, self.statuses = inner, {}

    def get(self, url, **kwargs):
        response = self.inner.get(url, **kwargs)
        if len(self.statuses) < 64:
            self.statuses[url] = response.status
        return response


def sec_contact(settings):
    """APLOMB_SEC_CONTACT (descriptive 'Organization email' User-Agent) takes precedence over the
    generic APLOMB_SOURCE_USER_AGENT. No contact is ever invented."""
    return os.getenv("APLOMB_SEC_CONTACT", "").strip() or settings.source_user_agent


def company_router(settings, store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get("/v1/research/company/{cik}")
    def company(cik: str, sid: str = Depends(session_dependency),
                country: str = Query(default="USA", pattern=r"^[A-Z]{3}$")):
        # Deliberately exact registry key. International registrants can have a CIK,
        # but an international ticker must never be silently sent to EDGAR.
        if country != "USA":
            raise unavailable("Regional disclosure provider; use an exact regional identifier")
        try:
            cik_id(cik)
        except ValueError as exc:
            raise ServiceError("validation_error", "A valid exact SEC CIK is required") from exc
        limiter.take(sid, "company-research", 4, 60)
        contact = sec_contact(settings)
        if not contact:
            raise unavailable("SEC source contact configuration")
        try:
            transport = StatusRecordingTransport(PublicHTTP(contact))
        except ValueError as exc:
            raise unavailable("SEC source contact configuration (descriptive contact required)") from exc
        service = ResearchService(transport, lambda: datetime.now(timezone.utc))
        return CompanyResearch(service, store).detail(sid, cik)

    return router
