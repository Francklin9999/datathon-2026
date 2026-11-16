# Datastore — immutable versions and gated reads

**Track:** T04. **Tier:** P0. Read [data pipeline](../../../data/SPEC.md), [schemas](../../../contracts/schemas.md), [controls](../../../contracts/controls.md).

## 1. Responsibility and outputs

Load an immutable snapshot, normalize known source columns, expose a universe and typed series, and count visible/withheld rows on every read. A store cannot provide an unfiltered “raw rows” method to tools. Raw ingestion code lives outside the run context. The selected manifest remains pinned throughout a run.

## 2. Types and interface

```python
@dataclass(frozen=True)
class DataSlice:
    rows: tuple[dict, ...]
    dataset_id: str
    data_version: str
    rows_read: int
    rows_withheld: int
    limitations: tuple[str, ...]

class DataStore(Protocol):
    def open(self, data_version: str) -> "Snapshot": ...

class TemporalGate(Protocol):
    def prices(self, tickers: list[str], start: date | None, end: date) -> DataSlice: ...
    def fx(self, start: date | None, end: date) -> DataSlice: ...
    def macro(self, series_id: str, start: date | None, end: date) -> DataSlice: ...
    def dataset(self, dataset_id: str, filters: dict) -> DataSlice: ...
    def describe(self, dataset_id: str) -> DatasetPassport: ...
```

`Snapshot.gate(as_of, mode)` returns the only run-visible reader. `Universe.get(ticker)` and `search(...)` expose assets known/eligible under that context, not future listings. `PriceFrame` passed to quant holds sorted dates, adjusted-price columns, listing currencies and data references; missing values are explicit. Source rows remain separately auditable. T01/T04/T05 freeze the concrete internal dataclasses without changing wire contracts.

## 3. Snapshot and cache behavior

Manifest contains contract version, snapshot ID, createdAt, source hashes, schema versions, row counts, first/last dates and availability policy per dataset. Check hashes and reject partial/unknown schemas. S3 download cache uses snapshot + checksum, atomic temporary-file rename and read-only access after validation. Lambda `/tmp` is an optimization, never the source of truth.

On-demand fetch publishes a new immutable snapshot/version manifest including the additional asset; it never mutates a pinned snapshot. Store provider retrieval timestamp and adjusted-close revision. A run requesting the new asset must pin the published version before starting. Failed fetches leave the active manifest unchanged.

## 4. Temporal gate

Use an exclusive timestamp boundary at the start of the next UTC day for `asOf`. Visible row iff `availableAt < boundary` and observation/reference date satisfies requested interval. Source availability is distinct from `retrievedAt`. For the v1 daily snapshot convention, a completed crypto UTC day is stamped at its final millisecond (23:59:59.999Z), which permits that day at an end-of-day cutoff; this is an explicit availability approximation, not proof of when a vendor originally delivered the row. Require actual availability in historical mode where available; unknown publication times/dates are withheld rather than guessed. Price-row daily policy and crypto end-of-day policy are documented, not asserted as perfect vintage reconstruction.

Macro context outside historical runs may use A-22's lag approximation with limitation. Historical mode excludes monthly macro without real release dates; revised series additionally lack original vintages and must be withheld unless vintage metadata is provided. Do not forward-fill across the cutoff from future rows. Allow FX preceding window start so conversion can carry the last previously available rate; no preceding FX → missing conversion, never use the first future rate.

Count `rowsRead` as returned source rows; `rowsWithheld` as candidate rows rejected by availability before other transformations. Repeated calls report their own reads; trace totals may count repeated reads, not falsely claim unique physical I/O. Include these semantics in tool summaries.

## 5. Universe normalization

Use organizer asset classes, group mapping and sectors. Single-name = equity or crypto, diversified funds excluded from single-name caps. Map TSX → CAN and US listings → USA; crypto/cash have null country. Cash pseudo-assets are explicit zero-return series only in their own currency; foreign cash carries FX return. Do not classify ZST.TO as actual cash or assume it funds `from_cash`.

Theme assignment is a sourced team assumption. ETF holdings have effective/report/retrieved dates and coverage weight; partial coverage cannot be normalized to imply full look-through. Unknown sectors/countries remain unknown.

## 6. Verification and handoff

