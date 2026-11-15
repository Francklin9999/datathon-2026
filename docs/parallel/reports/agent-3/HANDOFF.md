# Agent 3 world data handoff

Branch: `codex/agent-3-world-data` in `.worktrees/world-data`.
Base: `2604b9689e9f992b4e9e46c4a06ea89ec57ac155` (`codex/parallel-base-20261115`).
Commit: use `git rev-parse codex/agent-3-world-data` after push.

## Implemented and inspectable

- Added a source-backed, bounded `GET /v1/world/observations` API with mode, viewport, country, date, search, `asOf` and cursor filtering. Each item retains source URL, capture version, dates, time basis, limitations and available source geography. National, publication and bibliographic records stay in the list without fabricated map pins.
- Added 21 checksum-verified runtime provider captures totaling 36,093 rows, with raw and normalized SHA-256, quality reports, rights notes, source passports and capture-date availability gates. The captures are WRI plants; AviationWeather selected stations; NOAA polygon weather alerts; Federal Register publications; GDACS alerts; NASA POWER temperature; EPA SEMS site references; ECB press releases; UK sanctions update notes; USGS minerals; UN Comtrade exports; WITS fuel exports; UNCTAD export concentration; Statistics Canada CPI; USGS weekly magnitude 4.5 to below 6 earthquakes; France ADM1 geoBoundaries polygons; Ukraine 2025 UCDP GED coded events; Canada electricity-generation Climate TRACE modeled CO₂; openFDA drug enforcement class counts; Crossref climate bibliography; and EU TED published procurement notice metadata. Exact bounds and rights are in each provider manifest and source report.
- Extended World Explorer with ten navigable modes, observation list/detail, pins, sourced polygons, layer controls, geographic search, regional navigation and clear unavailable states. The existing event, airport, facility, hazard and portfolio views remain. National and institutional association is not promoted to an issuer or holding relationship.
- Added typed, source-hashed geographic relationships for bundled events and facility geography. Explicit historical world queries gate current-only bundled events at their build date.

The 218 checklist rows are fully dispositioned in `SOURCES.csv`: 14 baseline, 36 newly integrated, 4 staged evidence-only, 2 checked with empty current feeds, 2 checked with reuse rights unresolved, 55 login gated set aside, 6 paid or billing dependent excluded, and 99 still needing provider engineering. Rows can repeat a source under SRC and MASTER; they do not count distinct APIs. `REQUIREMENTS.md` and `BLOCKERS.md` state the incomplete acceptance and external dependencies.

## Provenance and scope

Every new capture is bounded, manually retrieved on 2026-11-15, and cannot be presented as available in earlier historical replay. WRI's 34,936 power-plant records are a static reference, not current generation or verified issuer ownership. AviationWeather covers six chosen stations, not aircraft movement. NOAA alerts preserve source polygons and labeled display anchors; 335 lacking supported geometry were excluded. GDACS covers its newest 100-record page and source points can be representative. NASA POWER is 186 gridded daily values at six requested points, not station measurements. EPA SEMS is a 438-record site-reference sample, not emissions or current contamination. Federal Register, ECB and UK sanctions rows are publication metadata and have no source point coordinates. USGS minerals, trade and CPI values are country or global records without invented points; CPI levels are not inflation rates. The monthly CPI and Climate TRACE dates are labeled reference periods. Climate TRACE estimates are modeled emissions, FDA aggregates count enforcement records rather than unique recalls, Crossref rows are bibliographic metadata, and TED buyer country is not a procurement performance location. UCDP points are source coded representative locations at the recorded precision. France ADM1 polygons retain source geometry for viewport intersection and have no invented pin. The reports beside this handoff state each selected slice, attribution and reuse terms.

Four additional captures remain only in evidence: Eurostat greenhouse-gas data (reuse terms unclear), EPA ECHO facility results (rights of underlying fields unclear), and ClinicalTrials.gov Canadian study locations (publication guidance requires continuous freshness). NHC's three official current basin feeds had no active cyclone advisory or geometry at capture time. OFAC was anonymously reachable, but an affirmative applicable redistribution basis was not established. Those checks are documented without presenting them as runtime datasets.

## Integration interfaces

Primary paths: `backend/aplomb/world/`, `web/src/features/world/`, `web/src/lib/world.ts`, `docs/parallel/reports/agent-3/`, `docs/evidence/parallel/agent-3/`.

Shared additive bridges are `backend/aplomb/contracts/{api,catalog}.py`, generated contract mirrors, `backend/aplomb/api/{app,queries,services}.py`, `backend/aplomb/datastore/passports.py`, and `web/src/api/client.ts`. `INTERFACES.md` documents the HTTP shape, snapshot loader and Agent 2 handoff. Agent 2's runtime must pass `historical=ctx.historical` to `world.search_events` for the current-event availability gate during tool replay. Validated issuer and holding relationships, grounded AI summaries and risk calculations require integration with Agent 2 and Agent 1. Merge this branch only after reconciling shared bridges and running combined gates.

## Verification

The runtime loader verified 21 manifests and 36,093 rows. The latest TED registration passed dataset HTTP smoke checks, contract generation and TypeScript type checking. Earlier focused provider, world-service and HTTP checks passed 66 tests; contract tests passed 213 tests, TypeScript type checking passed and a web static export built. Browser inspection loaded Japan country search and a Japanese aviation station; desktop evidence is `docs/evidence/parallel/agent-3/browser/aviation-japan-desktop.png`. The mobile viewport was checked for horizontal overflow while its captured source panel was loading. Later source additions were not covered by that web build. No new tests were written for the latest integrations and no full-suite pass is claimed. The full `npm run check` did not finish at the slow budget-watchdog integration test.

No deployment, production change, cloud mutation, merge or video publication was performed.
