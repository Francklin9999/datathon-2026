# Strategies — standing rules tested on history

**Owner:** T13. **Tier:** P1. Route `/strategies/`. [Backend](../../backend/aplomb/strategies/SPEC.md), [API §3.13](../../contracts/api.md).

## Purpose

Let the investor set up to three automations per profile (rebalancing, regular contributions, risk guard), see what each would have done on the history of today's holdings next to the same holdings left untouched, and what it would do next. Nothing is executed; strategies are saved in this browser (`aplomb.pref.strategies.v1.<profileId>`).

## Layout

- **Empty:** three cards, one per kind (icon, name, one sentence, Create).
- **List** (left): the saved strategies with their state (active or paused) and New strategy (inactive at three).
- **Settings:** name and the kind's fields, one line describing the configuration, Active on Home, Delete. Every change re-simulates after a short pause; invalid values are explained and not sent.
- **Results:** four figures against the untouched holdings (ending value, or gain on invested for contributions; time-weighted return; deepest fall; months outside the plan), the chart with and without (plus invested for contributions), the next action with its proposed trades, what it did (latest four, all in a details sheet with trades and costs), the plan check by rule, limitations.
- **Home:** the Automations widget lists the active strategies with their next action, from the same cached simulation.

## Verification

`web/tests/strategies-logic.test.ts` (defaults valid against the contract, request fields per trigger, form issues, descriptions, saved list limits). Browser: the three kinds created from the empty state, a trigger switch re-simulates, an invalid value is reported, three is the maximum, the sheet lists every action, Home shows the next actions; light and dark, 1440 and 390 px, no page error, no horizontal overflow, no widget scrolls.
