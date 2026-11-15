# Release hardening — 2026-11-15

Baseline: `9f103013e390533860b33b9ebea40750178a9ce9`. No tracked edits initially; existing untracked `.playwright-mcp/` preserved. Track owners below are responsibility areas from docs/04-TRACKS.md, not claims of active teammate ownership. No evidence of active edits was found in the initial Git state.

## Initial implementation inventory

“Prior” means recorded historical evidence, not re-execution in this audit. Pending means not yet verified in this audit. AWS flags were read directly from /v1/meta; frontend deployment manifest matches baseline. Backend release differs.

| Feature | Exists in code | Tested locally | Enabled in AWS | Functional end to end | Owner | Issue |
|---|---|---|---|---|---|---|
| Home | yes | suite pending | yes | prior live | Web | P1 hierarchy / brief repetition |
| Persona selection | yes | suite pending | yes | prior live | Web/API | switching requires recheck |
| Portfolio holdings | yes | suite pending | yes | prior live | Quant/Web | historical labels present |
| Portfolio analytics | yes | suite pending | yes | prior live | Quant | independently check synthetic math |
| Policy rules | yes | suite pending | yes | prior live | Rules | no full ETF look-through |
| Decision Desk | yes | suite pending | yes | prior live | Agents/Web | current release smoke pending |
| Position resizing | yes: positive percentage-point increases | suite pending | yes | prior live | Optimizer | decrease unsupported; no target-weight semantics |
| Agent execution | yes | scripted suite pending | yes | prior live | Agents | current smoke pending |
| Bedrock research | adapters/tools | captured transports | no open web | not verified | Research | feature/provider configuration |
| Analyst brief | yes | scripted suite pending | yes | prior live | Agents/Web | P1 static cards, repeated facts |
| Evidence drawer | yes | prior keyboard test | yes | prior live | Ledger/Web | current browser recheck pending |
| Claims Ledger | yes | suite pending | yes | prior live | Ledger | scoped references implemented |
| Independent auditor | code + model | suite pending | yes | prior live | Ledger | bounded checks, no universal guarantee |
| Sabotage tests | helpers + result contract | helper tests | no | no workflow provider | Ledger/Agents | P1 demo scene missing |
| Time Machine | yes | scripted suite pending | no | local prior only | Replay | disabled deployment |
| Historical reveal | yes | suite pending | no | local prior only | Replay | disabled deployment |
| World Explorer | yes | suite pending | no | local prior only | World/Web | disabled deployment |
| Event summarization | yes | scripted suite pending | no | local prior only | World/Agents | real model unverified |
| Sources | yes | suite pending | yes | prior live | Data/Web | no live price claim |
| Data passports | yes | suite pending | yes | prior live | Data | Tiingo publication local-only |
| Agents & System | yes | suite pending | yes | prior live | Web | backend SHA not surfaced coherently |
| Theme switching | yes | prior browser | yes | pending | Web | desktop/mobile recheck |
| Language switching | yes | prior local French | no | local only | Web/Agents | disabled per cut decision |
| Deployment | CDK + site CI | gate pending | yes | manifest verified | Infra | P0 backend/frontend release divergence |
| Monitoring | logs/dashboard/alarms | infra tests pending | yes | readback pending | Infra | no load/recovery guarantee |

## Integration and changes made

The user requested the latest repository during this audit. Fetched and fast-forwarded from `9f103013` to `e27e0b62668752adafcdcee6b572d6d0a42a3b3c`, preserving all hardening edits. Incoming commits added custom date ranges and a configurable dashboard. Home conflicts were resolved in favor of keeping that dashboard; the deleted KpiTiles component was not resurrected. A Git stash and `/tmp/aplomb-hardening-before-pull.patch` retain the pre-integration work. No commits were pushed by this audit. `.env` remains ignored and holds the user-authorized Tiingo key; no key is in this report.

