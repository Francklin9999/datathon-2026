# Aplomb — evidence before conviction

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

`dev:api` runs [scripts/dev_api.py](scripts/dev_api.py): it pins the active snapshot, materializes it under `data/` on first use, switches on every feature that has a provider and keeps run state in `.artifacts/`. Any `APLOMB_*` variable already set wins; see [.env.example](.env.example). Protected routes require `X-Aplomb-Session` (the web app generates it).

Everything deterministic works without credentials: profiles, `/check`, compare, Portfolio, Sources, World Explorer, Time Machine presets and reveal. Runs (decision, replay, Home brief, event brief, profile draft) and free-text parsing call Amazon Bedrock: set `APLOMB_MODEL_STRONG`, `APLOMB_MODEL_FAST` and AWS credentials first. Without model IDs those endpoints answer `503` and the pages say so; no fixture stands in.

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

AWS is operated by a teammate (D-09). No cloud credentials belong in this repository. The account closes Monday 2026-11-16 at 13:59 EST according to team logistics; capture genuine AWS proof before then. The team explicitly chose no offline replay mode; the Time Machine is a historical-data feature, not an offline deployment.
