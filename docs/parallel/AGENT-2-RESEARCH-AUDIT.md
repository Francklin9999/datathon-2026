# Agent 2 — Research, security identity, AI agents, audit and historical intelligence

Read [README.md](README.md), [FULL-SCOPE.md](FULL-SCOPE.md) and [INTERFACES.md](INTERFACES.md) first. Execute the entire assigned scope, not a small demo. You are an independently launched worker, not the final deployer. Do not ask the owner questions; record genuine external dependencies and continue independent engineering.

**Worktree:** `.worktrees/research-audit`. **Branch:** `codex/agent-2-research-audit`. **Baseline:** `codex/parallel-base-20261115`. **Reports:** `docs/parallel/reports/agent-2/`. **Evidence:** `docs/evidence/parallel/agent-2/`. **Ports:** 8102/3102/9322. No deployment, main/integration merges, extra agents or production flag changes.

## Primary-owned code

- `backend/aplomb/intelligence/`, `research/`, `agents/`, `ledger/`, `timemachine/`.
- Security/market/crypto provider adapters, filing/fund/ownership acquisition, security identifiers/crosswalks, ALFRED/FRED vintage adapters assigned in SOURCE-OWNERS.csv. Datastore historical/schema/passport changes are shared bridges; use focused new modules and report exact edits.
- `web/src/features/markets/`, `home/`, `audit/`, `system/`, `timemachine/`. New target-run/event-summary components may be supplied as separate components/patches for Agent 1/3's owned pages. Shared application wiring/contracts/client/components require small documented edits.
- Agent/tool budgets, prompt-injection defenses, run persistence/ownership/idempotency/resume/recovery, source verification and corresponding security tests. Propose infrastructure/IAM adjustments in source only if a demonstrated requirement exists; do not apply them to AWS.

## Baseline to preserve

Real Bedrock orchestration, deterministic finance/policy, ledger, strict writer grammar/auditor, signed reports, historical gates/reveal and isolated sabotage already exist. Do not replace them with role-playing or fixture responses. GLEIF legal-name search already stores raw/normalized session-owned captures and returns **candidates**, not proven issuers. `intelligence/entities.py` and `overlap.py` provide exact ISIN/LEI checksums, exchange/lifecycle IDs, dated evidence classes and look-through arithmetic, but are not yet a real security master/issuer holdings integration. Native FX account receipts and deterministic complete-target comparisons exist in contract 1.4.0; their claims are separate from reviewed agent reports.

## Assigned implementation

### A. Global instrument, issuer and research intelligence

Implement an exchange-aware instrument master with stable listing lifecycle/ISIN/MIC/currency identifiers, LEI and SEC CIK, and CUSIP only where licensed and documented provider crosswalks. Ticker alone is never globally unique; fuzzy names never establish identity. Add regional adapters without routing all international securities to U.S.-only providers. Integrate supported stocks, ETFs, bonds, indices, commodities, crypto/funds and other justified asset categories with honest data availability.

Complete source-backed security detail: actual price analytics, company information, financial statements, latest filings, news, ownership, sources and macro context. Add disclosed insider transactions, institutional/fund holdings, ETF ownership, fundamentals and other advanced research where assigned source access permits. Preserve true reporting/publication delays, revisions, licensing and estimates-versus-official distinctions.

Acquire at least real dated issuer ETF holdings and exact security mappings for an end-to-end look-through example; build the extensible pipeline for more funds. Agent 1 owns portfolio risk/overlap consumers; you own acquisition, provenance and identity resolution. Keep uncovered/unreported constituent weights explicitly unknown. Do not pass a synthetic fixture off as actual issuer evidence.

Put the dated relationship model into production use: security→issuer, parent/subsidiary, facility/entity relationships when directly documented, revenue geography/supply chains where evidence exists, claim→source and portfolio holdings. Expose direct/derived/model-inferred/unverified evidence classes. Agent 3 owns world facility/event source observations; consume their source IDs without guessing listed issuers or precise impacts.

### B. Controlled agent workflows and strategic research

Keep real planner/researcher/analyst/risk/writer/auditor tool calls and deterministic quant/policy services. Complete target-allocation/reduction/rebalance **agent** request/workflow support around the existing `CheckService.rebalance`; do not change Agent 1's finance semantics. Register all local facts into the actual run ledger with remapped dependencies, immutable context and correct run ownership before writing/review/signing. Add budgeted retries/fallbacks using actual supported Bedrock runtime configurations; maintain a tested fallback if AgentCore is unavailable.

