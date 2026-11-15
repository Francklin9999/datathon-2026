# Agent 2 integration interfaces

## Reviewed targets

POST `/v1/runs` now accepts `{kind:"rebalance",profileId,profileVersion,lang,positions:[{ticker,weightPct}],window?}`. It calls the existing deterministic `CheckServiceImpl.rebalance` during preparation, pins its complete result and profile/snapshot, remaps local facts/dependencies into the canonical run ledger, and records an actual preparation-phase `check.rebalance` receipt. It then uses real planner/writer/auditor/signing. Result union adds `kind:rebalance`; `TargetReview` can be embedded by Agent 1. No finance algorithms, orders or source valuation semantics are changed.

## Typed cross-agent bridges

`agents/bridges.py` exports `CandidateFinding` and `EventRelationship` provider ports. Candidate references must already resolve to verified same-run facts. Event leads require directly documented event→entity and security→same-entity edges, source URLs, verified same-run evidence and availability within cutoff; impact stays not established. Agent 1 candidate and Agent 3 source-observation production wiring remains pending.

## Source/identity interfaces

`intelligence/master_repository.py` publishes immutable validated listing records and source assertions with source bytes in the owning session. `crosswalk` resolves exact ISIN source assertions, preserving direct/derived/unverified classes. `openfigi.py` publishes direct provider identifier assertions from exact one-job ISIN mapping; no legal issuer inference. `gleif_relations.py` and `relationship_graph.py` expose dated relationships. `fund_pipeline.py` exports `holdings_snapshot` and `look_through` for Agent 1's consumers; live SEC acquisition is aside until accepted access.

Public routes are indexed in `contracts/api.md`; source-specific arguments/results and original source references are described in CONT reports. New research response bodies are branch-local snake_case; the integrator must reconcile them with shared generated response schemas/TypeScript clients. No common version bump was made.

GET `/v1/intelligence/source-capabilities` supplies demonstrated available workflows, preserved evidence, aside prerequisites and removed paid sources. Markets only renders acquisition forms for available workflows. Source catalogue is packaged in `intelligence/data/source_dispositions.json`, not read from repository docs at runtime. `scripts/dev_api.py` sets three permitted noncommercial source defaults only for local loopback research; explicit overrides win and no AWS/public deployment defaults are changed.

## Ledger/history

`Ledger.source_review_context(evidence_id)` returns bounded original source excerpts, offsets and full-source hash for cited same-run evidence. The hash enters verification and the signed ledger digest. Restore accepts validated legacy checkpoints while new checkpoints additionally hash run/cutoff/frozen state/documents. Unkeyed hashes detect corruption, not adversarial storage rewriting.

`ReplayServiceImpl(...,store=...)` persists reveal observations separately with parent hash, snapshot and session binding. Existing wire response stays compatible. `timemachine/records.py` and vintage parsers enforce availability; SEC PIT tools remain separate from frozen run inputs. Existing replay restrictions are preserved.

## Shared paths changed

- `backend/aplomb/api/{app,domain,runtime}.py`: source subrouter wiring, reveal store composition, new target run preparation.
- `backend/aplomb/contracts/{api,models}.py`, generated schema and TS: additive rebalance run request/result/input unions.
- `contracts/{api,schemas}.md`: target union and source endpoint documentation.
- `web/src/lib/{brief,labels}.ts`: new result recognition and labels.
- `scripts/dev_api.py`: strictly local loopback noncommercial source defaults.
- Shared datastore code unchanged; one historical gate regression added in shared tests.

Regenerate shared mirrors after merging all three branches. Preserve active manifest pointer, parent captures, production release settings and source-owner namespaces. Resolve the documented Agent 1 same-day explicit-asOf `/check` issue before combined historical acceptance. Final deployment and production A–G verification remain the returning integrator's responsibility.


Selected-account extension: existing `GET /v1/research/market-provider/{provider}?symbol=...` now dispatches fmp/eodhd/massive/marketstack and coinmarketcap/blockscout/alchemy/goldrush in addition to existing providers. Symbol is max120 and is interpreted as a provider symbol or exact numeric ID/address; chain identifiers retain case. Added providers support only the default quote operation and reject MIC/kind parameters unsupported by their source. Stock and chain modules export connection_status() and capture(store,sid,provider,identifier). chain capture includes sanitized HTTP method/body for RPC reproducibility. FRED is a rights-gated status/parser only; no fetch is exposed. J-Quants regional route exhausts bounded cursors. Runtime source catalogue records unselected providers removed, not awaiting signup.
