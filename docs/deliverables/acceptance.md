# Acceptance report

Environment and exact base revision are in the [machine report](evidence/report.json); the `workingTree` field records uncommitted T16 changes. Command: `UV_CACHE_DIR=/tmp/aplomb-uv-cache uv run python scripts/qa_smoke.py --output .artifacts/t16-2026-11-15`. Snapshot: `snap-20261113-starter`, as-of 2026-11-12, CAD, full window and unedited defaults except explicit funding/edit tests. This session checks actual code and data without credentials. Logs are retained under [evidence](evidence/integration.log).

**Release readiness: blocked.** A passing offline gate does not satisfy browser journeys or a current deployed cloud decision. “Passed” below means the entire stated row is covered by executed deterministic assertions. “Blocked” means supporting tests passed, but some required evidence remains absent. No failed test is relabelled as blocked.

The retained integration gate passed 742 Python tests, 155 web tests and 6 infrastructure tests, plus generated-contract drift, lint, strict TypeScript, specification checks, numeric controls and CDK synthesis. The normal static build passed. The separate [harness regressions](evidence/harness-tests.log) passed three tests proving command failures/timeouts fail the gate and earlier reports cannot be overwritten. This session did not record a video or publish a release.

| ID | Tier | Status | Executed evidence and remaining work |
|---|---|---|---|
| AT-01 | P0 | passed | HTTP probe and actual browser form verify 6 conflict/1 tension/1 pass, 16.96% volatility, 25.31% drawdown, 21.88% loss and 6.0-point boundary. Composed scripted-model decision also passes. This proves deterministic preview; current live-agent execution remains AT-12. |
| AT-02 | P0 | passed | HTTP probe and actual browser Compare verify Robert/Amira both conflict at 25 points; Robert conflict/Amira tension at 10; distinct checks and boundaries 6.0/11.0. |
| AT-03 | P0 | passed | Rules scenario test verifies every financial check passes, Energy conflicts and controversy is `nee`; optimizer and HTTP probe verify boundary zero. |
| AT-04 | P0 | passed | Rules baseline tests verify Robert/Amira compatible and Mateo insufficient with no financial conflict; HTTP probe verifies all three verdicts. |
| AT-05 | P0 | passed | Rules and HTTP probe confirm crypto exclusion conflict for Robert +5 BTC-USD. |
| AT-06 | P0 | blocked | Quant asset table tests reproduce TSLA/SPY/AGG returns in USD/CAD and fact metadata; independent reference scripts pass. Visibility of dates/source/window/currency in browser pending. |
| AT-07 | P0 | blocked | Composed run resolves every numeric segment to same-run verified facts over HTTP; ledger and web rendering tests pass. Clicking every figure and inspecting drawers pending. |
| AT-08 | P0 | passed | Ledger hostile-text suite covers missing IDs, EN/FR numeric literals, false comparisons, unsupported quotes/claims, one rewrite and fail-closed signing; workflow audit/review regressions pass with explicit model test doubles. Real-provider behavior is separate evidence. |
| AT-09 | P0 | blocked | Composed worker tests persist real code steps/durations and a failed model step without fabricated completions. Current real-model UI failure capture pending. |
| AT-10 | P0 | blocked | API ownership, parser refusal, repository isolation and mandatory disclaimer tests pass; static and hydrated Chrome checks verify disclaimers on all nine app pages at three widths. Complete execution-refusal and isolation browser journey pending. |
| AT-11 | P0 | blocked | Datastore/passport tests cover calendar, FX, adjustments, CNQ, revisions and survivorship. Sources browser inspection pending. |
| AT-12 | P0 | blocked | Earlier genuine AWS capture exists at a different revision and sourced snapshot. Fresh decision initiated from deployed UI with correlated current release/model/S3/DynamoDB/CloudWatch evidence pending. |
| AT-13 | P1 | blocked | Temporal gate, future-data perturbation and composed replay/reveal tests pass; signed parent is unchanged. Current deployed replay/UI capture pending. |
| AT-14 | P1 | blocked | Ledger sabotage helper proves parent immutability and honest detection; integrated sabotage service/run UI is unavailable. Keep feature disabled. |
| AT-15 | P1 | blocked | World tests and composed HTTP event brief verify sourced geography, holding links and impact not established. Browser pin/feed/brief journey pending. |
| AT-16 | P1 | blocked | Draft inference, unresolved fields, profile versions/409 and form helpers pass. Browser confirmation/save/stale-edit flow pending. |
| AT-17 | P1 | blocked | Goal/scenario/frontier unit tests and composed decision enforce bounded candidates and illustrative frontier. Browser goal/frontier journey pending. |
| AT-18 | P0 | passed | Quant funding tests cover all equations, held targets, ordered donor depletion, no negatives and insufficiency. HTTP probe checks NVDA new-money denominator and CAD total value. |
| AT-19 | P0 | passed | Repository concurrency tests cover atomic idempotency, duplicate claim, terminal-write/cancel races; worker tests cover cancellation during model work; composed HTTP verifies same key returns same run. |
| AT-20 | P0 | blocked | Web tests prove latest-response guard and stale-brief calculation; backend threshold/version controls pass. Rapid real-browser slider/edit journey pending. |

