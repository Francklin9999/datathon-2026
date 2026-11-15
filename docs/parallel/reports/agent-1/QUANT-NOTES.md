# Portfolio comparison and expanded quantitative models

These are deterministic, session-scoped numerical interfaces in `backend/aplomb/quant/expanded_api.py`, registered by `make_router(session)`. All source-dependent portfolio figures use the existing temporal gate, source receipts and pinned data version. No LLM, order, SQL or user-authored code is used.

## Common-currency portfolio comparison

`POST /v1/portfolios/compare` accepts `{profiles:[{profileId,version},...], currency, window, asOf?, knowledgeMode?}` (2–5 distinct session-owned profiles, versions required). Rates are target units per original profile-currency unit through the pinned CAD bridge. Exact source rows, timestamps, dataset passports, rate direction and converted capital are returned; if FX is unavailable, converted capital and modeled target-currency positions remain null/omitted rather than being mislabeled. The profile's existing capital is not silently repriced into an unavailable currency.

For `window.code=full`, all profiles use the longest common continuous master-calendar segment where every underlying asset and FX conversion is observed; `windowApplied` and `sampleRule` explicitly disclose truncation. Named/custom horizons retain exactly their requested window; any missing price/FX withholds affected returns rather than labeling a shorter history as one year or filling prices. `sameSample` is true only when all observations share exact dates and all portfolio returns are available. Each portfolio owns its own fact ledger, so fact IDs must not be combined without remapping. Weights are constant and rebalanced each return period; adjusted close includes provider corporate actions. Private appraisals, tax, costs and real transactions are excluded.

## Sourced covariance

`POST /v1/risk/covariance` takes `{profileId,version,window?,asOf?,knowledgeMode?}`. Returns the symmetric sample covariance of aligned fractional daily returns, with `ddof=1`, actual dates and number of return observations, and a local source receipt fact (`sourceFactIds`/`facts`) carrying a hash of actual gated price/FX levels and source passports. Missing history returns `dailyCovariance:null` and an explicit reason. Zero variance is a valid covariance of zero; non-finite/overflow, misaligned calendars and short samples are rejected or withheld. The matrix is in fractional return squared per day, not percent squared or annualized.

## Liquidity scenario

`POST /v1/profiles/{id}/liquidity-analysis` takes `{version,asOf,through,targetWithdrawal?,assumptions:[{ticker,saleDates,dailyCapacity,halfSpreadBps,impactBps,source,asOf}]}`. Dates are explicit user/source-supplied dates, not an inferred trading calendar; capacity is maximum gross sale value per given date in profile reporting currency. For each sale `net=gross*(1-(halfSpreadBps+impactBps)/10000)`; remaining position value carries to the next specified day. Inputs are scenario assumptions, not verified market depth, orders, market impact estimates or executable prices. A target can be covered by the explicitly modeled subset; if it is not and any nonzero holding lacks an assumption, full-portfolio feasibility is unknown (`totalNetProceeds:null`). Taxes, costs other than stated spread/impact, market movement, settlement and correlated selling are excluded. Private appraisals are excluded from traded-position calculations.

## Nested fund decomposition

`POST /v1/risk/nested-fund-look-through` takes `{asOf,historical,positions:{ISIN:fraction},knownFunds:[ISIN],snapshots:[{fundIsin,holdingsDate,evidence,constituents:[{isin,weight}]}],maxDepth?}`. Checksummed exact ISINs only; snapshots and evidence are caller-supplied and not independently verified. Fractional values are recursively apportioned with no scaling. Direct and indirect terminal security values, attributed source IDs/dates, paths and unresolved mass are returned separately. Missing known-fund snapshots, undisclosed amounts, cyclic fund structures, eight-level depth and 10,000-node complexity limits remain explicitly unresolved. A caller must identify known fund IDs; non-declared, non-snapshot positions remain direct securities. Historical reads require capture retrieval by cutoff. Actual issuer holdings/crosswalk acquisition belongs to Agent 2; synthetic fixture calculations do not establish real acquisition.

## Active-portfolio factor exposure

`POST /v1/profiles/{id}/factor-exposure` requires `{version,window?,asOf?,knowledgeMode?,names,...}` plus exactly one of:

- `source:{origin:'user'|'imported'|'source',description,currency,availableAt,evidence?}` and `factors:[{start,end,riskFree,factors:{name:fraction}}]`; `origin:'source'` requires dated evidence, but caller-provided source/currency remains unverified; or
- `captureId:'capture_...'` referencing the session-owned French US-factor capture. The application injects the existing financial capture store as `app.state.financial_capture_store`. The capture must have configured source-use permission, matching session ownership, unchanged raw and normalized SHA, validated French ZIP with exact normalized row reconciliation, and correct capture/knowledge availability. US factors are modeled in USD, so a non-USD reporting profile must instead supply verified same-currency factors; no guessed FX factor conversion occurs.

The portfolio's actual snapshot-derived adjusted-close returns and stated weights are used. Factor observations align by exact start/end date, with no missing return fill. For a captured daily factor, a matching end date is accepted only if its prior *provider* observation date equals the master return's start date, preventing hidden US-only/Canadian-holiday bridging. At least 30 aligned non-overlapping periods and a non-singular sample are required. Returns include alpha/beta/residual sample statistics, source provenance, date range, exclusions and a local portfolio input receipt. This is descriptive OLS, not a causal claim or forecast.

## Position quantities and modeled values

`POST /v1/profiles/{id}/position-details` takes `{version,quantities?:[{ticker,quantity,asOf,origin,source}]}`. It displays request-supplied or profile-saved quantity provenance when present; no quantity is manufactured when absent. Modeled position values remain weight × profile capital, never silently computed from assumed unit price. Quantities from user/imported records are unverified and temporary overrides are not saved. The separate profile model work handles quantity metadata persistence and clearing/retaining evidence for account transfers.

## Verification and boundaries

`UV_CACHE_DIR=/tmp/aplomb-agent-1-uv-cache uv run pytest backend/tests/unit/quant/test_expanded.py backend/tests/unit/quant/test_exposures.py -q` — **22 passed**. Independent references include Python `statistics.covariance`, hand-checked nested conservation/cycle/partial results, two-day liquidation cash flows and first-shortfall logic, and a 1.5-beta analytical regression. HTTP exercises actual profile service, version/session isolation, CAD-to-USD direction/rate, source fact ownership and absent-FX non-fabrication. A synthetic ZIP verifies captured factor parsing, exact temporal/period alignment, source reparse/hash reconciliation and historical withholding; no live provider or actual factor capture is claimed. `ruff` passes on all four new quantitative modules and focused test.

Cross-agent production dependencies: current financial factors require provider permission and successful actual capture; issuer identities/holdings and exact security crosswalks remain Agent 2-owned. No paid or login/API-key source was activated. Real portfolio risk for private or illiquid positions requires explicit returns, sale constraints and investor/source valuation history; none are fabricated. Settlement, tax, impact calibration, fund leverage/derivatives and joint optimizer workflows remain limited to their documented inputs.
