"""Closed lists the datastore needs from ``contracts/catalog.md`` and ``contracts/schemas.md``.

Catalog lists come from the generated mirror ``backend/aplomb/contracts/catalog.py`` (T01), so
they cannot drift from the contract; a test in ``backend/tests/unit/datastore`` also checks them
against ``contracts/catalog.md``. The remaining values are datastore policy.
"""

from __future__ import annotations

from aplomb.contracts import CONTRACT_VERSION as CONTRACT_VERSION
from aplomb.contracts.catalog import (
    ASSET_GROUP_BY_CLASS,
    AssetFlag,
    DatasetId,
    LimitationCode,
    ThemeTag,
)

# Catalog §10 — every dataset ID, in catalog order.

DATASET_IDS: tuple[str, ...] = tuple(code.value for code in DatasetId)

# Catalog §8 — theme tags.
THEME_TAGS: frozenset[str] = frozenset(tag.value for tag in ThemeTag)

# Catalog §9 — asset flags.
ASSET_FLAGS: frozenset[str] = frozenset(flag.value for flag in AssetFlag)

# Catalog §5 — limitation codes used by the datastore.
LIM_SAMPLE_WINDOW = "LIM_SAMPLE_WINDOW"
LIM_SURVIVORSHIP = "LIM_SURVIVORSHIP"
LIM_FX_FFILL = "LIM_FX_FFILL"
LIM_CALENDAR_INTERSECTION = "LIM_CALENDAR_INTERSECTION"
LIM_YAHOO_NOT_CERTIFIED = "LIM_YAHOO_NOT_CERTIFIED"
LIM_CNQ_FACTOR = "LIM_CNQ_FACTOR"
LIM_ETF_NO_LOOKTHROUGH = "LIM_ETF_NO_LOOKTHROUGH"
LIM_SECTOR_LABELS = "LIM_SECTOR_LABELS"
LIM_THEME_TAGS = "LIM_THEME_TAGS"
LIM_MACRO_REVISED = "LIM_MACRO_REVISED"
LIM_MACRO_LAG_ASSUMED = "LIM_MACRO_LAG_ASSUMED"
LIM_NO_CONTROVERSY_DATA = "LIM_NO_CONTROVERSY_DATA"
LIM_SHORT_HISTORY = "LIM_SHORT_HISTORY"
LIM_CASH_NO_INTEREST = "LIM_CASH_NO_INTEREST"

LIMITATION_CODES: frozenset[str] = frozenset(code.value for code in LimitationCode)

# schemas.md §3 — asset classes and the class -> group mapping.
ASSET_CLASS_TO_GROUP: dict[str, str] = dict(ASSET_GROUP_BY_CLASS)
LISTED_ASSET_CLASSES: frozenset[str] = frozenset(ASSET_CLASS_TO_GROUP) - {"cash"}
SINGLE_NAME_CLASSES: frozenset[str] = frozenset({"equity", "crypto"})
CURRENCIES: frozenset[str] = frozenset({"CAD", "USD", "EUR", "GBP", "CHF", "JPY", "HKD", "SGD", "AUD"})
TIERS: tuple[str, ...] = ("starter", "extended", "on_demand")

# The 11 GICS sector names (schemas.md §3 ``gicsSector``).
GICS_SECTORS: frozenset[str] = frozenset(
    {
        "Energy", "Materials", "Industrials", "Consumer Discretionary", "Consumer Staples", "Health Care",
        "Financials", "Information Technology", "Communication Services", "Utilities", "Real Estate",
    }
)

# Listing market -> ISO-3166 alpha-3 country (datastore SPEC §5). Unknown markets stay null.
MARKET_COUNTRY: dict[str, str] = {
    "TSX": "CAN",
    "TSXV": "CAN",
    "NASDAQ": "USA",
    "NYSE": "USA",
    "NYSE Arca": "USA",
    "NYSE American": "USA",
    "Cboe BZX": "USA",
}

# Master calendar reference tickers (A-15, quant SPEC §2): XIU.TO dates ∩ SPY dates.
CALENDAR_REF_CAD = "XIU.TO"
CALENDAR_REF_USD = "SPY"

# Cash pseudo-assets (schemas.md §1 Ticker).
CASH_TICKERS: dict[str, str] = {f"CASH.{code}": code for code in sorted(CURRENCIES)}

# A-21: risk rules need at least this many master-calendar price observations.
MIN_MASTER_OBS_FOR_RISK = 252
# api.md §2.3: an on-demand ticker with fewer raw rows is rejected.
MIN_ROWS_ON_DEMAND = 30