| Files | Behavior and reason | Validation |
|---|---|---|
| `backend/aplomb/agents/workflow.py`, `optimizer/services.py` | Three deterministic investigation priorities use policy severity, horizon, concentration and fixed-income evidence. Baseline fixed-income weight is registered before writing. Duration and ETF overlap remain questions, not inferred measurements. Ranking is explicitly a code heuristic, not a recommendation or verified market claim. Writer receives horizon and executive-summary instructions. | Three-persona composed runs; same-run verified fact references; lint |
| `backend/aplomb/ledger/audit.py` | Identical whitespace-normalized templates within a section are removed before review/signing. Repeated IDs remain invalid. This is a source-level fix; semantic or cross-section repetition can still occur. | Ledger regression and full suite |
| `backend/aplomb/profiles/service.py`, `web/src/features/home/KeyFigures.tsx` | A selected-window return is recorded through the existing extensible fact-ID map and displayed alongside value, volatility and drawdown. Fixed and custom return periods are checked against the chart. No shared wire shape changed. | Fixed-window and custom-window chart/fact tests |
| `web/src/features/home/HomePage.tsx`, `web/src/lib/brief.ts` | Brief appears before holdings in the default configurable layout, has one executive summary, three evidence-linked focus cards, relevant next-page links, and expandable details. A fully struck summary falls back to surviving facts. Overview errors do not prevent cached brief access. | Typecheck, summary regression, build, local browser sweep |
| `backend/aplomb/quant/metrics.py` | Rejects mismatched/non-finite inputs rather than silently truncating weighted returns. Normal calculation conventions unchanged. | Synthetic malformed-input regression; quant/replay/ledger tests |
| `backend/aplomb/research/adapters.py`, `research/tools.py` | Cached news rejects unsafe/undated/out-of-window/duplicate entries; first-seen date is distinguished from original publication. SEC response CIK, explicit currency units, filing dates, accession and historical periods are validated. | 29 research tests; bounded live probes reported below |
| `web/src/features/world/WorldPanels.tsx`, `features/decision/DecisionDeskPage.tsx`, `lib/world.ts` | Event → related holding → Decision Desk preserves ticker/persona/event/source-run identifiers in URL and existing originalText, with strict client grammar. Persona switch resets form. Context is untrusted, not a signed exposure claim. | 21 targeted tests, context round trip, actual local browser handoff |
| `web/src/lib/ui/scope.ts` | Rejects impossible calendar dates that JavaScript otherwise rolls into another month. | Leap-year/date regression |
| `backend/tests/ledger/test_sabotage_controlled.py` | Controlled fabricated-number, false-comparison and unsupported-interpretation attempts are struck. Review callbacks are explicitly scripted. | Three tests; no live sabotage claim |

Detailed connector status: [external inventory](13-EXTERNAL-DATA-INVENTORY.md). Quantitative conclusions and limits: [trust audit](14-TRUST-AUDIT.md). Handoff behavior: [World-to-Decision notes](15-WORLD-DECISION-HANDOFF.md).

## Commands and observed results

- `UV_CACHE_DIR=/tmp/aplomb-uv-cache uv sync --locked`: passed. Default cache was read-only; no dependency changes.
- `npm ci --cache /tmp/aplomb-npm-cache`: passed; zero reported web dependency vulnerabilities.
- `npm --prefix infra ci --cache /tmp/aplomb-npm-cache`: passed; npm reported two moderate infrastructure dependency vulnerabilities. No forced dependency upgrade was applied.
- Baseline `UV_CACHE_DIR=/tmp/aplomb-uv-cache npm run check`: 747 Python, 155 web, 6 infrastructure tests passed plus lint, types, generated contracts, spec/control checks and synthesis.
- First integrated gate: 762 Python tests, 16 subtests, 174 web tests and 6 infra tests passed. Later targeted additions: 176 web tests passed; custom-window and sabotage tests passed (10 tests). Final gate results are recorded below when complete.
- `npm run build:web`: passed; ten application/not-found static routes listed by Next. Build is not deployment.
- Existing headless Playwright/Chrome: nine local routes × five widths (390/768/1024/1280/1440), 45 successful loads; no uncaught page exceptions or sampled document overflow. Local API used starter snapshot. Full keyboard, screen-reader, contrast and console verification are not claimed.
- Live Tiingo adapter: AAPL returned nine USD observations for 2026-11-02 through 2026-11-12. Key stays in ignored `.env`. No new Tiingo data was published to AWS or represented as live observations.
- Live SEC: 403. GDELT: timed out at eight seconds. Neither is declared operational.

