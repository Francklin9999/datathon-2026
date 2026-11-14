# Aplomb — evidence before conviction

Aplomb tests hypothetical investment changes against a fictional investor's plan. Code calculates the figures and verdicts; agents investigate the request and explain the evidence. Every number in an explanation links to its calculation or source. Simulation only. Fictional profiles. Not financial advice.

## Current repository status

T01's shared contract foundation is implemented: Python models, generated TypeScript types, runtime validation, locked dependencies, and deterministic CI. **The application is not implemented or deployed yet.** Reference scripts and JSON fixtures support development; fixtures are not evidence of executed agents or AWS integration. See the [T01 handoff](docs/T01-HANDOFF.md) for imports and boundaries.

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
npm run check
```

The check verifies generated files, Python lint/tests, strict TypeScript, web runtime validation, Python-to-TypeScript serialization, specification links, fixture references/hashes, and numeric controls. After installation it runs without AWS credentials or live provider calls. CI runs the same command. To regenerate shared types after an approved contract edit, run `npm run generate:contracts`.

## Reference checks

Run from the repository root with Python 3 (standard library only):

```bash
python3 scripts/check_specs.py
python3 contracts/controls/controls.py Datathon2026/alphaforge_starter
python3 contracts/controls/rules_ctl.py Datathon2026/alphaforge_starter
python3 contracts/controls/rate_ctl.py Datathon2026/alphaforge_starter
```

T03/T13 will add application serve/build commands when their services exist. The intended local services are Next.js at `http://localhost:3000` and FastAPI at `http://localhost:8000/v1`; see [backend](backend/SPEC.md) and [web](web/SPEC.md).

AWS is operated by a teammate (D-09). No cloud credentials belong in this repository. The account closes Monday 2026-11-16 at 13:59 EST according to team logistics; capture genuine AWS proof before then. The team explicitly chose no offline replay mode; the Time Machine is a historical-data feature, not an offline deployment.
