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
