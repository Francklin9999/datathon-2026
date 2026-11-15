# Agent 1 — Investor, portfolio, policy and quantitative intelligence

Read [README.md](README.md), [FULL-SCOPE.md](FULL-SCOPE.md) and [INTERFACES.md](INTERFACES.md) first. You are one of three independently launched workers. Execute the complete assignment; do not propose an MVP or stop after one tested improvement. No further questions to the owner; genuine external inputs go in your blocker report while other work continues.

**Worktree:** `.worktrees/investor-quant` in the original repository. **Branch:** `codex/agent-1-investor-quant`. **Baseline:** `codex/parallel-base-20261115`. **Reports:** `docs/parallel/reports/agent-1/`. **Evidence:** `docs/evidence/parallel/agent-1/`. **Ports:** API 8101, web 3101, Chrome 9321. Do not deploy or merge other branches.

## Primary-owned code

- `backend/aplomb/profiles/`, `quant/`, `rules/`, optimizer algorithms (`check`, `rebalance`, `derive`, `frontier`, `scenarios`, `search`). `optimizer/services.py` and `tools.py` are shared bridges with Agent 2: keep edits minimal and document them.
- Financial FX/factor/scenario adapters and associated datastore additions. Source ownership is exact in SOURCE-OWNERS.csv; your own adapters should live in focused new modules.
- `web/src/features/profiles/`, `portfolio/`, `risk/`, `decision/` and their tests. Agent 2 may supply an independent component/patch for target agent analysis; incorporate it through documented interfaces rather than allowing concurrent edits in the same checkout.
- Relevant mathematical controls/reference fixtures and financial QA. Shared contracts/API/client/shell edits are additive and must be reported.

## Baseline to preserve

Generic session-owned profiles, three seeds, archive/restore, independent duplication and accounts already exist. Nine currencies have actual BoC-based calculations. Account creation now accepts native currency and retains independently checked FX receipts; analyses/aggregation use the profile reporting currency. Explicit capital edits clear obsolete native receipts. `POST /rebalance/check` already accepts complete final targets, supports reductions/removals and returns deterministic before/after metrics, checks and facts. It is read-only and does not claim a real agent review. Daily historical VaR/ES, variance contributions, correlation, frontier, source-linked metrics, explicit-input nominal goal scenarios and country/quote-currency proxy caps also exist. Audit them before adding or replacing functionality.

## Assigned implementation

### A. Full generic investor/profile policy model

Complete the reusable profile engine for arbitrary investor types, countries, reporting currencies and language. Retain seed profiles through exactly the same engine. Support risk tolerance versus risk capacity, liquidity requirements, multiple arbitrary horizons/start/end dates/deadlines, goals/priorities, spending/liability requirements where inputs exist, restrictions, permitted asset classes, position/sector/geography/currency/crypto/leverage limits, ESG/exclusions, drawdown and volatility budgets, themes, target allocations, rebalancing preferences and validated custom rules.

Every policy/input must retain origin: user, imported, system default, hypothetical assumption, or genuinely sourced implemented regulatory requirement. Defaults are never official regulation. Allow typed operations/thresholds/conditions without executing user-authored code or SQL. Preserve per-session isolation, versions, empty/missing-data behavior and conflict explanations. Do not invent tax obligations or financial liabilities; implement explicit-input models and show what remains unknown.

Provide usable create/edit/duplicate/archive/compare workflows, input validation, lossless round trips, accessible forms and account selection. Extend native account valuation with explicit refresh/as-of behavior, account editing/rebalancing, and transfers only with unambiguous conservation semantics. Preserve original valuation and rate receipts. Test stale FX refresh, historical availability, transfer/cash-flow conservation, retention of prior evidence on refresh, and unavailable-rate rollback. Integrate private/illiquid assets through documented user/source valuations and limitations rather than routing everything through traded-price providers.

### B. Portfolio intelligence and deterministic risk

Complete portfolio metrics/conventions: returns, sample windows, volatility, maximum drawdown, worst rolling returns, concentration/HHI/effective holdings, correlations/covariance, signed risk contributions, historical VaR/ES and stress scenarios. Financial calculations must be code, with aligned calendars, corporate actions, missing-data rules, rebalancing assumptions and explicit currency direction. Test against independent reference calculations and difficult zero/short/negative/overflow cases.

