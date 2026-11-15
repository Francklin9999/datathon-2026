# Global platform continuation — execution record

This continues branch `codex/global-platform-expansion` after `62836f5`. Contract **1.3.0** is a paired frontend/backend change. Production has not been updated by this branch.

## Execution board

| Work | State | Evidence / handoff |
|---|---|---|
| Existing release and teammate changes | Read; preserved | Previous AWS readback in `evidence/global-platform/aws-latest-release.json`; re-read before any release |
| Global FX | Implemented; clean reconstruction tested | Seven additional BoC CAD-per-unit series; immutable parent and derived snapshot; current/history availability distinguished |
| World Bank country context | Implemented | 838 annual observations, 217 countries/territories, four indicators; capture time and revisions visible |
| Entity identity and overlap models | Foundation implemented | Exact ISIN/LEI checksums, exchange/lifecycle IDs, dated evidence classes, overlap calculation; actual issuer holdings and security crosswalk still required |
| GLEIF research | Implemented | Bounded official search, candidate-only results, source hashes, session-owned immutable raw/normalized captures and one-hour cache in existing store |
| Airport reference | Implemented | 1,154 validated large scheduled-service airports; source attribution, country filtering, bounded spatial sampling, globe pins and accessible table |
| Profile lifecycle | Implemented | Archive/restore with versions, isolated exact duplication including accounts; imported policy origins |
| Goal scenarios | Implemented | Explicit capital/contributions/return/target, fractional horizons, shared-allocation check, traceable run-ledger inputs; no inferred financial feasibility |
| Exposure policies | Implemented | User country/listing and quotation-currency caps, deterministic evaluation, policy preservation during profile edit |
| Official emissions facilities | Implemented | ECCC 2024 capture: 1,863 validated geolocated facilities; 16 rejected; source hashes and licence; no issuer/owner/operator inference; public contact fields omitted |
| Verification | Passed for listed local scope | 834 Python tests + 16 subtests; full gate 179 web tests, supplementary latest suite 180; 6 infra tests; static build; 19 HTTP checks; 6-route smoke and 5 browser interactions; no browser exceptions; mobile 390 px without document overflow |
| Remaining full specification | Open | Updated `20-GLOBAL-IMPLEMENTATION-BACKLOG.md`; modules are not marked done merely because types or directory rows exist |

The three scoped agents left useful code before their runtime became unavailable. The primary agent integrated it, obtained actual captures, repaired failures, and owns the remaining verification. No running agent is assumed to be completing background work.

## Source and temporal handling

- BoC capture: `data/inputs/global-fx/`; snapshot `snap-20261115-globalfx` derives from the unchanged sourced parent. CAD bridges explicitly use CAD per source unit divided by CAD per target unit. Historical reads withhold rows until the captured availability boundary; original vintages are unknown.
- World Bank: `backend/aplomb/world/bundle/country_macro*`; WDI dataset-specific CC BY 4.0 attribution verified at https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators and https://datacatalog.worldbank.org/public-licenses . Annual latest captured observations are separate from real-time market data and historical replays.
- OurAirports: official maintainer CSV at https://davidmegginson.github.io/ourairports-data/airports.csv ; Unlicense/public-domain dedication at https://github.com/davidmegginson/ourairports-data/blob/main/LICENSE . Original site certificate validation failed, so the documented maintainer feed was used with normal TLS validation. Raw capture/country crosswalk are preserved in `data/inputs/airports/`. Country-code crosswalk attribution: World Bank, CC BY 4.0. No aircraft tracking, operating status or company relationship is inferred.
- GLEIF: source CC0 terms https://www.gleif.org/en/meta/lei-data-terms-of-use ; names remain unmatched candidates. Checksum failure blocks reuse. Expired cache plus provider failure returns unavailable instead of stale or invented results. Stored public-source payloads use the existing application store and existing S3 spill support on AWS.

The official ECCC CKAN metadata identifies the Open Government Licence – Canada. The dataset catalogue migrated to a JavaScript application: its actual public catalogue download endpoint supplied the source CSV. Retained projection: `data/inputs/eccc/facilities_source.csv.gz`; normalized bundle and original/projection hashes: `backend/aplomb/world/bundle/facilities*`. The legacy `Facility.operator` property carries the reporting-company legal name and is labelled accordingly in the UI. It does not prove ownership or operator status. Original capture includes contact fields; only the required non-contact columns are retained.

A fresh official AWS MCP read failed with expired/invalid credentials. The anonymous production metadata was re-read successfully and saved separately. Older exact Lambda routing/commit evidence remains historical; this continuation does not assert that an unavailable AWS read confirmed it. Refreshing AWS credentials is recorded in owner actions.

## Numerical and UX limits

Goal calculations are nominal user-assumption scenarios: compound annually, add the contribution at each completed year end, then compound any fractional remainder. Taxes, fees, withdrawals, liabilities and inflation are excluded and disclosed. Missing assumptions or overlapping allocation beyond the modeled portfolio withhold the result. Policy country weights describe listing-country proxies; currency weights describe quotation currencies. Neither is revenue geography or hedged economic exposure. Named accounts still require a common reporting currency. Private assets, actuarial funding, and universally licensed market coverage remain separate engineering/data requirements.

No deployment was attempted: the owner's authorization is conditional on the entire specification being complete. That condition remains unmet. No completed competition flow is used as evidence that all longer-term worldwide modules are finished.

## Verification record

[Machine-readable results and hashes](evidence/global-continuation/verification.json) distinguish the full gate from the supplemental geographic sampling test. The static export built successfully after the final UI changes. Logs, source passports, HTTP results and screenshots are retained alongside it. The local API/web/headless-browser processes started for this verification were stopped; pre-existing user servers were not stopped.
