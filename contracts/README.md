# contracts/ — the shared language of the repo

Everything that crosses a boundary between two tracks is defined here: JSON shapes, HTTP endpoints, run steps, tool signatures, enumerations and reference numbers. **If two tracks disagree, this folder wins.** If this folder is wrong, fix it here first, announce it, then change code.

Owner: track **T01 (Contracts & integration)**. See `docs/04-TRACKS.md`.

## Files

| File | What it defines | Main consumers |
|---|---|---|
| `schemas.md` | Every data type exchanged over the API or stored: Profile, Portfolio, PolicyRule, Fact, Evidence, Run, Brief, WorldEvent, DatasetPassport… | Everyone |
| `api.md` | Every HTTP endpoint: method, path, request, response, errors, examples | Backend API (T03), all web tracks (T13–T15) |
| `run-events.md` | Run lifecycle, the eight step types, what each step must record, polling rules | Agents (T08), API (T03), web (T14) |
| `catalog.md` | Closed lists: metric codes, method IDs, rule IDs, limitation codes, audit check codes, error codes, theme tags | Quant (T05), rules (T06), ledger (T10), web |
| `tools.md` | Signatures of the tools agents may call (quant, data, research, world) | Agents (T08), quant (T05), research (T09), world (T11) |
| `controls.md` | Reference numbers computed from the starter data. Tests must reproduce them. | Quant (T05), optimizer (T07), rules (T06), QA (T16) |
| `fixtures/` | Example JSON payloads the frontend can build against before the backend exists | Web tracks, contract tests |

## Global conventions (apply to every payload)

1. **JSON keys are camelCase.** Python code uses snake_case internally and converts at the API boundary (Pydantic alias generator).
2. **Dates** are `YYYY-MM-DD` strings. **Timestamps** are ISO-8601 in UTC with a `Z` suffix, e.g. `2026-11-14T20:25:00Z`.
3. **Percentages are numbers in percent units**: `25.0` means 25%. Field names end in `Pct`. Percentage-point differences use unit `pts`. Fractions (0.25) never cross the API.
4. **Money** is a number plus an explicit `currency` (`"CAD"` or `"USD"`). No implicit currency anywhere.
5. **Bilingual text** is an object `{ "en": "...", "fr": "..." }` (type `I18nText`). If French is cut (D-02), `fr` repeats the English text; the key is never missing.
6. **Nulls**: a field that does not apply is `null`, not omitted, unless the schema marks it optional with `?`.
7. **IDs** follow the formats in `schemas.md` §1. IDs are opaque to the frontend except where stated.
8. **Unknown fields must be ignored** by consumers (forward compatibility). Producers must not rely on that to ship undocumented fields.
9. **Enumerations are closed.** Adding a value is a contract change (see below).

## Versioning and change process

- The API is served under `/v1`. The contract version is `contractVersion` in `GET /v1/meta`; this folder is version **1.6.0**.
- **Additive change** (new optional field, new endpoint, new enum value): edit the file, add a line to the changelog below, tell the affected tracks. Bump the minor version.
- **Breaking change** (rename, removal, type change, semantic change): needs agreement of T01 plus every consumer listed in the table above. Bump the major version. During the datathon, avoid these after Saturday night.
- Every change updates the fixtures in the same commit. A fixture that does not match `schemas.md` is a bug.

## How code mirrors the contracts

| Contract | Python (backend) | TypeScript (web) |
|---|---|---|
| `schemas.md` types | `backend/aplomb/contracts/models.py` (Pydantic v2 models, one class per type, same names) | `web/src/contracts/types.ts` (one interface per type, same names) |
| `catalog.md` enums | `backend/aplomb/contracts/catalog.py` (`StrEnum`s and constant tables) | `web/src/contracts/catalog.ts` |
| `api.md` | Route handlers in `create_app` (`backend/aplomb/api/app.py`), plus the module routers it includes (`aplomb.quant.*_api`, `aplomb.intelligence.capability_routes`, `aplomb.intelligence.investor_examples`) | `web/src/api/client.ts` has a function for the core endpoints, not for every route; the source-capabilities shim is called from `web/src/features/markets/SourceAvailability.tsx` |
| `fixtures/*.json` | loaded by contract tests in `backend/tests/contract/` | `profiles.json` and `run.decision.robert-tsla-25.json` are served in fixture mode (`web/src/api/fixtures.ts`); `world.events.sample.json` is read only by tests and `scripts/check_specs.py` |

T01 writes the two mirrored files once and owns them. Other tracks import them and never redefine a type locally.

### Implemented generation and verification

The written 1.0.0 contract remains the authority for scope. Its executable mirror is now [Pydantic models](../backend/aplomb/contracts/models.py), [API envelopes](../backend/aplomb/contracts/api.py), and [wire primitives](../backend/aplomb/contracts/base.py). The catalog is generated directly from `catalog.md`. Python exports [JSON Schema](generated/schema.json); the locked local generator derives [TypeScript types](../web/src/contracts/types.ts). Do not hand-edit generated files.

Run `npm run generate:contracts` to update artifacts, and `npm run check` to verify them. CI rejects stale generated output. Tests compile every TypeScript declaration in `schemas.md` against the generated types, check every named type is exported, run shared [validation cases](validation-cases.json) in both languages, validate all three canonical fixtures, and pass actual Python serialization into the web validator. Schema references are restricted to local definitions; generation and validation make no network calls.

