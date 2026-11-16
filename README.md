# Aplomb — evidence before conviction

Current three-agent execution: [parallel launch instructions and assignments](docs/parallel/README.md). The prepared baseline is contract 1.4.0; no parallel worker is started automatically.

Global-platform expansion: [profiles/accounts, markets, risk and EONET implementation](docs/18-GLOBAL-PLATFORM.md), [owner actions](docs/19-OWNER-ACTIONS.md), and [remaining full-spec engineering](docs/20-GLOBAL-IMPLEMENTATION-BACKLOG.md). This local expansion is not deployed; the complete worldwide specification is not yet fulfilled.

Latest gap closure: [implemented fixes, real-model tests and recorded demonstration](docs/17-GAP-CLOSURE.md). Deployment remains with the team AWS operator; SEC/GDELT source access is still an external blocker.

Current hardening audit (2026-11-15): [release report](docs/12-RELEASE-HARDENING.md) records the latest pull, local changes, live AWS smoke, connector failures and remaining release gates. It supersedes older deployment/status claims below where they differ. Hardening changes are not yet deployed.

Aplomb tests hypothetical investment changes against a fictional investor's plan. Code calculates the figures and verdicts; agents investigate the request and explain the evidence. Every number in an explanation links to its calculation or source. Simulation only. Fictional profiles. Not financial advice.

## Current repository status

