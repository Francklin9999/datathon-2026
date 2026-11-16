# Global platform implementation — 2026-11-15

> Historical team-process record. The review pages, agent briefs and evidence files it names were removed from the repository; they remain in git history.

The later continuation execution record supersedes the currency, profile lifecycle, source and contract boundaries in the original batch below.

This is a **partial implementation of the full master specification**, not a declaration that
all 243 sources or the complete worldwide product are integrated. The owner requested the
largest complete implementation and made deployment conditional on completion of everything.
Accordingly, this batch changes source only; production remains unchanged.

## Latest live release (supersedes initial baseline below)

During this work the teammate deployed backend `cd20a9bb9e6201c1ce571f70e9cf9a3164c741e1`
and pushed documentation commit `d974f44`. At 07:46 UTC, independent AWS reads confirmed
UPDATE_COMPLETE, API/worker version 4, matching code hash
`b7wWoaxy8zAHJ+xTifwlIutORrRGZFM4heQnTIWQhT4=`, API Gateway routing to API :4 and API
dispatch targeting worker :4. Contract remains 1.0.0. The new source branch includes `d974f44`;
no teammate change was overwritten. The initial version-3 evidence is retained as history.
See latest direct AWS readback.

## Initial live baseline, read independently

At the initial read, CloudFormation stack Aplomb reported UPDATE_COMPLETE and Revision a85beea. Public `/v1/meta`
returns contract 1.0.0 and snap-20261114-sourced, with 31 instruments. World Explorer, hazards,
Time Machine, profile creator, goals, bilingual UI, frontier and Guardrails are enabled.
Sabotage, open-web research, on-demand tickers and facility layers are disabled.

API and worker published version 3 have matching code SHA-256
`nOEnmRCKo78XTBErVQt75LRnhLS/QwUSIxNn+nDAF8I=`. API physical function is
`Aplomb-ApiF70053CD-o5uvtMqYsPwc`; the worker is `Aplomb-worker`. A guessed API function name
failed during inspection; the physical name was then resolved through CloudFormation and read
successfully. Existing models and frozen Guardrail configuration were inspected, not changed.
There may be concurrent operator activity: always re-read routing, release and configuration
before a future deployment. Never replace the published release merely with local defaults.

## Implemented in this batch

| Area | Working behavior | Limits |
|---|---|---|
| Profiles | Optional country/type/language, multiple dated goals, risk-capacity and liquidity notes in typed contracts; UI adds country/type and objectives; save/copy/edit retains context | Fictional profiles; CAD/USD calculations remain; not a tax or liability engine |
| Personalization | Explicit objectives and context reach the portfolio writer as untrusted user input; nearest objective horizon affects deterministic focus priority | No invented goal feasibility, policy thresholds or regulatory duties |
| Portfolio accounts | Named accounts, switching, original Primary account, aggregation by position value, duplicate-security merging and optimistic versions; UI on Portfolio | 20 accounts/profile; 40 positions per analyzed portfolio; common reporting currency only; no arbitrary private asset valuations |
| Markets & Stocks | Search supported instruments; four quantitative security measurements; clickable fact evidence and source passports; Decision Desk entry | Supported snapshot universe, not universal exchange coverage; no invented financial statements |
| Risk Intelligence | Existing descriptive risk plus new daily historical VaR/ES and signed variance contributions with reproducible facts | Sample-specific; at least 100 daily returns for tails; undefined zero-variance shares; no forecasts |
| Worldwide directory | All 243 CSV/Markdown entries preserved; searchable source directory in Sources with category/access filters; deterministic generation/drift check | Candidate research remains separate from loaded dataset passports and integration status |
| World Explorer | NASA EONET v3 parser, bounded immutable capture, source hash and terms, new origin/filter/labels, updated world bundle and passports | 479 retained EONET events; point observations only; no guessed country, publication time, company exposure or financial effect |
| Compatibility | Contract 1.2.0 generated Python/JSON Schema/TypeScript together; prior data requires no profile migration | Paired release required; production 1.0.0 cannot serve the new routes |

EONET returned 500 records: 480 passed the point/location parser; 479 remain within the world
bundle's overall date window. The bundle contains 1,230 events total: 479 EONET, 83 official,
668 USGS. The earthquake-only hazard layer remains separately labeled. EONET geometry dates
are observations, not publication dates. The first source point is a display location for the
observation, not a complete storm/fire track. The bounded API result is not complete coverage.
See [NASA's v3 documentation](https://eonet.gsfc.nasa.gov/docs/v3).

The copied directory has 243 entries across nine categories; repeated providers in different
categories remain separate entries with stable category/name/URL-derived IDs. Being listed
never marks a provider integrated or grants public-display rights.

## Verification and evidence

Focused tests cover arbitrary context, multiple/fractional goal horizons, session separation,
profile persistence, account switching/aggregation/stale versions, security metrics and custom
windows, EONET locations and malformed records, exact discrete tail examples, variance
identities and risk claim references. The complete repository gate and static build are
recorded under global-platform evidence.

The static export builds successfully with the new Markets and Risk routes. Reproduce browser checks with `node scripts/global_browser_smoke.mjs` after starting the local API on 8001, the web app on 3001, and an isolated headless Chrome with remote debugging on 9224.

Browser checks use a separate Next output directory and isolated headless Chrome profile.
They cover Markets, Risk, Sources, Portfolio, Profiles and World Explorer; security selection
opens metrics; a 390-pixel viewport has no document overflow. HTTP smoke exercises the real
local composition (not fixtures), including account creation and aggregation. These checks
are not claims of production deployment or new real-model validation.

## Completion boundary

[Owner actions](19-OWNER-ACTIONS.md) records external access and decisions without asking
questions during unattended work. [Remaining engineering](20-GLOBAL-IMPLEMENTATION-BACKLOG.md)
records unfinished requirements, including work that needs no owner input. Those requirements
are not waived, renamed as completed, or represented by empty navigation pages. The previous
demo video describes its original deployed release and was not replaced by a misleading new
production demonstration.