DS-01 hashes/row counts match starter. DS-02 1,228 master dates and ten missing same-day FX rows. DS-03 future price/FX/macro rows withheld. DS-04 missing release date historical behavior. DS-05 old snapshot unchanged after fetch. DS-06 malformed duplicate/nonpositive rows rejected. DS-07 master-calendar missing asset observations never price-filled. DS-08 two read contexts cannot see each other's cutoff/version.

Supply T05 a local CSV-backed gated reader, T12 synthetic release-date fixtures, T09 a document-cache adapter and T13 complete dataset passports. Done includes offline tests and documented availability rules for every loaded dataset.

## 7. Implementation status (T04, 2026-11-14)

Implemented in `backend/aplomb/datastore/` with the Python standard library only (no manifest needed). Readers never import the ingestion module.

| Module | Content |
|---|---|
| `ingest.py` | Raw bundle → validation → normalization → staged write → hash re-check → atomic publish; CLI |
| `snapshot.py` | `LocalDataStore`, `CachedObjectStore` (S3-shaped, injected `fetch(key)`), `Snapshot` |
| `gate.py` | `TemporalGate` (spec interface plus quant/T12 helpers) |
| `universe.py` | `Universe`, `AssetRecord.to_wire()` (`Asset` wire shape) |
| `passports.py` | `DatasetPassport` for all 15 catalog datasets; trap register for `GET /datasets` |
| `ondemand.py` | `FetchedAsset`, `PriceProvider` protocol, `publish_on_demand` (P1) |
| `availability.py`, `quality.py`, `schemas.py`, `types.py`, `constants.py` | Policies, checks, schemas, result types, catalog subset |

### 7.1 Public calls

```python
store = LocalDataStore("data")                     # or CachedObjectStore(fetch, "/tmp/aplomb")
snap = store.open(store.active_version())          # verifies manifest + every checksum; pin for the run
gate = snap.gate(as_of, mode)                      # mode: "current" | "historical"
gate.prices(tickers, start, end) / gate.fx(start, end) / gate.macro(series_id, start, end)
gate.dataset(dataset_id, filters)                  # equality filters, plus "start"/"end" on the date column
gate.describe(dataset_id)                          # passport dict
gate.master_calendar(start=None, end=None)         # MasterCalendar: visible XIU.TO ∩ SPY dates
gate.price_frame(tickers, start=None, end=None, calendar="master")  # PriceFrame for T05; None = no observation
gate.fx_series(start=None, end=None)               # test/diagnostic helper: FxSeries.rate_on_or_before(day) -> (rate, published) | None
gate.universe()                                    # Universe.get/search/all/counts/cash
gate.availability_summary()                        # per dataset rowsVisible/rowsWithheld/lastVisibleDate (T12)
snap.datasets_response()                           # body of GET /datasets
```

`end=None` means `as_of`. Rows are fresh dicts with source columns plus `available_at` for the gate's mode. `DataSlice.dataset_read().to_wire()` gives a `ToolCall.datasetsRead` entry. Errors: `UnknownTicker`, `UnknownSeries`, `DatasetNotFound` (→ `not_found`), `DatasetMissing` (→ nee `dataset_missing`), `InvalidGateRequest` (→ `validation_error`), `SnapshotIntegrityError`, `IngestionError`.

Test and diagnostic helpers (no production caller; kept because the datastore tests use them): `gate.fx_series`/`FxSeries` (`rate_on`, `rate_on_or_before`), `PriceFrame.missing_dates`/`complete`, `DataSlice.last_visible_date` (the Time Machine and the agent workflow read `lastVisibleDate` from `gate.availability_summary()` instead) and `passports.PASSPORT_KEYS`. Production FX lookups go through `gate.fx` in `quant/market.py` (`MarketData._cad_quote`), which keeps each row's `available_at`. The API never calls `active_version()`: it opens the pinned `APLOMB_DATA_VERSION`. `LocalDataStore.active_version()` is how `scripts/dev_api.py` picks that pin when none is set (it reads `data/manifests/active.json` and checks the label); `CachedObjectStore.active_version()` has no production caller.

### 7.2 Availability rules actually applied

