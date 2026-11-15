# Agent 3 — Worldwide intelligence, globe, observations and ingestion

Read [README.md](README.md), [FULL-SCOPE.md](FULL-SCOPE.md) and [INTERFACES.md](INTERFACES.md) first. Implement the complete assigned scope, including the later global modules where authorized data exists. The user rejected an MVP. Do not ask further questions; record genuine access/rights/input blockers and continue independent engineering.

**Worktree:** `.worktrees/world-data`. **Branch:** `codex/agent-3-world-data`. **Baseline:** `codex/parallel-base-20261115`. **Reports:** `docs/parallel/reports/agent-3/`. **Evidence:** `docs/evidence/parallel/agent-3/`. **Ports:** 8103/3103/9323. Do not deploy, change production settings, merge another branch or start additional workers.

## Primary-owned code

- `backend/aplomb/world/`, world/event/geographic/macro/environment/infrastructure provider adapters, ingestion scripts and approved raw/normalized world captures.
- `web/src/features/world/`, `sources/`, `web/src/lib/world.ts`, globe styles/rendering/country panels and their tests.
- Source catalogue generation, world passports, geospatial/entity-observation normalization, ingestion schedules/monitoring source changes and operational documentation. Root dataplane schemas/gate/passports/storage/API/contracts are shared bridges: keep changes additive and list them.
- Your provider rows are exact in SOURCE-OWNERS.csv. Agent 2 owns securities/issuer/filing/crypto identifiers and source research orchestration; Agent 1 owns numerical finance/factor/FX models. Reuse their typed interfaces and existing Evidence/Relationship models.

## Baseline to preserve

World Explorer already has a global lazy-loaded globe/2D feed, event filtering/source panels and portfolio investigation links. The bundle has actual EONET observations, USGS earthquakes and official releases; WDI country panels contain 838 annual observations across 217 countries/territories. Static OurAirports reference contains 1,154 validated large scheduled-service airports. ECCC GHGRP contains 1,863 geolocated 2024 facilities (16 rejected rows), original/projection hashes and required-field source projection. Public contact fields are intentionally omitted. The legacy `Facility.operator` wire field is labeled **Reporting company**: it is not proof of ownership/operator status. Existing event/theme/listing-country matches are proxies with no assumed financial impact. Preserve these distinctions and immutable captures.

## Assigned implementation

### A. Complete World Explorer interaction

Complete global rotation/zoom, country selection/regional drill-down, geographic search, regional highlighting, source-backed markers, layer toggles, viewport queries, clustering/zoom-dependent rendering, portfolio overlays, historical filtering where data actually supports it and an accessible 2D fallback. Global navigation is separate from financial data coverage; never claim universal markets because the map covers Earth.

Support all requested modes through real modules and meaningful loaded states: news; portfolio exposure; global macro/markets; trade/shipping; energy; hazards; conflicts/geopolitics; aviation; ESG/environment; economic infrastructure. No empty panels or decorative unsupported layers. Disabled/unavailable providers must have clear reasons without inventing records.

Event detail needs title/location/category, observation/publication/retrieval context, original sources, real sourced AI summary through Agent 2's orchestration, economic channels, company candidates/documented relationships, portfolio evidence, uncertainty and follow-up questions. Build the complete investigation route Event → Sources → Companies → Holdings → Risk investigation → Decision Desk. Geographic proximity alone proves neither ownership nor financial effect. No precise expected price impact without a supported model from Agent 1.

### B. Worldwide source-to-feature integrations

Audit every assigned provider row and complete usable adapters/pipelines, starting with actual existing connectors and then the missing layers. Include:

