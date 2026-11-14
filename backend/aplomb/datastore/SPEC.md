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
