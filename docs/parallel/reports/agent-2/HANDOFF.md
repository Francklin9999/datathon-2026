# Agent 2 handoff

Branch: `codex/agent-2-research-audit`. Base: `2604b9689e9f992b4e9e46c4a06ea89ec57ac155` (`codex/parallel-base-20261115`). Implementation SHA: `1a513d9f2bc402113adbf252e5f0b10016efb238`; the final report commit SHA is returned to the owner.

## Result

Preserved and continued Claude's implementation. Latest selected-account scope: 31 working catalogue rows, 4 pending rows for the single FRED/ALFRED permission blocker, and 62 removed rows; total 97. OpenDART is an additional working regional adapter outside these catalogue rows. Fourteen of fifteen supplied accounts have real successful supported operations; FRED remains disabled due provider terms. Other pending providers were removed by owner instruction. See ADAPTER-STATUS.md and ACCESS-REQUESTS.md.

Working workflows: GLEIF exact/Level-2 relationships, GLEIF Golden Copy intraday deltas, OpenFIGI ISIN mappings, Wikidata candidate assertions, Canada/Ireland corporate registries, ESMA authorizations, EBA 2025 market-risk observations, Alternative.me sentiment, Coin Metrics daily observations, Binance Vision daily history and DEX Screener exact-pool observations. All preserve identity/units/dates/source evidence and session-owned captures. Loopback-only noncommercial research defaults enable the three explicitly permitted research sources; explicit opt-outs prevail, no production defaults changed.

The branch also adds reviewed rebalance runs around existing finance semantics, canonical local-fact remapping, actual preparation-phase tool receipts, bounded original-source context for independent interpretation review, stronger comparison/checkpoint integrity, a generic objective-aware focus bridge, source-owned instrument/crosswalk persistence, dated issuer graphs, extensible SEC company/ownership/fund parsers, persistent separate reveals and point-in-time selectors. Source-specific CONT reports describe exact interfaces and limitations.

## Evidence and validation

- Actual public HTTP captures: source CONT reports and `docs/evidence/parallel/agent-2/`. OpenFIGI returned 553 mappings and published 553 source assertions; public-working/http-results.json records successful Coin Metrics, Binance Vision checksum history and DEX HTTP paths. Identity evidence records exact GLEIF pair, parent graph, Wikidata and crosswalk calls. Registry/sentiment/EU/Golden Copy captures remain inspectable.
- Fresh SEC probe using existing authorised project contact returned HTTP403; `sec-live-status.json`. SEC sources and N-PORT example are removed from active Markets coverage by owner instruction; prior audit captures remain.
- Fresh official AWS MCP STS and Converse plus a local reviewed rebalance with three actual Bedrock calls: aws-live-checks.json and live-rebalance-run.json. The real writer's unsupported sentences were struck; result passed_with_strikes. This live run predates later source-context/tool-receipt refinements and is not evidence of a final deployed release.
- HTTP/browser replay/reveal and target-review flows used explicitly SCRIPTED model gateways. Screenshots, reusable harnesses and logs are retained; no fixture is called a live model or live issuer source.
- Latest focused regression group: 24 tests passed (company detail, API route enumeration/wire boundary, agent execution). Earlier focused ledger/history/source groups are described in stream reports. The full suite was not re-run after the owner's API-first instruction. Preliminary check.log is an earlier failed mid-edit gate and is superseded by focused/static results, not claimed passing.
- Ruff, web TypeScript and final static export passed; logs retained. A harmless Mangum event-loop deprecation warning remains in the focused run. All evidence file hashes are indexed in verification.json.

## Integration and unresolved scope

Read REQUIREMENTS.md and INTERFACES.md before merging. Full worldwide specification is NOT complete. Agent 1 candidate findings and Agent 3 source observations need production bridge integration; source-backed facility/supply/revenue edges and universal historical ownership/news coverage are not fabricated. The documented Agent 1-owned same-day explicit-asOf /check mode selection requires integration repair. SEC live acquisition is excluded by owner instruction; other key/rights sources stay aside. No current capture is inserted into a frozen historical run.

New research bodies use branch-local snake_case response structures and local TS types; the integrator must reconcile them with shared generated contracts/clients. No common contract version bump, manifest activation, cloud/IAM mutation, production flag change or deployment occurred. Re-read actual release state before eventual full acceptance/deployment. The root integration checkout and other agents' primary modules remain untouched.

## Shared changes

See INTERFACES.md for exact shared bridges: API app/domain/runtime, contract request/result unions, generated schema/TS, contracts API/schema docs, brief/label helpers and local dev defaults. Existing optimizer finance semantics are preserved. Source modules remain in Agent 2-owned namespaces. Root .playwright-mcp is unrelated and untouched. Temporary browser/server processes were stopped and generated target build cache removed.

