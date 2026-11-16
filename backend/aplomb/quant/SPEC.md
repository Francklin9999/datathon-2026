# Quant engine — reproducible figures and funding mathematics

**Track:** T05. **Tier:** P0. Public tool names: [tools §3](../../../contracts/tools.md). Expected numbers: [controls](../../../contracts/controls.md). No model/network/AWS dependency inside maths.

## 1. Interface and result model

Implement `asset_metrics`, `calendar_year_return`, `portfolio_snapshot`, `portfolio_metrics`, `apply_move`, `compare_funding`, `stress_replay`, `correlation`, `exposure`, `price_move_after`. A calculation receives gated rows, explicit currency/window and ledger; returns value + fact reference or typed missing reason. `PortfolioMetrics` holds volatility, positive drawdown, signed stress return, HHI/effective-N and their fact IDs; missing members are nullable with reasons. Register each source-dependent result in the ledger before returning it.

## 2. Calendar (`M_CAL_INTERSECTION`)

Master dates = sorted intersection of XIU.TO and SPY observed dates in the pinned version, clipped to cutoff/window. Starter: 1,228 price levels, 1,227 returns. Sample crypto on these dates; returns bridge weekends/holidays. Do not price-fill missing equities. On-demand assets use that same calendar with their own coverage intersection; affected whole-portfolio risk is unavailable if an included position lacks needed common history. Always show actual period and nObs.

## 3. Adjustments (`M_PRICE_ADJ_CLOSE`)

Use `adj_close` directly. Never reapply splits/dividends. Corporate actions are annotations only. Non-positive/nonfinite prices fail ingestion. Attach CNQ limitation if the window spans 2022-08-22, source-sector/ETF-look-through and survivor/sample limitations as relevant. Last adjusted close must be labelled adjusted, not current executable quote.

## 4. Currency (`M_FX_BOC_FFILL`)

CAD value of USD price = price × USD/CAD on or before that date. USD value of CAD price = price ÷ USD/CAD. Carry FX only forward from an earlier available rate; no backward fill. Price and FX availability both constrain facts. USD cash changes in CAD with FX; CAD cash changes in USD with inverse FX. Same-currency cash has zero return, no interest (`LIM_CASH_NO_INTEREST`).

## 5. Returns

Simple return `P_end / P_start - 1`; wire value multiplies by 100. Calendar-year asset return uses last own-calendar observation on/before Dec 31 of prior/current year, with explicit actual dates; this includes crypto Dec 31. Portfolio calendar-year/stress returns use master-calendar boundary levels. Do not annualize a displayed total return. Descriptive annualized return for frontier = `(V_end/V_start) ** (252/n_returns) - 1`, labelled historical. Unsupported full trailing windows return null, rather than relabelling shorter history “5Y.”

## 6. Risk and concentration

Daily returns `r[t] = P[t]/P[t-1]-1`. Annualized vol = sample SD (`ddof=1`) × sqrt(252) × 100. At least two returns mathematically; risk-rule eligibility requires at least 252 **price observations** (A-21), with nObs reflecting observations rather than returns. Drawdown = positive `-min(V/runningMax(V)-1) × 100`, including initial level. Controls print negative declines; API drawdowns are positive magnitudes. Worst rolling 12m needs 253 levels for a 252-return interval. Pearson correlations are null for zero-variance/insufficient pairs; no NaN on wire. HHI = sum(fraction_weight²), effective N = 1/HHI. Sector cap sums direct equity weights divided by total portfolio value, never by equities alone.

## 7. Portfolio history (`M_PORT_CONST_WEIGHTS`)

At each master return period `r_p[t] = sum(w_i * r_i[t])`; compound `V[t]=V[t-1]*(1+r_p[t])`. Current fractional weights are constant/daily rebalanced. Use sample SD of these returns, not weighted standalone volatilities. Sum aligned currency-converted returns. Initial value includes all positions. No transaction costs/taxes/interest modeled; not an actual account track record.

## 8. Funding (`M_WEIGHTS_AFTER_MOVE`)