| Dataset | Current mode | Historical mode |
|---|---|---|
| prices_daily | TSX/U.S. row D at D 21:00Z; crypto row D at D 23:59:59.999Z | same |
| fx_usdcad_daily | D 21:30Z (Bank of Canada ~16:30 ET); reads add the last earlier visible rate | same |
| corporate_actions | ex-date 00:00Z, annotation only | same |
| assets_universe | availability of the asset's first price row | same |
| macro_rates | real release time if loaded; else A-22 (daily: next weekday 00:00Z; monthly: reference month end + 45 days) | monthly needs a real release time; revised series (FRED, per `data/metadata/macro_series.csv`) also need `vintageAt`; else withheld |
| asset_themes | not gated | from `assignedAt` (a 2026 team assignment is not historical evidence) |
| macro_release_dates | `publishedAt` | same |

The 21:00Z/21:30Z stamps equal the Eastern close/publication in winter and are one hour late in summer (never early). Weekdays approximate business days (no holiday calendar).

### 7.3 Decisions and known limits

- Source hashes use content with CRLF normalized to LF (`sha256`, equal on every checkout); `sha256Bytes` records local bytes. Normalized files are deterministic, so a clean clone re-materializes `raw/` and `normalized/` from the committed manifest and fails if a hash differs.
- Universe and price reads raise `UnknownTicker` for an asset not yet known at `as_of`. `no_fx_needed` is not emitted (it depends on the profile's reporting currency).
- Theme tags remain team assumptions (`isAssumption=true`). In `snap-20261114-sourced`, 36 of 44 carry an official issuer page checked on 2026-11-14 whose wording is quoted in the justification; the 8 others (big-tech grouping, Shopify as software, Couche-Tard as staples, Microsoft as software, Bitcoin) rest on the universe file. No `dividend_payers` assignment. In historical mode they are withheld, so `Universe.search(theme=...)` returns nothing before 2026-11-14 (T07/T12 to confirm this is wanted).
- `CPIAUCSL` and `UNRATE` have no 2025-10 observation in the organizer file: flagged, not filled.
- O-05 is closed for the Canada CPI (`STATIC_TOTALCPICHANGE`): each of the 58 reference months carries its Statistics Canada release date from The Daily, and every published 12-month change was checked equal to the stored value. US monthly series (FRED, latest vintages) have no release/vintage data, so they keep the A-22 lag in current runs and stay withheld in historical runs.
- On-demand fetches use `providers.TiingoProvider` (documented Tiingo End-of-Day API, adjusted close by the CRSP method, token in the `Authorization` header) when `APLOMB_TIINGO_TOKEN` is set and the data directory is local and writable; the accepted asset is published as `snap-<date>-od-<ticker>-<n>` and becomes the served version (`/meta` reports it). Tiingo's plans state "Internal Use Only": whether a public demo fits is the owner's decision. The meta endpoint has no currency or asset type, so only U.S.-listed non-fund instruments are accepted (USD, single-name equity, sector "unknown"); funds and non-U.S. listings answer `422 insufficient_data`, provider outages `503`. A rejected fetch (e.g. fewer than 30 rows) answers `accepted: false` with a provisional `Asset` built from the provider rows; nothing is published. Yahoo is not used. In AWS (read-only S3 snapshots) the endpoint stays unavailable.
- Cold `open()` of the starter snapshot parses ~50k rows (about 2 s on the development laptop); snapshots are cached per process.

### 7.4 AWS upload layout

`CachedObjectStore` reads `manifests/<version>.json` and `normalized/<version>/<dataset>.csv` under `APLOMB_DATA_PREFIX` (infra uses `snapshots/<version>/`). Upload exactly those files, for example `aws s3 cp data/manifests/snap-20261114-sourced.json s3://<bucket>/snapshots/snap-20261114-sourced/manifests/` and `aws s3 cp --recursive data/normalized/snap-20261114-sourced s3://<bucket>/snapshots/snap-20261114-sourced/normalized/snap-20261114-sourced/`; every file is checksum-verified on download.

### 7.5 Verification

`cd backend && python -m pytest tests/unit/datastore -q` (or `python -m unittest discover -s tests/unit/datastore -t .`): 99 offline tests covering DS-01…DS-08 and DAT-01…DAT-07, plus catalog mirror checks against `contracts/catalog.md`. Synthetic bundles with release/vintage dates for T12 live in `backend/tests/unit/datastore/_support.py` (`synthetic_bundle(with_releases=True)`).