## Changed paths

- `backend/aplomb/agents/bridges.py`
- `backend/aplomb/agents/focus.py`
- `backend/aplomb/agents/models.py`
- `backend/aplomb/agents/registry.py`
- `backend/aplomb/agents/runtime.py`
- `backend/aplomb/agents/signing.py`
- `backend/aplomb/agents/trace.py`
- `backend/aplomb/agents/workflow.py`
- `backend/aplomb/api/app.py`
- `backend/aplomb/api/domain.py`
- `backend/aplomb/api/runtime.py`
- `backend/aplomb/contracts/api.py`
- `backend/aplomb/contracts/models.py`
- `backend/aplomb/intelligence/capabilities.py`
- `backend/aplomb/intelligence/capability_routes.py`
- `backend/aplomb/intelligence/chain_public.py`
- `backend/aplomb/intelligence/chain_routes.py`
- `backend/aplomb/intelligence/coinmetrics.py`
- `backend/aplomb/intelligence/crypto_markets.py`
- `backend/aplomb/intelligence/data/eba_2025_market_risk.csv.gz`
- `backend/aplomb/intelligence/data/fund-isin-mappings.json`
- `backend/aplomb/intelligence/data/sec-nport-aapu-indexed-excerpt.json`
- `backend/aplomb/intelligence/data/source_dispositions.json`
- `backend/aplomb/intelligence/defi_routes.py`
- `backend/aplomb/intelligence/defi_sources.py`
- `backend/aplomb/intelligence/disclosure_examples.py`
- `backend/aplomb/intelligence/entities.py`
- `backend/aplomb/intelligence/eu_registers.py`
- `backend/aplomb/intelligence/eu_routes.py`
- `backend/aplomb/intelligence/exact.py`
- `backend/aplomb/intelligence/fund_pipeline.py`
- `backend/aplomb/intelligence/gleif_relations.py`
- `backend/aplomb/intelligence/golden_copy.py`
- `backend/aplomb/intelligence/golden_routes.py`
- `backend/aplomb/intelligence/holdings_ingest.py`
- `backend/aplomb/intelligence/issuer_holdings.py`
- `backend/aplomb/intelligence/master.py`
- `backend/aplomb/intelligence/master_adapters.py`
- `backend/aplomb/intelligence/master_repository.py`
- `backend/aplomb/intelligence/master_routes.py`
- `backend/aplomb/intelligence/openfigi.py`
- `backend/aplomb/intelligence/registries.py`
- `backend/aplomb/intelligence/registry_routes.py`
- `backend/aplomb/intelligence/relationship_graph.py`
- `backend/aplomb/intelligence/sec_structured.py`
- `backend/aplomb/intelligence/sentiment.py`
- `backend/aplomb/intelligence/sentiment_routes.py`
- `backend/aplomb/intelligence/stooq.py`
- `backend/aplomb/intelligence/wikidata.py`
- `backend/aplomb/intelligence/wikidata_routes.py`
- `backend/aplomb/ledger/audit.py`
- `backend/aplomb/ledger/core.py`
- `backend/aplomb/research/company_detail.py`
- `backend/aplomb/research/company_routes.py`
- `backend/aplomb/research/disclosures.py`
- `backend/aplomb/research/regional.py`
- `backend/aplomb/research/sec_extra.py`
- `backend/aplomb/timemachine/pit_routes.py`
- `backend/aplomb/timemachine/records.py`
- `backend/aplomb/timemachine/sec_pit.py`
- `backend/aplomb/timemachine/service.py`
- `backend/aplomb/timemachine/vintages.py`
- `backend/tests/agents/test_bridges.py`
- `backend/tests/agents/test_execution.py`
- `backend/tests/agents/test_source_review_context.py`
- `backend/tests/integration/test_agent_runtime.py`
- `backend/tests/integration/test_run_composition.py`
- `backend/tests/integration/test_track_composition.py`
- `backend/tests/ledger/test_comparison_binding.py`
- `backend/tests/ledger/test_ledger.py`
- `backend/tests/research/test_company_detail.py`
- `backend/tests/unit/datastore/test_global_fx.py`
- `backend/tests/unit/test_regional_research.py`
- `backend/tests/unit/test_security_sources.py`
- `backend/tests/unit/timemachine/test_records.py`
- `backend/tests/unit/timemachine/test_timemachine.py`
- `backend/tests/unit/timemachine/test_vintages.py`
- `contracts/api.md`
- `contracts/generated/schema.json`
- `contracts/schemas.md`
- `docs/evidence/parallel/agent-2/aws-live-checks.json`
- `docs/evidence/parallel/agent-2/check.log`
- `docs/evidence/parallel/agent-2/eu-regulators/capture-manifest.json`
- `docs/evidence/parallel/agent-2/eu-regulators/esma-bnp-20261115.json`
- `docs/evidence/parallel/agent-2/focused-regressions.log`
- `docs/evidence/parallel/agent-2/history-browser-replay.png`
- `docs/evidence/parallel/agent-2/history-browser-replay.txt`
- `docs/evidence/parallel/agent-2/history-browser-reveal.png`
- `docs/evidence/parallel/agent-2/history-browser-reveal.txt`
- `docs/evidence/parallel/agent-2/history-browser-scripted.mjs`
- `docs/evidence/parallel/agent-2/history-scripted-http.txt`
- `docs/evidence/parallel/agent-2/live-rebalance-run.json`
- `docs/evidence/parallel/agent-2/public-working/binance-vision-result.json`
- `docs/evidence/parallel/agent-2/public-working/coinmetrics-capture-0.json`
- `docs/evidence/parallel/agent-2/public-working/coinmetrics-result.json`
- `docs/evidence/parallel/agent-2/public-working/cryptomkt-capture-0.json`
- `docs/evidence/parallel/agent-2/public-working/cryptomkt-capture-1.json`
- `docs/evidence/parallel/agent-2/public-working/defi-capture-0.json`
- `docs/evidence/parallel/agent-2/public-working/dexscreener-result.json`
- `docs/evidence/parallel/agent-2/public-working/http-results.json`
- `docs/evidence/parallel/agent-2/registries/ca-1007-normalized.json`
- `docs/evidence/parallel/agent-2/registries/ca-1007-response.json`
- `docs/evidence/parallel/agent-2/registries/ie-279457-normalized.json`
- `docs/evidence/parallel/agent-2/registries/ie-279457-response.json`
- `docs/evidence/parallel/agent-2/ruff.log`
- `docs/evidence/parallel/agent-2/sec-live-status.json`
- `docs/evidence/parallel/agent-2/security/coinmetrics-btc-2026-11-15.json`
- `docs/evidence/parallel/agent-2/security/gleif-apple-isin-search.json`
- `docs/evidence/parallel/agent-2/security/gleif-apple-isins-page-4.json`
- `docs/evidence/parallel/agent-2/security/gleif-golden-intraday-2026-11-15.csv.zip`
- `docs/evidence/parallel/agent-2/security/gleif-golden-metadata-2026-11-15.json`
- `docs/evidence/parallel/agent-2/security/gleif-golden-selected-2026-11-15.json`
- `docs/evidence/parallel/agent-2/security/identity-live-http-2026-11-15.json`
- `docs/evidence/parallel/agent-2/security/openfigi-aapl-all-response.json`
- `docs/evidence/parallel/agent-2/security/openfigi-aapl-all-result.json`
- `docs/evidence/parallel/agent-2/security/openfigi-aapl-response.json`
- `docs/evidence/parallel/agent-2/security/openfigi-aapl-result.json`
- `docs/evidence/parallel/agent-2/security/openfigi-http.json`
- `docs/evidence/parallel/agent-2/security/sec-nport-aapu-indexed-excerpt.json`
- `docs/evidence/parallel/agent-2/security/wikidata-apple-isin-2026-11-15.json`
- `docs/evidence/parallel/agent-2/sentiment/alternative-fng-normalized.json`
- `docs/evidence/parallel/agent-2/sentiment/alternative-fng-response.json`
- `docs/evidence/parallel/agent-2/static-build.log`
- `docs/evidence/parallel/agent-2/target-review-browser.mjs`
- `docs/evidence/parallel/agent-2/target-review-scripted.png`
- `docs/evidence/parallel/agent-2/target-review-scripted.txt`
- `docs/evidence/parallel/agent-2/target-review-success.png`
- `docs/evidence/parallel/agent-2/typecheck.log`
- `docs/evidence/parallel/agent-2/verification.json`
- `docs/parallel/reports/agent-2/ADAPTER-STATUS.md`
- `docs/parallel/reports/agent-2/AGENTS-HANDOFF.md`
- `docs/parallel/reports/agent-2/BLOCKERS.md`
- `docs/parallel/reports/agent-2/CONT-api-progress.md`
- `docs/parallel/reports/agent-2/CONT-chain-public.md`
- `docs/parallel/reports/agent-2/CONT-company.md`
- `docs/parallel/reports/agent-2/CONT-defi-public.md`
- `docs/parallel/reports/agent-2/CONT-eu-regulators.md`
- `docs/parallel/reports/agent-2/CONT-golden-copy.md`
- `docs/parallel/reports/agent-2/CONT-holdings.md`
- `docs/parallel/reports/agent-2/CONT-master.md`
- `docs/parallel/reports/agent-2/CONT-openfigi.md`
- `docs/parallel/reports/agent-2/CONT-regional.md`
- `docs/parallel/reports/agent-2/CONT-relationships.md`
- `docs/parallel/reports/agent-2/CONT-timemachine.md`
- `docs/parallel/reports/agent-2/HISTORY-HANDOFF.md`
- `docs/parallel/reports/agent-2/INTERFACES.md`
- `docs/parallel/reports/agent-2/REGIONAL-HANDOFF.md`
- `docs/parallel/reports/agent-2/REQUIREMENTS.md`
- `docs/parallel/reports/agent-2/SECURITY-HANDOFF.md`
- `docs/parallel/reports/agent-2/SOURCES.csv`
- `docs/parallel/reports/agent-2/STATUS.md`
- `scripts/dev_api.py`
- `scripts/live_research_audit.py`
- `web/src/contracts/types.ts`
- `web/src/features/audit/EvidenceAuditPage.tsx`
- `web/src/features/markets/BitcoinNetwork.tsx`
- `web/src/features/markets/BitcoinSentiment.tsx`
- `web/src/features/markets/CompanyRegistry.tsx`
- `web/src/features/markets/CompanyResearch.tsx`
- `web/src/features/markets/CryptoHistory.tsx`
- `web/src/features/markets/DefiResearch.tsx`
- `web/src/features/markets/DisclosureExample.tsx`
- `web/src/features/markets/EURegulatory.tsx`
- `web/src/features/markets/FundHoldings.tsx`
- `web/src/features/markets/GoldenCopy.tsx`
- `web/src/features/markets/InstrumentMaster.tsx`
- `web/src/features/markets/IssuerEvidence.tsx`
- `web/src/features/markets/IssuerHoldings.tsx`
- `web/src/features/markets/MarketsPage.tsx`
- `web/src/features/markets/OpenFigi.tsx`
- `web/src/features/markets/ProviderObservations.tsx`
- `web/src/features/markets/RegionalResearch.tsx`
- `web/src/features/markets/SecExplorer.tsx`
- `web/src/features/markets/SourceAvailability.tsx`
- `web/src/features/markets/StooqPrices.tsx`
- `web/src/features/markets/WikidataCandidates.tsx`
- `web/src/features/system/AgentsSystemPage.tsx`
- `web/src/features/system/TargetReview.tsx`
- `web/src/features/timemachine/PointInTimePanel.tsx`
- `web/src/features/timemachine/TimeMachinePage.tsx`
- `web/src/lib/brief.ts`
- `web/src/lib/labels.ts`

