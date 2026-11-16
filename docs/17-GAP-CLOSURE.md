# Remaining-gap closure — 2026-11-15

> Historical team-process record. The review pages, agent briefs and evidence files it names were removed from the repository; they remain in git history.

This report supersedes the earlier “uncommitted/undeployed” summary for source status: the first hardening batch was committed and pushed as `4cd6ab2`. The changes described here are a subsequent local batch. The user explicitly left AWS deployment with their teammate. No AWS code/configuration or routing was changed by this audit.

| Gap | Change and evidence | Remaining release requirement |
|---|---|---|
| Custom dates return 422 in AWS | Backend custom-window implementation and selected-period fact/chart regression tests already exist in pushed source. Exact failing requests are in the release-owner handoff. | Teammate deploys matching backend and repeats both overview/performance queries. Local code cannot repair an old Lambda artifact without deployment. |
| Report quality | Home/event briefs now get one optional repair for struck assertions, followed by the same complete audit. Repair receives verified facts, language and policy checks. Tests prove one retry only and disclose any surviving strikes. | Paired release and production report review. No claim of universally clean prose. |
| Real Home brief | Current local composition using genuine Bedrock via official AWS MCP completed with one rewrite, zero final strikes and an executive summary plus three ranked evidence-linked focus cards. | Local snapshot and no Guardrail in this smoke; not the deployed artifact. Evidence. |
| Sabotage workflow | Contract 1.1.0 replaces the impossible signed “before audit” shape with an explicit unaudited draft. An authorized child forks the frozen parent ledger, calls the configured writer and auditor, and reports `caught` only for an actually struck designated attempt. Already-audited parent templates remain the base. | Deploy frontend/backend together and validate configured Guardrail and writer behavior before enabling feature. |
| Real sabotage smoke | First genuine test exposed malformed writer token output and failed safely; fixed workflow then succeeded with actual writer/reviewer, immutable parent and other-session 404. The writer produced no injected sentence: `caught=false` is correct. | This proves workflow execution and honest non-attempt reporting, not a real-model successful lie/catch. Fixed evidence; earlier failed evidence retained. |
| SEC acquisition | Existing official endpoints use bounded transport and explicit unavailable states; CIK, filing, period, units and provenance checks are implemented/tested. Companyfacts/submissions and targeted companyconcept were tried. | SEC returned HTTP 403. The deployment operator needs an accepted source access path/contact/network; no proxy or block bypass was used. |
| GDELT acquisition | DOC search now uses existing ResearchService cache and provenance, with 90-day/20-record bounds. Validates JSON/timestamps/links; never maps publisher country to event location. | Live requests timed out or returned 429, including one-record request. Source-backed GDELT summaries cannot be claimed without actual acquisition. |
| Official event evidence | Existing research policy permits exact reviewed Bank of Canada/Federal Reserve/Statistics Canada hosts with terms. Genuine Bank of Canada capture registered a verified same-run excerpt. | Not a substitute labeled as SEC or GDELT. Model interpretations and holding links still require their own evidence. |
| Recorded demonstration | [5:36 subtitled live recording](deliverables/demo/aplomb-live-subtitled.webm), 1280×720, real deployed decision, evidence, actual execution, replay/reveal and official event. Complete ffmpeg decode passed; revealed outcomes inspected. | Silent, no spoken narration. Sabotage is explicitly shown as not deployed. Recording identifies its actual release, which differs from current local source. |

## What failed and was fixed during real-model validation

The existing MCP smoke bridge used 2,048 output tokens while the runtime uses 4,096. A real writer response hit `max_tokens`, and the run failed honestly. The bridge now matches the runtime output budget and counts cache-token usage using the existing provider accounting helper. This does not change production inference settings. A fresh Home run then completed cleanly after one audit repair.

The first real sabotage writer attempted to rewrite the entire parent with malformed tokens; its repair still omitted required policy citations, so A12 rejected signing. The corrected flow accepts only the specifically designated test assertion and reconstructs the already-audited parent base from typed segments. The entire child draft is independently audited again. It never invents an attempt when the model declines.

## Contract migration and release owner

Version 1.1.0 changes the previously disabled sabotage result only; all ordinary decision/portfolio/event/replay contracts remain intact. Generated schema and TypeScript are updated together. Existing deployed sabotage was disabled and has no stored successful results to migrate. The release owner must still deploy paired artifacts; an older Evidence page cannot display the new unaudited draft shape correctly.

Retain published API/worker version 2 and old frontend artifacts/configuration before the release. Use the existing CDK/package/CI tooling. Keep SEC/GDELT unavailable when calls fail. Keep sabotage off until the deployed real workflow, persistence, session boundaries and configured Guardrail pass. No extra AWS service is required.

## Final follow-up controls

Additional scripted integration tests cover worker crashes at both writer and auditor boundaries, all three attack modes, immutable parent content and session isolation. Child language must match the original report; a mismatched request returns 409 instead of mixing languages. Inherited sentence IDs are prefixed so a parent named `S-INJECTED` cannot be mistaken for a new attack. The UI differentiates no attempted assertion from attempted-but-not-caught. The real-model evidence predates this identifier-prefix-only change, which was verified by focused regression tests.

The first 1.1 gate passed 780 Python tests, 16 subtests, 177 web tests and six infrastructure tests; a later full gate/package covers recovery and identifier changes. No configured AWS Guardrail was applied in the local genuine Bedrock probes. Deployed application runs shown in the video use the deployed configuration.

## Final verification and release artifacts

The final full gate passed **784 Python tests, 16 subtests, 177 web tests and six infrastructure tests**, plus generated contracts, lint, strict TypeScript, specification/control validation and CDK synthesis. Four warnings remain (Mangum event-loop deprecation and test-time Pydantic serializer warnings); no tests were skipped to obtain this result. The static web build and pinned AWS Lambda Python 3.12 x86_64 container import check passed. A final small UI wording correction accurately labels the combined unaudited draft as preserved parent content plus a model-produced attempted assertion; TypeScript/web tests were rerun.

Gate log, build log, package log and artifact metadata are retained. The prepared Lambda archive is `infra/.build/gap-closure/lambda.zip`. This is local source based on `4cd6ab2` plus the reviewed gap-closure diff; no production deployment or feature-flag change occurred. The deployment owner must commit the reviewed source, set its full release SHA and deploy paired frontend/backend artifacts, then repeat the custom-date and sabotage checks. Source/provider access remains the only additional external acquisition blocker; no clean SEC/GDELT live journey is claimed.

## Deployment update received before commit

The teammate committed deployment evidence in `cd20a9b`: API/worker version 3 runs `a85beea`, including custom date windows. A fresh independent HTTP recheck now returned **200** from both Robert overview and performance for `2024-01-01` through `2025-01-01`, echoing the custom window. This supersedes the earlier 422 blocker; readback evidence. The subsequent 1.1.0 sabotage/report-quality batch described here still requires its paired deployment. Update: that batch was deployed as release `f098339` (API and worker version 5, contract 1.1.0) with `sabotage_demo` still off; [evidence](../infra/evidence/release-f098339-2026-11-15.json).
