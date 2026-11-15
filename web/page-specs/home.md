# Home — Portfolio Analyst Brief

**Owner:** T13. **Tier:** P0. Route `/`. Purpose: establish fictional investor, plan health and what deserves review before the user opens Decision Desk.

## Inputs and calls

After shared bootstrap call overview and performance in parallel, then cached brief for selected profile/language. `/profiles/{id}/brief` returning null permits one `portfolio_brief` run, deduped in the client and through run idempotency. Manual Refresh uses force=true. Cache is keyed on session/profile version/data version/window/language; a stale brief stays labelled stale rather than presented as current.

## Layout and behavior

Header: persona, fictional capital/reporting currency, horizon/risk level, data date and window. Metric strip: current fictional portfolio value, historical YTD/trailing return where supported, annualized volatility and positive drawdown. Performance card uses constant-weight series with actual dates, currency and limitation. Plan-health card shows verdict/counts and links to Portfolio rules. Analyst brief shows exactly three focus cards plus audited prose, with numeric segments clickable into the run ledger.

Actions: Test a move → Decision Desk retaining persona/window; Inspect plan → Portfolio; Refresh brief → real new run/progress. Do not generate a new analysis on every render/poll or language switch loop. Never label constant-weight historical returns actual account gains. Metadata like capital may be sourced from overview facts rather than requiring an agent run.

## Failure states and acceptance

Overview failure has retry and no zeroed financial summary. Missing trailing history prints “Unavailable for this period.” Mateo baseline shows insufficient evidence separately from financially passing rules. Model outage leaves deterministic cards usable with honest failed-brief status. Persona switch cancels stale requests and clears prior persona's prose until properly keyed cached content arrives.

HOME-01 baseline values match controls. HOME-02 at most one automatic missing-brief creation. HOME-03 edited rule invalidates old brief. HOME-04 every generated number opens its own fact and disclaimer remains visible. HOME-05 mobile/performance-table alternative. T13 hands a complete page with all loading/unavailable states to T16.
