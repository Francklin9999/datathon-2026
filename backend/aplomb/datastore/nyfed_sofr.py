"""A pinned NY Fed SOFR capture, usable as rate context, never as a yield curve.

The effective date is when the underlying repo transactions occurred, not when
the rate was published. A download of today's revised observations establishes
availability only at capture, so this adapter never backdates knowledge.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from .errors import IngestionError
from .timeutil import normalize_ts, parse_date

TERMS = "https://www.newyorkfed.org/terms-of-use"
SOURCE = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"


@dataclass(frozen=True)
class SofrObservation:
    effective_date: str
    percent_rate: float
    revision_indicator: str


@dataclass(frozen=True)
class SofrCapture:
    source_url: str
    retrieved_at: str
    sha256: str
    observations: tuple[SofrObservation, ...]

    def latest(self, known_at: str, effective_on_or_before: str) -> SofrObservation | None:
        """Return latest effective rate only if the pinned capture was already known."""
        known_at = normalize_ts(known_at, "known_at")
        cutoff = parse_date(effective_on_or_before, "effective_on_or_before")
        if known_at < self.retrieved_at:
            return None
        return next((row for row in reversed(self.observations)
                     if parse_date(row.effective_date) <= cutoff), None)

    def change_basis_points(self, known_at: str, start: str, end: str) -> float | None:
        """Simple observed change in basis points, with no causal or forecast claim."""
        if parse_date(start, "start") >= parse_date(end, "end"):
            raise ValueError("start must precede end")
        first, last = self.latest(known_at, start), self.latest(known_at, end)
        if first is None or last is None or first.effective_date == last.effective_date:
            return None
        return round((last.percent_rate - first.percent_rate) * 100, 8)


def read_capture(payload: bytes, metadata: dict) -> SofrCapture:
    """Validate origin, bytes, dates, uniqueness and percentage-unit observations."""
    try:
        digest = hashlib.sha256(payload).hexdigest()
        if digest != metadata["rawSha256"] or metadata["series"] != "SOFR":
            raise ValueError("capture hash or series mismatch")
        retrieved = normalize_ts(metadata["retrievedAt"], "retrievedAt")
        url = metadata["sourceUrl"]
        parts = urlsplit(url)
        if (f"{parts.scheme}://{parts.netloc}{parts.path}" != SOURCE or parts.fragment
                or parts.username or parts.password):
            raise ValueError("unexpected SOFR source URL")
        params = parse_qs(parts.query, strict_parsing=True)
        if set(params) != {"startDate", "endDate"} or any(len(v) != 1 for v in params.values()):
            raise ValueError("unexpected SOFR query")
        start = parse_date(params["startDate"][0], "startDate")
        end = parse_date(params["endDate"][0], "endDate")
        if start > end:
            raise ValueError("invalid date interval")
        document = json.loads(payload)
        items = document["refRates"]
        if not isinstance(items, list) or not items:
            raise ValueError("no observations")
        capture_time = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
        rows, seen = [], set()
        for item in items:
            day = parse_date(item["effectiveDate"], "effectiveDate")
            rate = item["percentRate"]
            if (day in seen or not start <= day <= end or item["type"] != "SOFR"
                    or isinstance(rate, bool) or not isinstance(rate, (int, float))
                    or not math.isfinite(rate) or not isinstance(item["revisionIndicator"], str)
                    or datetime.combine(day, datetime.min.time(), timezone.utc) > capture_time):
                raise ValueError("invalid, duplicate or future rate observation")
            seen.add(day)
            rows.append(SofrObservation(day.isoformat(), float(rate), item["revisionIndicator"]))
        rows.sort(key=lambda row: row.effective_date)
        return SofrCapture(url, retrieved, digest, tuple(rows))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IngestionError(f"invalid NY Fed SOFR capture: {exc}") from exc
