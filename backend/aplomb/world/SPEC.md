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
| `geo.py` | Country reference table (ISO3, EN/FR name, approximate centroid), source-place resolution, dateline-aware bounding box, the country presentation of §8.6 (`present_iso3`, `present_name`, `present_rows`) |
| `dataset.py` | `load_bundle()` verifies every file against the manifest SHA-256 and row counts, then presents countries (§8.6); `BundleProvider` loads lazily |
| `service.py` | `WorldServiceImpl`: the `WorldService` protocol of the API plus `search_events` for the `world.search_events` tool |
| `assessment.py` | Source-supported country and corporate-name resolution, disclosed theme rules for screening every provider and reference record |
| `facilities.py` | ECCC GHGRP annual facility emissions (`/world/facilities`); no fuzzy security matching or ESG scoring |
| `country_macro.py` | World Bank WDI annual country indicators: bounded capture and immutable snapshot for the country panel |
| `geo_boundaries.py` | Bounding-box queries over captured source polygons (NASA CMR granule and GIBS tile footprints) |
| `relationships.py` | `EVENT_OCCURRED_AT` geographic edges served in `/world/events/{eventId}`; no ownership or financial claim |
| `providers/` | Content-addressed provider captures (`snapshot.py` loader and publisher, per-source capture modules, `ingest.py` manual refresh CLI) served by `/world/observations` in the modes `news`, `macro` and `environment` |
| `passports.py` | Passports of `world_events` and `natural_hazards` once loaded, plus one per provider capture; `WorldDatastoreService` overlays them on `GET /datasets` |
| `bundle/` | The committed bundle: `events.json`, `hazards.json`, `manifest.json`; `facilities*.json`, `country_macro*.json` (each with its manifest); `providers/<datasetId>-<date>-<sha16>/` captures |

### 8.1 What is loaded, and what is not

First build of 2026-11-15 (`snap-20261115-world`), window 2021-11-12 to 2026-11-12, every source answered. The bundle now committed is a later version (§8.4); this table records the first build:

| Source | Items | Location precision | Category |
|---|---|---|---|
| USGS earthquake catalog, magnitude 6 or more | 668 events and 668 hazards | point (catalog epicentre) | natural_disaster |
| Bank of Canada press releases (RSS, recent items only) | 10 | country | monetary_policy when the title names the policy or interest rate, else other |
| Federal Reserve Board monetary-policy press feed (recent items only) | 15 | country | monetary_policy |
| Statistics Canada, The Daily: the 58 CPI releases already listed in `macro_release_dates` | 58 | country | macro_release |

A NASA EONET v3 capture (2026-10-15 to 2026-11-12, bounded to the first 500 records: 480 items, 20 rejected) was added afterwards as `snap-20261115-world-eonet-570970dd`; the event feed rule of §8.2 now keeps it out of the feed.

Not part of the event bundle, and stated as such in `manifest.json` `notIngested` and on the Sources page: GDELT (the article index is not fetched at build time, O-07; bounded GDELT captures are separate `world_gdelt_*` provider observations), facility emissions (ECCC GHGRP is served separately as `emissions_facilities`; EPA facility emissions are not loaded) and NASA FIRMS (MODIS detections are not served); NASA EONET natural events and USGS earthquakes below magnitude 6.0 are kept out of the feed by its rule (§8.2). The two press feeds list recent releases only, so official events before autumn 2026 are limited to the CPI releases. This is a cited sample, not world coverage; `total`, `coverage` and the passports describe loaded data only.

Rebuild (network needed; the API never needs it). Step 1 rebuilds the base bundle, including EONET over the last `--eonet-days` days of the window (default 28, at most 366, first 500 records). It writes **in place** unless `--out` is given, and an in-place run replaces the committed expanded bundle of §8.4, so build into a fresh directory and expand it:

```bash
cd backend
uv run python -m aplomb.world.ingest --start 2021-11-12 --end 2026-11-12 --out /tmp/world-base
uv run python ../scripts/expand_world_events.py --base /tmp/world-base --out /tmp/world-expanded \
  --start 2025-11-12 --end 2026-11-12 --min-magnitude 5
```

Check the output, then copy `events.json`, `hazards.json` and `manifest.json` into `bundle/`. A source that fails is recorded with its error and contributes nothing; if no event at all can be read the existing bundle is left untouched. The build date becomes the version label and fixes the importance scores. `scripts/ingest_eonet.py` refreshes only EONET into a fresh `--out`. The other layers have their own capture commands: `scripts/ingest_facilities.py`, `scripts/ingest_world_bank.py` and `python -m aplomb.world.providers.ingest --source <name>` (provider captures, each a new content-addressed directory; earlier versions are never deleted).

