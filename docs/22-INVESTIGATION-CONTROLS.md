# Investor accounts and complete target allocations

This continues the full-specification implementation after `9c072b1`; it does not redefine the requested scope. Contract **1.4.0** requires a paired frontend/backend release. No deployment occurred.

## Implemented

Native account capital can be entered in any configured reporting currency. Account creation uses the pinned FX snapshot to convert that explicitly modeled capital into the investor's reporting currency. It retains native currency/value, reporting value, conversion rate, valuation date, dataset version, exact source rows and source passports. Selecting an account and aggregating accounts use the same reporting-currency engine; original native inputs remain inspectable.

The independent receipt checker re-reads the pinned source rows and verifies snapshot, cutoff, quote set, source version, source metadata, row identity, currency direction and multiplication. Same-currency identity conversion has no external quote checks. Tests inject an inverted rate, incorrect result, incorrect source quote and substituted source URL, and assert the precise failure. Duplicate profiles receive independent account IDs. Cross-session reads remain isolated. Explicit capital edits in reporting currency clear the obsolete native receipt; switching accounts preserves valid receipts. Combined values outside the supported finite range fail without persisting an invalid state.

Decision Desk now accepts a complete final target allocation through `POST /rebalance/check`. Final weights include all retained assets and sum to 100%; omitted holdings have zero target. Reductions, complete removals and increases are calculated at constant modeled capital. Before/after metrics, policy checks, changes and source-backed calculation facts share the same snapshot, reporting currency and analysis window. No profile or order is modified. Stale versions, duplicate holdings, unsupported instruments and invalid weight totals are rejected.

The target-allocation UI exposes the complete target form, before/after metrics, allocation changes, policy checks and calculation evidence. It clears results on input changes, disables edits while a request is pending, and resets its context when the investor/version/window changes. The pre-existing incremental-purchase workflow retains its original size and funding semantics.

## Limits preserved

Account FX is a fixed conversion of fictional user-entered capital. It does not infer live account balances, tax basis, fees, transfer activity or private-asset valuations. Native capital is not silently repriced on account selection. Complete target comparisons assume frictionless rebalancing; spreads, tax lots, transaction costs, market impact and liquidity need separate supported models.

The target comparison is deterministic. It does not claim that research agents or an independent model reviewer ran. Missing controversy evidence remains insufficient, including for Mateo. The signed agent workflow still uses the existing move/goal request contracts; a full target-allocation agent workflow remains engineering work.

## Verification

The full repository gate passed: **845 Python tests**, **16 subtests**, **180 web tests**, six infrastructure tests, generated-contract consistency and specification checks. The static export built. Eight real local HTTP checks exercised native currency conversion, aggregation, final-target analysis, fact references, unchanged profile state and error cases. Browser interaction checks created a JPY account through the form, rendered its sourced CAD receipt, aggregated accounts and rendered a final-target comparison. No JavaScript exceptions or mobile document overflow at 390 px were observed.

The first browser attempt exposed a harness input-selection/escaping problem: its simulated input appended to the initial allocation and inserted a literal backslash sequence. The UI correctly rejected that invalid allocation. The corrected harness selects the visible text and inserts actual line breaks; the successful run is retained. No application validation was weakened to pass the harness.

Evidence and command logs: [investigation controls](evidence/investigation-controls/verification.json). Earlier evidence remains historical. AWS credential renewal and the owner's full-completion deployment condition remain separate from this local engineering work.
