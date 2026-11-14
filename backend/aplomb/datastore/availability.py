"""Availability policies: when may a row be read? (datastore SPEC §4, architecture "Date consistency").

Each row gets two timestamps, one per gate mode. The gate shows a row iff its timestamp is
strictly before the exclusive boundary (start of the UTC day after ``asOf``). Empty = unknown
availability = withheld. These are explicit, documented approximations of daily vendor
availability on a retrospectively adjusted snapshot, not a reconstruction of original vintages.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .timeutil import ALWAYS_AVAILABLE, UNKNOWN_AVAILABILITY, month_end, next_weekday, ts

# Exchange closes at 16:00 America/Toronto and America/New_York. 21:00Z equals 16:00 EST and
# is one hour after the close during daylight time, so the stamp is never earlier than the close.
EXCHANGE_CLOSE_UTC = (21, 0, 0, 0)
# Bank of Canada publishes its daily USD/CAD rate around 16:30 ET (sources_metadata.csv);
# 21:30Z = 16:30 EST, one hour late during daylight time (conservative).
BOC_FX_PUBLICATION_UTC = (21, 30, 0, 0)
# A completed crypto UTC day is stamped at its final millisecond (datastore SPEC §4).
CRYPTO_END_OF_DAY_UTC = (23, 59, 59, 999)
# A-22: monthly macro becomes usable 45 days after the end of its reference month.
MONTHLY_MACRO_LAG_DAYS = 45

BASIS_RELEASE = "release_date"
BASIS_NEXT_BUSINESS_DAY = "assumed_next_business_day_A22"
BASIS_MONTHLY_LAG = "assumed_45_day_lag_A22"


@dataclass(frozen=True)
class Availability:
    current: str
    historical: str


def price_row(d: date, asset_class: str) -> Availability:
    """Daily price policy: exchange rows at the close, crypto rows when their UTC day ends."""
    if asset_class == "crypto":
        stamp = ts(d, *CRYPTO_END_OF_DAY_UTC)
    else:
        stamp = ts(d, *EXCHANGE_CLOSE_UTC)
    return Availability(stamp, stamp)


def fx_row(d: date) -> Availability:
    """Same-day Bank of Canada publication policy."""
    stamp = ts(d, *BOC_FX_PUBLICATION_UTC)
    return Availability(stamp, stamp)


def corporate_action_row(ex_date: date) -> Availability:
    """Reference-only annotation, readable from the start of its ex-date."""
    stamp = ts(ex_date)
    return Availability(stamp, stamp)


def theme_row(assigned_at: date) -> Availability:
    """Team assignment: ungated in current runs; in historical runs only after the assignment day.

    data SPEC: a theme assignment is "not historical evidence without dated support".
    """
    return Availability(ALWAYS_AVAILABLE, ts(assigned_at))


def release_metadata_row(published_at: str) -> Availability:
    """A release-date record is itself known once the release has happened."""
    return Availability(published_at, published_at)


@dataclass(frozen=True)
class MacroAvailability:
    current: str
    historical: str
    basis: str


def macro_row(
    reference_date: date,
    frequency_class: str,
    revised_latest_vintage: bool,
    published_at: str | None,
    vintage_at: str | None,
) -> MacroAvailability:
    """Macro policy.

    Current mode: real release time when known, else A-22 (daily: next business day; monthly:
    45 days after the reference month ends). Historical mode: monthly series need a real release
    time; revised (latest-vintage) series also need the vintage time of the stored value.
    Unknown -> withheld. Never forward-filled from the future.
    """
    if frequency_class == "daily":
        assumed = ts(next_weekday(reference_date))
        assumed_basis = BASIS_NEXT_BUSINESS_DAY
    elif frequency_class == "monthly":
        assumed = ts(month_end(reference_date) + timedelta(days=MONTHLY_MACRO_LAG_DAYS))
        assumed_basis = BASIS_MONTHLY_LAG
    else:  # pragma: no cover - validated at ingestion
        raise ValueError(f"unknown frequency class {frequency_class!r}")

    if published_at:
        current, basis = published_at, BASIS_RELEASE
    else:
        current, basis = assumed, assumed_basis

    if published_at:
        release = published_at
    elif frequency_class == "daily":
        release = assumed  # A-22 next-business-day approximation is accepted for daily series
    else:
        release = None  # monthly without a real release date: unknown

    if release is None:
        historical = UNKNOWN_AVAILABILITY
    elif revised_latest_vintage:
        historical = max(release, vintage_at) if vintage_at else UNKNOWN_AVAILABILITY
    else:
        historical = release
    return MacroAvailability(current, historical, basis)
