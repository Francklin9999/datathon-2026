# Portfolio — holdings, rules and descriptive risk

**Owner:** T13. **Tier:** P0; frontier P1. Route `/portfolio/`.

## Data contract

Use selected profile plus overview/performance; frontier is fetched lazily when its flag and chart panel are active. All values stay in reporting currency, actual requested window and snapshot version. Rule edits PATCH one threshold/enabled flag, receive new profileVersion, invalidate overview/brief and rerun deterministic checks. Preview overrides through `/check` are not saved unless explicit Save is pressed.

## Sections and interactions

Holdings table: asset/name/class, weight, market value and supported trailing return; sum weights footer. Allocation by group and direct-equity sector, country exposure clearly labelled listing-country proxy. Risk cards: vol, drawdown, 2022 signed return with rule loss magnitude distinction, HHI/effective N and correlation matrix when <=20 positions. Every rule row: R code, editable-assumption label, threshold/value/status/headroom, derivation explanation and fact/source links.

Editing respects PolicyRule bounds and step. Fixed sim.only cannot be disabled. Restoring derived rules asks the user to distinguish preserving user edits (reset=false) versus resetting them (reset=true); show resulting plan and invalidate prior signed briefs. Holdings editor P1 validates distinct tickers, nonnegative weights, 100±0.01 total and positive capital; version conflict prompts reload with edits preserved locally (in memory, for the reload that remounts the editors at a newer version; the editor says the entries were kept and asks to check them before saving; `web/src/lib/draftStore.ts`). No actual transfer/order action.

## Frontier

Use backend points, never browser-computed replacements. Axes historical vol and annualized historical return, current portfolio/budget indicators and exact window/currency. Distinguish risk-only minimum-variance curve from historical-MV illustration. Mandatory past-not-future/sample/MV limitations. A click only inspects hypothetical weights; does not save them or claim optimal future performance.

## Verification

PORT-01 weights/categories reflect selected profile. PORT-02 edit bounds/version/isolation and stale-brief state. PORT-03 direct-sector/no-lookthrough label. PORT-04 unsupported returns/correlations empty correctly. PORT-05 frontier unavailable/flag off doesn't break P0 page. PORT-06 keyboard editing and horizontal table scroll. Baseline Mateo's controversy nee must remain visible.