Use `model.to_wire()` for Python payloads so omitted optional keys remain absent while required nullable fields remain present. Optional keys reject explicit null unless the written type includes null. Use `validateContract(name, unknownJson)` from [the web validator](../web/src/contracts/validate.ts) before consuming HTTP JSON. `PartialProfile` mirrors the shallow `Partial<Profile>` draft type; supplied fields retain their original types and nullability.

Wire validation covers shapes, closed enums, finite numbers, dates, identifiers, custom-window dates, funding donors, nonempty goal targets and nonempty rule patches. Calculation correctness, sums of portfolio weights, horizon ordering, resource existence, reference integrity, run transitions, and session authorization remain service responsibilities (T03–T12); fixture reference and numeric integrity are independently checked by `scripts/check_specs.py`. Contract validation does not replace those domain checks.

T01's handoff and exact consumer imports are in [the integration handoff](../docs/T01-HANDOFF.md). No HTTP service or cloud deployment is implied by the generated schema registry.

### Outside the generated registry

Some routes listed in `api.md` have no type in the generated registry. Their handlers return plain dictionaries or declare no generated response model, so `validateContract` cannot check them. Each response shape is written twice, once as the Python dictionary and once as a hand-written web check. No test compares the two, so a rename on either side fails only at runtime.

| Route (`api.md` index) | Web check |
|---|---|
| A1.6 strategic-candidates, A1.7 allocation-targets | `web/src/api/focusModels.ts` |
| A1.20 joint-plan, A1.21 compare, A1.26 position-details | `web/src/api/expandedInvestor.ts` |
| A1.8 requirements-scenario, A1.13 target-funding | partial inline checks in `web/src/api/client.ts` |
| A1.1 account-valuations | `web/src/api/readModels.ts` (`accountValuationsResult`) |
| `/intelligence/source-capabilities` shim ("Markets research source capabilities" in `api.md`) | local checks in `web/src/features/markets/SourceAvailability.tsx` |

The credentialed market routes (`/research/market-connections`, `/research/market-provider/{provider}`, `/research/tiingo/{symbol}`), `/intelligence/regional` and `/intelligence/entities` were removed with the rest of the Markets research surface. Their models (`MarketConnectionsResponse`, `MarketObservationResponse`, `RegionalResearchResponse`, `EntitySearchResponse`) stay in the registry only while `web/src/api/client.ts` references them; no route returns them. The market models keep their snake_case keys (a documented exception to convention 1) and switch the camelCase alias off.

A1.20 joint-plan declares the Pydantic model `JointPlanResult` (`backend/aplomb/quant/joint_plan_api.py`), but that model is not in the generated registry.

Typing these routes means four steps, none of them done yet: add their models to `backend/aplomb/contracts/api.py`, set `response_model` on each route, regenerate, and switch `client.ts` to `call()`.

## Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-11-14 | First version. |
| 1.6.0 | 2026-11-15 | Additive, all new keys optional: `BatchCheckResponse.differences` (`RuleDifference[]`, a pair of checks aligned by rule), `OverviewResponse.holdingReturns` (every holding's 1-year return and fact), and models for the existing payloads of `/research/market-connections`, `/research/market-provider/{provider}`, `/research/tiingo/{symbol}` and `/intelligence/regional` (no key changed, except that the `tiingo` entry of `/research/market-connections` now also carries `documentation_url`, optional in the model). Also additive since 1.5.0 (commit a2cdd7e, optional): `WorldPortfolioAssessment` and `assessment?` on `WorldEventResponse`, `WorldObservation`, `AirportReference`, `Facility` and `Hazard`, returned when `profileId` is supplied. A 1.6.0 site keeps working against a 1.4.0 or 1.5.0 API: it shows the extra rows only when the keys are present. |
| 1.5.0 | 2026-11-15 | Additive: POST `/profiles/{profileId}/strategies/simulate` (standing strategies simulated on history), method `M_STRATEGY_SIM`, limitations `LIM_STRATEGY_COSTS` and `LIM_STRATEGY_EXECUTION`. |
| 1.4.0 | 2026-11-15 | Native-currency account capital with independently checked FX receipts, reporting-currency aggregation, and complete target-allocation policy/risk comparison. |
| 1.3.0 | 2026-11-15 | Global sourced FX, archived/duplicated profiles, explicit goal scenarios, country/currency policy caps, entity candidates, annual country context and airport references. Paired frontend/backend release required. |
| 1.2.0 | 2026-11-15 | Optional investor context, multiple portfolio accounts, asset analytics, historical tail risk, and EONET event origin. Paired frontend/backend release required. |
| 1.1.0 | 2026-11-15 | Previously disabled sabotage result uses an explicitly unsigned writer draft; coordinate frontend and backend release. |

### Pre-implementation completion review (2026-11-14)

The interrupted 1.0.0 draft was completed before implementation. Corrections: baseline Mateo is insufficient without controversy evidence; profile drafts use Partial<Profile>; nullable overview risk matches missing-data behavior; batch endpoint is indexed; informational counts include flags; first-conflict boundary wording is explicit; async idempotency is session/body-scoped; polling uses completed-step watermark and indexes include session/profile version. No deployed v1 clients existed. See decision-log §6 and the per-module specs for rationale. T01 freezes mirrors against this completed 1.0.0 pack.

T01 implementation freeze (2026-11-14): executable mirrors, generated registry, shared rejection cases, fixture serialization checks, lockfiles, and CI added without changing wire version 1.0.0. `RuleId` has fixed enum constants plus the documented validated theme/sector/asset/ticker families; custom IDs use lowercase Crockford base32, matching the published example.
