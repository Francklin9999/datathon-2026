"""Validate rights-cleared ALFRED-style real-time period observations.

This module does not fetch, persist, or send data to a model. FRED's published terms
restrict API caching and use of content in AI development; provision the appropriate
permissions before wiring such data into a workflow. Inputs to this module in tests are
synthetic. A series' original publisher may impose additional restrictions.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from aplomb.datastore.timeutil import normalize_ts, parse_date


@dataclass(frozen=True)
class VintageObservation:
    series_id: str
    observation_date: str
    value: Decimal
    realtime_start: str
    realtime_end: str
    retrieved_at: str
    dataset_version: str
    source_url: str
    # ALFRED real-time dates identify date-level vintages, not the source's exact
    # release time. Treat their start as end-of-day UTC and never fabricate a time.
    publication_at: None = None

    @property
    def available_at(self) -> str:
        return self.realtime_start + "T23:59:59.999Z"


def parse_observations(document: dict, *, series_id: str, retrieved_at: str,
                       dataset_version: str, source_url: str) -> tuple[VintageObservation, ...]:
    """Parse bounded official JSON observation shape; reject inconsistent revision ranges.

    ``realtime_start`` / ``realtime_end`` are inclusive dates. Missing values are
    omitted. Availability on the date-level vintage does not assert an exact
    source publication timestamp. The caller is responsible for documented rights.
    """
    if not re.fullmatch(r"[A-Z0-9_]{1,32}", series_id):
        raise ValueError("invalid series ID")
    if not dataset_version or len(dataset_version) > 128:
        raise ValueError("invalid dataset version")
    if not source_url.startswith("https://api.stlouisfed.org/fred/series/observations"):
        raise ValueError("invalid source URL")
    # API keys must never become part of source metadata.
    if "?" in source_url or "#" in source_url:
        raise ValueError("source URL must not include query parameters")
    retrieved = normalize_ts(retrieved_at, "retrieved_at")
    rows = document.get("observations") if isinstance(document, dict) else None
    if not isinstance(rows, list) or len(rows) > 100_000:
        raise ValueError("invalid or oversized observations")
    out = []
    ranges: dict[str, list[tuple[date, date]]] = {}
    for row in rows:
        try:
            observed = parse_date(row["date"], "observation date")
            first = parse_date(row["realtime_start"], "realtime_start")
            last = parse_date(row["realtime_end"], "realtime_end")
            if first > last or observed > first or first.isoformat() > retrieved[:10]:
                raise ValueError("invalid temporal ordering")
            value = row["value"]
            if value == ".":
                continue
            value = Decimal(value)
            if not value.is_finite():
                raise ValueError("nonfinite value")
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise ValueError("invalid observation") from exc
        intervals = ranges.setdefault(observed.isoformat(), [])
        if any(first <= prior_end and prior_start <= last for prior_start, prior_end in intervals):
            raise ValueError("overlapping vintage intervals")
        intervals.append((first, last))
        out.append(VintageObservation(series_id, observed.isoformat(), value, first.isoformat(),
                                      last.isoformat(), retrieved, dataset_version, source_url))
    return tuple(sorted(out, key=lambda x: (x.observation_date, x.realtime_start)))


def visible_at(rows: tuple[VintageObservation, ...], cutoff: str) -> tuple[VintageObservation, ...]:
    """Return only the vintage valid on the requested end-of-day UTC cutoff."""
    day = parse_date(cutoff, "cutoff").isoformat()
    return tuple(row for row in rows if row.observation_date <= day
                 and row.realtime_start <= day <= row.realtime_end)


FRED_TERMS_URL = "https://fred.stlouisfed.org/legal/"


def alfred_access(environ=None) -> dict:
    """Rights gate for ALFRED vintages. Reports state only; it never fetches or ingests data.

    FRED/ALFRED terms restrict use of their content in connection with AI systems and restrict
    caching and redistribution. The adapter stays unavailable unless an operator both confirms
    documented rights (``APLOMB_ALFRED_RIGHTS_CONFIRMED=true``) and supplies ``APLOMB_FRED_KEY``.
    Even then this build has no ingestion path: the status says so instead of implying coverage.
    The key value is never returned.
    """
    env = os.environ if environ is None else environ
    confirmed = env.get("APLOMB_ALFRED_RIGHTS_CONFIRMED", "").strip().lower() in {"1", "true", "yes"}
    keyed = bool(env.get("APLOMB_FRED_KEY", "").strip())
    missing = [name for name, ok in (("APLOMB_ALFRED_RIGHTS_CONFIRMED", confirmed), ("APLOMB_FRED_KEY", keyed)) if not ok]
    return {
        "provider": "ALFRED (Federal Reserve Bank of St. Louis)",
        "status": "rights_confirmed_ingestion_not_wired" if not missing else "unavailable",
        "missing": missing,
        "terms_url": FRED_TERMS_URL,
        "ingested": False,
        "used_in_replay": False,
        "reason": ("FRED/ALFRED terms restrict use with AI systems, caching and redistribution. No vintage is "
                   "fetched, stored or sent to a model by this build; revised macro series stay withheld in replays."),
    }
