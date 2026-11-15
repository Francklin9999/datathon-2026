"""Raw input headers and normalized dataset schemas.

Raw headers are the *actual* headers of the organizer CSVs (checked 2026-11-14) and of the
team metadata files in ``data/metadata/``. Ingestion rejects any other header: it never edits
raw files to make them fit (data SPEC "Validate actual source headers before adapters").

Normalized schemas carry a ``schema_version``. A loader rejects a snapshot whose manifest names
a dataset schema version it does not know (datastore SPEC §3).
"""

from __future__ import annotations

from dataclasses import dataclass

MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Column:
    name: str
    type: str  # date | timestamp | string | number | integer | boolean
    description: str


@dataclass(frozen=True)
class NormalizedSchema:
    dataset_id: str
    schema_version: int
    date_column: str | None  # observation/reference date used by start/end filters
    columns: tuple[Column, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)


# --- Raw inputs -------------------------------------------------------------------------------

RAW_HEADERS: dict[str, tuple[str, ...]] = {
    "assets_universe.csv": ("asset_id", "ticker", "name", "asset_class", "market", "currency", "sector"),
    "prices_daily.csv": ("date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "currency"),
    "corporate_actions.csv": ("ex_date", "ticker", "action", "value", "unit"),
    "fx_usdcad_daily.csv": ("date", "usdcad", "cadusd"),
    "macro_rates.csv": ("date", "series_id", "value", "unit", "frequency", "label", "source"),
    "sources_metadata.csv": (
        "file", "content", "source", "source_url", "retrieved_on", "coverage", "frequency", "processing",
        "limitations", "terms_of_use",
    ),
    # Team metadata (data/metadata/), copied into every snapshot so the snapshot is self-contained.
    "asset_themes.csv": ("ticker", "theme", "justification", "sourceUrl", "assignedAt", "isAssumption"),
    "macro_series.csv": ("seriesId", "publisher", "frequencyClass", "revisedLatestVintage", "basis"),
    "macro_release_dates.csv": ("seriesId", "referenceDate", "publishedAt", "vintageAt", "sourceUrl"),
    # On-demand additions (datastore SPEC §3), appended by ondemand.publish_on_demand.
    "ondemand_assets.csv": (
        "ticker", "name", "asset_class", "market", "currency", "sector", "provider", "source_url",
        "retrieved_at", "terms",
    ),
    "ondemand_prices.csv": ("date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "currency"),
}

# Organizer files that must be present in a starter source directory.
STARTER_REQUIRED = (
    "assets_universe.csv",
    "prices_daily.csv",
    "corporate_actions.csv",
    "fx_usdcad_daily.csv",
    "macro_rates.csv",
    "sources_metadata.csv",
)
STARTER_OPTIONAL = ("data_quality_warnings.txt",)
METADATA_REQUIRED = ("asset_themes.csv", "macro_series.csv")
METADATA_OPTIONAL = ("macro_release_dates.csv",)

# --- Normalized datasets -----------------------------------------------------------------------

_AVAIL = (
    Column(
        "available_at",
        "timestamp",
        "UTC time from which the row may be read in current-mode runs; empty = withheld",
    ),
    Column(
        "available_at_historical",
        "timestamp",
        "UTC time from which the row may be read in historical (Time Machine) runs; empty = unknown, withheld",
    ),
)

NORMALIZED: dict[str, NormalizedSchema] = {
    "assets_universe": NormalizedSchema(
        "assets_universe",
        1,
        None,
        (
            Column("asset_id", "string", "Organizer asset ID (A01..A31) or OD-<ticker> for on-demand assets"),
            Column("ticker", "string", "Ticker as in the source, upper case"),
            Column("name", "string", "Asset name as in the source"),
            Column("asset_class", "string", "equity | etf_equity | etf_bond | etf_commodity | crypto"),
            Column("asset_group", "string", "equity | fixed_income | commodity | crypto (schemas.md §3 mapping)"),
            Column("market", "string", "Listing market label as in the source"),
            Column("currency", "string", "Listing ISO currency code"),
            Column("sector", "string", "Sector label from the source; 'unknown' when unsourced"),
            Column("gics_sector", "string", "Same label when it is one of the 11 GICS sector names, else empty"),
            Column("country", "string", "ISO-3166 alpha-3 of the listing market; empty for crypto or unknown"),
            Column("is_single_name", "boolean", "true for equity and crypto"),
            Column("tier", "string", "starter | extended | on_demand"),
            *_AVAIL,
        ),
    ),
    "prices_daily": NormalizedSchema(
        "prices_daily",
        1,
        "date",
        (
            Column("date", "date", "Trading day (UTC calendar day for crypto)"),
            Column("ticker", "string", "Ticker"),
            Column("open", "number", "Open, listing currency"),
            Column("high", "number", "High, listing currency"),
            Column("low", "number", "Low, listing currency"),
            Column("close", "number", "Close adjusted for splits only, listing currency"),
            Column("adj_close", "number", "Close adjusted for splits and dividends (Yahoo back-adjusted)"),
            Column("volume", "number", "Volume as reported"),
            Column("currency", "string", "Listing currency"),
            *_AVAIL,
        ),
    ),
    "corporate_actions": NormalizedSchema(
        "corporate_actions",
        1,
        "ex_date",
        (
            Column("ex_date", "date", "Ex-date"),
            Column("ticker", "string", "Ticker"),
            Column("action", "string", "dividend | split"),
            Column("value", "number", "Dividend per share or split ratio (new:old)"),
            Column("unit", "string", "Unit as reported, e.g. 'CAD per share', 'split ratio (new:old)'"),
            *_AVAIL,
        ),
    ),
    "fx_usdcad_daily": NormalizedSchema(
        "fx_usdcad_daily",
        1,
        "date",
        (
            Column("date", "date", "Bank of Canada publication day"),
            Column("usdcad", "number", "CAD per 1 USD"),
            Column("cadusd", "number", "USD per 1 CAD (organizer: 1/usdcad rounded to 6 decimals)"),
            *_AVAIL,
        ),
    ),
    "fx_boc_global": NormalizedSchema(
        "fx_boc_global", 1, "date", (
            Column("date", "date", "Bank of Canada daily observation date"),
            Column("currency", "string", "ISO currency quoted in CAD per one unit"),
            Column("cad_per_unit", "number", "Indicative Canadian dollars per one unit of currency"),
            *_AVAIL,
        ),
    ),
    "macro_rates": NormalizedSchema(
        "macro_rates",
        1,
        "date",
        (
            Column("date", "date", "Reference date (for monthly series: first day of the reference month)"),
            Column("series_id", "string", "Series ID as in the source"),
            Column("value", "number", "Value in `unit`"),
            Column("unit", "string", "Unit as in the source"),
            Column("frequency", "string", "Frequency label as in the source"),
            Column("label", "string", "Series label as in the source"),
            Column("source", "string", "Publisher as in the source"),
            Column("frequency_class", "string", "daily | monthly (data/metadata/macro_series.csv)"),
            Column("revised_latest_vintage", "boolean", "true when values are latest revised figures"),
            Column("published_at", "timestamp", "Actual release time from macro_release_dates; empty if unknown"),
            Column("vintage_at", "timestamp", "Time the stored value became the published vintage; empty if unknown"),
            Column("availability_basis", "string", "How available_at was derived (see passport availability rule)"),
            *_AVAIL,
        ),
    ),
    "asset_themes": NormalizedSchema(
        "asset_themes",
        1,
        None,
        (
            Column("ticker", "string", "Ticker"),
            Column("theme", "string", "Theme tag (catalog §8)"),
            Column("justification", "string", "One-line reason for the assignment"),
            Column("source_url", "string", "Supporting source URL; empty when the assignment rests on the universe file only"),
            Column("assigned_at", "date", "Day the team made the assignment"),
            Column("is_assumption", "boolean", "true: team assumption, not an official classification"),
            *_AVAIL,
        ),
    ),
    "macro_release_dates": NormalizedSchema(
        "macro_release_dates",
        1,
        "reference_date",
        (
            Column("series_id", "string", "Series ID"),
            Column("reference_date", "date", "Reference date of the observation (matches macro_rates.date)"),
            Column("published_at", "timestamp", "Actual first publication time (UTC)"),
            Column("vintage_at", "timestamp", "Time the stored value's vintage was published; empty if unknown"),
            Column("source_url", "string", "Release calendar or vintage source"),
            *_AVAIL,
        ),
    ),
}

# Planned datasets: minimum columns from data/SPEC.md, shown in their passports.
PLANNED_COLUMNS: dict[str, tuple[Column, ...]] = {
    "default_profiles": (
        Column("profileId", "string", "robert | mateo | amira"),
        Column("profile", "object", "Profile, portfolio and rules (backend/aplomb/profiles/SPEC.md)"),
    ),
    "macro_release_dates": NORMALIZED["macro_release_dates"].columns[:5],
    "etf_holdings": tuple(
        Column(n, t, d)
        for n, t, d in (
            ("fundTicker", "string", "ETF ticker"),
            ("constituentId", "string", "Issuer constituent identifier"),
            ("ticker", "string", "Constituent ticker"),
            ("weightPct", "number", "Weight in percent"),
            ("reportDate", "date", "Holdings report date"),
            ("publishedAt", "timestamp", "Issuer publication time"),
            ("sourceUrl", "string", "Issuer document URL"),
        )
    ),
    "world_events": (Column("event", "object", "WorldEvent wire fields plus raw-source references"),),
    "attention_pageviews": (
        Column("ticker", "string", "Ticker"),
        Column("date", "date", "Day"),
        Column("views", "integer", "Page views"),
    ),
    "emissions_facilities": (Column("facility", "object", "Facility emissions record (world SPEC)"),),
    "natural_hazards": (Column("hazard", "object", "Earthquake or wildfire record (world SPEC)"),),
    "research_documents": tuple(
        Column(n, t, d)
        for n, t, d in (
            ("documentId", "string", "Document ID"),
            ("url", "string", "Canonical URL"),
            ("retrievedAt", "timestamp", "Retrieval time"),
            ("publishedAt", "timestamp", "Publication time; null if unknown"),
            ("textHash", "string", "SHA-256 of cached text"),
            ("storageKey", "string", "Object key of the cached text"),
            ("licence", "string", "Licence / terms"),
        )
    ),
    "filings_index": (Column("filing", "object", "SEC EDGAR filing metadata (research SPEC)"),),
}
