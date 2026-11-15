# Agent 3 integration interfaces

## World observations

`GET /v1/world/observations` accepts `mode`, `bbox=west,south,east,north`, repeated `country`, `from`, `to`, `asOf`, `q`, `limit` and a filter-bound `cursor`. The response returns `items`, `total`, `nextCursor`, `dataVersion`, `capturedAt` and per-mode `modes` availability/count/reason. Each item has the original source URL, `retrievedAt`, optional `publishedAt`, `occurredAt`, `timeBasis`, `datasetId`, `countryIso3`, limitations, optional point location and optional source polygon geometry. `location=null` means source point coordinates were not established; `countryIso3` can still carry a sourced national reporting area. The France ADM1 boundaries have top-level `geometry` with no invented pin, and polygon intersection applies to viewport filters. NOAA polygon anchors retain original source geometry in `location.geometry`. `reference_period` time basis marks monthly display anchors rather than observed instants. UCDP's coded location precision is kept in the source detail.

Example: `/v1/world/observations?mode=aviation&bbox=100,-40,160,-20&limit=20` returns a bounded south Pacific sample; it makes no claim about worldwide station coverage. `asOf=2026-11-14` returns no new provider captures because all new captures were retrieved on 2026-11-15.

`GET /v1/world/events/{eventId}` has an additive `geographicRelationships` array of typed, hashed source-supported `EVENT_OCCURRED_AT` edges. No security or issuer relationship is inferred.

## Provider capture interface

`load_provider_snapshots(directory=..., as_of=None) -> (rows, manifests)` validates raw and normalized SHA-256, identity, dates and coordinates. It selects the newest captured version per provider; a capture after `as_of` is withheld. A damaged capture disables the optional provider collection for world observations and passports, while core portfolio reads continue. Per-provider corruption isolation within that collection remains to be implemented. `python -m aplomb.world.providers.ingest --source ...` is a bounded manual refresh path; no runtime request reaches a provider.

Current provider IDs are listed in `backend/aplomb/world/passports.py` and mirrored by `DatasetId` and `contracts/catalog.md`. The latest additions include `world_usgs_geojson`, `world_geoboundaries_fra_adm1`, `world_ucdp_ged_ukraine_2025`, `world_climate_trace_canada_electricity_co2`, `world_fda_drug_enforcement_counts`, `world_crossref_climate_bibliography` and `world_ted_published_notice_metadata`. `trade_portwatch_ports` is registered as planned pending reuse permission and actual capture. The new datasets are separate verified world bundles; the active price snapshot manifest was not changed. WITS/UN Comtrade captures have conditional free-use permissions and must be reassessed for any commercial API or streaming product.

## Cross-agent dependency

Agent 2's `backend/aplomb/api/runtime.py` tool wrapper currently calls `world.search_events(as_of=str(ctx.as_of), **args)`. For true historical replay it should call `world.search_events(as_of=str(ctx.as_of), historical=ctx.historical, **args)`. Agent 3's service supports the additive `historical` parameter and tests the capture boundary. This prevents current-only bundled events from appearing as knowledge available on an earlier date while preserving current snapshot research calls. Agent 2 owns that runtime edit and the end-to-end replay test.

Documented entity-to-security, facility operator, revenue geography and supply-chain relationships require Agent 2's verified identifiers and dated evidence; modeled impacts require Agent 1's calculations. The world service returns `not_established` for existing portfolio proxies and does not promote a matching country or name into a financial fact.

## Shared bridges

- `backend/aplomb/contracts/{api,catalog}.py`, `contracts/catalog.md`, generated JSON/TypeScript contracts: typed observation response, geographic relationship and provider dataset IDs.
- `backend/aplomb/api/{app,queries,services}.py`: bounded observations HTTP route and service protocol.
- `backend/aplomb/datastore/passports.py`: planned descriptors for provider IDs so the existing snapshot catalog remains valid before world overlays mark verified captures in use.
- `web/src/api/client.ts`: typed observations request.

All bridges are additive. The integrator must regenerate mirrors after reconciling the three branches, check dataset-ID and contract conflicts, and rerun full contract/API/web gates. No production migration or feature flag change is made here.

## Latest provider geometry and units

The provider registry, `DatasetId`, catalogue and datastore descriptors now include the newer SDMX, energy, carbon, satellite, OSM/Nominatim, ADS-B, MarineCadastre, Copernicus, FIRMS, New York Fed SCE, Ember and Geofabrik captures. Each capture is a separate versioned bundle and is only available from its retrieval time in replay.

OSM Eiffel Tower and NASA GIBS footprints use source polygon geometry for viewport intersection without invented pins. The GIBS polygon is an image-tile footprint, not a claim of clear observed imagery. Copernicus points are activation-area centroids, FIRMS points are thermal-detection pixel centers, MarineCadastre points are annual raster query anchors, and Geofabrik points are mapped transport reference objects from a Monaco extract that may include neighboring France. These roles are explicit in item limitations and source summaries. Ember records are monthly country generation totals in TWh with no point coordinates; Fraunhofer Energy-Charts values are 15-minute national power in MW. Both are distinct from plant generation or issuer exposure.

The HAPI INFORM 2025 national risk capture adds 191 `hazards` mode country-list observations with no map point. The HAPI app identifier is used only by explicit manual capture in `world/providers/hapi.py`; runtime reads require no credential. The key remains in an ignored local environment file and is redacted from all committed capture URLs. The INFORM composite is humanitarian context, not a disaster event or financial risk score.
