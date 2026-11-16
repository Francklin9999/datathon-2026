# Optimizer — assumptions and bounded scenario search

**Track:** T07. **Tier:** derivation/max-size P0; goals/rebalance/frontier P1. Inputs from [quant](../quant/SPEC.md), [rules](../rules/SPEC.md), [decisions A-01–18](../../../docs/02-DECISIONS.md).

## 1. Public interface

`derive_thresholds(profile_fields, context) -> DerivedRules`; `max_compatible_size(profile, ticker, funding, context) -> SizeSearch`; `compare_funding(...) -> list[FundingOption]`; `goal_candidates(goal, context, max_candidates=3) -> list[Scenario]`; `alternatives(...)`; `rebalance(target, context)`; `propose_portfolio(profile_fields, context) -> Portfolio`; `frontier(...)`. Context pins gated return matrix, profile, universe, ledger and window. No AWS or model calls; agents select research and bounded tasks, never rewrite optimizer output.

## 2. Volatility budgets (`M_DERIVE_VOL_BUDGET`)

Low 6%, low_moderate 9%, moderate 12%, moderate_high 16%, high 22%. These are editable assumptions, not empirical truths or regulatory requirements. Risk-only inputs set thresholds; historical mean returns cannot influence them. Unavailable reference data produces a missing derivation, not a silently invented number.

## 3. Threshold derivation

Compute single-stock Q3 of annualized currency-converted volatilities using inclusive/linear quantiles; crypto median. Freeze the reference universe to starter assets for v1 so on-demand names cannot change every person's plan. Use full gated eligible history for derivation unless explicitly requested otherwise. Persist derivation window/version/reference universe.

- Position cap percent = `clamp(round5(100 * 0.4 * budgetPct / sigmaStockPct),5,25)`.
- Sector cap = min(40, 2 × position cap).
- Crypto cap = `clamp(round5(100 * 0.4 * budgetPct / sigmaCryptoPct),0,25)`; for low interest/avoid speculative halve then floor to a multiple of 5; none → exclusion.
- Growth cap = greatest 5-point equity fraction whose reference mix (50% XIU.TO, 50% SPY, rest XBB.TO) meets budget. Evaluate the entire 0–100 grid because risk may initially decrease. Fixed-income floor = max(0,100-growthCap-10).
- Stress limit = budget × 1/1.25/1.5 for horizon midpoint <=5/<=10/>10. Open-ended horizon uses min. Drawdown ceiling = 2 × budget.
- Add profile preference rules and diversification floor using [profile mapping](../profiles/SPEC.md). `round5` uses round-to-nearest with ties-to-even, matching Python reference scripts. Record exact formula and operands.

If no reference mix meets the budget (possible for low risk), return a structured derivation issue; do not pick the least-bad mix as a compliant one. For a custom starting portfolio, include explicit same-currency cash if needed and retest every rule.

## 4. Largest size and funding ranking

Scan sizes 0,0.5,… up to funding capacity/100 points. Zero is an internal baseline test, not a valid positive move API call. Return the last size before the first **conflict**, even if it has tension/nee. Baseline conflict → size 0 and `baselineConflict=true`; report no feasible positive prefix. An evidence-only gap must remain attached to the result. Never call this a proof of full compatibility; wire field is kept for v1 compatibility.

This is a contiguous prefix on a discrete grid, not a mathematical global maximum: diversification can make constraints nonmonotone. Do not use binary search or leap over a conflicting size. Cache matrix/covariance and batch metrics; materialize facts only for retained boundary/candidate scenarios, not every grid point, to stay within ledger limits.

Automatic funding evaluates pro-rata, real cash, named donor set and new money. Named-donor default: eligible non-target equities/crypto sharing target themes first, then other growth assets; sort by descending weight then ticker, add until size covered. Disclose exact donors; never choose excluded/unowned names. Rank feasible modes lexicographically by conflict count, tension count, nee count, amount of external money, turnover, mode name. Exactly one recommended option if any feasible. This is a hypothetical funding scenario ranking, not an instruction to sell.

## 5. Candidates, rebalance and starting portfolio

Goals screen up to eight eligible theme/class/ticker matches with enough history, remove explicit exclusions, and test sizes/funding under existing rules plus goal-specific max loss/vol. Rank by conflicts, tensions, nee, target-exposure shortfall (or greatest exposure if no target), turnover, ticker; never expected return. Retain up to three distinct candidates and mark exactly one best-fit if any exist. Return fewer if only fewer are supported, with an explicit limitation. A goal constraint never loosens a profile rule.

Alternatives share documented tags, with independent rule checks; similarities do not imply equivalence. Rebalance uses a deterministic bounded greedy/grid search minimizing turnover and number of changes under all enabled constraints. Validate final weights, rules and funding; no solution found within budget is an honest outcome, not a proof none exists. Multiple additive moves apply sequentially to the preceding variant and its current denominator, with the order recorded.