Evidence: [gate](evidence/release-hardening/check.log), [build](evidence/release-hardening/build.log), [browser](evidence/release-hardening/browser.json), [live API run](evidence/release-hardening/live-smoke.json), [cloud readback](evidence/release-hardening/cloud-readback.json).

## Deployment status

Initial public frontend manifest identified `9f103013`; a final re-read identified `e27e0b62668752adafcdcee6b572d6d0a42a3b3c`, built at 2026-11-15T06:31:58Z. That upstream publication happened independently of this audit. The current hardening edits are uncommitted and **not deployed**. [Final frontend manifest](evidence/release-hardening/deployment-final.json).

CloudFormation reports `UPDATE_COMPLETE`, stack revision `b0e6a15+architecture-audit-20261114`. API/worker code SHA-256 is `qGTy22/uscGZGaW/izrqc1Mrr/9YvqHS0aofOyFRcoQ=`; the API pins worker version `1`. Stack revision does not prove a matching source tree. The backend does not publish a coherent Git SHA in `/meta`.

Enabled flags: profile_creator, guardrails, frontier_chart. Disabled: bilingual, world_explorer, world_layer_facilities, world_layer_hazards, time_machine, goal_requests, sabotage_demo, research_open_web, on_demand_tickers. Snapshot `snap-20261114-sourced`, data through 2026-11-12; 31 starter assets. Recheck `/meta` before a presentation.

New genuine AWS run: `run_01M7EY8RQY5YHB02XJKEGRTW5Y`, Robert +25 percentage points TSLA funded pro rata. It succeeded in CloudWatch at 34,751.6 ms with 32,551 input and 2,278 output tokens. Planner/reviewer used GPT-6 Astra; writer used Claude Opus 5.5. Guardrail applied, action none. Audit passed with three sentences struck; that is qualified output, not a clean universal verification. Another session received 404. DynamoDB independently contained 77 run records. This exercises API Gateway/Lambda, Bedrock, Guardrail, persisted run retrieval and CloudWatch; it does not verify new working-tree code, autonomous research tools or full S3 checkpoint bytes. Exhaustive IAM simulation, deployment-role review, concurrency/load and new S3 integrity checks remain incomplete.

## Release and rollback boundaries

Do not publish this frontend alone: the new selected-window return needs its paired backend implementation. The upstream custom-window frontend likewise needs a matching backend. Preserve the last known-good frontend artifact and its object-version report, published API/worker version 1, pinned snapshot, feature flags and previous complete CloudFormation template before any release. Existing [site rollback procedure](../infra/deploy/README.md) re-publishes a retained artifact and invalidates CloudFront; no buckets need deletion. Backend rollback must restore the previous published API invocation target and worker configuration together, retaining the old versions and IAM. Rollback was documented, not executed or rehearsed in this audit. No infrastructure service or production flag was added.

## Remaining risks, ranked

