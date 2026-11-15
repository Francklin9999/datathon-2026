# World Explorer backend

**Track:** T11. **Tier:** P1; facilities/hazards are cut-list item 2. [HTTP §6](../../../contracts/api.md), [world types](../../../contracts/schemas.md) and [source register](../../../data/SOURCES.md).

## 1. Responsibility

Serve cached, source-backed events and geographic portfolio exposure. Globe interaction never triggers an uncontrolled third-party fanout. Supply feed, country panel, facilities and hazards using bounded/paginated queries. Event brief generation is T08's workflow using T09 research and this module's documented link candidates.

## 2. Internal services

`list_events(filters, cursor) -> EventPage`; `get_event(id, profile_id=None) -> EventDetail`; `country_exposure(profile, gate) -> list[CountryExposure]`; `country_panel(iso3, profile, gate)`; `list_facilities(filters)`; `list_hazards(filters)`; `layers()`. Wire responses follow API contract exactly. Bounding boxes crossing the dateline split internally; validate latitude [-90,90], longitude [-180,180], date interval <=366 days and API limits.

## 3. Batch ingestion and normalization

Ingest GDELT batch, official release feeds and manually curated **real** source events. “Curated” means human-selected, not fictional. Preserve canonical URL, raw source ID, occurrence/publication/retrieval timestamps, language and location precision. `eventId` hashes canonical primary URL; remove tracking params with a documented allow-list, not arbitrary query data. Merge same-URL duplicates; do not merge distinct stories solely on shared headline. When merging near duplicates, keep all source URLs and choose a deterministic primary source to retain identity.

Company mentions resolve via explicit alias table with ambiguous-name rejection. Geocoding requires source-supported place and precision; unknown location stays outside globe and appears in feed rather than invented coordinates. Country centroid uses precision country, never fake point precision. Headline/source counts are preserved; sourceCount is distinct publishers, not repeated syndication copies.

## 4. Importance (`M_EVENT_IMPORTANCE`)

Deterministic display priority only: `min(1, 0.45*official + 0.35*min(distinctPublishers,5)/5 + 0.20*recency)`, with official=1 for an official primary source else 0, recency=max(0,1-ageDays/30) at **dataset build time**. Store build timestamp so score does not drift per request. Score does not represent predicted market impact. UI can filter categories/counts without changing portfolio rules.

## 5. Geographic exposure and optional layers

Default country weights use listing-country proxy; sum unmatched/crypto/cash in an unknown bucket shown separately, not silently dropped or redistributed. ETF look-through overrides a fund's listing proxy only to the covered constituent weight; uncovered residual stays unknown, no double counting. Record basis per row. Country panel labels listing location versus documented operational exposure.

Facilities retain registry/year/operator/reported emissions; match ticker only through exact/probable issuer-name mapping with evidence. Probable matches are visibly uncertain. No emissions “score” inferred from incomplete facilities. Hazards show source/time/magnitude; proximity alone does not establish business impact. Layer available=false when its dataset is absent; counts/coverage describe loaded data, not world completeness.

## 6. Event-to-holding mechanism

Produce candidates with link types: named_in_source, listing_country, sector, theme, documented_exposure, etf_lookthrough. Evidence IDs support every stronger factual link; listing/sector/theme proxies are labelled assumptions. Financial impact defaults not_established. Optional observed asset return uses first master observation on/after event date and N subsequent master days, explicit actual period, fact source and `LIM_PRICE_MOVE_NOT_CAUSAL`; cannot use future rows in historical contexts.

## 7. Scale, failure and tests

Batch early, cache source calls and obey backoff. Paginate all events; cap rendered pins independently from stored event count, with explicit “showing X of Y” and category/time filters. Live lookup failure serves dated cache with stale label, never fabricates freshness. No requirement for all global news can be claimed; report coverage and retrieval failures.

WLD-01 URL dedupe/stable ID. WLD-02 ambiguous company/geography not invented. WLD-03 priority reproducible at build date. WLD-04 ETF residual/unknown weights sum correctly. WLD-05 country/date/bbox filters and pagination. WLD-06 probable facility match warning. WLD-07 event brief no impact claim without observed fact. WLD-08 unavailable layer and upstream failure. Handoff T15 a representative paginated dataset and empty/error states before live batch integration.

## 8. Implementation status (T11, 2026-11-15)

Implemented in `backend/aplomb/world/` with the standard library only.

| Module | Content |
|---|---|
| `ingest.py` | Batch CLI: fetch, pure parsers, canonical URL and `eventId`, alias table, merge, importance, deterministic bundle writer |
| `geo.py` | Country reference table (ISO3, EN/FR name, approximate centroid), source-place resolution, dateline-aware bounding box |
| `dataset.py` | `load_bundle()` verifies every file against the manifest SHA-256 and row counts; `BundleProvider` loads lazily |
| `service.py` | `WorldServiceImpl`: the `WorldService` protocol of the API plus `search_events` for the `world.search_events` tool |
| `passports.py` | Passports of `world_events` and `natural_hazards` once loaded; `WorldDatastoreService` overlays them on `GET /datasets` |
| `bundle/` | The committed bundle: `events.json`, `hazards.json`, `manifest.json` |

