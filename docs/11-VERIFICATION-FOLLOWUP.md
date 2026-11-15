# 11 — Completion of the independent review

**Checked:** 2026-11-15, approximately 00:00–00:07 EST. Repository base: `f46c453`. This completes the verification work interrupted in Claude's session after the instruction “check all”. It does not implement the review's proposed product changes.

**Verdict: ship the demonstrated P0 scope with fixes; keep goal requests disabled.** The repository gate and both browser sweeps pass. A previously unreported goal edge case fails the workflow, and the brief-quality defects in [the original review](09-INDEPENDENT-REVIEW.md) remain. Release acceptance is still incomplete: several P1 paths have only scripted-model evidence, CI authentication is unavailable, and the submission video is not recorded.

## Evidence and boundaries

| Check | Result | Evidence |
|---|---|---|
| Full repository gate | Passed: 742 Python tests, 155 web tests, 6 infrastructure tests, generated contracts, lint, TypeScript, spec links and CDK synth | [Gate log](evidence/review-continuation/check.log) |
| Normal static export | Passed, all application routes generated | [Build log](evidence/review-continuation/build.log) |
| Local browser sweep | 27/27 page/viewport checks and both persona comparisons passed | [Local report](evidence/review-continuation/browser-isolated/browser.json) |
| Deployed browser sweep | 27/27 page/viewport checks and both persona comparisons passed | [Deployed report](evidence/review-continuation/browser-isolated/live/browser.json) |
| Provenance drawers and keyboard | All 20 numeric chips in a signed local test brief opened a drawer with a method; Tab remained in the drawer, Escape closed it, focus returned | [Interaction report](evidence/review-continuation/browser-isolated/extra.json) |
| Profile form | Invalid blank submission rejected; copied fictional profile saved; concurrent update accepted; stale form then displayed the conflict and retained unsaved fields | [Follow-up interactions](evidence/review-continuation/followup/followup.json) |
| Rapid size changes | After 25 → 1 → 20 → 2 → 10, final size and preview matched Robert's 10-point case: 2 conflicts, 2 tensions, 4 fit | [Interaction report](evidence/review-continuation/browser-isolated/extra.json) |
| Historical replay and reveal | Started from the local form at 2025-02-19; signed result completed; later outcomes stayed hidden until Reveal was clicked; UI re-read the parent and confirmed its signed hash unchanged | [Follow-up interactions](evidence/review-continuation/followup/followup.json) |
| Goal runs | No-target AI goals returned three scenarios in EN and FR. A target already met by the portfolio failed in both languages | [Interaction report](evidence/review-continuation/browser-isolated/extra.json), root cause below |
| French screens | All nine local application pages rendered with `html lang="fr"`; localized numeric formatting observed | [Interaction/accessibility report](evidence/review-continuation/browser-isolated/extra.json) |
| Automated accessibility | axe-core 4.10.3 found zero automatic WCAG A/AA violations on nine local French and nine deployed English pages. Contrast checks remained incomplete | [Interaction/accessibility report](evidence/review-continuation/browser-isolated/extra.json) |
| Cloud persistence | Earlier live Robert run independently matched in DynamoDB, CloudWatch and versioned S3 checkpoint storage | [Cloud readback](evidence/review-continuation/cloud.json) |
| Current release | CloudFront identifies `f46c453`; live API flags remain as in the original review | [Deployment capture](evidence/review-continuation/deployment.json) |
| GitHub CI | Unverified: GitHub connector returned `401 Bad credentials`; unauthenticated repository API returned 404 | Workflow files inspected; neither response proves CI success or repository visibility |

The sweeps covered Home, Portfolio, Profiles, Decision Desk, Evidence & Audit, Sources, World Explorer, Time Machine and Agents & System at 375, 768 and 1440 px. They checked hydration, loaded personas, disclaimer, page overflow, Tab focus and uncaught JavaScript exceptions. Disabled deployed routes passed by rendering their unavailable state; this does not establish that their underlying features work in production. Robert/Amira comparisons at 25 points were conflict/conflict; at 10 points, conflict/tension.

