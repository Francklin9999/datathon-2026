# 04 — Parallel work map

Sixteen independent ownership tracks support more than ten contributors. Each row is a claimable responsibility. T01 keeps the roster of real names in the team's coordination channel; nobody is assigned implicitly by this document.

| Track | Deliverable / owned paths | Immediate independent start | Handoff consumers |
|---|---|---|---|
| T01 Contracts & integration | `contracts/` except controls; shared Python/TS models; root manifests/CI | Validate fixtures, generate mirrors, freeze interfaces | Everyone |
| T02 AWS operator | `infra/`, cloud configuration | Verify models, Guardrails and Browser availability; CDK skeleton | T03/T08/T16 |
| T03 API & persistence | `backend/aplomb/api/`, backend entry points | Repositories, errors, routers against stub services | All web owners |
| T04 Data & datastore | `data/`, `backend/aplomb/datastore/` | Import immutable starter CSVs, manifests, temporal gate, passports | T05/T09/T11/T12 |
| T05 Quant | `backend/aplomb/quant/`, `contracts/controls/` | Reference controls, funding maths, portfolio metrics using local CSV adapter | T06/T07/T08 |
| T06 Profiles & rules | `backend/aplomb/profiles/`, `backend/aplomb/rules/` | Defaults and pure rule evaluation using metric fixtures | T03/T07/T08 |
| T07 Optimizer | `backend/aplomb/optimizer/` | Derivation, grid scan, goal ranking using quant/rules protocols | T06/T08/T13 |
| T08 Agents & execution | `backend/aplomb/agents/` | State machine, prompts, registry, fake-model integration tests | T03/T10/T14 |
| T09 Research | `backend/aplomb/research/` | Source adapters, document caching, citation verification with captured responses | T08/T10/T11 |
| T10 Ledger & audit | `backend/aplomb/ledger/` | Token parser, numeric/claim checks, signing, sabotage with synthetic text | T08/T14 |
| T11 World backend | `backend/aplomb/world/`, world ingestion jobs | Cached events, dedupe/geography, exposure with fixture data | T09/T15 |
| T12 Historical gate | `backend/aplomb/timemachine/` | As-of validation, presets, withheld counts, isolated reveal | T04/T08/T15 |
| T13 Web shell & portfolio | `web/src/app/` shell/Home/Portfolio/Profiles/Sources, shared components | Design tokens, API client, fixture source, persona state | T14/T15 |
| T14 Decision & audit UI | Decision Desk, Evidence & Audit page components | Run timeline, slider, compare, evidence drawer against fixtures | T13 |
| T15 World & history UI | World Explorer, Time Machine, Agents & System | Client-only globe, feed fallback, historical/reveal panels | T13 |
| T16 QA & delivery | `tests/`, `scripts/check_specs.py`, delivery docs | Acceptance matrix, cross-track smoke harness, video/one-pager outline | Everyone |

T13 creates route skeletons and shared layout; T14/T15 own their page bodies under agreed component folders. T01 alone edits shared model files, web package manifest and root CI after initial proposals. T03 owns backend dependency manifest; module owners request additions with version/rationale. T04 owns source manifests; T11 provides world ingestion data through the documented ingestion boundary.

## Required first handoffs

| Provider → consumer | Boundary |
|---|---|
| T04 → T05 | `DataStore`, `TemporalGate`, `PriceFrame`, `Universe` |
| T05 → T06/T07 | `PortfolioMetrics`, `PortfolioSnapshot`, missing-metric behavior and move functions |
| T06 → T03/T08 | `ProfileService`, `check_rules`, `verdict_of` |
| T07 → T06/T08 | Threshold derivation, max-size result, candidates |
| T10 → T08 | Ledger registration, writer grammar, auditing and signing |
| T03 → T08 | Run repository, dispatcher, claim/checkpoint operations |
| T08 → web | Real `Run` objects with stable references and incremental updates |
| T11/T12 → T15 | World pages and historical presets/reveal contracts |

Interfaces are specified now; implementations can begin against fakes. A provider's first handoff includes a typed callable and one offline test. Any mismatch is fixed centrally before consumers work around it.

## Everyone-on-main workflow

D-39 is retained. Coordinate file claims, make small path-scoped commits, inspect status/diff before committing and never use `git add .` to collect others' changes. Do not rewrite shared history or discard somebody else's uncommitted files. Run changed-track tests before pushing, then T01's integration check. If two people need one file, let its owner incorporate the requested edit.

## Integration order and cut handling

First verify deterministic Robert flow, then real persisted Bedrock flow, then all P0 acceptance checks. P1 tracks build concurrently behind flags. At Sunday 18:00 the owner applies D-02: bilingual → facilities/hazards → Time Machine → creator/free-text goals. Update `/meta`, backend validation and navigation together. No developer may hide a broken P0 flow as a fixture-only “success.”