### 8.2 Decisions taken in this track

- **Bundle location.** The bundle lives inside the Python package (on disk, about 123 MB with `providers/` and 4.8 MB without it, per `du -sh` on 2026-11-15) rather than in the S3 snapshot prefix, so the Lambda artifact, local runs and tests read the same verified files with no extra upload. It has its own version label; `X-Aplomb-Data-Version` stays the price snapshot.
- **Location is mandatory in the wire type.** `WorldEvent.location` needs coordinates, so an item without a source-supported place cannot be represented and is rejected at ingestion (counted per source in the manifest). An earthquake whose place string names no country keeps `countryIso3 = null` and an empty `relatedCountries`.
- **Country resolution.** Only the country named at the end of the source place string (or a U.S. state after a comma) is accepted; ambiguous names such as "Georgia" resolve to nothing. An ISO3 outside the reference table is displayed as its code.
- **Company mentions.** `COMPANY_ALIASES` in `ingest.py` lists unambiguous corporate names only: a bare "Apple", "Amazon", "Tesla" or "Fortis" is not a mention. No event of the current bundle names a holding.
- **Theme proxy (team assumption).** A monetary-policy event is tagged with the bond themes of its country (`bonds_canada`; `bonds_us`, `long_treasuries`). Wherever it produces a link the note says "team assumption".
- **Event feed rule (team decision).** The only natural-disaster events in the feed are USGS earthquakes of magnitude 6.0 or more, the magnitude read from the catalog record in `hazards.json`. `ingest.build_bundle` applies it, so every build (the CLI and `scripts/expand_world_events.py`) does; `manifest.json` records it as `method.naturalDisasterRule`, gives each USGS/EONET source its kept `items` and `excludedByFeedRule`, and lists the excluded sources in `notIngested`. Every captured earthquake stays in `hazards.json` and `/world/hazards`.
- **No event relationship review.** No documented event-to-issuer relationship source is connected, so an `event_brief` result carries no `relationshipReview` (the optional contract field is kept); its links are the code matches below.
- **Event-to-holding links.** One row per holding with its strongest code match: `named_in_source`, then `theme`, then `listing_country`. `impact` is always `not_established` on this endpoint, `evidenceIds` is empty and `documented_exposure` is never emitted; an observed price change is added only by the `event_brief` run, and only for a holding named in the source.
- **Unknown bucket.** `GET /world/exposure` returns holdings without a listing country (crypto, cash) under `countryIso3 = "ZZZ"` (ISO 3166 user-assigned), always last, never redistributed. Basis is `listing_country` for every row because no `etf_holdings` dataset is loaded (`LIM_ETF_NO_LOOKTHROUGH`).
- **Defaults.** Events: the last 30 days of the dataset. Country panel: the last 366 days. Hazards: the whole dataset. A cursor is bound to its filter set and data version; reusing it with other filters is a `validation_error`.
- **Event brief cutoff and provenance.** An `event_brief` run pins the event, its code-matched holdings and the manifest record of its source at creation. Its information cutoff (`asOf`) is the later of the price data date and the bundle build date. The cited event fact is available from the source's stated publication time, or from the retrieval time when the source states none; no time is assumed.
- **Bounding box.** `minLon` greater than `maxLon` is a box that crosses the dateline; it is accepted by the API and evaluated as two boxes.
- **Facilities.** ECCC GHGRP reporting year 2024 is loaded (`emissions_facilities`, 1,863 rows, `snap-20261115-eccc-6c708ab589`). With `APLOMB_FEATURE_WORLD_LAYER_FACILITIES=true` (`dev:api` sets it; the flag defaults to `false`, and the AWS stack enables it only when `world_layer_facilities` is in `application.features`) the layer reports `available = true`, the capability is advertised and `GET /world/facilities` answers `200`; otherwise the route answers `feature_disabled`. The research tool `emissions.facilities` is offered only in a run whose cutoff is on or after the capture day. Rows carry no security match (`ticker = null`, `matchConfidence = none`). The capture has no historical vintages, so a request with `asOf` is a `validation_error` (422).
- **Observation modes.** `/world/observations` serves `news`, `macro` and `environment` only; any other `mode` is a `validation_error`. Aviation, trade and shipping, conflicts, energy, economic infrastructure and observation-level hazards were removed with their captures, capture modules and the airport reference (`/world/airports`), because they do not serve the persona decisions. Their dataset ids stay in `contracts/catalog.md` §10 for this release only, with `planned` "Not served" passports, so a site built from this contract still accepts an older API's responses. With `scope=all`, feed events appear as `macro` (monetary policy, macro releases), `environment` (the feed earthquakes) or `news`.
- **Provider captures.** A damaged capture (checksum, row count or schema) drops only its own source; the other sources are still served, and `/world/observations` gives the integrity reason only for the modes of the damaged sources (every empty mode when the source's mode cannot be told from its ID).

### 8.3 Verification

`uv run pytest backend/tests/unit/world` (offline; run it from the repository root, some tests read `data/inputs/` by relative path): WLD-01 identity and merge, WLD-02 ambiguous places and company names, WLD-03 importance at the build date and deterministic bundle, WLD-04 country weights and unknown bucket for the three personas, WLD-05 filters, cursors, bounding boxes and the dateline, WLD-07 links without impact, WLD-08 failed source, tampered bundle and unavailable layers; WLD-06 has no probable match to test (facility rows carry no security match). Parser inputs in the tests are synthetic payloads in the source formats; the committed bundle is checked for integrity, contract validity and identity. `backend/tests/integration/test_run_composition.py` exercises every world endpoint and the `event_brief` run through HTTP.

### 8.4 Extended globe coverage

The current bundle (`snap-20261115-world-expanded-54bfcad0-m6`) supersedes the
initial counts above. It contains 751 events (83 official releases and 668 USGS
earthquakes of magnitude 6.0 or more) and 2,528 earthquake hazards. An additional
USGS magnitude-5 capture covers 2025-11-12 to 2026-11-12: 1,999 source records,
no rejected records; all of them are hazards, and the feed rule of §8.2 keeps the
1,860 earthquakes below magnitude 6.0 and the 479 NASA EONET events out of the
feed. The bundle was rebuilt offline from the previous verified bundle with the
same build time, so the kept events and every hazard are unchanged. Raw source
evidence, hashes and prior capture metadata are retained.
`scripts/expand_world_events.py` produces a fresh verified directory before
publication.

Provider snapshots supply additional news location metadata, macro and market
releases and environmental observations. `GET /world/observations` supports `scope=providers` to
avoid duplicating core events, `mapOnly=true` to retain actual source coordinates,
and `order=coverage` to interleave datasets and geographic cells. These options
are included in the cursor signature; default date ordering remains supported.
The frontend's initial provider overview loads up to 2,000 points, with further
loading and topic/region filters. Verified event pages still load completely.

Source observations retain their provenance, precision, capture gate and limitations.

### 8.5 Portfolio assessments for every globe record

Every portfolio-scoped event detail, provider observation, emissions facility
and earthquake includes a completed holdings assessment.
Screen all positive-weight positions against the source's explicit issuer names,
disclosed theme proxies and supported countries. Return one row per holding with
its strongest name/theme/listing-country match, plus unique matched weight,
holdings checked, calculation time and matching inputs.

Source country codes and supported source-place strings are used; GDELT FIPS
codes require an explicit mapping and are never treated as ISO alpha-2. Unknown
geography stays unknown. Name mentions from reporting-company fields remain
name mentions, not ownership or reviewed security relationships. Source capture
files are unchanged by the assessment. Financial impact and operating exposure
remain unestablished.

An empty match list is a completed screen, with the source and holding coverage
gaps shown alongside it. Provider cursors include profile and effective holding
inputs, so a profile switch or portfolio edit cannot mix assessed pages.
The event feed's relevance flag uses the same matcher as its detail popup,
including theme proxies.

### 8.6 Country presentation (team decision)

Source codes and names for Israel, the West Bank and Gaza are presented as one
region, `PSE` / Palestine, in every world output: event `relatedCountries`,
`location.countryIso3`, `location.placeName` and titles, hazard titles, provider
observations (country code, title and place or country name fields), facilities,
the country panel, exposure and every assessment. It is applied once when a
capture is loaded (`dataset.load_bundle`, `providers.snapshot.load_provider_snapshots`,
`facilities.load_facilities`), after every checksum has been verified; the captured
files and their hashes are never changed. Names are replaced as whole words
(`Israel`, `West Bank`, `Gaza Strip`, `West Bank and Gaza`); `Israeli` and the city
of Gaza are left as written.

`GET /world/countries/ISR` answers the `PSE` panel, and `country=ISR` filters select
`PSE`. Where a source publishes both an `ISR` and a `PSE` series (World Bank
indicators per indicator, WGI per source), the source's own `PSE` series is served
and the ISR-coded rows are withheld, never merged or summed: 4 World Bank rows and
1 WGI row. The passports of `world_events`, `natural_hazards`,
`world_bank_indicators` and of every affected provider capture state the decision
in `processing`, and their `rowCount` counts the rows served.