All newly created runs and profiles were local and disposable. The local application used the real datastore, optimizer, rules and auditor with the explicitly labelled `scripted-test-gateway (no LLM)`. No AWS configuration, feature flag, deployment or production profile was changed. Existing local services were left running.

## New defect: a goal already met becomes an internal failure

Reproduction: Amira, decision run, theme `ai`, `targetExposurePct: 15`, all other goal constraints empty, starter snapshot. Both `lang: en` and `lang: fr` fail after the risk step with public error code `internal`. The same goal with `targetExposurePct: null` succeeds with three candidates.

The direct backend reproduction exposed this exception:

```text
RuntimeError: No goal candidate: The portfolio already reaches the target exposure; no candidate is needed.
```

[The candidate search](../backend/aplomb/optimizer/scenarios.py) deliberately returns no scenarios when the target is already reached. [The workflow adapter](../backend/aplomb/optimizer/services.py) treats every empty candidate set as an exception. This is a normal product outcome, not a failed calculation, and is unrelated to French.

**Recommended fix before enabling goals:** represent “already meets target” and “no feasible candidate” explicitly. Return the unchanged portfolio with its measured exposure and current rule assessment, or introduce a typed no-change outcome through the contracts and UI. Do not invent a trade to satisfy the current non-empty scenario requirement. Add composed-workflow coverage for both empty-candidate reasons; the existing integration case uses no target and misses this edge case. Goal requests remain off in the live API.

**Fixed after the review:** an empty candidate set now yields one no-change scenario (`sc_goal_no_change`, no move, current rule assessment, measured exposure, the reason in EN/FR) instead of an internal failure. `backend/tests/integration/test_run_composition.py` covers the already-met target in EN and FR and a goal no eligible asset can serve (Robert, `BTC-USD`). Goal requests stay off in the live API until the backend is redeployed and one real-model goal run passes there.

## What the recovered session had already checked

The final tool results from Claude's interrupted session were recovered into [a sanitized evidence file](evidence/review-continuation/recovered-claude-checks.json). They are prior observations, not new executions:

- Live parser refused an execution request (`trade_execution`) and an open-ended stock recommendation (`advice_request`). Another session received 404 for the reviewed run; a request without a session received 422.
- All 20 distinct fact references in the live brief resolved. The subsequent probe correctly classified them as 8 computed, 4 scenario, 1 input and 7 assumption facts, all verified. The first probe's `allVerified: false` incorrectly assumed that every fact must be computed; it is not a product defect.
- Live baselines, Robert's crypto exclusion, 10-point persona comparison, Sources and Portfolio were checked. Sources displayed 15 dataset passports and nine trap records; Frontier returned its historical-illustration limitations.
- A local scripted replay withheld post-cutoff rows, had no fact period ending after the cutoff, rejected an unsupported early date, and kept the parent result unchanged after reveal.
- A local scripted event brief succeeded and explicitly stated that financial impact was not established. It contained no research evidence. This verifies composition and honesty, not the quality of a real model's event analysis.

## Cloud evidence now captured

Read-only AWS calls discovered the `Aplomb` stack and independently retrieved the original live run `run_01M7ERBNQM5DVKQ01XX4DKRJ4D`:

- DynamoDB: succeeded, revision 38, 69 fact children, six completed step children, plus META and STATE (77 records total).
- CloudWatch: the same run ID, worker version `1`, runtime signature, 34,344.8 ms, 36,547 input tokens and 2,672 output tokens. DynamoDB records three model calls and zero tool calls.
- S3: the STATE pointer resolves to a versioned 352,982-byte checkpoint. `HeadObject` length and SHA-256 metadata match the pointer. The sourced snapshot manifest's object version also matches the earlier deployment capture. This is metadata/readback correlation, not a new full-byte integrity audit.
- Published worker `1` is active; its code hash matches `$LATEST`. Reserved concurrency remains 2. No load test was performed.

