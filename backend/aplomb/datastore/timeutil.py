"""Date and timestamp helpers.

Availability timestamps are stored as fixed-width UTC strings ``YYYY-MM-DDTHH:MM:SS.fffZ`` so
that lexicographic order equals chronological order. An empty string means "availability
unknown under this mode": such rows are withheld, never guessed.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta, timezone

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")

# Rows of static metadata that are not time-gated under a given mode carry this timestamp.
ALWAYS_AVAILABLE = "0001-01-01T00:00:00.000Z"
UNKNOWN_AVAILABILITY = ""


def parse_date(value: object, field: str = "date") -> date:
    """Parse a strict ``YYYY-MM-DD`` string or pass through a ``date``."""
    if isinstance(value, datetime):
        raise ValueError(f"{field}: expected a date, got a datetime")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        raise ValueError(f"{field}: expected YYYY-MM-DD, got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:  # e.g. 2022-02-30
        raise ValueError(f"{field}: invalid calendar date {value!r}") from exc


def iso_date(value: object, field: str = "date") -> str:
    """Normalize to an ISO date string after strict validation."""
    return parse_date(value, field).isoformat()


def ts(d: date, hour: int = 0, minute: int = 0, second: int = 0, millis: int = 0) -> str:
    """UTC timestamp string for a date and time of day."""
    return f"{d.isoformat()}T{hour:02d}:{minute:02d}:{second:02d}.{millis:03d}Z"


def normalize_ts(value: str, field: str = "timestamp") -> str:
    """Validate an ISO-8601 UTC timestamp (``Z`` suffix) and return the fixed-width form."""
    if not isinstance(value, str) or not _ISO_TS.match(value):
        raise ValueError(f"{field}: expected ISO-8601 UTC timestamp ending in Z, got {value!r}")
    parsed = datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond // 1000:03d}Z"


def date_or_ts_to_ts(value: str, field: str) -> str:
    """Accept a date (taken as 00:00:00Z that day) or a UTC timestamp."""
    if _ISO_DATE.match(value or ""):
        return ts(parse_date(value, field))
    return normalize_ts(value, field)


def boundary_for(as_of: date) -> str:
    """Exclusive gate boundary: start of the next UTC day after ``as_of`` (datastore SPEC §4)."""
    return ts(as_of + timedelta(days=1))


def utc_now_iso(now: datetime) -> str:
    """Format an aware datetime as an API timestamp (second precision, ``Z``)."""
    if now.tzinfo is None:
        raise ValueError("clock must return an aware datetime")
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def next_weekday(d: date) -> date:
    """First Monday–Friday strictly after ``d`` (no holiday calendar: documented approximation)."""
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