Implement supported factor exposure/DNA, currency sensitivity, interest-rate, credit-spread and commodity shocks, liquidity considerations and optimization/scenario comparisons with actual documented models and inputs. Source factors/rates/positioning from your assigned providers where terms/access permit; do not generate unsupported precise impacts. Use interfaces from Agent 2 for actual ETF constituent snapshots/security identifiers; Agent 2 owns issuer acquisition/crosswalk evidence, you own portfolio arithmetic and factor/overlap presentation. Build the consumers against exact typed IDs and dated captured fixtures while acquisition proceeds independently.

Provide quantities where supported, otherwise clearly labeled modeled position sizes, detailed holdings, direct/indirect allocations, currency/country/sector exposure, portfolio comparisons and all risk UI with fact/source inspection. Listing country and quote currency must remain labeled proxies where economic exposure/hedges are unknown.

### C. Complete decision controls and personalization candidates

Extend the current final-target comparison into complete controlled change semantics: increase, reduce, remove, add, compare sizes and rebalance, explicitly distinguishing final target weight, incremental purchases, new money and internal funding/withdrawals. Preserve valid weights/capital and reject impossible financing/leverage without an implemented model. Sliders must recalculate deterministically, without a full LLM run per adjustment. Provide alternatives and limitations; do not manufacture a maximum compatible-size bound for a non-monotonic multi-asset problem.

Produce typed deterministic candidate findings for the Home strategic brief: at most three primary focus candidates by default, ranked from actual risk/policy/goal/horizon findings with claim IDs, affected holdings, evidence, investigations and navigation targets. Agent 2 owns LLM wording/orchestration; supply candidate and context interfaces and tests. Resolve conflicting objectives through explicit calculations/assumptions, not persona labels or invented feasibility. Implement liability/spending/goal feasibility when sufficient inputs exist; report the exact missing inputs otherwise.

Support global/custom A–C demos, ESG insufficiency where relevant, and provide quantitative inputs for historical F. Implement all unblocked financial scope, not only P0.

## Source work

Audit and disposition every row assigned to Agent 1 in SOURCE-OWNERS.csv and MASTER-SOURCE-COVERAGE.csv, including organizer starter data and STLFSI4 (reuse Agent 2’s FRED adapter). Complete adapters that power the assigned risk/FX/rate/factor/positioning features with validated, versioned, attributed captures and meaningful tests. Rate reports, options summaries and short-sale volume are not live option chains or short interest. Additional currency support must be driven by actual source coverage. Unknown permissions/paid keys remain external blockers, not invented free access. Other agents own general security feeds, filings and world layers.

## Required acceptance and handoff

- Arbitrary profiles/horizons and simultaneous goals work without seed-name branches; origins and assumptions survive edits/copies.
- Individual/aggregate accounts conserve values, preserve evidence and reject unavailable rates/stale/cross-session operations. No implicit duplicate capital or stale native receipt.
- Every new quantitative metric/model reproduces independent reference cases, with units/dates and correct unknown states.
- Rebalance/reduction/funding semantics are explicit, stable and financially valid; no order path or unsupported leverage.
- All affected controls work through actual HTTP and UI, including at least one non-CAD/USD custom profile and mobile/keyboard interaction.
- Run focused financial tests, the full repository gate/static build and scoped browser scenarios. Label scripted agents if used; do not claim live Bedrock execution from a fake gateway.
- Finish the reports required by README.md, including requirement/source matrices, shared-file changes, interface examples, exact tests, evidence and blockers. Commit and push only your assigned branch; return its SHA and handoff path for independent integration.

## Explicit known baseline fix

Fix the shared `InfoTip` mobile overflow as part of your UI ownership. At configured screen/viewport 390 px on Decision Desk, a hidden start-aligned `.info-bubble` extends to x=482 and widens the document/innerWidth to 482. The target-allocation table is already inside its scrolling wrapper; do not misdiagnose or remove it. See [baseline QA](../evidence/parallel/baseline/browser/README.md) and the baseline mobile diagnostics. Preserve hover, keyboard focus, tap, escape/outside-close and accessible descriptions; keep visible tooltips within the viewport instead of merely hiding page-wide overflow. Assert configuredViewport=390, actual viewport and document width independently. `web/src/components/ui/InfoTip.tsx` and its focused CSS rules are shared files explicitly authorized for your minimal fix.
