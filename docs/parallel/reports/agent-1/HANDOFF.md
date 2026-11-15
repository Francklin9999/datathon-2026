# Agent 1 handoff

Branch: `codex/agent-1-investor-quant`. Immutable baseline: `2604b9689e9f992b4e9e46c4a06ea89ec57ac155`. Final commit is the commit containing this report; obtain it with `git rev-parse codex/agent-1-investor-quant`. No deployment, active manifest change, paid subscription, account creation, other branch merge or force push.

## Expanded follow-up in progress

This branch has additional policy, quantitative and FX changes beyond the previously verified checkpoint below. **Do not interpret that checkpoint as verification of the current working tree.** The primary worker will record the fresh full gate, static build, HTTP/browser results, final SHA and any unresolved issues after the expanded changes settle. The immutable opt-in `snap-20261115-a1-fx-expanded` manifest adds 25 Bank of Canada-based reporting currencies; the integration-owned active snapshot remains unchanged. See `REQUIREMENTS.md`, `INTERFACES.md`, `POLICY-NOTES.md`, `QUANT-NOTES.md` and `docs/evidence/parallel/agent-1/fx-expanded-publication.json`.

New work includes bounded typed conditional policies and permitted-class enforcement; dated user/imported custom theme classifications; optimistic account editing and dated quantity provenance/history; common-currency multi-profile comparisons; sample covariance; explicit sale-capacity/liquidity assumptions; nested fund look-through with unresolved cycles/missing portions; active-portfolio factor regression against explicit or rights-gated captured inputs; and a joint spending/goal plan with explicit capital, priority, inflation and cashflow assumptions. Each remains bounded by its stated inputs and provenance; actual issuer crosswalks, factor captures and independent real-world valuations are not manufactured.

The new shared-file edits extend the previously listed set with `backend/aplomb/agents/workflow.py`, `backend/aplomb/api/runtime.py`, `backend/aplomb/datastore/global_fx.py`, `backend/aplomb/optimizer/rebalance.py`, `backend/aplomb/optimizer/services.py`, `backend/aplomb/rules/engine.py`, `backend/aplomb/timemachine/service.py`, `contracts/api.md`, `web/src/api/expandedInvestor.ts`, and additive profile/risk/portfolio/decision UIs. The parallel ownership contract assigns `agents/workflow.py` and `timemachine/service.py` to Agent 2, so their current edits require explicit cross-owner review or a narrow integration patch rather than being treated as ordinary shared wiring. Integrator review must resolve those changes and regenerate contracts. The previous changed-path inventory below is the earlier checkpoint, not a final inventory of the present worktree; derive the complete list against the immutable baseline before handoff.

## Previous checkpoint verification result

The verification follow-up passed **903 Python tests + 16 subtests, 208 web tests and 6 infrastructure tests**, including all 13 focused provider cases; four existing deprecation/serializer warnings are retained in the log, with no failed tests. The complete `npm run check` exited 0. Final static export exited 0. Real HTTP smoke passed **37 requests** (including paid/login rejection and permission-gated paths). Eleven extended browser interactions and separate hover/focus/touch/Escape/outside tooltip checks passed, with no browser errors and independently measured 390/390/390 mobile bounds on all four owned routes. Logs: `check-providers-final.log`, `provider-build.log`, `http-providers-final.log`, `browser-extended-verified.log`, `browser-final.log`.

The gate initially found an incorrect ledger accessor in the newly added capacity test; it was corrected to `get_fact`, the focused regression passed, and the full gate was rerun successfully. The HTTP harness respected a real 429 via `Retry-After`; production rate limits were not weakened. Final app/dev/browser processes started by this worker were stopped.

Current source scope: five new actual captured feeds plus existing BoC; **five additional anonymous connectors** are implemented/covered with synthetic source-format cases, but actual data-use permission/source availability is still a separate requirement. CME is excluded; OANDA, FRED and FINRA API short interest are set aside for login/API-key requirements. No paid source, login or credential is used by active acquisition choices. Do not describe mocked transport tests or HEAD reachability as live data integration.