## Where to inspect assertions

- Numeric controls and boundaries: [rules](../../backend/tests/unit/rules/test_rules.py), [quant](../../backend/tests/unit/quant/test_quant.py), [optimizer](../../backend/tests/unit/optimizer/test_optimizer.py), [HTTP probe](../../scripts/qa_smoke.py).
- Full composed workflow, failed step, fact resolution, replay/reveal, goal: [composition tests](../../backend/tests/integration/test_run_composition.py). Only the model is scripted.
- Hostile explanations: [ledger suite](../../backend/tests/ledger/test_ledger.py), [review regressions](../../backend/tests/integration/test_review_regressions.py).
- Isolation and races: [repositories](../../backend/tests/api/test_repositories.py), [execution](../../backend/tests/agents/test_execution.py), [profiles](../../backend/tests/unit/profiles/test_profiles.py).
- UI logic: [web tests](../../web/tests/web-logic.test.ts), [T15 API tests](../../web/tests/t15-api.test.ts). These are not browser E2E tests.

## Nonfunctional gates

See [HTTP measurements](evidence/http-controls.json) for all 20 warm reads and 20 warm checks, their median/p95/max and target comparisons. Reads rotate personas; checks rotate Robert/Amira/Mateo, TSLA/CNQ/crypto and sizes. Timing includes local request handling and serialization; construction and first calls are reported separately. These are measurements on this machine, not production service objectives. Parser latency, genuine current-release run duration and Lambda cold starts remain unmeasured.

The [static export record](evidence/report.json) lists direct HTTP routes and asset count. It does not establish S3/CloudFront delivery for the current release. The headful browser connector could not start without an X server; headless Chrome was then used successfully. The [browser record](evidence/browser.json) contains 27 page/viewport checks (nine app pages at 375, 768 and 1440 px), loaded personas, hydration, visible disclaimers, no page-level horizontal overflow, Tab focus and no uncaught JavaScript exceptions. It also records actual form-driven Robert/Amira comparison results at 25 and 10 points. Screenshots show [mobile World Explorer](evidence/browser-375-world-explorer.png), [desktop baseline](evidence/browser-1440-decision-desk.png) and [TSLA preview](evidence/browser-decision-25.png).

Command: `UV_CACHE_DIR=/tmp/aplomb-uv-cache uv run python tests/run_browser_smoke.py .artifacts/t16-browser-release`. The API served temporary starter data, no model configuration, no fixture adapter and no persistent demo state. This is a browser smoke pass, not a full screen-reader/keyboard audit or a completed signed-brief journey. An earlier attempt lost its independently launched static/Chrome processes; its [failure record](evidence/browser-interrupted.json) is retained. The managed runner keeps service lifetimes together. One existing Mangum event-loop deprecation warning is retained in the Python log.

## Cloud evidence boundary

The [prior AWS artifact](../../infra/evidence/aws-architecture-2026-11-14.json) records base revision `b0e6a15`, deployment revision `b0e6a15+aws-architecture`, snapshot `snap-20261114-sourced`, real model usage, versioned S3 objects, DynamoDB readback, CloudWatch metrics and browser observations. Its decision run `run_01M7EAZEQVQ0F6BW4FBC8FY6DP` has a recorded duration of about 37.2 seconds (one historical sample). It does not prove that today's checkout is deployed or that starter-snapshot numeric expectations apply to sourced data. Keep both version labels visible in the demo. No new cloud call was made by this gate.