### 8.1 What is loaded, and what is not

Build of 2026-11-15 (`snap-20261115-world`), window 2021-11-12 to 2026-11-12, every source answered:

| Source | Items | Location precision | Category |
|---|---|---|---|
| USGS earthquake catalog, magnitude 6 or more | 668 events and 668 hazards | point (catalog epicentre) | natural_disaster |
| Bank of Canada press releases (RSS, recent items only) | 10 | country | monetary_policy when the title names the policy or interest rate, else other |
| Federal Reserve Board monetary-policy press feed (recent items only) | 15 | country | monetary_policy |
| Statistics Canada, The Daily: the 58 CPI releases already listed in `macro_release_dates` | 58 | country | macro_release |

Not loaded, and stated as such in the manifest and the Sources page: GDELT (the article index returned no usable batch on the build date and its items carry no source-supported event location, O-07), facility emissions (cut-list item 2), NASA FIRMS (needs a key). The two press feeds list recent releases only, so official events before autumn 2026 are limited to the CPI releases. This is a cited sample, not world coverage; `total`, `coverage` and the passports describe loaded data only.

Rebuild (network needed, about one minute; the API never needs it):

```bash
cd backend && uv run python -m aplomb.world.ingest --start 2021-11-12 --end 2026-11-12
```

A source that fails is recorded with its error and contributes nothing; if no event at all can be read the existing bundle is left untouched. The build date becomes the version label and fixes the importance scores.

### 8.2 Decisions taken in this track

- **Bundle location.** The bundle lives inside the Python package (about 0.8 MB) rather than in the S3 snapshot prefix, so the Lambda artifact, local runs and tests read the same verified files with no extra upload. It has its own version label; `X-Aplomb-Data-Version` stays the price snapshot.
- **Location is mandatory in the wire type.** `WorldEvent.location` needs coordinates, so an item without a source-supported place cannot be represented and is rejected at ingestion (counted per source in the manifest). An earthquake whose place string names no country keeps `countryIso3 = null` and an empty `relatedCountries`.
- **Country resolution.** Only the country named at the end of the source place string (or a U.S. state after a comma) is accepted; ambiguous names such as "Georgia" resolve to nothing. An ISO3 outside the reference table is displayed as its code.
- **Company mentions.** `COMPANY_ALIASES` in `ingest.py` lists unambiguous corporate names only: a bare "Apple", "Amazon", "Tesla" or "Fortis" is not a mention. No event of the current bundle names a holding.
- **Theme proxy (team assumption).** A monetary-policy event is tagged with the bond themes of its country (`bonds_canada`; `bonds_us`, `long_treasuries`). Wherever it produces a link the note says "team assumption".
- **Event-to-holding links.** One row per holding with its strongest code match: `named_in_source`, then `theme`, then `listing_country`. `impact` is always `not_established` on this endpoint, `evidenceIds` is empty and `documented_exposure` is never emitted; an observed price change is added only by the `event_brief` run, and only for a holding named in the source.
- **Unknown bucket.** `GET /world/exposure` returns holdings without a listing country (crypto, cash) under `countryIso3 = "ZZZ"` (ISO 3166 user-assigned), always last, never redistributed. Basis is `listing_country` for every row because no `etf_holdings` dataset is loaded (`LIM_ETF_NO_LOOKTHROUGH`).
- **Defaults.** Events: the last 30 days of the dataset. Country panel: the last 366 days. Hazards: the whole dataset. A cursor is bound to its filter set and data version; reusing it with other filters is a `validation_error`.
- **Event brief cutoff and provenance.** An `event_brief` run pins the event, its code-matched holdings and the manifest record of its source at creation. Its information cutoff (`asOf`) is the later of the price data date and the bundle build date. The cited event fact is available from the source's stated publication time, or from the retrieval time when the source states none; no time is assumed.
- **Bounding box.** `minLon` greater than `maxLon` is a box that crosses the dateline; it is accepted by the API and evaluated as two boxes.
- **Facilities.** No registry is loaded: the layer reports `available = false`, the capability is not advertised and the endpoint answers `501`.

### 8.3 Verification

`uv run pytest backend/tests/unit/world` (44 tests, offline): WLD-01 identity and merge, WLD-02 ambiguous places and company names, WLD-03 importance at the build date and deterministic bundle, WLD-04 country weights and unknown bucket for the three personas, WLD-05 filters, cursors, bounding boxes and the dateline, WLD-07 links without impact, WLD-08 failed source, tampered bundle and unavailable layers; WLD-06 has no data to test (no facility registry). Parser inputs in the tests are synthetic payloads in the source formats; the committed bundle is checked for integrity, contract validity and identity. `backend/tests/integration/test_run_composition.py` exercises every world endpoint and the `event_brief` run through HTTP.
