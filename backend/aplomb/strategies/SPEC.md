# Strategies — standing rules simulated on history

**Tier:** P1. Endpoint: [api.md §3.13](../../../contracts/api.md). Method `M_STRATEGY_SIM` ([catalog §2](../../../contracts/catalog.md)). No model, network or AWS dependency; nothing is stored or executed.

## 1. Purpose

A strategy is an automation the investor configures once and that would act on its own over time. The product already tests one hypothetical move against the plan; a strategy tests a *standing policy* on the history of today's holdings, next to the same holdings left untouched, and checks the plan's allocation rules along the way. Three kinds, the most studied and most used in practice:

| Kind | Acts when | What it does |
|---|---|---|
| `rebalance` (`calendar`) | Last master day of each month, quarter or year | Restores today's weights |
| `rebalance` (`band`) | A day when a position is more than `bandPts` points from its target | Restores today's weights |
| `contribute` | First master day of each month or quarter | Adds `amount`: by target weights, or to the positions furthest below target (never sells) |
| `risk_guard` | The fall from the strategy's own peak reaches `triggerDrawdownPct` | Moves `shiftPct` % of each equity and crypto position to the safe asset; restores today's weights once the fall is under `reentryDrawdownPct` |

## 2. Simulation (`simulate.py`, pure)

- Holdings in money start at `totalValue × weight` and drift with each asset's simple daily return on the master calendar (quant SPEC §2, §5); USD assets are already converted (quant §4).
- The strategy decides at the close of each day **before the last**. The last day is "today": what the strategy would do then is `nextAction`, never part of the history.
- A trade sets new amounts; costs are `costBps / 10 000 × Σ |traded|`, taken pro rata from the result. Trades conserve money apart from costs.
- The baseline starts identical and never acts (no contributions, no rebalancing).
- Contributions are flows: the time-weighted index (`twrPct`, `volPct`, `maxDrawdownPct`) removes them. `invested` = starting value + contributions; `gain` = end value − invested.
- `turnoverPct` = Σ |traded| ÷ mean daily value × 100. At most 200 actions are returned (the latest), `actionsTruncated` says so.
- The safe asset defaults to the largest bond fund held, else `CASH.<currency>`; a requested safe asset must not be equity or crypto.

## 3. Plan check (`service.py`)

At every month end, the strategy's and the baseline's weights are checked with `quick_statuses` against the profile's enabled **allocation** rules (metrics `weight.*`: caps and floors). Risk rules (volatility, drawdown, stress) need a whole window and are not re-evaluated per month. A month is "in conflict" when any of these rules is in conflict.

## 4. Limits

Historical sample only (`LIM_PAST_NOT_FUTURE`, `LIM_SAMPLE_WINDOW`); actions at the trigger day's close (`LIM_STRATEGY_EXECUTION`); flat costs, no taxes or spreads (`LIM_STRATEGY_COSTS`); simulation only (`LIM_SIMULATION_ONLY`). Cash earns nothing (`LIM_CASH_NO_INTEREST`, when cash is involved).

## 5. Verification

`backend/tests/unit/strategies/test_simulate.py` (synthetic prices: rebalancing restores target and conserves money, costs reduce value, band acts only past the band, contributions never sell and are not returns, the risk guard de-risks then returns and lowers the deepest fall, the last day is only proposed, determinism) and `backend/tests/integration/test_domain_http.py::test_strategy_simulation` (contract-validated responses for the three kinds on starter data, defaults echoed, errors).