Credential continuation: five supplied accounts were saved only in ignored local configuration and verified with real requests. Six previously aside catalogue rows are now working (22 working, 52 aside, 23 removed of 97); OpenDART is an additional regional workflow outside those catalogue rows. See [CREDENTIALS.md](CREDENTIALS.md) for operations, free quota limitations and signup links. Financial statement period ends are never treated as original publication times.

Owner access cleanup: all 17 SEC-refused catalogue rows are removed from active coverage and signup requests; historical audit data remains. Glassnode is excluded as paid, Flipside has no verified current signup, and Blockchain.com is corrected to a no-key engineering task. Current total: 22 working, 52 aside, 23 removed (97 assigned catalogue rows). See [ACCESS-REQUESTS.md](ACCESS-REQUESTS.md) for deduplicated official links and precise owner versus engineering actions.


## Selected-account continuation

The final scope supersedes prior inventory checkpoints: 31 working catalogue rows, 4 rows for one FRED/ALFRED permission blocker, 62 removed. New code stock_accounts.py and chain_accounts.py plugs into existing keyed_market_router and connection status; KeyedMarkets consumes the same result shape. Provider-specific identifiers remain exact. J-Quants completes cursor pagination and fails explicitly above its bounds. All nine newly connected accounts have actual retained success receipts. Existing five remain configured; no secret values are tracked. Runtime crypto venue catalogue now excludes unselected live feeds while preserving working Binance Vision history. Removed parsers and audit evidence are retained for historical traceability; no active acquisition control for removed sources remains.

Shared additive wiring: keyed_markets.py dispatch, capabilities.py inventory, crypto_markets.py runtime venue selection, blank .env.example fields, Markets components and contracts/api.md. Provider data is source-reported and current as captured; it is not fed into original historical cutoffs or inferred global security identities. FRED has no ingestion and its key does not resolve permission. Evidence supplied-accounts records real HTTP/capture results and focused validation separately from earlier broad gates. No deployment.
