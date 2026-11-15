"""Closed lists the datastore needs from ``contracts/catalog.md`` and ``contracts/schemas.md``.

T01 owns the shared mirror ``backend/aplomb/contracts/catalog.py``. It did not exist when the
datastore was written, so the subset used here is copied verbatim from the contract. When the
shared mirror lands, import from it instead and delete the duplicates (a test in
``backend/tests/unit/datastore`` checks these values against ``contracts/catalog.md``).
"""

from __future__ import annotations

from aplomb.contracts.catalog import DatasetId

CONTRACT_VERSION = "1.0.0"

# Catalog §10 — every dataset ID, in catalog order.

DATASET_IDS: tuple[str, ...] = tuple(code.value for code in DatasetId)

# Catalog §8 — theme tags.
THEME_TAGS: frozenset[str] = frozenset(
    {
        "ai", "semiconductors", "software", "cloud", "ecommerce", "electric_vehicles", "big_tech",
        "banks", "insurance", "fossil_energy", "pipelines", "utilities", "rail_transport",
        "consumer_staples", "healthcare", "retail", "broad_canada", "broad_us", "nasdaq_growth",
        "esg_screened", "bonds_canada", "bonds_us", "long_treasuries", "cash_like", "gold", "crypto",
        "dividend_payers",
    }
)

# Catalog §9 — asset flags.
ASSET_FLAGS: frozenset[str] = frozenset(
    {
        "short_history", "zero_volume_rows", "split_anomaly", "on_demand", "no_fx_needed",
        "seven_day_calendar", "sector_label_unsourced",
    }
)

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

LIMITATION_CODES: frozenset[str] = frozenset(
    {
        "LIM_PAST_NOT_FUTURE", LIM_SAMPLE_WINDOW, LIM_SURVIVORSHIP, "LIM_CONSTANT_WEIGHTS", LIM_FX_FFILL,
        LIM_CALENDAR_INTERSECTION, LIM_YAHOO_NOT_CERTIFIED, LIM_CNQ_FACTOR, LIM_ETF_NO_LOOKTHROUGH,
        LIM_SECTOR_LABELS, LIM_THEME_TAGS, "LIM_THRESHOLDS_ASSUMED", "LIM_BONDS_SAMPLE",
        LIM_MACRO_REVISED, LIM_MACRO_LAG_ASSUMED, LIM_NO_CONTROVERSY_DATA, "LIM_EVIDENCE_TIER",
        "LIM_IMPACT_NOT_ESTABLISHED", "LIM_PRICE_MOVE_NOT_CAUSAL", "LIM_LLM_KNOWLEDGE", LIM_SHORT_HISTORY,
        LIM_CASH_NO_INTEREST, "LIM_SIMULATION_ONLY", "LIM_ATTENTION_PROXY", "LIM_REGISTRY_MATCH",
        "LIM_STRATEGY_COSTS",
        "LIM_STRATEGY_EXECUTION",
        "LIM_MV_ILLUSTRATION",
    }
)

# schemas.md §3 — asset classes and the class -> group mapping.
ASSET_CLASS_TO_GROUP: dict[str, str] = {
    "equity": "equity",
    "etf_equity": "equity",
    "etf_bond": "fixed_income",
    "etf_commodity": "commodity",
    "crypto": "crypto",
    "cash": "cash",
}
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
