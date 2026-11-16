# Aplomb — evidence before conviction

A self-explaining agentic assistant that tests a hypothetical investment move against a fictional investor's own plan, and shows what supports every conclusion. Built for **AlphaForge AI**, Datathon 2026 (National Bank × AWS × PolyFinances).

**Simulation only. Fictional profiles. Not financial advice.** Aplomb has no trading tool.

- **Live app**: https://d1r325uzu5fe7x.cloudfront.net (AWS account available until 2026-11-16 13:59 EST)
- **One-pager**: [docs/deliverables/one-pager.pdf](docs/deliverables/one-pager.pdf)
- **Technical documentation**: [docs/deliverables/technical.pdf](docs/deliverables/technical.pdf) ([Markdown](docs/deliverables/technical.md))
- **Demo script**: [docs/deliverables/demo.md](docs/deliverables/demo.md)

## What it does

Pick Robert, Amira or Mateo, the three personas of the case, and test an idea such as "add 25% of Tesla".

- **Code computes everything**: adjusted returns, volatility, drawdown, the 2022 stress, concentration, currency conversion, and every rule of the investor's plan. It also finds the largest size the plan allows.
- **Agents explain and check**: a planner frames the request and chooses which extra analyses the code runs, a researcher reads allow-listed official sources, a writer drafts in English or French from recorded facts only, and an auditor verifies every sentence before signing the brief.
- **Every figure is clickable**: it opens the method, inputs, source rows, period and limitations behind it.

Same idea, different investors: Robert at +25 points hits six rule conflicts and a 6-point limit; Amira hits three, with an 11-point limit; Mateo's Energy exclusion blocks CNQ even though eight other checks pass.

## How it works

```
Next.js app ─► CloudFront + S3 ─► API Gateway ─► API Lambda (FastAPI, deterministic analytics)
                                                    └─► Worker Lambda: plan → research → quant → risk → write → audit → sign
                                                          Amazon Bedrock (two models + Guardrail), DynamoDB, S3, CloudWatch
```

Details, methods, data sources, a traced example and validation: [technical documentation](docs/deliverables/technical.md).

## Run it locally

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 22.19 or later.

```bash
uv sync --locked
npm ci
npm --prefix infra ci
npm run dev:api      # materializes the pinned data snapshot, starts the API on :8000
npm run dev:web      # starts the web app on :3000
```

Deterministic features (portfolios, rule checks, size limits, strategies, world exposure, data passports) work without credentials. Agent runs need Amazon Bedrock access: set `APLOMB_MODEL_STRONG` and `APLOMB_MODEL_FAST` (see [.env.example](.env.example)). `npm run dev:web:aws` points the local web app at the deployed API.

## Checks

```bash
npm run check
```

Runs the generated-file checks, lint, the Python test suite, type checks, the web tests, the specification and link checks, and the infrastructure tests with CDK synth. CI runs the same gate on every push; pushes to `main` publish the site.

## Repository

| Path | Contents |
|---|---|
| `backend/aplomb/` | API, agent workflow, quant engine, rules, ledger and audit, data store, world module (each with a `SPEC.md`) |
| `web/` | Next.js static web app |
| `contracts/` | API, schemas, catalog and tools contracts; generated JSON schema and TypeScript types |
| `data/` | Snapshot manifests, inputs and data documentation |
| `infra/` | AWS CDK stack, packaging script, release evidence |
| `scripts/` | Development server, ingestion, contract generation and checks |
| `docs/` | Product, architecture, compliance and deliverables |
| `Datathon2026/` | The official case, slides and starter dataset |

## Data and licences

The case starter dataset (31 assets, daily prices from 2021-11-12 to 2026-11-12, dividends and splits, Bank of Canada USD/CAD, Bank of Canada and FRED macro series) is extended with Bank of Canada global FX, Wikimedia page views, issuer and official documents, and dated world events and hazards. Every dataset has a passport (source, licence, coverage, processing, availability rule, limitations) in the app's Sources page and in [data/](data/). Prices come from Yahoo Finance via yfinance under Yahoo's terms and are not certified.
