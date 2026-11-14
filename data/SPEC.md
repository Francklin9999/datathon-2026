# Data ingestion and versioned snapshots

**Track:** T04; T09/T11 contribute enrichment adapters. **Tier:** starter ingestion P0, extended sources P1. [Datastore interface](../backend/aplomb/datastore/SPEC.md), [source register](SOURCES.md), [dataset passports](../contracts/schemas.md) §12.

## Pipeline and immutable inputs

Keep `Datathon2026/alphaforge_starter/` unchanged. Its build script is an organizer reproduction tool, not an application startup dependency. Import local CSVs into a versioned snapshot; do not redownload Yahoo data for baseline controls. Layout: `data/raw/<version>/`, `data/normalized/<version>/`, `data/manifests/<version>.json`, `data/metadata/` for assignments and availability. Large generated datasets are excluded from Git; retain manifests, metadata and checksums.

Ingestion stages: read source → validate raw schema/rows → preserve hash and retrieval metadata → normalize types/classification → attach availability policy → write staged objects → validate cross-dataset coverage → atomically publish manifest. Failed ingestion never replaces the active manifest. A snapshot ID covers a coherent set of versioned datasets, not mutable filenames.

## Minimum dataset schemas

| Dataset | Required columns and keys | Availability policy |
|---|---|---|
| assets_universe | asset_id,ticker,name,asset_class,market,currency,sector; ticker unique | Static 2026 selection, disclose survivorship |
| prices_daily | date,ticker,open,high,low,close,adj_close,volume,currency; key date+ticker | Explicit daily policy; adjusted snapshot is not original vintage |
| corporate_actions | ex_date,ticker,action,value,unit; normalize ex_date to date and retain unit | Reference only; never reapply |
| fx_usdcad_daily | date,usdcad,cadusd; positive, date unique | Same-day publication policy, holiday forward-fill only from past |
| macro_rates | date,series_id,value,unit,frequency,label,source; date+series unique | Reference date distinct from actual release/vintage |
| asset_themes | ticker,theme,justification,sourceUrl,assignedAt,isAssumption | Team assignment; not historical evidence without dated support |
| macro_release_dates | seriesId,referenceDate,publishedAt,vintageAt,sourceUrl | Real release and vintage metadata required for historical use |
| etf_holdings | fundTicker,constituentId,ticker,weightPct,reportDate,publishedAt,sourceUrl | Dated issuer document; preserve partial coverage |
| research_documents | documentId,url,retrievedAt,publishedAt,textHash,storageKey,licence | Cached text, no invented publication date |
| world_events | WorldEvent wire fields plus raw-source references | Occurrence/publication/retrieval kept separate |

Validate actual source headers before adapters: names in this spec describe intended normalized columns and must not trigger manual edits to raw CSVs. Register all optional datasets from the catalog as planned until loaded and checked. DatasetPassport.status cannot be in_use just because an endpoint responds.

## Data quality

Reject duplicates, malformed dates/nonfinite values, unknown ticker/currency, nonpositive adjusted prices and inconsistent primary keys. Flag zero-volume observations, calendar mismatch, split anomalies, suspicious returns and coverage gaps without silently deleting them. No price interpolation. Master calendar and conversion are calculation-layer transformations documented in passports. Check original input counts and checksums before controls; run per-series coverage validation for macro.

Starter controls: 31 assets, 40,049 prices, 658 corporate actions, 1,245 FX rows and 8,281 macro rows. Do not claim zero detected anomalies means economically verified values. Retain CNQ annotation and vendor-source limits.

## Extensions and ownership

On-demand: normalize ticker identity/listing/currency, public CAD/USD listings only, >=30 raw rows for acceptance and >=252 master observations for risk rules. Publish a new snapshot before exposing it to runs. Unknown sector/theme returns unknown until sourced; do not ask the LLM to fabricate a classification. Revisions invalidate source-dependent caches by version.

T09 owns fetched documents/attention/filings; T11 events/facilities/hazards; T04 integrates their output with manifests/passports. Every contributed dataset includes source/terms, actual retrieval date, checksums, schema, quality checks, availability and limitations. Avoid whole copyrighted article redistribution; store only permitted content and quoted evidence needed by the demo.

## Tests and handoff

DAT-01 all starter counts/keys. DAT-02 idempotent ingestion and source hash stability. DAT-03 staged failure cannot corrupt active version. DAT-04 release/reference-date separation. DAT-05 source traps mapped to passports. DAT-06 on-demand acceptance/short-history/rejection. DAT-07 metadata round-trips to `GET /datasets`. Done includes a small local snapshot, S3-upload-ready manifest and deterministic loader tests; no AWS access required for the first handoff.

## Current state (T04, 2026-11-14)

Snapshot `snap-20261113-starter` is published and active: `data/manifests/snap-20261113-starter.json` (hashes, counts, coverage, availability policies, checks, quality flags) and `data/manifests/active.json`. `raw/` and `normalized/` are gitignored and rebuilt from the manifest. Team metadata copied into each snapshot: `data/metadata/asset_themes.csv` (44 theme assumptions) and `data/metadata/macro_series.csv` (frequency class and revision status per series, from the organizer metadata). `macro_release_dates.csv` is optional and absent until O-05 is closed.

Materialize or verify the snapshot (idempotent; fails without changing anything if a source or hash differs):

```bash
cd backend && python -m aplomb.datastore.ingest --source ../Datathon2026/alphaforge_starter --data-root ../data --version snap-20261113-starter
```

A changed source or metadata file needs a new version label. Implementation details, availability rules and limits: [datastore §7](../backend/aplomb/datastore/SPEC.md).
