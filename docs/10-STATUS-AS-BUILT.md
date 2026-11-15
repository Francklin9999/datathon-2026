# 10 — Status as built

**As of:** Sunday 2026-11-15, 00:07 EST. Initial review: `7c4c457`; continuation and current CloudFront release: `f46c453`. Backend worker version and code hash are captured separately in the [verification follow-up](11-VERIFICATION-FOLLOWUP.md). Backend release `9f10301` (API and worker version 2, 2026-11-15 06:28 UTC) enabled the flags marked below; see [its evidence](../infra/evidence/release-9f10301-2026-11-15.json).
**Purpose:** one page that says what exists, where it runs, and what a judge can actually open. It replaces guessing from the original plan. Findings and recommendations are in the [independent review](09-INDEPENDENT-REVIEW.md).

## How to read the columns

| Column | Meaning | Source |
|---|---|---|
| Built | Code exists in the repository | Repository contents and the track handoffs in this folder |
| Tested offline | The track handoffs and the draft acceptance report say the automated suite covers it. The suite itself passes at this commit (742 Python, 155 web, 6 infrastructure tests); the review did not map individual tests to features | `npm run check`, run during the review; handoffs in this folder |
| Deployed | Its feature flag is on in the deployed API. Features without a flag are marked from what was seen on the deployed site | `GET /v1/meta` re-read during the continuation; flags unchanged |
| Seen live | Exercised in a browser against the deployed stack during the review | Review session |

"Seen live: no" means only that the review did not exercise it, not that it is broken.

## 1. Product features

| Feature | Decision | Built | Tested offline | Deployed | Seen live |
|---|---|---|---|---|---|
| Three default personas with fictional portfolios and derived rules | D-17 | yes | yes | yes | yes |
| Home: metrics, history chart, allocation, plan health | — | yes | yes | yes | yes |
| Home: AI portfolio brief, cached | D-37 | yes | yes (scripted model) | yes | yes, real run completed |
| Portfolio page: holdings, rules, risk, frontier chart | D-19 | yes | yes | yes | page rendered in deployed sweep; frontier API checked in recovered session |
| Decision Desk: free-text request parsed and confirmed | D-13 | yes | yes (scripted model) | yes | yes |
| Decision Desk: specific move, deterministic preview and slider | D-13 | yes | yes | yes | yes |
| Decision Desk: funding comparison with a recommended option | D-15 | yes | yes | yes | yes |
| Decision Desk: largest size before the first conflict | D-16 a | yes | yes | yes | yes |
| Decision Desk: audited agent run with timeline | D-06, D-22 | yes | yes (scripted model) | yes | yes, 34.3 s |
| Decision Desk: compare two profiles | — | yes | yes | yes | yes, deployed browser: 25-point and 10-point comparisons |
| Decision Desk: hypothetical alternatives on conflict | D-16 c | optimizer function exists | yes | not produced in the live run | no |
| Decision Desk: clarifying question to the user | D-16 d | yes | yes | no flag; part of the decision workflow, not confirmed live | no |
| Decision Desk: exposure goals with candidate scenarios | D-13, D-14 | yes; already-met target returns a no-change scenario (`af8d4d0`) | yes, both empty-candidate reasons in EN/FR | yes (release `9f10301`) | yes, real-model run: Amira 15% AI target, French, no-change scenario signed |
| Evidence & Audit: brief with audit markings, fact drawers | D-20 | yes | yes | yes | yes |
| Sabotage demonstration | D-21 | helpers only; no run kind | helper tests | **no** | no |
| Agents & System page | D-22 | yes | yes | yes | yes |
| Sources page with dataset passports and traps | — | yes | yes | yes | yes, recovered content inspection and current deployed sweep |
| Profile creator, form and free-text draft | D-17 | yes | yes (scripted model) | yes | deployed page loads; local form validation, copy/save and stale-edit verified; real-model draft journey pending |
| World Explorer: globe, event feed, exposure by country | D-29 to D-32 | yes | yes | yes (release `9f10301`) | yes: globe and portfolio-matching feed on CloudFront, 1440 and 375 px |
| World Explorer: AI event brief | D-31 | yes | yes (scripted model) | yes (release `9f10301`) | local API composition with scripted model, recovered session |
| World layers: natural hazards (USGS) | D-32 | yes | yes | yes (release `9f10301`) | API `/world/hazards` answered; layer listed on the page |
| World layers: emissions facilities, wildfires | D-32 | no | — | no | — |
| Time Machine: date-gated run and reveal | D-28 | yes | yes (scripted model) | yes (release `9f10301`) | yes, real-model replay at 2025-02-19 signed, prices gated at the cutoff, reveal to 2025-12-31 |
| French interface and briefs | D-36 | yes | interface and formatting verified locally; generated French prose unverified | yes (release `9f10301`) | French interface on CloudFront; one real-model French goal run |
| Hype meter (page views) | D-33, A-19 | rule exists; no data provider | rule tests | rule shows "no data loaded" | yes, as "no data" |
| On-demand tickers | D-24 | yes, local data directory only (Tiingo) | adapter tests | **no** | no |
| Wide universe beyond the starter assets | D-23 | no | — | 31 assets | — |
| Research in runs (EDGAR, GDELT, web fetch) | D-26, D-33 | tools exist | captured-transport tests | **no** | no |
| Open-web browsing | D-33 | no provider | — | no | — |