The same persisted audit confirms the two A02 strikes and zero rewrites reported in §4.1 of the original review. The CloudFront revision now identifies a later frontend release (`f46c453`) than the one used to start that run (`7c4c457`); the worker's published code hash is recorded separately. Do not describe this as a fresh decision launched from the latest frontend.

## Acceptance rows: remaining evidence

This table supplements the frozen [delivery acceptance report](deliverables/acceptance.md), rather than relabelling partial rows as passed.

| Rows | What this continuation adds | What remains |
|---|---|---|
| AT-01, AT-02, AT-04, AT-05 | Current deployed preview/comparison plus recovered live baseline and exclusion probes | No new deterministic discrepancy found |
| AT-03, AT-18, AT-19 | Full existing automated gate re-run | Specialized browser funding, cancellation and duplicate-submission journeys not exhaustively repeated |
| AT-06, AT-07 | All 20 chips in a local signed test brief clicked; methods visible; recovered live references resolved | Exhaustive live proof drawers and asset USD/CAD table journey |
| AT-08 | Offline hostile-text coverage passes; cloud readback confirms live false-positive A02 strikes | Fix and real-provider verification of the brief defect |
| AT-09 | Persisted live six-step trace and local honest goal failure | Controlled real-provider failure journey |
| AT-10 | Disclaimers on every route/viewport; recovered live refusal/isolation probes; local drawer focus cycle | Full refusal/isolation journey through visible controls; human screen-reader review |
| AT-11 | Live Sources page and dataset/trap content; full datastore tests | No new source-quality certification is implied |
| AT-12 | Original live UI run now correlated with DynamoDB, S3 and CloudWatch | Fresh latest-release UI decision if the release gate requires that exact frontend revision |
| AT-13 | Local form-driven replay/reveal plus recovered date-gating evidence | Deployed real-model replay; feature remains off |
| AT-14 | Live AWS sabotage (release `42e2023`): all three modes inserted and caught in EN and FR; parent unchanged; other session 404 | Human review of the result card on a visible screen |
| AT-15 | World pages hydrate locally; recovered local event-brief composition | Pin/feed/brief journey with a real model on AWS; feature remains off |
| AT-16 | Local validation, copy/save, stale-edit UI verified | Agent-draft confirmation journey with a real model |
| AT-17 | Local signed goals with no target; Portfolio/Frontier pages load | Fix already-met goal, test no-feasible outcome, real-model goal/frontier journey |
| AT-20 | Rapid input changes settle on the correct final preview; stale profile fields retained after a conflict | Throttled out-of-order responses and signed-brief/rule-edit journey in browser |

Visual regression is **inconclusive**: screenshots were captured but no approved visual baseline comparison was performed. Automated accessibility is not a screen-reader audit; contrast has manual-review items. Core Web Vitals and judging-window concurrency were not measured. French generated prose remains unverified: the scripted gateway writes English prose even when its result language is `fr`, so its successful run proves wiring and formatting only.

## Priority after verification

1. Fix the live brief: preserve the stress and compatible-size explanation, provide profile context, and remove repeated limitations. Prefer a trusted window-label token for years; do not broadly allow numeric prose or weaken relation checks.
2. Handle normal empty-candidate goal outcomes before enabling the feature. Use an unchanged scenario or a typed result, with a visible reason.
3. Make planner actions and step summaries reflect executed work; keep fixed controls clearly identified.
4. Run real-model acceptance only for the features chosen to ship, capture the exact release and AWS trace, then record the video and finish the jury-facing deliverables.

These are outstanding implementation and submission tasks. This continuation changes review documents and retains verification evidence; it does not claim those fixes have shipped.
