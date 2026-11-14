# Aplomb — evidence before conviction

Aplomb tests hypothetical investment changes against a fictional investor's plan. Code calculates the figures and verdicts; agents investigate the request and explain the evidence. Every number in an explanation links to its calculation or source. Simulation only. Fictional profiles. Not financial advice.

## Current repository status

This repository contains challenge materials, a visual prototype, and an implementation-ready specification pack. **The application is not implemented or deployed yet.** Reference scripts and JSON fixtures support development; fixtures are not evidence of executed agents or AWS integration.

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

## Checks available now

Run from the repository root with Python 3 (standard library only):

```bash
python3 scripts/check_specs.py
python3 contracts/controls/controls.py Datathon2026/alphaforge_starter
python3 contracts/controls/rules_ctl.py Datathon2026/alphaforge_starter
python3 contracts/controls/rate_ctl.py Datathon2026/alphaforge_starter
```

Application installation commands will be added by T01 when manifests and lockfiles exist. The intended local services are Next.js at `http://localhost:3000` and FastAPI at `http://localhost:8000/v1`; see [backend](backend/SPEC.md) and [web](web/SPEC.md). Do not describe those services as runnable until implemented.

AWS is operated by a teammate (D-09). No cloud credentials belong in this repository. The account closes Monday 2026-11-16 at 13:59 EST according to team logistics; capture genuine AWS proof before then. The team explicitly chose no offline replay mode; the Time Machine is a historical-data feature, not an offline deployment.
