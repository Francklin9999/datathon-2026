# Backend implementation specification

**Owners:** T03 for packaging/API, module owners T04–T12. **Tier:** P0 foundation.

## Runtime and package layout

One Python package lives under `backend/aplomb/`. T03 implements HTTP entry point `aplomb.api.app:create_app` and AWS handler `aplomb.api.lambda_handler:handler`; T08 implements `aplomb.agents.worker:handler`, requiring an explicitly configured services factory. Python 3.12, FastAPI/Pydantic/Mangum/AWS SDK/Strands versions are pinned in the root manifest/lockfile. API Gateway v2 adapter compatibility is tested locally; deployed compatibility still requires live smoke. See the [T08 handoff](../docs/T08-HANDOFF.md) for supported workflows and missing providers.

The root `pyproject.toml`/`uv.lock` includes Python 3.12, Pydantic, FastAPI, uvicorn, Mangum, boto3 and test tools. `uv sync --locked` installs the package; `uv run pytest` runs the contract, API and composition suites. T08 requests agent dependencies through the shared-manifest owner.

| Module | Owner | Specification |
|---|---|---|
| contracts | T01 | [Shared schemas](../contracts/schemas.md) and [catalog](../contracts/catalog.md) |
| api | T03 | [HTTP, repositories and dispatch](aplomb/api/SPEC.md) |
| datastore | T04 | [Versioned data and gate](aplomb/datastore/SPEC.md) |
| quant | T05 | [Calculations and funding](aplomb/quant/SPEC.md) |
| profiles / rules | T06 | [Profiles](aplomb/profiles/SPEC.md), [rules](aplomb/rules/SPEC.md) |
| optimizer | T07 | [Derivation and scenario search](aplomb/optimizer/SPEC.md) |
| agents | T08 | [Workflow, models and registry](aplomb/agents/SPEC.md) |
| research | T09 | [Source adapters](aplomb/research/SPEC.md) |
| ledger | T10 | [Facts, explanations and audit](aplomb/ledger/SPEC.md) |
| world | T11 | [Events and exposure](aplomb/world/SPEC.md) |
| timemachine | T12 | [Historical execution](aplomb/timemachine/SPEC.md) |

## Composition contract

`create_app(settings, services=None)` builds dependencies once. Services bundle profile service, check service, run service, datastore, ledger factory, research/world adapters and repositories. Modules receive protocols and context, not FastAPI Request objects. HTTP routes call services and map domain errors to `ApiError`. Local repositories can be memory/file implementations; production uses DynamoDB/S3 with equivalent behavior.

Configuration is read once into validated Settings. Required fields: environment (`local|aws`), region, data directory or S3 bucket/prefix/version, profiles/runs/cache tables, worker function name, strong/fast model IDs, Guardrail ID/version, allowed origins, source user-agent, feature flags and run limits. Environment variable names are frozen in [infra](../infra/SPEC.md). Validate required AWS fields on startup; local deterministic work can start without model credentials.

## Local implementation milestone

T03 supplies [.env.example](../.env.example), dependency-injected services, repositories and a local dispatcher. Run `uv run uvicorn aplomb.api.app:app --reload --port 8000` from root after installation. Missing domain providers return explicit unavailable/disabled errors. See [the API handoff](../docs/T03-HANDOFF.md) for interfaces, configuration and limitations. The local asynchronous dispatcher runs independently of the HTTP response lifecycle and checkpoints through the same repository protocol as AWS.

No AWS calls in module import paths or pure unit tests. No automatic model calls at startup. No dependency from quant/rules back into agents/API. Run the shared fixture validation and relevant module tests before integration. Completion requires deterministic `/check`, genuine worker persistence and consistent API error envelopes.
