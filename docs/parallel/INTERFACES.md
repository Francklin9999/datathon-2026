# Interfaces and ownership across the three branches

Use the baseline contracts and services first; add backward-compatible fields rather than replacing them. Record additional needs in your own report. Do not wait idle for another agent: develop the caller or provider against a narrow typed port and honest tests, and document the final adapter needed.

## Agent 1 → Agent 2

- `ProfileService.get(session_id, profile_id)` is session-owned and returns the generic typed profile, active modeled portfolio and policies. Robert/Amira/Mateo remain seed data, never runtime switches.
- `CheckService.check(session_id, CheckRequest)` retains incremental purchase semantics.
- `CheckService.rebalance(session_id, RebalanceRequest)` returns a read-only complete target comparison. `optimizer/rebalance.py:check_targets` currently supplies before/after metrics, policy checks and the local ledger; it does not run agents or sign a reviewed report. Agent 2 should orchestrate the real target workflow around the deterministic calculation rather than reimplement finance.
- The canonical run ledger must own every fact ID used in a run. Remap local dependencies before registration. `profiles/goals.py:register_goal_funding` is an existing example. Do not copy a local F-001 reference blindly into a different ledger.
- Profile context/goals/liabilities feed personalization as typed untrusted user data. Agent 1 owns definitions/calculations; Agent 2 owns planner/writer/auditor consumption. Preserve unknown/assumed fields and horizon conflicts.
- Agent 1 owns `optimizer` algorithms; treat `optimizer/services.py` and `optimizer/tools.py` as shared bridges requiring small documented edits. Agent 2 can add separate target adapters and research tools without editing algorithm internals.

## Agent 2 → Agent 3

- `intelligence/entities.py` already defines exact listing lifecycle/ISIN/LEI identifiers, Evidence and dated Relationship classes plus evidence classes. Agent 2 owns extensions and actual validated security/entity crosswalks. Preserve existing constructors or add defaulted fields.
- Agent 3 supplies documented event/facility/geographic/entity relationships with provider IDs, dates, source and uncertainty. Do not create a company-to-security link from similar names or geographic proximity.
- Current `HoldingExposure` distinguishes named-in-source, listing-country, sector, theme, documented exposure and ETF look-through. Existing theme/listing-country outputs are proxies; do not relabel them as financial exposure or causation.
- Source-backed event summaries must use the real controlled research/writer/auditor path. Agent 3 owns source observations and event panels; Agent 2 owns shared agent/tool/audit orchestration. Each can implement a narrow adapter and provide integration examples without modifying the other's core.

## Source and historical pipeline

- Shared wire contracts: `contracts/`, `backend/aplomb/contracts/`, generated schema and TS. Extend additively in each branch; integrator reconciles and regenerates. Do not independently change CONTRACT_VERSION from 1.4.0.
- Keep current/historical availability distinct. Observation date alone never proves availability. ALFRED vintages and historical gates are Agent 2; Agent 1 owns numerical methods; Agent 3 stores true event/indicator metadata and enforces historical exclusions for non-vintage captures.
- A data source is integrated only after access/terms review, validation, immutable storage/versioning, feature consumption, attribution and meaningful tests. Existing public captures remain immutable. Do not edit parent manifests to make new results pass.
- Use existing storage interfaces and source metadata. Provider adapters should be new domain modules rather than large edits to common files. Shared datastore schema/gate/passport changes must be listed explicitly.
- All 243 existing directory rows have one source owner in SOURCE-OWNERS.csv. Duplicated provider entries remain separate rows with stable IDs. Cross-consumers should reuse their owner's adapter/contract; do not flood the same provider independently or infer another agent integrated it.

## Shared UI/backend composition

Primary feature/page ownership is stated in each task. Shared shell, navigation, request envelopes, root routes and service composition may receive minimal additive wiring on isolated branches; document it. Prefer new subrouters/modules and one registration call to rewriting `api/app.py`. Shared component API changes require compatibility defaults. Preserve dark/light readability, keyboard controls, mobile bounds, loading/error states and profile/run context keys.

## Root-only responsibilities

Final branch merge/conflict resolution, final shared contract version, final full-spec acceptance, source-rights reconciliation, actual production release discovery, deployment/rollback and the final combined demonstration/video are owned by the returning integrator. Agents must provide implementation, test fixtures/captures, demo scripts and evidence for their assigned parts, not deploy independently.

## New source IDs and secondary consumers

Keep all existing IDs stable. To reduce collisions, new dataset IDs should use Agent 1's `fx_`/`factors_`/`risk_`, Agent 2's `market_`/`security_`/`filings_`/`fund_`/`entity_`/`alfred_`, and Agent 3's `world_`/`trade_`/`energy_`/`environment_` namespaces where suitable. Record exceptions. Source ownership is acquisition responsibility, not exclusivity of consumption: Agent 2 can present derivatives research using Agent 1's disclosed positioning/options inputs; Agent 3 can display rates from Agent 1 or dated issuer relationships from Agent 2. Do not change a source's meaning or freshness to satisfy a consumer.

## Snapshot publication and integration-only dependencies

Treat `data/manifests/active.json` as an integration-owned pointer. Each agent may create a distinct immutable versioned snapshot/manifest under an owned prefix (for example `snap-20261115-a1-*`, `a2-*`, `a3-*`) and exercise it with an explicit local override. Never overwrite a parent manifest/capture or silently activate a branch-local snapshot for the shared baseline. Document parent version, checksums, availability, rights and reconstruction. The returning integrator selects the final combined active version.

If another agent's new runtime bridge is unavailable on your isolated branch, use a narrow typed local test adapter and explicitly labeled captured/synthetic test inputs while implementing your side. Production must fail honestly/unavailable until wired to a real provider. Keep the cross-agent end-to-end acceptance marked **pending integration**, not completed from a fixture. Do not wait idle or pretend a mock is a production connector.

Cross-agent temporal acceptance (Agents 1 and 2): the snapshot observation cutoff can equal 2026-11-12 while global BoC retrieval is 2026-11-15. Test both `/check` with explicitly supplied `asOf == snapshot.data_as_of` and the Time Machine path. Verify whether the request means current-snapshot analysis or genuine point-in-time knowledge; an explicit historical request must not gain later captured/revised rows merely because its day equals the latest observation day. Preserve the existing replay historical-gate guard. This is an edge-case test requirement, not a claim that a replay defect has already been established.
