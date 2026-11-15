"""HTTP boundary for Time Machine point-in-time calibration (SEC) and the ALFRED rights gate.

These endpoints are read-only and separate from replay runs: nothing they return is added to a
run's inputs, ledger or signed result. The published-later comparison is meant for the reveal.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query

from aplomb.api.errors import ServiceError
from aplomb.api.limiter import SessionLimiter
from aplomb.datastore.timeutil import parse_date
from aplomb.ledger.sources import strict_json
from aplomb.research.company_detail import cik_id
from aplomb.research.core import ResearchContext, ResearchError

from .sec_pit import (
    LIMITATIONS,
    CaptureCache,
    SecPointInTimeSource,
    point_in_time,
    published_later,
    sec_contact,
)
from .vintages import alfred_access

DATE = r"^\d{4}-\d{2}-\d{2}$"
EARLIEST = date(1994, 1, 1)


def _invalid(message: str, field: str) -> ServiceError:
    return ServiceError("validation_error", message, {"field": field})


def _unconfigured() -> dict:
    return {"status": "unavailable", "reason": "sec_contact_unconfigured",
            "message": "Set APLOMB_SEC_CONTACT (\"Name email\") to enable SEC point-in-time reconstruction. "
                       "No contact is invented and nothing is fetched without it.",
            "limitations": list(LIMITATIONS)}


def _safe(build, *args) -> dict:
    """A source that fails record validation is reported unavailable, never partially guessed."""
    try:
        return build(*args)
    except ValueError:
        return {"status": "unavailable", "reason": "source_records_failed_validation",
                "message": "SEC rows failed point-in-time record validation; nothing is shown.",
                "limitations": list(LIMITATIONS)}


def point_in_time_router(store, session_dependency, feature, clock=None):
    router = APIRouter()
    limiter = SessionLimiter(store)
    cache = CaptureCache()
    now = clock or (lambda: datetime.now(timezone.utc))

    def check_date(value: str, field: str) -> date:
        try:
            day = parse_date(value, field)
        except ValueError as exc:
            raise _invalid(f"{field} must be a valid YYYY-MM-DD date", field) from exc
        if day < EARLIEST or day >= now().astimezone(timezone.utc).date():
            raise _invalid(f"{field} must be between {EARLIEST} and yesterday (UTC)", field)
        return day

    def capture(sid: str, cik: str, cutoff: date):
        contact = sec_contact()
        if contact is None:
            return None
        try:
            cik = cik_id(cik)
        except ValueError as exc:
            raise _invalid("A valid exact SEC CIK is required", "cik") from exc
        key = (hashlib.sha256(sid.encode()).hexdigest(), cik, cutoff.isoformat(), now().date().isoformat())
        found = cache.get(key)
        if found is not None:
            return found
        limiter.take(sid, "timemachine-pit", 6, 60)
        try:
            source = SecPointInTimeSource(contact, clock=now)
        except ValueError:
            return None
        found = source.capture(sid, cik, cutoff)
        if found.sources:
            cache.put(key, found)
        return found

    @router.get("/v1/timemachine/point-in-time/{cik}")
    def available_at_cutoff(cik: str, cutoff: str = Query(pattern=DATE), sid: str = Depends(session_dependency)):
        feature("time_machine")
        day = check_date(cutoff, "cutoff")
        found = capture(sid, cik, day)
        return _unconfigured() if found is None else _safe(point_in_time, found, day.isoformat())

    @router.get("/v1/timemachine/point-in-time/{cik}/published-later")
    def later(cik: str, cutoff: str = Query(pattern=DATE), until: str = Query(pattern=DATE),
              sid: str = Depends(session_dependency)):
        feature("time_machine")
        day, end = check_date(cutoff, "cutoff"), check_date(until, "until")
        if end <= day:
            raise _invalid("until must be after cutoff", "until")
        found = capture(sid, cik, day)
        return _unconfigured() if found is None else _safe(published_later, found, day.isoformat(), end.isoformat())

    @router.get("/v1/timemachine/sec-ticker-candidates")
    def ticker_candidates(ticker: str = Query(pattern=r"^[A-Za-z0-9.\-]{1,12}$"), sid: str = Depends(session_dependency)):
        """Exact current SEC ticker matches as candidates only; the user must confirm a CIK."""
        feature("time_machine")
        contact = sec_contact()
        if contact is None:
            return _unconfigured()
        limiter.take(sid, "timemachine-ticker", 6, 60)
        url = "https://www.sec.gov/files/company_tickers.json"
        try:
            source = SecPointInTimeSource(contact, clock=now)
            context = ResearchContext("pit_" + hashlib.sha256(sid.encode()).hexdigest()[:32], now().date(),
                                      mode="point_in_time")
            document = source.service.fetch(url, context)
            if document.canonical_url != url:
                raise ResearchError("exact_sec_endpoint_required")
            data = strict_json(document.text)
            if not isinstance(data, dict):
                raise ResearchError("invalid_source_json")
        except (ResearchError, ValueError, TypeError):
            return {"status": "unavailable", "reason": "source_unavailable_or_invalid", "candidates": []}
        wanted = ticker.strip().upper()
        candidates = []
        for row in data.values():
            if (isinstance(row, dict) and isinstance(row.get("ticker"), str) and row["ticker"].upper() == wanted
                    and type(row.get("cik_str")) is int and row["cik_str"] > 0):
                candidates.append({"cik": str(row["cik_str"]).zfill(10), "ticker": row["ticker"],
                                   "title": row.get("title") if isinstance(row.get("title"), str) else None})
        return {"status": "available", "ticker": wanted, "candidates": candidates[:10],
                "source": {"url": url, "sha256": document.content_hash,
                           "retrieved_at": document.retrieved_at.isoformat()},
                "limitations": ["Current SEC ticker association only. Tickers are reassigned over time; a ticker "
                                "does not establish identity at a historical cutoff. Confirm the CIK before use."]}

    @router.get("/v1/timemachine/vintages/status")
    def vintages_status(sid: str = Depends(session_dependency)):
        feature("time_machine")
        return alfred_access()

    return router
