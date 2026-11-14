# Verification strategy and implementation gates

**Track:** T16 integrates; module owners implement relevant tests. [Acceptance matrix](../docs/07-ACCEPTANCE.md) is the release checklist; this file explains how to test it. Current repo has specs/reference scripts, not a working app test suite.

## Test layers

| Layer | Location planned | What it proves |
|---|---|---|
| Specification integrity | `scripts/check_specs.py` | Local links/files, fixture JSON integrity and reference consistency |
| Numeric controls | `contracts/controls/`, backend quant/optimizer/rules tests | Published calculations match immutable starter data |
| Pure units | `backend/tests/unit/` | Funding, rules, date gate, parser/auditor functions with no network |
| Contract | `backend/tests/contract/`, web validation | Pydantic/TS models validate canonical fixture/API examples |
| Integration | `backend/tests/integration/` | Services/repos/workflow using local fake transport/models |
| Browser | `web/tests/` | Forms/compare/slider/citations/polling/accessibility/static deep links |
| Live provider/AWS | separate opt-in smoke commands | Actual source adapters and cloud execution, with captured provenance |

T01 creates exact runnable CI commands only after manifests exist. CI deterministic jobs must not require credentials or network. Keep live tests opt-in and bounded; missing AWS access is reported blocked, never passed through a fixture. Do not regenerate price data in any test.

## Numeric oracle and synthetic edge cases

Use [control tables](../contracts/controls.md) and standard-library reference scripts as independent expected results. Compare full precision before display, at printed tolerances; drawdown control tables print negative decline but API expects positive magnitude. Check both currencies and own-calendar asset returns versus master-calendar portfolio stress.

Synthetic tests cover holidays/no prior FX, foreign cash, constant prices, missing observations, duplicate data, short histories, current holdings containing the move target, donor insufficiency, nonmonotone size scans, no feasible reference mix, exact threshold boundaries, baseline conflict and evidence-only insufficiency. Never loosen tolerances to hide a formula/calendar mismatch.

## Workflow and trust tests

Fake models emit valid plan/writer JSON and deliberately malformed/hostile variants. Assert mandatory controls cannot be bypassed, <=2 revise loops, <=1 rewrite, terminal immutability, duplicate async event handling, session isolation and idempotency races. Audit tests inject EN/FR digits/number words, unknown references, false comparisons, forged quotes, future facts, banned instructions and unsupported impact.

Perturb only future data and prove historical facts unchanged. Exercise missing real macro release/vintage and 2022 stress before year-end. Reveal must not mutate parent facts/hash/verdict. Source transport tests simulate redirects/private hosts/429/timeout/truncated passages and prompt injection. No source text may grant tool authority.

## Browser and performance tests

Use contract fixture mode for deterministic browser scenarios with persistent fixture banner. Test rapid slider/persona changes, partial batch errors, running-step updates, terminal full fetch, refresh restore, stale brief and disabled routes. Verify keyboard focus and text statuses at 375/768/1440 px; a globe feed alternative is required. Static-export build served as static files must support route refresh without a Next.js server.

Measure warm `/check` latency over a small documented sample (e.g. 20 checks with scenario mix), read latency and genuine run duration; record cold starts separately. Do not repeat expensive cloud runs just to improve a screenshot. A load/latency result records revision, environment, sample size and data version.

## Completion evidence

Each track supplies command/result and known limits. T16 maintains actual AT status, failing logs and artifact links under deliverables; specs are not a pass report. First live gate is real Robert decision plus S3/DynamoDB/Bedrock proof. Remaining P0 checks block submission readiness; P1 failures trigger D-02 decisions and truthful flags. Documentation-only handoff is complete when linked specs, examples and numeric reference commands validate; application implementation begins from this pack.