Publication remains pending: automatic approval review rejected the push to `https://github.com/Francklin9999/datathon-2026` because destination/payload publication was not verified as authorized/trusted. No indirect push or workaround was attempted. The earlier checkpoint was committed locally; the expanded follow-up is not yet committed. Explicit approval is needed before retrying publication. See BLOCKERS.md.

## Implemented behavior

- Generic profiles preserve dated horizons/goals/requirements, risk capacity versus tolerance, arbitrary investor types, language/country, input origins, allocation targets and rebalancing preferences. Core derivation now uses the explicitly disclosed lower of capacity/tolerance table budgets; user/imported overrides are retained. Caps/floors run through the actual deterministic rule engine. Profile duplication/session/version behavior is preserved.
- Native-account FX refresh preserves receipts and applies explicit historical availability gates. Reporting-value transfers proportionally move traded holdings and conserve combined capital, retiring obsolete receipts. Unavailable-rate/stale/cross-session failures do not silently save partial state.
- Additional private/illiquid appraisals retain dated user/imported provenance and appraisal history, with independent FX receipts. They are excluded from traded risk/returns and explicitly additional to modeled traded capital.
- Explicit nominal requirements scenarios distinguish spending/liability withdrawals and liquidity reserves, report exact missing inputs, stop at first shortfall and never invent taxes, borrowing or income.
- Deterministic complete-target financing distinguishes deposits/withdrawals/internal sales and purchases. Final policy/risk comparison retains its documented original-capital basis; financing separately values after-flow holdings. Existing incremental sliders and read-only final-target checks remain intact.
- Numerical consumers support first-order signed FX/rate/spread/commodity/factor sensitivities, exact-ISIN dated partial fund look-through/overlap, and QR factor regression on explicitly supplied aligned samples. Unknown sensitivities/unresolved holdings remain unknown. Synthetic/caller inputs are never presented as actual issuer/factor acquisition.
- At most three ranked candidate findings have locally owned facts and affected holdings/missing-input navigation. Claim IDs remain empty until the real writer/auditor creates them. Policy navigation points to the actual Risk route.
- Five attributed real new captures (SOFR/COT/swaps/Treasury curve/debt) feed the HTTP/UI. Five additional anonymous source connectors have bounded acquisition, parsing, session-owned immutable storage and UI, with honest permission gates. Paid CME is excluded and login/API-key OANDA/FRED/FINRA short-interest are set aside per latest user instructions. New FRED raw data was removed before commit. See PROVIDERS.md and SOURCES.csv; wired is not a live-access claim.
- Tooltip placement uses a viewport-clamped fixed portal; hidden tooltips do not expand document width. Accessible description, focus, hover handler, touch, Escape and outside-close remain supported. No page-wide overflow suppression was added.

## Validation and latest user override

Before the final API-first pass, `UV_CACHE_DIR=/tmp/aplomb-agent-1-uv-cache npm run check` passed **889 Python tests + 16 subtests, 208 web tests and 6 infrastructure tests**, generated/static/spec checks and infra synthesis. Log: `docs/evidence/parallel/agent-1/check-final.log`. Static export passed (`build.log`).

Real local API smoke: `UV_CACHE_DIR=/tmp/aplomb-agent-1-uv-cache uv run python scripts/agent1_http_smoke.py`, **37 requests**, EUR/FR investor and JPY valuation, conservation/rollback, private appraisal, explicit scenarios/fund/factors/candidates and current-versus-historical cutoff. Evidence `http-smoke.json`. No model invoked; investor/model inputs are synthetic. A real replay request lacked configured model IDs and returned honest unavailable; scripted tests are not Bedrock evidence.