1. **P0 release consistency:** a backend release with immutable source/artifact identity and live validation is still required. New local improvements are not production evidence; custom-window support must be confirmed against AWS before advertising it as operational.
2. **P1 external intelligence:** SEC/GDELT failed live acquisition; ALFRED vintages, environmental registries, PortWatch and FIRMS are not integrated. Tiingo public redistribution rights are not established by possession of a token. Official [Tiingo documentation](https://www.tiingo.com/documentation/) distinguishes personal/internal access from distribution. Keep the token server-side and external research disabled in replay.
3. **P1 disabled journeys:** real-model replay/reveal, event summaries, goal edge cases and sabotage child-run execution need release validation. Controlled sabotage tests are not a substitute for a live writer/auditor demo.
4. **P1 trust scope:** ranking is a transparent heuristic using severity/horizon, not the full proposed exposure/evidence-quality scoring model. Focus prose is code-owned; numeric evidence resolves to the ledger. Same-section exact dedupe does not guarantee no semantic repetition. Fallback executive facts do not guarantee executive-summary quality from a real model.
5. **P1 lineage:** event context stored in originalText is explicitly untrusted. Backend validation of event-to-asset/source-run relationships needs a reviewed typed contract. Relevance never establishes impact.
6. **P1 release operations:** full new IAM, S3 bytes, CI execution status, recovery and capacity evidence remain incomplete. Session capability is not user authentication. Do not claim identity security.
7. **P2 presentation:** professional visual review, contrast, complete keyboard/screen-reader checks and final video/one-pager review remain. Local browser load checks do not certify these.

## Five-minute demonstration and recovery

Use the deployed supported scope: (1) Robert Home and fictional/current-weight historical labels; (2) TSLA +25 percentage points, explicit pro-rata funding; (3) deterministic policy conflicts and mathematically compatible boundary; (4) real execution timeline; (5) evidence drawer and audit markings; (6) Sources passports and Agents & System. The new live API smoke proves that core workflow, not every browser action in a single recorded take.

Amira's +25-point TSLA preview returned 3 conflicts/2 tensions/2 passes. Robert returned 6 conflicts/1 tension/1 pass. Mateo +25 CNQ.TO returned 2 conflicts/7 passes and one evidence gap; the gap is not a clean ESG rating. These are current deployed snapshot results, not investment recommendations.

Local World → official Federal Reserve event → AGG → Decision Desk navigation is demonstrable; local composed replay/reveal is test-covered. Exclude World, Time Machine and sabotage from a claimed live AWS demonstration while their flags are off. A complete requested seven-scene demo and recording are **not ready**. Retain non-sensitive evidence in this folder; there is no new offline application replay mode.

Highest-impact next action: publish and identify a coherent reviewed backend/frontend release with rollback artifacts, then repeat the real Robert workflow and validate custom windows before enabling optional features. The full requested definition of done has **not** been met.

## Continuation — latest observations supersede earlier deployment status

The user confirmed a teammate actively owns AWS deployment. This audit therefore performs **no production deployment or configuration changes**. The teammate's release changed `/meta` during this session. World Explorer, hazards, Time Machine, goals and bilingual UI are now enabled; sabotage, open-web research, on-demand tickers and facilities remain off. The stack is `UPDATE_COMPLETE`, identifies revision `9f10301`, pins worker version **2**, and the worker code hash is `fXgpQWhFGgZdl8UgJ50zS0NV4gfuSnBhcphein7gNKQ=`. Frontend still identifies `e27e0b62668752adafcdcee6b572d6d0a42a3b3c`. Earlier disabled-feature statements in this report describe the initial observation only. See [current meta](evidence/release-hardening/meta-current.json).

**Confirmed P0 mismatch:** custom dashboard windows exist in the public frontend, but deployed Robert overview and performance both return HTTP 422 for `window=custom&start=2024-01-01&end=2025-01-01`. The local backend supports this query and has tests. Release owner must deploy compatible backend before claiming custom dates are working. Do not undo the teammate's frontend work.

Additional genuine live checks:

- Robert replay run `run_01M7EYY7494GJHJBZQDE6Y84W7`, cutoff 2023-06-30: succeeded with real models. All 69 checked facts had no availability date or period end after cutoff. Reveal twice produced equal outcomes, original response was unchanged, and another session received 404. This verifies tool-level constraints and immutability, not absence of model hindsight or source revisions.
- Amira's already-met AI target: succeeded with `sc_goal_no_change`, no moves. Audit passed with strikes. [Sanitized optional-run evidence](evidence/release-hardening/live-optional.json).
- Deployed World Explorer at 390 and 1440 px: no sampled overflow or page errors. A real Federal Reserve event brief completed with a signed report, but four fact sentences and two assumption sentences were struck. The original source returned HTTP 200. Holdings associations were shared-theme or listing-country proxies, not documented causal exposure. Our new persistent handoff is local only. [World handoff report](15-WORLD-DECISION-HANDOFF.md).

Additional local work:

- Official Bank of Canada, Federal Reserve Board and Statistics Canada exact hosts are reviewed in the existing research policy. A genuine Bank of Canada source excerpt was registered and verified in one ledger. GDELT and SEC acquisition remain unavailable; no replacement feed was fabricated.
- Tiingo fetched ORCL through a disposable local HTTP composition, published a versioned snapshot, exposed its passport and completed `/check` against that same version; unknown ticker returned 404. No public Tiingo data deployment occurred.
- GDELT discovery now rejects local/non-public literal addresses, non-HTTPS/credentialed/nonstandard-port links, invalid full timestamps, and tracking-only duplicate URLs. Discovery does not prove an article's location, publication date or correctness.
- Auditor cross-checks simple directional wording against the typed relation, including reversed operand extraction. Five controlled sabotage cases cover the attack paths; unsupported qualitative interpretations still need the model reviewer.
- Agents & System displays validated frontend manifest identity and reads optional `X-Aplomb-Build` from API health. New backend `APLOMB_BUILD_REVISION` accepts only a full Git SHA; API exposes it through CORS without changing JSON contracts. CDK sets it only when the release revision is a full SHA. The build revision participates in runtime pinning when supplied. It is not configured in the current deployed artifact and must remain shown as unavailable there.
- Home explicitly distinguishes full-portfolio/global-window brief context from dashboard holdings filters and custom date ranges. No filtered/custom brief is implied.

The current new code remains local and uncommitted. A native Lambda artifact was built with the existing packaging script and its imports checked in the pinned Python 3.12 AWS image. It must be refreshed after the final edits and associated with an actual committed source revision by the deployment owner. A passing package is not a deployed release. Existing infrastructure, snapshot and prior published versions remain untouched by this audit.

Updated demonstration scope: real AWS Decision → signed audit/evidence and real replay/reveal now have current live evidence. World map/source/event brief also executed, with material audit removals visible. The persistent World → holding → Decision context is verified locally, not deployed. Full recorded five-minute narrative, real sabotage writer child-run, new intelligent Home prose with real model, and final submission video remain unfinished. The highest-impact next step remains the **paired release**, specifically closing the deployed custom-window 422 mismatch with the teammate who owns AWS.

## Final local validation for this continuation

The last full `UV_CACHE_DIR=/tmp/aplomb-uv-cache npm run check` passed: **773 Python tests, 16 subtests, 177 web tests, 6 infrastructure tests**, generated contracts, lint, strict TypeScript, spec/control validation and CDK synthesis. One existing Mangum event-loop deprecation warning remains. `npm run build:web` passed. `UV_CACHE_DIR=/tmp/aplomb-uv-cache bash infra/scripts/package-backend.sh` passed, including imports inside the pinned AWS Python 3.12 x86_64 runtime container. Final logs replace the intermediate gate/build logs in this evidence directory.

A local release archive and patch are prepared in `infra/.build/release-hardening/`: `lambda.zip`, `source.patch`, `manifest.json`. [Artifact digest evidence](evidence/release-hardening/artifact.json) records the dirty source baseline and hashes; it deliberately does not pretend the artifact is the clean base commit. The deployment owner must review and commit the intended source, set the full release identity, retain rollback versions and perform a paired release. Source work, tests and artifacts are concrete and reviewable; production publication remains with the teammate as requested.

The [release-owner handoff](16-RELEASE-OWNER-HANDOFF.md) gives the exact P0 reproduction, packaging commands, release verification and rollback boundaries. The user-authorized Tiingo key remains in ignored `.env` with mode 0600 and is absent from the tracked diff and Lambda packaging paths. No credentials are included in the release report or artifact metadata.
