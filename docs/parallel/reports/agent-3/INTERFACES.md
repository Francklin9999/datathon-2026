# Agent 3 integration interfaces

## World observations

`GET /v1/world/observations` accepts `mode`, `bbox=west,south,east,north`, repeated `country`, `from`, `to`, `asOf`, `q`, `limit` and a filter-bound `cursor`. The response returns `items`, `total`, `nextCursor`, `dataVersion`, `capturedAt` and per-mode `modes` availability/count/reason. Each item has the original source URL, `retrievedAt`, optional `publishedAt`, `occurredAt`, `timeBasis`, `datasetId`, limitations and optional location. `location=null` means source location was not established and the item belongs in the source list, not on the map. NOAA polygon anchors retain original source geometry in `location.geometry`.

Example: `/v1/world/observations?mode=aviation&bbox=100,-40,160,-20&limit=20` returns a bounded south Pacific sample; it makes no claim about worldwide station coverage. `asOf=2026-11-14` returns no new provider captures because all new captures were retrieved on 2026-11-15.

`GET /v1/world/events/{eventId}` has an additive `geographicRelationships` array of typed, hashed source-supported `EVENT_OCCURRED_AT` edges. No security or issuer relationship is inferred.

## Provider capture interface

`load_provider_snapshots(directory=..., as_of=None) -> (rows, manifests)` validates raw and normalized SHA-256, identity, dates and coordinates. It selects the newest captured version per provider; a capture after `as_of` is withheld. A damaged capture disables the optional provider collection for world observations and passports, while core portfolio reads continue. Per-provider corruption isolation within that collection remains to be implemented. `python -m aplomb.world.providers.ingest --source ...` is a bounded manual refresh path; no runtime request reaches a provider.

Current provider IDs: `world_aviation_weather`, `world_noaa_alerts`, `world_gdacs_alerts`, `world_federal_register`, `energy_wri_plants`. `trade_portwatch_ports` is registered as planned pending reuse permission and actual capture. Shared `DatasetId` and `contracts/catalog.md` mirror those names. The new datasets are separate verified world bundles; the active price snapshot manifest and common contract version were not changed.

## Cross-agent dependency

Agent 2's `backend/aplomb/api/runtime.py` tool wrapper currently calls `world.search_events(as_of=str(ctx.as_of), **args)`. For true historical replay it should call `world.search_events(as_of=str(ctx.as_of), historical=ctx.historical, **args)`. Agent 3's service supports the additive `historical` parameter and tests the capture boundary. This prevents current-only bundled events from appearing as knowledge available on an earlier date while preserving current snapshot research calls. Agent 2 owns that runtime edit and the end-to-end replay test.

Documented entity-to-security, facility operator, revenue geography and supply-chain relationships require Agent 2's verified identifiers and dated evidence; modeled impacts require Agent 1's calculations. The world service returns `not_established` for existing portfolio proxies and does not promote a matching country or name into a financial fact.

## Shared bridges

- `backend/aplomb/contracts/{api,catalog}.py`, `contracts/catalog.md`, generated JSON/TypeScript contracts: typed observation response, geographic relationship and provider dataset IDs.
- `backend/aplomb/api/{app,queries,services}.py`: bounded observations HTTP route and service protocol.
- `backend/aplomb/datastore/passports.py`: planned descriptors for provider IDs so the existing snapshot catalog remains valid before world overlays mark verified captures in use.
- `web/src/api/client.ts`: typed observations request.

All bridges are additive. The integrator must regenerate mirrors after reconciling the three branches, check dataset-ID and contract conflicts, and rerun full contract/API/web gates. No production migration or feature flag change is made here.