Real browser: `node scripts/agent1_browser_smoke.mjs` and `node scripts/agent1_browser_extended.mjs`, actual API/web at 8101/3101, Chrome 9321. Eleven extended interactions passed, including arbitrary EUR form and all numerical input consumers. Four owned routes independently measured **configured viewport=390, actual viewport=390, document=390** with no browser errors. Tooltip focus/Escape and tap/outside-close passed. Evidence: `browser/browser-extended.json`, `browser/browser-interactions.json`, screenshots in `browser/`. Failed early harness attempts are retained as historical diagnostic logs; final logs have `final` or successful JSON records. The final harness also asserts mouse hover/open and mouse-leave close.

The user temporarily requested API additions over new test cases, then explicitly reauthorized small tests and complete verification. The new provider suite passes **13 focused tests**, and verification repaired actual ownership/cache/integrity/revocation/filter/error-handling defects. It also identified that FINRA short interest requires Gateway credentials; that source is now set aside, leaving five anonymous connector paths. The prior repository-wide gate is recorded in `check-providers-final.log`; it predates the expanded follow-up. Static export passed again in `provider-build.log`. Details: PROVIDER-VERIFICATION.md.

Real HEAD reachability is recorded in `provider-reachability.json`: AQR, Cboe, OCC and public FINRA short-volume endpoints returned 200; French host did not connect. HEAD is only transport/metadata evidence, not successful data acquisition or permission. FINRA API metadata HEAD failure is explicitly not interpreted as GET dataset absence; it is out of active scope due to login requirements.

## Integration and genuine limitations

Read REQUIREMENTS.md for every assigned requirement and remaining engineering, BLOCKERS.md for external dependencies, SOURCES.csv for all 16 SRC plus 11 MASTER rows, INTERFACES.md for payloads, and PROVIDERS.md for anonymous/source-access status. This branch is **not a claim that the worldwide full specification is complete**. Bounded predicate trees, explicit-input liquidity, nested-fund decomposition and joint planning now exist; market execution/private risk, automatic sourced factor/issuer attachment, comprehensive field-level legacy provenance and guaranteed joint feasibility remain limited. Real reviewed Home/target orchestration and actual issuer crosswalks depend on Agent 2; merged production demonstrations/snapshot publication belong to the integrator.

Merge this branch independently before Agent 2/3. Reconcile additive shared models/routes/client/catalog mirrors without changing 1.4.0 independently; regenerate once after integration. New routes in `financial_provider_api.py` intentionally remain a narrow additive port rather than a separately bumped contract. The existing application store supplies session-owned capture retention and S3 spilling; no new database/service/IAM is introduced. Do not enable permission assertions without actual provider rights. Do not activate paid/login feeds contrary to the latest user scope.

## Shared-file changes

- `.gitignore`
- `backend/aplomb/api/app.py`
- `backend/aplomb/contracts/api.py`
- `backend/aplomb/contracts/models.py`
- `backend/aplomb/datastore/cftc_cot.py`
- `backend/aplomb/datastore/cftc_swaps.py`
- `backend/aplomb/datastore/fama_french.py`
- `backend/aplomb/datastore/financial_connectors.py`
- `backend/aplomb/datastore/financial_inputs_api.py`
- `backend/aplomb/datastore/financial_provider_api.py`
- `backend/aplomb/datastore/finra_volume.py`
- `backend/aplomb/datastore/nyfed_sofr.py`
- `backend/aplomb/datastore/treasury_inputs.py`
- `contracts/api.md`
- `contracts/generated/schema.json`
- `web/src/api/client.ts`
- `web/src/api/focusModels.ts`
- `web/src/api/investorModels.ts`
- `web/src/api/riskModels.ts`
- `web/src/components/ui/InfoTip.tsx`
- `web/src/contracts/types.ts`
- `web/src/styles/components.css`

Shared wiring is additive: API routes/router/store composition, profile/account request/response fields, schema/TS mirrors, client validation, source readers and minimal tooltip/CSS. `contracts/api.md` documents the new routes. `.gitignore` only excludes isolated build directories. API route inventory handling accommodates current FastAPI included-router wrappers while retaining exact documented endpoint equality. Existing baseline source captures and the integration-owned active manifest remain unchanged.

