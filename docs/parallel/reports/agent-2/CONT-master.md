# CONT-master — instrument master, crosswalk, Wikidata

## Added
- `master.py`: MIC-less records allowed for `crypto`, `index`, `commodity` (provider + exact provider asset ID required); `isin_state` (`exact` / `not_in_source_record`, absence is never "no ISIN exists"); code-owned `MIC_ROUTES` (XNAS, XNYS, ARCX, XASE, BATS → SEC/Tiingo; XTKS → J-Quants; XKRX, XKOS → OpenDART; XLIM → captured BVL only; anything else `no_adapter`, never SEC) and `PROVIDER_ROUTES` (coinmetrics); `route_hint()`; `ASSET_COVERAGE`; `IdentifierAssertion` model (scheme, role, evidence class `direct|derived|unverified`, origin, source-stated dates, mandatory rule for `derived`, checksum/syntax validation). `source_route()` keeps its old signature and results (XTKS filings still `unavailable`).
- `master_repository.py`: completed. Separate `IDENTIFIER#<sha(session)>` partition: `publish_assertions()` stores the raw source once (`SOURCE#sha`) plus immutable assertions citing that hash; `assertions()` re-validates owner and source linkage. `crosswalk(store, sid, isin, as_of)` merges listing records (captured baseline + published), repository assertions, existing session GLEIF pair captures (`ENTITY_PAIR#`) and Wikidata candidate captures (`WIKIDATA#`), with per-row sources (URL, capture time, SHA-256, licence). Unverified rows report `corroborated_by` when a direct/derived row has the same value; the class is never upgraded. Routing per MIC, separating `listing_record` from `unverified_candidate` basis.
- `master_adapters.py` (new): `publish_gleif_pair` (reuses `exact.exact_pair`; only a matched row is published as `direct`), `publish_wikidata` (code-owned SPARQL: P946 ISIN, P1278 LEI, P5531 CIK, P414 exchange with P249 ticker and P580/P582 qualifiers; MIC only when the exchange item carries P7534; otherwise `exchange_item_ticker` with the exchange QID; all `unverified`), `publish_coinmetrics_asset` (crypto record keyed `coinmetrics:<id>`, gated by `APLOMB_COINMETRICS_NONCOMMERCIAL=1`).
- `master_routes.py` (new): `GET /v1/intelligence/master/crosswalk?isin&as_of`, `GET /v1/intelligence/master/coverage`, `POST /v1/intelligence/master/adapters/{gleif-pair?isin&lei | wikidata?isin | coinmetrics/{asset}}` (4/min/session each).
- `InstrumentMaster.tsx`: rewritten. Exact ISIN + as-of → crosswalk table (class, origin, source link, capture time, hash, stated validity, corroboration), listing lifecycle table, routing by MIC, Wikidata and GLEIF adapter actions, Coin Metrics provider-asset lookup/publish, coverage table. `WikidataCandidates.tsx`: card id + link to the crosswalk.

## Shared-file edits
- `backend/aplomb/api/app.py`: `include_router(master_router(...))` after the wikidata router; the two `/v1/intelligence/listings` routes now read `InstrumentRepository(store, sid).snapshot(...)` and listing search accepts `provider` + `provider_asset_id`.

## Env vars
`APLOMB_SOURCE_USER_AGENT` (Wikidata contact; existing), `APLOMB_COINMETRICS_NONCOMMERCIAL=1` (existing). No new ones.

## Facts checked live on 2026-11-15
- Wikidata property labels: P414 stock exchange, P249 ticker symbol (qualifier for P414), P7534 "ISO 10383 market identifier code", P1278 LEI, P5531 Central Index Key, P946 ISIN. **P2283 is "uses", not MIC**; the code uses P7534.
- A hand-run SPARQL for US0378331005 returned Q312 with LEI HWUPKR0MPOU8FGXBT394, CIK 0000320193, XNAS:AAPL (start 1980-12-01) and XTKS:6689 (1990-09-01 → 2004-12-25). Not saved as evidence.
- Wikidata P7534 values for the routed MICs match the exchange names used in `MIC_ROUTES` (community data, not the ISO 10383 file).

## Not verified / limitations
- Verification run: module imports, Ruff on owned files + `app.py`, `npx tsc --noEmit`. No tests were added or run, no HTTP calls to the new routes, no browser checks.
- The adapter's SPARQL query (with `?isin` FILTER and all OPTIONALs) has not been run in the form the code sends it; it differs slightly from the hand-run query.
- Index and commodity kinds have no adapter (status `unavailable`); FRED terms restrict caching/AI use, so it was not used.
- Wikidata date-precision qualifiers are not fetched; a stated day may stand for a month or year.
- Listing-record identifiers cite the whole record's evidence; there is no per-field attribution.
- Routing gives the adapter name only; it does not convert tickers to J-Quants or DART codes.
