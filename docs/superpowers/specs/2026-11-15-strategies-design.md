# Aplomb — standing strategies (automations) simulated on history

**Date:** 2026-11-15 · **Contract:** 1.5.0 ([api.md §3.13](../../../contracts/api.md)) · **Backend:** [strategies SPEC](../../../backend/aplomb/strategies/SPEC.md) · **Page:** [strategies](../../../web/page-specs/strategies.md)

## Request (user)

Add an investment-strategy feature: the investor creates two or three kinds of strategies, configures them, and they act a little like automations. The user does not know the field: research it, analyse whether it is useful and whether it can earn points at the hackathon, plan, then implement.

## Analysis

- **What Aplomb does:** it tests *one* hypothetical move against a fictional investor's plan, with code-computed figures and an audit trail.
- **What it lacked:** investors and advisers also set *standing rules* that act over time. This is the core of robo-advisers and of an adviser's first set-up.
- **Choice of kinds.** The three most studied and most used kinds were kept:
  - **Rebalancing** (calendar or tolerance band), for the classic trade-off between risk control and turnover.
  - **Regular contributions** (dollar-cost averaging, optionally into the underweight positions, rebalancing without selling).
  - **Drawdown-based de-risking** (risk guard with re-entry), for protection against the whipsaw cost.
- **Why it can score:**
  - It extends the product's core idea from one move to a policy over time.
  - It reuses the existing deterministic engine, real data and the plan's rules.
  - Every automated action is listed with its date, reason and trades, and checked against the plan: the product's evidential signature.
  - It is honest by construction: a historical simulation compared with the untouched holdings, limits stated, nothing executed.

## Plan, as carried out

1. **Contract (1.5.0, additive).**
   - Endpoint `POST /profiles/{id}/strategies/simulate` and `StrategyConfig`, a discriminated union on `kind`.
   - Response `StrategySimulation`.
   - Method `M_STRATEGY_SIM`, limitations `LIM_STRATEGY_COSTS` and `LIM_STRATEGY_EXECUTION`.
   - Python, JSON Schema and TypeScript regenerated.
2. **Backend `aplomb/strategies/`.**
   - `simulate.py`, pure: drifting holdings, decisions at the close, baseline, time-weighted metrics, next action.
   - `service.py`: defaults, safe asset, inputs from the quant engine, plan check with `quick_statuses` on allocation rules.
   - The route goes through the profile service.
3. **Web.**
   - Client method and pure `lib/strategies.ts`: defaults, validation, request body, saved list.
   - The Strategies page (rail entry after Decide) and the Automations widget on Home, sharing the cached simulation.
4. **Docs and verification.**

## Decisions

- **Stateless server, strategies saved in the browser** (at most three per profile). Profile edits are server-side, but a strategy is a UI preference that only parameterises a deterministic read. This avoids a new store and a Profile schema change during the datathon.
- **The last day is "today".** Strategies act only before it, and what they would do on it is the next action. That way the dashboard shows a proposal, never a hidden past trade on today's data.
- **Time-weighted figures,** so contributions do not look like returns and every strategy compares with the untouched baseline. The value, the invested amount and the gain are also shown for contributions.
- **The plan check covers allocation rules only, at month ends.** Re-evaluating volatility or drawdown limits per month would need a window per date and would mix definitions.
- **Defaults are chosen so each kind does something on all three investors** (the risk-guard trigger is 8 %: Robert's deepest fall is 9.9 %) and stay within the contract's bounds.

## Findings on the starter data (window full, 10 bps)

| Investor, strategy | Return (with / untouched) | Deepest fall | Months outside the plan |
|---|---|---|---|
| Robert, quarterly rebalance | 49.4 % / 53.7 % | 9.7 % / 9.9 % | 0 / 13 of 61 |
| Amira, quarterly rebalance | 127.8 % / 113.8 % | 31.2 % / 28.9 % | 0 / 22 |
| Amira, risk guard 8 / 50 / 3 | 64.3 % / 113.8 % | 24.1 % / 28.9 % | 0 / 22 |
| Amira, 1,000 CAD a month to the underweight | 133.2 % / 113.8 % | 30.9 % / 28.9 % | 31 / 22 |

- **Rebalancing** keeps the plan's allocation rules and slightly lowers volatility. It can cost return when equities rally (Robert) or add some (Amira).
- **The risk guard** reduces the deepest fall but, in this rising sample, misses rebounds.
- **Contributions to the underweight positions "buy the dip"** (crypto in 2022). Growth exposure later rises: more return and more risk, and more months below Amira's diversifier floor.

These are the non-obvious results the page is meant to surface.

## Verification

- **Backend.**
  - `pytest backend/tests/unit/strategies` covers the 7 synthetic behaviours.
  - `test_domain_http.py::test_strategy_simulation` covers the three kinds on starter data, validated against the contract: defaults echoed, custom window, 422 errors, 404.
  - The contract and generated-file tests pass.
- **Web.**
  - `tests/strategies-logic.test.ts` has 5 tests.
  - Typecheck is clean.
- **Browser** (Chrome, live local API).
  - From the empty state, the three kinds were created and each was simulated. A trigger switch re-simulates; an invalid value is explained; three is the maximum; the action sheet lists every action; Home shows the three next actions.
  - Checked in light and dark, at 1440 and 390 px: no page error, no horizontal overflow, no widget scrolls.
  - One simulation takes about 0.3 s.
