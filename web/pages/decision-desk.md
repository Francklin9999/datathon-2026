# Decision Desk — request, compare and test

**Owner:** T14. **Tier:** P0 moves; goals/clarifications P1. Route `/decision-desk/?runId=...`.

## Request flow

Free-text field (1–600 chars) calls `/requests/parse`; present interpretation, missing fields, warnings/refusal and a structured form for user confirmation. Manual form works without model: ticker search, added percentage points, explicit funding or automatic comparison and named donors. Show distinction between added size and target weight/new-money denominator. Unknown ticker may be fetched only when on-demand flag enabled and accepted by API.

Preview `/check` is deterministic. “Analyze evidence” creates a decision run with confirmed request/lang/window and originalText, then polls. User can navigate away/return using runId. Waiting_input renders question and options only when backend actually requests it; submitting answers resumes same run. Refusals explain simulation scope and preserve manual form.

## Results

Verdict with full rule status counts and unresolved-evidence indicator, before/after weights/metrics, failed/tension checks, boundary size, funding comparison, hypothetical scenarios, audited brief and genuine timeline. Respect selectedScenarioId and distinguish requested scenario from best-fit alternative. Funding recommendation is labelled a hypothetical comparison, not an action button. Source chips open the correct run's ledger.

Slider debounces ~250 ms, sends `/check` only, cancels/ignores older requests. On changing input/rules/window show preview with current values and mark previous brief “Written for [original request]; rerun to update explanation.” No model calls or fictitious agent progress for deterministic previews. At size=0, preview baseline with move=null rather than invalid zero-size move.

## Compare and goals

Compare two profiles side by side via `/check/batch`, same exact ticker/size/funding/window. Explain different thresholds, holdings and missing evidence. Do not promise different headlines at 25 TSLA: both Robert/Amira conflict. Provide 10-point comparison for conflict vs tension.

Goal editor (flagged) confirms themes/classes/tickers, target exposure and extra loss/vol bounds. Display up to three distinct candidates and best fit; fewer is an honest supported outcome. Do not loosen existing rules for a goal. Show rebalance only when actually computed and validated. Every scenario displays funding/turnover/assumptions and its own fact namespace/variant.

## Acceptance

DESK-01 AT-01–03 exact contracts. DESK-02 missing/refused parser and manual fallback. DESK-03 stale request race and zero baseline. DESK-04 boundary wording/tension/evidence gap. DESK-05 batch partial error preserves successful pane. DESK-06 refresh restores run and terminal full response. DESK-07 clear distinction preview/run/scenario facts. DESK-08 keyboard slider/form/mobile rule table. All P0 controls remain usable when optional goal flags are off.
