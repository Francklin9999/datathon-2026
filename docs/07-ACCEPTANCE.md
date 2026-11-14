# 07 — Acceptance contract

Run deterministic checks against `snap-20261113-starter`, CAD, full window, unedited defaults unless a row says otherwise. Numeric expectations come from [controls](../contracts/controls.md). T16 collects evidence; each track executes its own checks. “Planned” is not “passed.”

| ID | Tier | Input / action | Required outcome | Owners |
|---|---|---|---|---|
| AT-01 | P0 | Robert +25 TSLA, pro-rata | conflict; 6 conflicts/1 tension/1 pass among counted checks; vol 16.96%, positive drawdown 25.31%, stress loss 21.88%; boundary 6.0 points | T05–07/T14 |
| AT-02 | P0 | Compare Robert/Amira +25 TSLA, then +10 | At 25 both conflict with different checks and caps; at 10 Robert conflict, Amira tension; boundaries 6.0 and 11.0 pro-rata | T06/T07/T14 |
| AT-03 | P0 | Mateo +10 CNQ.TO | financial checks pass; Energy exclusion conflict; controversy nee; size boundary 0 | T06/T09 |
| AT-04 | P0 | Default baselines with no controversy dataset | Robert/Amira compatible; Mateo insufficient, all financial checks pass, controversy nee | T06 |
| AT-05 | P0 | Robert +5 BTC-USD | crypto exclusion conflict despite any favorable historical metric | T06 |
| AT-06 | P0 | Recompute TSLA/SPY/AGG calendar 2022 in USD and CAD | Match printed controls; actual dates, source, window and currency visible | T05/T04 |
| AT-07 | P0 | Click every numeric segment in a completed brief | Resolve same-run verified fact, method, source, inputs, period, currency; no dangling references | T10/T14 |
| AT-08 | P0 | Inject missing ID, bare digits, false comparison, unsupported claim | Correct sentence struck/repaired; one rewrite max for missing structure; no signed unsafe text | T10/T08 |
| AT-09 | P0 | Real run and a tool failure | Actual steps/tools/durations persist; failure remains visible; no invented completed steps | T03/T08/T14 |
| AT-10 | P0 | All pages; execution-like request; session isolation | Disclaimer always present, execution refused, no order tool, another session's runs/custom profiles inaccessible | T03/T08/T13 |
| AT-11 | P0 | Open Sources and known dataset traps | Passports cover all used data; calendar/FX/adjustments/CNQ/revisions/survivorship honestly handled or disclosed | T04/T13 |
| AT-12 | P0 | Cloud decision from deployed UI | Genuine Bedrock call, Lambda metrics, S3 data version, DynamoDB result and correlated logs captured | T02/T16 |
| AT-13 | P1 | Historical run before future rows/releases, then reveal | No future input/reference in signed decision; gate counts match; reveal separate and labelled; current-vintage limits visible | T04/T12/T15 |
| AT-14 | P1 | Sabotage completed run | Immutable parent; marked child; lie, failed check and final repair/strike visible; do not claim caught if not detected | T10/T14 |
| AT-15 | P1 | Event pin → exposure → brief | Source/date/location precision; cited holding link; no invented impact; feed works without globe | T11/T15 |
| AT-16 | P1 | Form/text custom profile, save, stale edit | Inferred fields explained; unsupported fields unresolved; confirmation before persistence; version mismatch 409 | T06/T08/T13 |
| AT-17 | P1 | Goal and frontier | <=8 assets screened, <=3 distinct goal candidates, <=6 scenarios; best fit based on constraints/exposure, historical MV only illustrative | T07/T08 |
| AT-18 | P0 | New-money and existing-holding moves | Exact weight equations, no negative donors, denominator and currency explicit | T05 |
| AT-19 | P0 | Duplicate worker delivery, idempotent create and concurrent cancellation | Single claimed execution; same idempotency key/body returns same run; terminal state never overwritten | T03/T08 |
| AT-20 | P0 | Slider rapidly moved and threshold edited | Code-only checks; old response cannot overwrite latest; brief marked stale until rerun; no false model progress | T14 |

## Nonfunctional gates

Warm read targets <500 ms, `/check` <1500 ms, parser <10 s; analyze runs aim <90 s with a hard 180 s worker budget. Report measurements and sample size, including cold starts separately. Static export must load on nested routes from S3/CloudFront. Keyboard operation and readable mobile layouts cover all P0 journeys. A clean clone must reproduce deterministic checks without credentials.

T16 writes an actual pass/fail/blocked report under `docs/deliverables/` during implementation. Record command/revision/date/environment and artifacts for each tested row. The present specification pack does not claim any application acceptance row has passed.