Let fractional current weights sum to 1, target weight `w_t`, added fraction `s=sizePct/100`, portfolio value V. Non-new-money modes keep V fixed and require `0<s<=1-w_t`. Never round internal weights.

| Mode | Exact equation / feasibility |
|---|---|
| pro_rata | `w'_t=w_t+s`; for every other i, `w'_i=w_i*(1-w_t-s)/(1-w_t)`; fail if denominator zero |
| from_cash | Donors are actual CASH pseudo-assets other than target, aggregate D; `w'_i=w_i*(D-s)/D` for donors; other positions unchanged; require D>=s |
| from_holdings | Explicit ordered unique donors excluding target; drain each donor in order by `min(w_i, remaining_s)` until funded; require total donors >=s and all donors owned; never spill to unlisted holdings |
| new_money | Deposit `s*V`, immediately allocate to target; `V'=V*(1+s)`; `w'_t=(w_t+s)/(1+s)`; all others `w'_i=w_i/(1+s)` |

Reject negative/nonfinite size, duplicate donors and target among donors. `auto` is resolved by optimizer; quant never guesses. New-money input bounded at 100 points by the v1 contract; it is neither leverage nor external FX conversion. Zero-weight positions can be dropped after exact computation.

Default portfolios have no actual cash: `from_cash` is infeasible even though they hold ZST.TO. For automatic named-holding funding, optimizer proposes and records a deterministic donor set; user-explicit sets are never silently altered.

## 9. Historical stress

2022 = last master day 2021 to last master day 2022 using constant weights; return is signed. Rule measures `max(0,-returnPct)` separately. Rate cycle = 2022-03-02 through 2023-07-13 (baseline day before first increase recorded March 3), informational only. Missing either boundary means unavailable, not a shorter disguised scenario. Historical runs before year-end 2022 cannot know the full 2022 stress.

## 10. Verification

QNT-01 starter counts/calendar/FX. QNT-02 all printed asset returns/vols/drawdowns. QNT-03 baseline and scenario portfolio controls within printed tolerance. QNT-04 all four funding equations on held and unheld target, insufficient donor balance and new denominator. QNT-05 percent/fraction conversion and positive drawdown. QNT-06 missing history, zero variance, foreign cash and no prior FX. QNT-07 historical cutoff never changes from future-row perturbation. QNT-08 2022 stress returns vs positive loss inputs.

Done: offline controls pass, facts have sources/methods/windows and unavailable values propagate to rules. Expose reusable aligned return matrices for T07 so grid scans do not reload CSVs hundreds of times.

## 11. Implementation status (T05, 2026-11-14)

Implemented in `backend/aplomb/quant/` (no AWS, model or network imports):

