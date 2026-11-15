# Agent 3 world data handoff

Branch: `codex/agent-3-world-data` in `.worktrees/world-data`.
Base: `2604b9689e9f992b4e9e46c4a06ea89ec57ac155` (`codex/parallel-base-20261115`).
Final commit: see `git rev-parse codex/agent-3-world-data` after the branch is pushed.

## Implemented and inspectable

- Added a bounded, source-backed `/v1/world/observations` API with mode, viewport, country, date, search, `asOf` and cursor filtering. It returns original URLs, dates, capture version, mode availability, limitations and optional sourced geometry. An unlocated policy publication remains in the list without a map pin.
- Captured six provider datasets with raw and normalized SHA-256, quality reports, rights and conservative capture-date replay gates: 34,936 WRI power plants, six requested international NOAA AviationWeather stations, three NOAA polygon weather alerts, 20 Federal Register publications, 100 recent GDACS disaster alerts, and 186 NASA POWER daily temperature values at six points. Their captures and manifests are in `backend/aplomb/world/bundle/providers/`; evidence is in `docs/evidence/parallel/agent-3/source-audit/`.
- Extended World Explorer with ten navigable modes, source observation list/detail, pins and layer controls, geographic search and regional navigation, and clear unavailable states. Preserved separate core event, airport, facility, hazard and portfolio views. A map position is not promoted to a company or financial relationship.
- Added typed, source-hashed geographic relationships for world events and facility geography. Explicit historical world queries gate the current-only event bundle at its build date.

The complete task is **not finished**. `REQUIREMENTS.md` and all 218 checklist rows in `SOURCES.csv` give the exact status: 14 baseline rows, 12 new integrations, 129 unimplemented rows requiring engineering, 57 login gated rows set aside, and 6 paid or billing dependent rows excluded on the user's instruction. These are checklist rows, not distinct APIs. `BLOCKERS.md` separates actual external access and rights dependencies from unfinished engineering.

## Provenance and scope

WRI plant records are an attributed static reference, with source owner text retained as reported metadata and no asserted listed issuer. NOAA alerts retain polygon source geometry and a labeled display anchor; 335 records without supported geometry were excluded. AviationWeather is a six-station sample, not a global flight feed. Federal Register results are unlocated policy metadata, not geographic events. GDACS is only the newest 100-record page; coordinates may be representative and do not show the impact footprint. NASA POWER values are gridded daily estimates at six requested points for October 2026, not weather station measurements or global coverage; local solar time dates display as UTC midnight day anchors. All six captures were retrieved on 2026-11-15 and cannot be presented in earlier historical replay. Existing WDI annual values, ECCC reporting-company fields, and OurAirports static reference keep their original limits.

## Changed paths and integration interfaces

Primary-owned changes: `backend/aplomb/world/` (provider transport, parsers, immutable snapshots, bundle captures, service, passports and relationships); `web/src/features/world/`, `web/src/lib/world.ts`; world tests; `docs/parallel/reports/agent-3/` and `docs/evidence/parallel/agent-3/`.

Additive shared bridges:

| Paths | Purpose |
|---|---|
| `backend/aplomb/contracts/{api,catalog}.py`, `contracts/catalog.md`, `contracts/generated/schema.json`, `web/src/contracts/{catalog,types}.ts` | Observation/relationship types and provider dataset IDs, with generated mirrors. |
| `backend/aplomb/api/{app,queries,services}.py` | Observation route, query bounds and service protocol. |
| `backend/aplomb/datastore/passports.py` | Planned descriptors so baseline `/datasets` remains valid while world passports override verified captures as in use. |
| `web/src/api/client.ts` | Typed observations request. |
| `backend/tests/integration/test_run_composition.py`, `web/tests/t15-api.test.ts` | HTTP and client coverage for shared wiring. |

`INTERFACES.md` documents the HTTP shape, snapshot loader and Agent 2 handoff. Agent 2's runtime needs to pass `historical=ctx.historical` into `world.search_events` to apply the new bundle availability gate during tool replay. Validated issuer/holding relationships and sourced AI event summaries require Agent 2's work; financial calculations require Agent 1. Merge this branch after reconciling those shared bridges, regenerate the contracts and rerun all gates.

## Verification

Focused provider, world service and world HTTP integration checks passed: 66 tests.
`npm run test:contracts` passed 213 tests, `npm run typecheck` passed, and
`APLOMB_NEXT_DIST_DIR=.next-world-data-final npm run build:web` produced a static
export. The full `npm run check` did not finish; its pytest phase reached the
slow budget-watchdog integration test and was stopped. No full-suite pass is
claimed. Browser inspection loaded Japan country search and a Japanese aviation
station; desktop evidence is at
`docs/evidence/parallel/agent-3/browser/aviation-japan-desktop.png`. The mobile
viewport was checked for horizontal overflow but its captured source panel was
still loading, so loaded mobile data is not claimed. The GDACS and NASA POWER captures were added
after the web build; generated contracts and TypeScript type checking passed
after that addition.

No deployment, production change, cloud mutation, merge or video publication was performed.
