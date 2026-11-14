# Backend implementation specification

**Owners:** T03 for packaging/API, module owners T04–T12. **Tier:** P0 foundation.

## Runtime and package layout

Implement one Python package under `backend/aplomb/`. HTTP entry point `aplomb.api.app:create_app`; AWS handler `aplomb.api.lambda_handler:handler`; worker handler `aplomb.agents.worker:handler`. These are planned paths, not existing runnable files. Target a mutually supported Python runtime, pin FastAPI/Pydantic/Strands/AWS SDK versions and commit a lockfile. A Lambda HTTP adapter may be used; T02/T03 verify payload compatibility before deployment.

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

T03 supplies a backend manifest, `.env.example` without secrets, and documented commands for installing, serving and testing. Intended development invocation after implementation: `python -m uvicorn aplomb.api.app:app --reload --port 8000` from `backend/`, provided an `app` export is created. A local asynchronous dispatcher must run independently of the HTTP response lifecycle and checkpoint through the same repository protocol as AWS.

No AWS calls in module import paths or pure unit tests. No automatic model calls at startup. No dependency from quant/rules back into agents/API. Run the shared fixture validation and relevant module tests before integration. Completion requires deterministic `/check`, genuine worker persistence and consistent API error envelopes.
