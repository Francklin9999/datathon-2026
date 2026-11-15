# Agent 1 handoff

Branch: `codex/agent-1-investor-quant`. Immutable baseline: `2604b9689e9f992b4e9e46c4a06ea89ec57ac155`. Final commit is the commit containing this report; obtain it with `git rev-parse codex/agent-1-investor-quant`. No deployment, active manifest change, paid subscription, account creation, other branch merge or force push.

## Implemented behavior

- Generic profiles preserve dated horizons/goals/requirements, risk capacity versus tolerance, arbitrary investor types, language/country, input origins, allocation targets and rebalancing preferences. Core derivation now uses the explicitly disclosed lower of capacity/tolerance table budgets; user/imported overrides are retained. Caps/floors run through the actual deterministic rule engine. Profile duplication/session/version behavior is preserved.
- Native-account FX refresh preserves receipts and applies explicit historical availability gates. Reporting-value transfers proportionally move traded holdings and conserve combined capital, retiring obsolete receipts. Unavailable-rate/stale/cross-session failures do not silently save partial state.
- Additional private/illiquid appraisals retain dated user/imported provenance and appraisal history, with independent FX receipts. They are excluded from traded risk/returns and explicitly additional to modeled traded capital.
- Explicit nominal requirements scenarios distinguish spending/liability withdrawals and liquidity reserves, report exact missing inputs, stop at first shortfall and never invent taxes, borrowing or income.
- Deterministic complete-target financing distinguishes deposits/withdrawals/internal sales and purchases. Final policy/risk comparison retains its documented original-capital basis; financing separately values after-flow holdings. Existing incremental sliders and read-only final-target checks remain intact.
- Numerical consumers support first-order signed FX/rate/spread/commodity/factor sensitivities, exact-ISIN dated partial fund look-through/overlap, and QR factor regression on explicitly supplied aligned samples. Unknown sensitivities/unresolved holdings remain unknown. Synthetic/caller inputs are never presented as actual issuer/factor acquisition.
- At most three ranked candidate findings have locally owned facts and affected holdings/missing-input navigation. Claim IDs remain empty until the real writer/auditor creates them. Policy navigation points to the actual Risk route.
- Five attributed real new captures (SOFR/COT/swaps/Treasury curve/debt) feed the HTTP/UI. Six additional anonymous source connectors have bounded acquisition, parsing, session-owned immutable storage and UI, with honest permission gates. Paid CME is excluded and login/API-key OANDA/FRED are set aside per latest user instructions. New FRED raw data was removed before commit. See PROVIDERS.md and SOURCES.csv; wired is not a live-access claim.
- Tooltip placement uses a viewport-clamped fixed portal; hidden tooltips do not expand document width. Accessible description, focus, hover handler, touch, Escape and outside-close remain supported. No page-wide overflow suppression was added.

## Validation and latest user override

Before the final API-first pass, `UV_CACHE_DIR=/tmp/aplomb-agent-1-uv-cache npm run check` passed **889 Python tests + 16 subtests, 208 web tests and 6 infrastructure tests**, generated/static/spec checks and infra synthesis. Log: `docs/evidence/parallel/agent-1/check-final.log`. Static export passed (`build.log`).

Real local API smoke: `UV_CACHE_DIR=/tmp/aplomb-agent-1-uv-cache uv run python scripts/agent1_http_smoke.py`, **31 requests**, EUR/FR investor and JPY valuation, conservation/rollback, private appraisal, explicit scenarios/fund/factors/candidates and current-versus-historical cutoff. Evidence `http-smoke.json`. No model invoked; investor/model inputs are synthetic. A real replay request lacked configured model IDs and returned honest unavailable; scripted tests are not Bedrock evidence.

Real browser: `node scripts/agent1_browser_smoke.mjs` and `node scripts/agent1_browser_extended.mjs`, actual API/web at 8101/3101, Chrome 9321. Ten extended interactions passed, including arbitrary EUR form and all numerical input consumers. Four owned routes independently measured **configured viewport=390, actual viewport=390, document=390** with no browser errors. Tooltip focus/Escape and tap/outside-close passed. Evidence: `browser/browser-extended.json`, `browser/browser-interactions.json`, screenshots in `browser/`. Failed early harness attempts are retained as historical diagnostic logs; final logs have `final` or successful JSON records. Hover is implemented but was not separately asserted by the final harness.

The user then explicitly requested API additions over new test cases. **No new provider test cases were written and no full regression rerun is claimed after the final provider/capacity edits.** Provider code lint, application construction and TypeScript checks passed; `provider-typecheck.log` records the latter. `provider-build.log` records the final static build result. These limited checks are distinguished from the earlier full gate.

## Integration and genuine limitations

Read REQUIREMENTS.md for every assigned requirement and remaining engineering, BLOCKERS.md for external dependencies, SOURCES.csv for all 16 SRC plus 11 MASTER rows, INTERFACES.md for payloads, and PROVIDERS.md for anonymous/source-access status. This branch is **not a claim that the worldwide full specification is complete**. In particular arbitrary predicate trees, market liquidation/private risk models, automatic sourced factor/issuer attachment, nested funds, comprehensive field-level legacy provenance and joint goal optimization remain limited/unimplemented. Real reviewed Home/target orchestration and actual issuer crosswalks depend on Agent 2; merged production demonstrations/snapshot publication belong to the integrator.

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

## All intentional changed paths

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
- `docs/evidence/parallel/agent-1/browser-extended.log`
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
- `docs/evidence/parallel/agent-1/check-final.log`
- `docs/evidence/parallel/agent-1/check-initial.log`
- `docs/evidence/parallel/agent-1/check.log`
- `docs/evidence/parallel/agent-1/http-smoke.json`
- `docs/evidence/parallel/agent-1/infra.log`
- `docs/evidence/parallel/agent-1/provider-build.log`
- `docs/evidence/parallel/agent-1/provider-typecheck.log`
- `docs/evidence/parallel/agent-1/pytest-diagnostic.log`
- `docs/evidence/parallel/agent-1/typecheck.log`
- `docs/parallel/reports/agent-1/BLOCKERS.md`
- `docs/parallel/reports/agent-1/HANDOFF.md`
- `docs/parallel/reports/agent-1/INTERFACES.md`
- `docs/parallel/reports/agent-1/PROFILE-NOTES.md`
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