## Previous checkpoint changed paths (not the final expanded inventory)

- `.gitignore`
- `backend/aplomb/api/app.py`
- `backend/aplomb/contracts/api.py`
- `backend/aplomb/contracts/models.py`
- `backend/aplomb/datastore/cftc_cot.py`
- `backend/aplomb/datastore/cftc_swaps.py`
- `backend/aplomb/datastore/fama_french.py`
- `backend/aplomb/datastore/financial_connectors.py`
- `backend/aplomb/datastore/financial_inputs_api.py`
- `backend/aplomb/datastore/financial_provider_api.py`
- `backend/aplomb/datastore/finra_volume.py`
- `backend/aplomb/datastore/nyfed_sofr.py`
- `backend/aplomb/datastore/treasury_inputs.py`
- `backend/aplomb/optimizer/check.py`
- `backend/aplomb/optimizer/derive.py`
- `backend/aplomb/profiles/account_fx.py`
- `backend/aplomb/profiles/goals.py`
- `backend/aplomb/profiles/service.py`
- `backend/aplomb/quant/candidates.py`
- `backend/aplomb/quant/cashflows.py`
- `backend/aplomb/quant/engine.py`
- `backend/aplomb/quant/exposures.py`
- `backend/aplomb/quant/factors.py`
- `backend/aplomb/quant/metrics.py`
- `backend/aplomb/quant/scenario_api.py`
- `backend/aplomb/quant/target_funding.py`
- `backend/aplomb/rules/definitions.py`
- `backend/aplomb/rules/templates.py`
- `backend/tests/integration/test_track_composition.py`
- `backend/tests/unit/datastore/test_cftc_cot.py`
- `backend/tests/unit/datastore/test_cftc_swaps.py`
- `backend/tests/unit/datastore/test_fama_french.py`
- `backend/tests/unit/datastore/test_financial_inputs_api.py`
- `backend/tests/unit/datastore/test_financial_providers.py`
- `backend/tests/unit/datastore/test_finra_volume.py`
- `backend/tests/unit/datastore/test_nyfed_sofr.py`
- `backend/tests/unit/datastore/test_treasury_inputs.py`
- `backend/tests/unit/optimizer/test_optimizer.py`
- `backend/tests/unit/profiles/test_account_operations.py`
- `backend/tests/unit/profiles/test_exposure_limits.py`
- `backend/tests/unit/quant/test_exposures.py`
- `contracts/api.md`
- `contracts/generated/schema.json`
- `data/inputs/risk-cftc/legacy-futures-202611.json`
- `data/inputs/risk-cftc/legacy-futures-202611.metadata.json`
- `data/inputs/risk-cftc/swaps-irs-202610.html`
- `data/inputs/risk-cftc/swaps-irs-202610.metadata.json`
- `data/inputs/risk-fred/stlfsi4-202610.metadata.json`
- `data/inputs/risk-nyfed/sofr-202610.json`
- `data/inputs/risk-nyfed/sofr-202610.metadata.json`
- `data/inputs/risk-treasury/debt-202610.json`
- `data/inputs/risk-treasury/debt-202610.metadata.json`
- `data/inputs/risk-treasury/par-202610.metadata.json`
- `data/inputs/risk-treasury/par-202610.xml`
- `docs/evidence/parallel/agent-1/browser-attempt-1.log`
- `docs/evidence/parallel/agent-1/browser-extended-final.log`
- `docs/evidence/parallel/agent-1/browser-extended-verified.log`
- `docs/evidence/parallel/agent-1/browser-extended.log`
- `docs/evidence/parallel/agent-1/browser-final.log`
- `docs/evidence/parallel/agent-1/browser-run.log`
- `docs/evidence/parallel/agent-1/browser/browser-account-receipt.png`
- `docs/evidence/parallel/agent-1/browser/browser-eur-profile.png`
- `docs/evidence/parallel/agent-1/browser/browser-eur-spending.png`
- `docs/evidence/parallel/agent-1/browser/browser-extended.json`
- `docs/evidence/parallel/agent-1/browser/browser-fund-look-through.png`
- `docs/evidence/parallel/agent-1/browser/browser-interactions.json`
- `docs/evidence/parallel/agent-1/browser/browser-mobile-tooltips.png`
- `docs/evidence/parallel/agent-1/browser/browser-target-allocation.png`
- `docs/evidence/parallel/agent-1/browser/browser-visible-tooltip.png`
- `docs/evidence/parallel/agent-1/build.log`
- `docs/evidence/parallel/agent-1/capacity-regression.log`
- `docs/evidence/parallel/agent-1/check-final.log`
- `docs/evidence/parallel/agent-1/check-initial.log`
- `docs/evidence/parallel/agent-1/check-providers-final.log`
- `docs/evidence/parallel/agent-1/check.log`
- `docs/evidence/parallel/agent-1/http-final.log`
- `docs/evidence/parallel/agent-1/http-providers-final.log`
- `docs/evidence/parallel/agent-1/http-smoke.json`
- `docs/evidence/parallel/agent-1/infra.log`
- `docs/evidence/parallel/agent-1/provider-build.log`
- `docs/evidence/parallel/agent-1/provider-reachability.json`
- `docs/evidence/parallel/agent-1/provider-typecheck.log`
- `docs/evidence/parallel/agent-1/pytest-diagnostic.log`
- `docs/evidence/parallel/agent-1/typecheck.log`
- `docs/parallel/reports/agent-1/BLOCKERS.md`
- `docs/parallel/reports/agent-1/HANDOFF.md`
- `docs/parallel/reports/agent-1/INTERFACES.md`
- `docs/parallel/reports/agent-1/PROFILE-NOTES.md`
- `docs/parallel/reports/agent-1/PROVIDER-VERIFICATION.md`
- `docs/parallel/reports/agent-1/PROVIDERS.md`
- `docs/parallel/reports/agent-1/REQUIREMENTS.md`
- `docs/parallel/reports/agent-1/SOURCES.csv`
- `docs/parallel/reports/agent-1/STATUS.md`
- `scripts/agent1_browser_extended.mjs`
- `scripts/agent1_browser_smoke.mjs`
- `scripts/agent1_http_smoke.py`
- `web/src/api/client.ts`
- `web/src/api/focusModels.ts`
- `web/src/api/investorModels.ts`
- `web/src/api/riskModels.ts`
- `web/src/components/ui/InfoTip.tsx`
- `web/src/contracts/types.ts`
- `web/src/features/decision/RebalancePanel.tsx`
- `web/src/features/portfolio/Accounts.tsx`
- `web/src/features/portfolio/AllocationTargets.tsx`
- `web/src/features/portfolio/CustomPolicies.tsx`
- `web/src/features/portfolio/PortfolioPage.tsx`
- `web/src/features/portfolio/PrivateAssets.tsx`
- `web/src/features/portfolio/RequirementsScenario.tsx`
- `web/src/features/profiles/AllocationInputs.tsx`
- `web/src/features/profiles/InvestorInputs.tsx`
- `web/src/features/profiles/ProfileCompare.tsx`
- `web/src/features/profiles/ProfilesPage.tsx`
- `web/src/features/risk/FinancialInputs.tsx`
- `web/src/features/risk/FinancialProviders.tsx`
- `web/src/features/risk/FocusCandidates.tsx`
- `web/src/features/risk/ModelInputs.tsx`
- `web/src/features/risk/RiskPage.tsx`
- `web/src/features/risk/SensitivityScenario.tsx`
- `web/src/lib/profileForm.ts`
- `web/src/styles/components.css`
- `web/tests/investor-models.test.ts`
- `docs/evidence/parallel/agent-1/verification-final.json`
