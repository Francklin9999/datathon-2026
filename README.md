# Aplomb — evidence before conviction

Aplomb tests hypothetical investment changes against a fictional investor's plan. Code calculates the figures and verdicts; agents investigate the request and explain the evidence. Every number in an explanation links to its calculation or source. Simulation only. Fictional profiles. Not financial advice.

## Current repository status

Shared contracts (T01), AWS CDK (T02), API/persistence (T03), datastore (T04), agent execution (T08), research capture (T09), and ledger/audit (T10) have implemented modules and deterministic checks. A genuine Bedrock profile-draft run completed plan/audit/sign and was re-read from durable local storage. Decision controls and application composition remain provider dependencies; the default API returns explicit unavailable/disabled responses. No application stack is deployed. JSON fixtures remain development examples. See the [track integration report](docs/T08-T10-INTEGRATION.md) for evidence and precise limits, plus the [API](docs/T03-HANDOFF.md) and [AWS](infra/README.md) handoffs.

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

## Local API

```bash
uv run uvicorn aplomb.api.app:app --reload --port 8000
```

`GET http://localhost:8000/v1/health` works immediately. `/meta` requires a configured snapshot version; see [.env.example](.env.example) and the API handoff for configuration. Protected routes require `X-Aplomb-Session`. T04–T12 supply the actual profile/data/calculation/agent providers; the default composition makes their absence visible.

## Reference checks

Run from the repository root with Python 3 (standard library only):

```bash
python3 scripts/check_specs.py
python3 contracts/controls/controls.py Datathon2026/alphaforge_starter
python3 contracts/controls/rules_ctl.py Datathon2026/alphaforge_starter
python3 contracts/controls/rate_ctl.py Datathon2026/alphaforge_starter
```

T13 will add the Next.js shell and build commands. The intended web URL is `http://localhost:3000`; see [backend](backend/SPEC.md) and [web](web/SPEC.md).

AWS is operated by a teammate (D-09). No cloud credentials belong in this repository. The account closes Monday 2026-11-16 at 13:59 EST according to team logistics; capture genuine AWS proof before then. The team explicitly chose no offline replay mode; the Time Machine is a historical-data feature, not an offline deployment.