Complete the horizon-aware strategic portfolio brief using Agent 1's deterministic candidate findings. Default to no more than three primary focus areas; include priority, time horizon, holdings, claim/source references, uncertainty, useful investigation and navigation. Adapt to arbitrary investor objectives/constraints, not seed names. Include real world/security context from source tools when temporally available; do not inject Nov-15 captures into a Nov-12 information cutoff.

Support grounded event summaries/research hypotheses with Agent 3's source observations, documented issuer relationships and explicit impact states. Geographic proximity is not causation. Missing evidence or model failure must preserve verified deterministic outputs and show the failure.

### C. Claims ledger, independent audit and reliability

Complete reproducible claim types, source/version/parameters/units/availability records, independent numerical/comparison/policy/reference checks, historical restrictions, source interpretation review and signing. Verify more than a model's self-asserted confidence. Sabotage tests must reject fabricated numbers, inverted comparisons and unsupported source interpretations with the exact check that failed; do not claim universal truth guarantees.

Harden external-document and investor-text prompt injection, tool permissions, session/run isolation, cache dimensions, retry/budget/idempotency, worker checkpointing and failure recovery. Research source bodies remain data, never instructions. Do not expose secrets in traces or error messages. Agents/System and Evidence/Audit must display real execution/tools/evidence, not decorative agents.

### D. Historically disciplined Time Machine

Integrate actual ALFRED/FRED vintages and other available point-in-time security/fundamental/news/ownership data. Preserve observation, publication, availability, retrieval and dataset-version timestamps. Exclude unavailable data based on true availability, not observation date alone. Frozen original runs remain immutable; reveal stores separately linked subsequent observations, outcome comparisons and source records.

Explicitly distinguish deterministic historical calibration from claims about a modern LLM predicting history; tool restrictions do not erase pretrained knowledge. Provide credible replay/reveal and sabotage demos with actual preserved evidence.

## Source findings already observed (research leads, not completed integrations)

- Official GLEIF API documentation link: https://www.gleif.org/en/lei-data/gleif-api ; the linked Postman documentation returned 403 to the bounded HTTP probe. Respect access controls.
- `GET https://api.gleif.org/api/v1/lei-records?filter[isin]=US0378331005&page[size]=5` returned one Apple record, LEI `HWUPKR0MPOU8FGXBT394`. Its documented related-resource URL is `/api/v1/lei-records/{LEI}/isins`.
- Related ISIN rows explicitly contain both `attributes.isin` and `attributes.lei`. Default pagination was 15 of 956 rows for Apple. **The related endpoint ignored `filter[isin]`** in a probe: it returned unrelated first rows and total 956. Never treat HTTP 200 or an ignored filter as proof of the requested pair; inspect the actual pair and pagination.
- GLEIF's official Nov-15 ISIN/LEI ZIP download is linked at https://www.gleif.org/en/lei-data/lei-mapping/download-isin-to-lei-relationship-files . The capture exceeded a 32 MB cap, so no complete archive was retained. Use a justified bounded/streamed pipeline or proven exact lookup, not a fake partial/full import.
- GLEIF terms identify access-service data as CC0; review mapping-specific terms/limitations as well. Original historical publication/availability must not be inferred merely from a capture.
- Prior SEC calls returned 403; GDELT timed out/429 (Agent 3 owns GDELT). Approved descriptive source contact/configuration may be needed; do not invent a contact, bypass controls or silently substitute source attribution.

## Required acceptance and handoff

Map every assigned Downloads SRC row, original master MASTER row (including Coin Metrics Community and SEC structured RSS/Data Library), and every research/agent/audit/history requirement to real implementation/evidence or a precise external blocker. Prove strong IDs, real captured relationships, actual holdings look-through inputs, source date restrictions, cross-run reference rejection, numeric/comparison sabotage, prompt-injection resistance and graceful provider/model failure. Provide real UI/HTTP workflows and local full gate/static build. Record live Bedrock/AWS checks separately; credential failure does not excuse unimplemented local workflows. Produce all reports specified in README.md, commit/push only your branch, and return SHA plus handoff path for independent review.