| Module | Content |
|---|---|
| `metrics.py` | Pure maths: simple returns, sample-SD volatility x sqrt(252), positive drawdown, worst rolling 252, constant-weight compounding, Pearson, HHI |
| `funding.py` | `apply_move(weights, ticker, size_pct, mode, from_tickers)` -> `MoveResult`; exact §8 equations; `FundingError(code, reason)` |
| `market.py` | `MarketData`: gated master-calendar levels in the reporting currency, FX only from an earlier or same-day rate, nothing filled |
| `engine.py` | `QuantEngine(gate, ledger, currency, subject_id, created_at, window)`; `PortfolioView.measure(metric, key)`, `.metrics()`, `.snapshot()`; `asset_metrics`, `calendar_year_return`, `correlation`, `price_move_after`, raw `risk_values` for grid scans |
| `facts.py` | Fact builder validated by `aplomb.contracts.models.Fact`, EN/FR display formatting, interim `LocalLedger` (subset of T10's `Ledger`: `add_fact`, `get_fact`) |

Later explicit-input models behind the A1.x HTTP routes of [api.md §1](../../../contracts/api.md), all mounted by `backend/aplomb/api/app.py` behind the session dependency:

| Module | Content | Routes (`/v1` prefix) |
|---|---|---|
| `scenario_api.py` | HTTP boundary for user-supplied scenarios | `POST /risk/scenario` (A1.9), `POST /decision/target-funding` (A1.13), `POST /risk/fund-look-through` (A1.11), `POST /profiles/{id}/requirements-scenario` (A1.8), `POST /risk/factor-fit` (A1.10) |
| `exposures.py` | Exact-identifier dated fund look-through, disclosed overlap, first-order `linear_shock` | used by `/risk/scenario`, `/risk/fund-look-through` |
| `target_funding.py` | `compare_target_funding`: final-target arithmetic with explicit deposit or withdrawal | used by `/decision/target-funding` |
| `cashflows.py` | `requirement_scenario`: nominal liquid-capital scenario, no borrowing assumption | used by `/profiles/{id}/requirements-scenario` |
| `factors.py` | `fit_factor_exposures`: OLS on explicitly aligned start/end return periods | used by `/risk/factor-fit`, `/profiles/{id}/factor-exposure` |
| `expanded_api.py` | `make_router(session)`: session-bound comparisons, matrices and explicit-input models | `POST /portfolios/compare` (A1.21), `POST /risk/covariance` (A1.22), `POST /profiles/{id}/liquidity-analysis` (A1.23), `POST /risk/nested-fund-look-through` (A1.24), `POST /profiles/{id}/factor-exposure` (A1.25), `POST /profiles/{id}/position-details` (A1.26) |
| `covariance.py` | `sample_covariance` on identical return calendars | used by `/risk/covariance` |
| `liquidity.py` | `sale_scenario`: explicit sale-date capacity, spread and impact | used by `/profiles/{id}/liquidity-analysis` |
| `nested.py` | `nested_look_through`: bounded exact-ISIN nested decomposition with explicit unknown mass | used by `/risk/nested-fund-look-through` |
| `joint_plan.py`, `joint_plan_api.py` | Dated shared-capital plan across goals and cash requirements | `POST /profiles/{id}/joint-plan` (A1.20) |
| `candidates.py` | `strategic_brief`: deterministic focus candidates with a local ledger | `GET /profiles/{id}/strategic-candidates` (A1.6), route defined in `app.py` |

`measure()` returns `Measurement(value, fact_id, unit, worst, nee_reason)`; unavailable figures carry a catalog NeeReason (`short_history`, `not_visible_at_asof`, `asset_unknown`). A-21 (252 master observations) gates risk metrics per asset. Ties for the largest position/sector follow portfolio order (controls list NVDA for Amira). Facts with the same key and value are reused; a different value under one key is rejected, so callers must give each portfolio its own variant. Stress 2022 and the rate cycle are unavailable until `asOf` reaches the window end.

Verification: `uv run pytest backend/tests/unit/quant` reproduces every value of controls §4, §6, §8 (volatility, drawdown, 2022, total, YTD, 1y, rate cycle) and the §9 scenario risk figures, plus QNT-04…QNT-08 with synthetic snapshots; `test_expanded.py`, `test_exposures.py` and `test_joint_plan.py` in the same folder cover the later models. The ten `quant.*` tools of [tools §3](../../../contracts/tools.md) are wrapped in `backend/aplomb/optimizer/tools.py` (`HANDLERS`) and registered by `register_domain_tools`, which `build_registry` in `backend/aplomb/api/runtime.py` calls.


## 12. Historical tail and variance diagnostics (contract 1.2.0)

`historical_tail_pct` uses aligned constant-weight portfolio daily returns. With n >= 100,
select k = ceil(0.05*n) largest losses (-100*r). Historical daily VaR95 is max(0, the smallest
selected loss); ES95 is max(0, the selected mean). Confidence is 95%, holding period one
master-calendar day. No interpolation, annualization or square-root horizon extrapolation.
This is the empirical equal-weight discrete-tail convention, not a calibrated future-loss model.

`variance_shares_pct` computes 100*w_i*Cov(r_i,r_p)/Var(r_p), using sample covariance and variance
on the same aligned observations. Defined shares sum to 100%; negative contributions are
possible. A zero-variance sample returns undefined contributions rather than dividing by zero.
The API attaches price/FX source receipts, composition input, calculation method, reporting
currency and window to each defined diagnostic. Existing financial policy rules are unchanged.