[Open the deployed app](https://d1r325uzu5fe7x.cloudfront.net). The live AWS application serves the sourced snapshot, fictional profiles, portfolio metrics, deterministic rules and dataset passports. Durable portfolio-brief and decision workflows now execute real Bedrock calls: GPT-6 Astra plans/reviews, Claude Opus 5.5 writes, and Python owns the calculations and audit. A frozen Standard-tier Bedrock Guardrail is applied before signing. Profile drafts, idempotent creation, duplicate delivery, session isolation and S3 checkpoint integrity have live evidence.

See the [AWS architecture and demo guide](docs/AWS-ARCHITECTURE.md), [live architecture evidence](infra/evidence/aws-architecture-2026-11-14.json), and [deployment handoff](infra/README.md). Signed outputs carry explicit audit statuses; unsupported sentences are removed from normal views. The [full-stack follow-up audit](docs/FULL-ARCHITECTURE-AUDIT.md) documents published-version routing, retained release IAM, configured execution budgets and remaining recovery/capacity gaps. On-demand ticker publishing is currently local-only.

The repository now also contains the World Explorer backend (T11), the Time Machine (T12) and their pages with Agents & System (T15), wired into the same composition: replay and event-brief runs, the world endpoints and the reveal run locally and in offline tests, with the real code controls and auditor and a scripted stand-in for the model. They are **not yet deployed**: the deployed stack keeps research, world, replay and sabotage disabled until a release with these modules passes its live checks. See the [T11/T12/T15 and integration handoff](docs/T11-T12-T15-HANDOFF.md).

Start with [the team entry point](docs/00-START-HERE.md), then claim a track in [the parallel work map](docs/04-TRACKS.md). The binding interfaces live in [contracts](contracts/README.md). Product-owner decisions and explicitly unconfirmed defaults are in [the decision log](docs/02-DECISIONS.md).

## Repository map

| Path | Purpose |
|---|---|
| `docs/` | Product, architecture, ownership, conventions, acceptance and delivery |
| `contracts/` | HTTP API, types, tools, lifecycle, catalogs, numeric controls and fixtures |
| `backend/aplomb/` | Per-module implementation specifications for Python/FastAPI |
| `web/` | Next.js app, design and page specifications |
| `data/` | Ingestion, source terms, snapshot and availability requirements |
| `infra/` | AWS CDK deployment and evidence-capture specification |
| `tests/` | Integrated verification strategy |
| `Datathon2026/` | Organizer materials, immutable starter CSVs and visual reference |

## Install and check

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and Node.js 22.19 or newer. From the repository root:

```bash
uv sync --locked
npm ci
npm --prefix infra ci
npm run check
```

The check verifies generated files, Python lint/tests, ASGI and API Gateway response contracts, strict TypeScript, web runtime validation, specification links, fixture references/hashes, numeric controls, infrastructure assertions and offline CDK synthesis. After installation it runs without AWS credentials or live provider calls. CI runs the same command. To regenerate shared types after an approved contract edit, run `npm run generate:contracts`.

## Run it locally

Two terminals, from the repository root (Linux, macOS or Windows):

```bash
npm run dev:api     # API on http://localhost:8000/v1
npm run dev:web     # web app on http://localhost:3000
```

`dev:api` runs [scripts/dev_api.py](scripts/dev_api.py): it pins the active snapshot, materializes it under `data/` on first use, switches on every feature that has a provider and keeps run state in `.artifacts/`. Any `APLOMB_*` variable already set wins, then the `APLOMB_*` lines of the git-ignored `.env` (on-demand tickers need `APLOMB_TIINGO_TOKEN`); see [.env.example](.env.example). Protected routes require `X-Aplomb-Session` (the web app generates it).

Everything deterministic works without credentials: profiles, `/check`, compare, Portfolio, Sources, World Explorer, Time Machine presets and reveal. Runs (decision, replay, Home brief, event brief, profile draft) and free-text parsing call Amazon Bedrock: set `APLOMB_MODEL_STRONG`, `APLOMB_MODEL_FAST` and AWS credentials first. Without model IDs those endpoints answer `503` and the pages say so; no fixture stands in.

To try the AI features without model IDs or AWS credentials on your machine, run `npm run dev:web:aws` instead of `npm run dev:web`: the web app on http://localhost:3000 then uses the deployed AWS API (listed in `infra/deploy/site.json`, which accepts that origin), and every run it starts is a real run on the team's account.

`uv run uvicorn aplomb.api.app:app --port 8000` starts the same application with whatever the environment configures (all flags off by default).

## Reference checks

Run from the repository root with Python 3 (standard library only):

```bash
python3 scripts/check_specs.py
python3 contracts/controls/controls.py Datathon2026/alphaforge_starter
python3 contracts/controls/rules_ctl.py Datathon2026/alphaforge_starter
python3 contracts/controls/rate_ctl.py Datathon2026/alphaforge_starter
```

On Windows use `uv run python` in place of `python3`. `npm run build:web` writes the static export to `web/out/`; see [backend](backend/SPEC.md) and [web](web/SPEC.md).

## Data capture and evidence scripts

Not part of `npm run check`. Run them from the repository root (their default paths are relative to it): Python scripts with `uv run python scripts/<name>.py`, browser smokes with `node scripts/<name>.mjs`. The capture scripts fetch from the network unless a capture file is given, and never overwrite: each writes into a new directory (or snapshot version) that you review before copying it into the committed data.

| Script | Purpose | Prerequisites and arguments | Output |
|---|---|---|---|
| [ingest_eonet.py](scripts/ingest_eonet.py) | Refresh only the NASA EONET slice of the world bundle, keeping the other sources | Network; `--out NEW --start YYYY-MM-DD --end YYYY-MM-DD` (at most 366 days) | `events.json`, `hazards.json`, `manifest.json` in `--out` (candidate for `backend/aplomb/world/bundle/`) |
| [ingest_airports.py](scripts/ingest_airports.py) | Current-only OurAirports reference layer with the World Bank country crosswalk | Network, or `--capture` / `--crosswalk-capture` (for example the files under `data/inputs/airports/`); `--out NEW`, optional `--captured-at` | `airports.json`, `airports_manifest.json` and the two gzipped captures in `--out` |
| [ingest_facilities.py](scripts/ingest_facilities.py) | ECCC GHGRP facility layer, projected without contact or personal columns | Network, or `--capture` (for example `data/inputs/eccc/facilities_source.csv.gz`); `--out NEW`, optional `--captured-at` | `facilities.json`, `facilities_manifest.json`, `facilities_source.csv.gz` in `--out` |
| [ingest_world_bank.py](scripts/ingest_world_bank.py) | Current-only World Bank WDI country snapshot | Network; `--out NEW` | `country_macro.json`, `country_macro_manifest.json` in `--out` |
| [ingest_global_fx.py](scripts/ingest_global_fx.py) | Publish the pinned Bank of Canada FX capture as a new data snapshot; never activates it | Defaults: `--data-root data`, `--base-version snap-20261114-sourced`, `--new-version snap-20261115-globalfx` (the active version, whose committed manifest the rebuild must then match exactly), captures under `data/inputs/global-fx/`; refuses if `raw/` or `normalized/` of the new version already exist | `raw/`, `normalized/` and `manifests/<new-version>.json` under `--data-root`; `data/manifests/active.json` is not changed |
| [probe_gleif_entities.py](scripts/probe_gleif_entities.py) | Bounded public GLEIF candidate search; does not establish instrument mappings | Network; `--query TEXT --output NEW.json` | `NEW.json` plus the raw response `NEW.raw.json` (for example `docs/evidence/global-platform/gleif-apple-capture.json`) |
| [continuation_smoke.py](scripts/continuation_smoke.py) | HTTP contract smoke of a GBP profile (overview, goals, exposure limit, duplicate, archive), world airports, countries and ECCC facilities, and GLEIF entity search; no model, AWS writes or fixtures | A local API, by default `http://localhost:8001/v1` (`uv run python scripts/dev_api.py --port 8001 --no-reload`); override with `APLOMB_QA_API` | `http-smoke.json` in `APLOMB_QA_OUTPUT` (default `docs/evidence/global-continuation`) |
| [controls_http_smoke.py](scripts/controls_http_smoke.py) | HTTP smoke for native-currency account receipts and complete target allocations | Same API as above (`APLOMB_QA_API`, default port 8001) | `http-smoke.json` in `APLOMB_QA_OUTPUT` (default `docs/evidence/investigation-controls`) |
| [continuation_browser_smoke.mjs](scripts/continuation_browser_smoke.mjs) | Headless-Chrome walk through GBP goals, airports, ECCC facilities and GLEIF pages | API on 8001, web on 3001 built against it (`NEXT_PUBLIC_APLOMB_API_BASE=http://localhost:8001/v1`; site overridable with `APLOMB_QA_SITE`), Chrome with remote debugging on 9224 | Screenshots and `browser-interactions.json` in `APLOMB_QA_OUTPUT` (default `docs/evidence/global-continuation`) |
| [controls_browser_smoke.mjs](scripts/controls_browser_smoke.mjs) | Headless-Chrome check of the account receipt and target-allocation views | Same as above | Screenshots and `browser-interactions.json` in `APLOMB_QA_OUTPUT` (default `docs/evidence/investigation-controls`) |
| [site_review_browser_smoke.mjs](scripts/site_review_browser_smoke.mjs) | Regression checks of the welcome dialog focus trap and the Markets stock results and analysis period | Local API and web, site by default `http://localhost:3000` (`APLOMB_QA_SITE`), Chrome debugging endpoint by default `http://localhost:9224` (`APLOMB_QA_CDP`); no model calls | `PASS:` lines on standard output; no files |

AWS is operated by a teammate (D-09). No cloud credentials belong in this repository. The account closes Monday 2026-11-16 at 13:59 EST according to team logistics; capture genuine AWS proof before then. The team explicitly chose no offline replay mode; the Time Machine is a historical-data feature, not an offline deployment.