Proposed custom starting portfolio uses documented broad-equity/bond/cash/gold reference assets, explicit preference exclusions and risk-only validation. If controversy evidence is absent, proposal can be financially feasible but overall insufficient. Never invent holdings from vague free text or claim a historical starting mix is verified ESG-clean.

## 6. Descriptive frontier

For a bounded eligible universe use sample covariance of aligned returns. `M_FRONTIER_MINVAR`: long-only variance minimization at a grid of total-equity allocation targets, sum weights=1; plot realized historical annualized return afterwards. `M_FRONTIER_HIST_MV`: long-only min variance at feasible historical mean-return targets; label illustration. Singular covariance → documented regularization or omit plot with limitation. Neither curve feeds rules or forecast claims. Persist numerical tolerance, solver/version, constraints and deterministic seed if sampling used.

## 7. Verification and completion

OPT-01 reproduce all default thresholds, Q3=31.22 and crypto median=59.97 controls within tolerance. OPT-02 reproduce TSLA boundaries Robert 6.0, Amira 11.0, Mateo financial-prefix 10.0 plus evidence limitation; CNQ Mateo 0. OPT-03 new-money and donor-set controls. OPT-04 synthetic nonmonotone grid does not skip first conflict. OPT-05 baseline conflict and no feasible mix. OPT-06 deterministic tie-breaking and no return-based candidate ranking. OPT-07 no double-counting overlapping theme exposure (union of matched positions). OPT-08 frontier never affects verdict.

Handoff includes structured missing/no-solution results and performance measurements; it does not require P1 charts to finish before P0 size search is integrated.

## 8. Implementation status (T07, 2026-11-14)

P0 is implemented in `backend/aplomb/optimizer/`:

| Module | Content |
|---|---|
| `derive.py` | `derive_thresholds(profile, engine, created_at, window)` -> `Derivation(rules, fact_ids, values, issues)`: A-02..A-10 from recomputed reference statistics (starter single-stock Q3, crypto median, full 0–100 reference-mix grid); `no_feasible_reference_mix` issue instead of a least-bad mix |
| `search.py` | `max_compatible_size` (contiguous 0.5-point prefix from zero, stops at the first conflict, records remaining tension/nee), `compare_funding` (four modes, lexicographic ranking, one recommended), `auto_donors` (theme-sharing growth holdings first, owned and not excluded) |
| `check.py` | `CheckServiceImpl` for T03 (`POST /check`): overrides, as-of gate (historical before the data date), funding resolution, rule checks, baseline conflict, size facts; `prepare`/`assess` split for the agent steps |
| `services.py` | `deriver`/`proposer` hooks for `ProfileServiceImpl`, `DecisionControls` (T08 `CodeControls` for move requests: requested and max-compatible scenarios, plus the optional analyses a plan selects from `OPTIONAL_ANALYSES`; every plan task is returned as executed or skipped in `planTasks`), `build_domain_services` |

Grid points use `PortfolioView(record=False)` and `rules.engine.quick_statuses` (same comparisons, no facts); only retained results become facts. `uv run pytest backend/tests/unit/optimizer` reproduces controls §7 thresholds (Q3 31.22, crypto median 59.97) and every §9 boundary (Robert 6.0, Amira 11.0, Mateo TSLA 10.0 with the evidence gap attached, Mateo CNQ 0, new money 6.0/11.0/12.5, named donors 12.0), the §9.2 funding table, AT-01/02/03/18, PRF-04 and a synthetic nonmonotone grid. A warm `/check` for Robert +25 TSLA takes about 0.1 s locally.

P1 is implemented too:

| Module | Content |
|---|---|
| `scenarios.py` | `goal_candidates` (screen up to 8 eligible named/theme/class matches, goal loss/volatility limits only add conflicts, smallest size reaching a target exposure else the first-conflict boundary, union exposure without double counting, ranking by conflicts, tensions, nee, target shortfall, turnover, ticker), `alternatives` (assets sharing a theme tag, sized to fit), `rebalance` (bounded greedy search over broad funds, bonds, gold and same-currency cash, donors = assets driving conflicts; "none found" is reported, never claimed impossible) |
| `frontier.py` | `M_FRONTIER_MINVAR` at 0–100% equity targets and `M_FRONTIER_HIST_MV` via a risk-aversion grid, long-only, FISTA projected gradient (no numpy), fixed tolerance/iteration limits, facts per point, served by `GET /profiles/{id}/frontier` |
| `tools.py` | The 21 catalog tools of T04–T07 (`universe.*`, `profile.get`, `data.describe`, `macro.series`, `quant.*`, `rules.check`, `optimizer.*`) with Pydantic args; `register_domain_tools(registry)` for T08 |

`DecisionControls` handles goal requests (up to three candidates, best fit selected; when the target is already met or no eligible asset can serve the goal, one `sc_goal_no_change` scenario keeps the current portfolio, proposes no move and states the reason), adds up to two alternatives when a move conflicts and a rebalance when the current portfolio already conflicts, within six scenarios. Tests: `backend/tests/unit/optimizer/test_scenarios.py` (the agent-registry part needs POSIX `fcntl` through T03's storage import).