- GDELT DOC/Event/GKG/geographic data, official central-bank/regulatory feeds, sourced news/policy/conflicts/sanctions, ReliefWeb/UCDP and other authorized sources.
- World Bank/macro/country comparisons and regional indicators assigned to you, including IMF/OECD/BIS/Eurostat/Statistics Canada and other supported country sources. Annual observations are not real-time geopolitical signals. FRED/ALFRED vintage research is Agent 2; core FX/rate/factor sources assigned to Agent 1 are not yours to duplicate.
- IMF PortWatch ports/chokepoints/activity, trade/shipping disruptions and UN Comtrade/WTO/WITS/UNCTAD where assigned. Respect IMF reuse terms; port activity is not direct issuer exposure. AIS coverage is regional/historical unless an authorized live source supports more.
- Energy infrastructure, plants/operators and generation/commodity context from EIA/JODI/Ember/GEM/WRI/USGS/other assigned sources. Relationships must be explicitly evidenced and dated; do not infer a public issuer from a similar company name.
- Earthquakes/disasters/fire/storm/flood and satellite observations from existing USGS/EONET plus GDACS/FIRMS/NOAA/Copernicus as supported. Keep actual observation/geometry precision; no marker for invalid/missing coordinates.
- ESG/environmental facility sources: deepen ECCC and add EPA/other regional registries, air quality/emissions/environmental observations and public attention where assigned. Facility emissions are not a comprehensive ESG score, allegation, controversy conclusion or automatic financial loss.
- Airport/infrastructure reference expansion and authorized aviation observations. Airport reference is not aircraft tracking. Never imply continuous global coverage from incomplete observations; respect authorization, quotas and data rights.
- Geographic boundaries/place/entity normalization, selected ports/airports/factories/data centers/strategic resources and satellite overlays with appropriate attribution. Do not use public Nominatim as unlimited geocoding/autocomplete.

Each source must pass current access/terms/quota/geography/freshness/history review, schema validation, entity/date normalization, quality checks/deduplication, immutable/versioned storage, actual feature consumption, attribution/passports and meaningful tests. A directory row or HTTP 200 is not enough. Conserve source bandwidth, cache approved snapshots and keep explicit incomplete/paginated coverage.

### C. Relevance and entity observations

Produce source-backed geographic/entity/facility relationships using the existing typed Evidence/Relationship classes. Agent 2 supplies validated security/entity resolution; feed explicit source IDs and timestamps rather than fuzzy-name assertions. Distinguish headquarters, operating facilities, reported revenue geography, supply chains and inferred economic hypotheses.

Expose relevance states separately: no documented link, potentially relevant, documented nonfinancial link, measurable exposure and modeled financial impact. Quantify only supported relationships through Agent 1's services. Preserve uncertainties and source date/availability constraints. Current-only captures must not leak into historical replay merely because their observation dates are old.

### D. Data operations and reliability

Use the existing S3/DynamoDB/CloudWatch architecture. Implement bounded provider-specific timeouts/retries/rate limiting/pagination, content hashing, deduplication, cache/revision handling, idempotent ingestion and quality reports. Add justified source-monitoring/scheduling definitions in source code/IaC proposals without applying cloud changes or adding needless infrastructure. Retain dataset passports with source URLs, observation/publication/availability/retrieval, version, rights, quality, geographic role, entity IDs, approved payload reference and limitations.

Keep globe lazy loading, viewport limits, source-panel responsiveness, layer isolation, loading/error states, dark/light readability, keyboard accessibility, mobile behavior and source-failure recovery. Do not let an optional source failure break portfolio/core workflows.

## Required acceptance and handoff

Provide actual geolocated source captures for new modules, immutable checksums, valid coordinates, empty/invalid/pagination/failure tests, source/source-passport consistency and current-versus-historical boundary tests. Demonstrate a real event with original source → grounded summary → documented holding relationship or honest insufficiency → Decision Desk. Prove global country navigation and non-North-American data. Verify toggles/clusters/search/panels through HTTP and browser/mobile, not just parser tests. Capture your scenarios for the eventual combined demo; do not publish a video/site or deploy. Complete all reports from README.md, including every assigned source row's status, commit/push only your branch, and return its SHA and handoff path.