"Scripted model" means the test replaces the language model with `backend/tests/integration/_scripted.py`; the code controls and the auditor are the real ones.

## 2. Platform

| Area | State | Source |
|---|---|---|
| Web hosting | Static Next.js export on S3 behind CloudFront, revision `f46c453` | [deployment capture](evidence/review-continuation/deployment.json) |
| API | API Gateway and Lambda, FastAPI | `/v1/meta` answered in 0.22 s |
| Runs | Asynchronous worker Lambda, steps persisted, polled by the page | Live run observed |
| Models | `us.openai.gpt-6-astra` (planner, audit review) and `us.anthropic.claude-opus-5-5` (writer) through Bedrock. The parser's model is not recorded on a run step; the README says it shares the writer's model | `/v1/meta` and the step records of the live run |
| Guardrail | Applied on the live run, action "none" | Audit report of the live run |
| Data | Snapshot `snap-20261114-sourced` (starter data plus real Canadian CPI release dates and sourced theme tags) | `/v1/meta`, [source register](../data/SOURCES.md) |
| Storage | DynamoDB for profiles, runs and cache; S3 for snapshots and large checkpoints | [AWS architecture](AWS-ARCHITECTURE.md) (not inspected in the console during the review) |
| Deployment | CDK stack; site deployed by GitHub Actions through OIDC | Repository history |
| Continuous integration | Workflows present; full local gate passes | GitHub connector returned 401; hosted CI status unverified |

## 3. Acceptance rows against live evidence

Rows are defined in the [acceptance contract](07-ACCEPTANCE.md). This table adds only what the review observed on the deployed stack. Note that the deployed snapshot is `snap-20261114-sourced`, while the acceptance contract names the starter snapshot; the figures observed were identical at the printed precision.

| Row | Observed on the deployed stack |
|---|---|
| AT-01 | Yes through the Decision Desk: conflict, 6/1/1, volatility 16.96%, stress 21.88%, drawdown 25.31%, boundary 6.0 |
| AT-02 | Partly: Amira's `/check` at 25 points matches (3 conflicts, 2 tensions, boundary 11). The compare panel itself and the 10-point case were not exercised |
| AT-03 | Yes through `/check`: Energy exclusion conflict, controversy "not enough evidence", boundary 0 |
| AT-04 | Robert's baseline only: fits the rules, 8 fit, 3 information |
| AT-07 | Recovered live references all resolve; continuation clicked all 20 numeric chips in a local signed test brief. Exhaustive live drawers remain pending |
| AT-08 | Partly, and unintentionally: a real run had two sentences struck by A02; see the review, §4.1 |
| AT-09 | Real run: yes, actual steps, models, durations and token counts persisted. Tool failure: not exercised |
| AT-10 | Disclaimer visible on the two pages screenshotted (Home, Decision Desk). Other pages, refusal of an execution request and session isolation not exercised |
| AT-12 | A genuine decision was started from the deployed interface and completed (run `run_01M7ERBNQM5DVKQ01XX4DKRJ4D`). Matching CloudWatch, S3 checkpoint metadata and DynamoDB records are now [captured](evidence/review-continuation/cloud.json). This remains the original UI run, not a new run from frontend revision `f46c453` |
| AT-13 to AT-17 | Local replay/reveal and profile form verified; goals expose an already-met-target failure. Real-model P1 journeys remain pending; see [follow-up matrix](11-VERIFICATION-FOLLOWUP.md) |

## 4. Deliverables

| Deliverable (brief p.15–16) | State |
|---|---|
| Prototype | Deployed and working for the P0 journeys |
| Code repository with README | Present; README has install, check and run instructions. A clean-clone install was not performed in the review |
| Demonstration video, about five minutes | Not recorded |
| Technical documentation | Draft committed in `f46c453`: [technical note](deliverables/technical.md). Written for engineers; see the review, §6 |
| One-pager | Draft committed in `f46c453`: [one-pager](deliverables/one-pager.md). See the review, §6 |
| Acceptance report | Committed in `f46c453`: [acceptance report](deliverables/acceptance.md), based on offline checks; it marks release readiness "blocked" pending browser and cloud evidence |

## 5. Dates

From the team's logistics (not in an organizer file in this repository): code and repository Sunday 2026-11-15 23:59 EST; AWS accounts close Monday 2026-11-16 13:59 EST; video, technical documentation and one-pager Monday 14:00 EST; finals Friday 2026-11-20.

At the time of writing that leaves about 24 hours for code and about 38 hours of AWS access (rounded; refreshed just after midnight). The video and every AWS screenshot must be captured inside that second window.

## 6. Keeping this page true

Update the "Deployed" column from `/v1/meta` after each deployment, and the "Seen live" column only after someone has watched the feature work on the deployed stack. Do not mark a feature live from a passing test.

## 7. Verification continuation

The [completed verification report](11-VERIFICATION-FOLLOWUP.md) supersedes the original review’s list of unchecked pages. Both browser sweeps passed 27 page/viewport checks and two persona comparisons. Local drawer keyboard behavior, profile validation/stale edits, rapid preview changes and replay/reveal were exercised. Automated accessibility found no violations but left contrast checks incomplete; no screen-reader or approved visual-baseline review is claimed. The goal edge case and the live brief defect remain unfixed.
