# Profile, policy and account implementation notes

Implemented in `backend/aplomb/profiles`, `backend/aplomb/rules`, additive model/API contracts, and narrow routes in `backend/aplomb/api/app.py`.

- Named accounts can be refreshed from their original native amount against the pinned current snapshot. An explicit `asOf` invokes the historical gate, including when it equals the observation cutoff; a later retrieval cannot enter a historical result. The old independently checked receipt is retained in `valuationHistory`, as it is after capital edits or transfers. Failed conversion and stale versions leave the profile unchanged. No synthetic FX rate is introduced.
- Transfers specify a reporting-currency amount and move a proportional slice of each source position to the destination, without an external cash flow. Both accounts retain positive balances and prior receipts; incompatible IDs, stale versions, non-finite values and excessive/full depletion are rejected. Aggregate holdings and value conserve the pre-transfer total. This transfers the traded modeled holdings only, not private assets.
- Private asset entries carry a user/imported source description, dated appraisal, liquidity notes and a separate current FX receipt. New appraisals preserve prior evidence. `GET /v1/profiles/{id}/account-valuations` adds their reporting values to traded account values without treating them as traded instruments. Returns, policy weights and risk still cover traded holdings only; the summary states this limitation and warns against entering the same asset in both sections. There is no sourced history, liquidity execution model, independent appraisal verification, or private risk estimate.
- Declarative custom caps/floors measure existing position, direct-sector, asset class, listing-country, quote-currency or known theme data through the same rule engine and fact ledger. Each carries user origin and runs in normal overview and decision checks; user text is not executable. Country and currency are proxies, and incomplete classifications produce insufficient evidence. Unknown topics, arbitrary user code, unrestricted comparator expressions, sector look-through, leverage and ESG scoring are not supported.
- Profile duplication retains policy origin. Context accepts arbitrary investor type text, explicit capacity/tolerance provenance, multiple dated horizons, goal dates, named liquidity/spending/liability requirements, themes, allocation targets and rebalancing preferences. Context round trips and version/session isolation use the existing profile engine. The target and rebalancing entries are preferences, not automatic transactions or enforced rules. The source of optional inputs can be recorded in `inputOrigins`; older records without metadata do not acquire fabricated origins. Regulatory origin is reserved and rejected absent a verified implementation.
- Goal scenarios report exact missing fields and retain goal origin in input facts; scenarios remain nominal assumptions, not forecasts. Calculations exclude inflation, taxes, fees and withdrawals. Cash-flow requirements require the separately documented numerical interface; profile entries alone do not establish feasibility.

## API interfaces

- `POST /v1/profiles/{id}/custom-rules`: `{version, dimension, key, operation: "cap"|"floor", threshold}`.
- `POST /v1/profiles/{id}/accounts/{accountId}/refresh`: `{version, asOf?}`.
- `POST /v1/profiles/{id}/accounts/{accountId}/transfer`: `{version, destinationAccountId, amountReporting}`.
- `POST /v1/profiles/{id}/accounts/{accountId}/private-assets`: `{version, assetId?, name, assetType, liquidityNotes, valuationDate, origin, sourceDescription, nativeCurrency, nativeValue}`. Omitting `assetId` creates a record; supplying it appends a valuation.
- `GET /v1/profiles/{id}/account-valuations`: additive account and aggregate valuation summary.
- `GET /v1/profiles/{id}/strategic-candidates`: deterministic candidates and local fact ledger; the orchestration owner must remap facts before claiming a reviewed run.

These additions require regenerating the shared schema/client mirrors, preserving the common contract version until integration. Two additional independently owned quantitative/data routers are registered in `api/app.py` using the existing session dependency.

## Validation and remaining work

`pytest backend/tests/unit/profiles backend/tests/unit/rules backend/tests/unit/optimizer`: 113 passed plus 16 subtests (before the final added private FX-failure assertion). Targeted Ruff passed on the changed profile, rules, contract, API and profile-test paths. HTTP tests exercise account creation, refresh, version rejection, session isolation and candidate response. Private valuation, retention, aggregate arithmetic, validation and unavailable-FX rollback are exercised at the service boundary.

Broader policy origin coverage and UI editing remain incomplete: origin metadata is optional for pre-existing core input fields, custom conditions cover only the enumerated numeric portfolio measurements, user-provided allocation targets are not yet compared to actual values, and illiquid values are intentionally excluded from market-risk calculations. These are implementation limitations, not external blockers. Additional HTTP/browser acceptance and complete gate results belong in the main handoff.
