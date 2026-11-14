# T01 — Contracts and integration handoff

Contract version: **1.0.0**. Scope: shared boundary types, runtime validation, reproducible dependency setup, and deterministic integration checks. HTTP handlers, application pages, agent execution and deployment belong to the remaining tracks.

## Setup and checks

From the repository root, with Python 3.12, uv and Node.js >=22.19:

```bash
uv sync --locked
npm ci
npm run check
```

`npm run check` runs generation drift checks, Python lint/tests, strict TypeScript, web validation and serialization checks, and the existing specification/numeric checker. Installation downloads locked packages; subsequent checks need no network or credentials. CI uses this same command. Python is installed as the `aplomb` package from `backend/aplomb/`; no manual `PYTHONPATH` is required.

## Consumer imports

```python
from aplomb.contracts.api import CheckRequest, ProfilesResponse, CreateRunRequest
from aplomb.contracts.models import CheckResult, Profile, Run
from aplomb.contracts.catalog import MetricCode, ErrorCode, ERROR_HTTP_STATUS
from aplomb.contracts.registry import adapter

request = CheckRequest.model_validate_json('{"profileId":"robert","move":null}')
assert request.profile_id == "robert"
assert request.to_wire() == {"profileId": "robert", "move": None}
# Discriminated unions use TypeAdapter through the shared registry:
run_request = adapter("CreateRunRequest").validate_json(
    '{"kind":"profile_draft","lang":"en","text":"A fictional profile"}'
)
```

```typescript
import type { CheckRequest, Profile, Run } from '../contracts/types';
import { MetricCode } from '../contracts/catalog';
import { validateContract } from '../contracts/validate';

const request: CheckRequest = { profileId: 'robert', move: null };
const profiles = validateContract('ProfilesResponse', unknownResponseJson);
// profiles.items is Profile[]; malformed JSON raises ContractValidationError.
```

The TypeScript import paths are relative to a consumer in `web/src/api/`. The snippet's `unknownResponseJson` represents parsed HTTP JSON; it is not a fixture fallback. The root [schema registry](../contracts/generated/schema.json) exposes every type under `$defs`; a registry document is tooling input, not an HTTP response.

## Owned files and change flow

| Area | Files |
|---|---|
| Python wire types | `backend/aplomb/contracts/base.py`, `models.py`, `api.py`, `registry.py` |
| Generated catalogs | `backend/aplomb/contracts/catalog.py`, `web/src/contracts/catalog.ts` |
| Generated schemas/types | `contracts/generated/schema.json`, `web/src/contracts/types.ts` |
| Web runtime validator | `web/src/contracts/validate.ts` |
| Verification | `contracts/validation-cases.json`, `backend/tests/contract/`, `web/tests/contracts.test.ts` |
| Tooling | root Python/npm manifests and lockfiles, `web/tsconfig.json`, `scripts/*contracts*`, `.github/workflows/contracts.yml` |

Edit the written contract first for a boundary change, then its Python mirror; run `npm run generate:contracts`, review artifacts, and run `npm run check`. Catalog values/defaults/error status mappings come from `contracts/catalog.md`. Generated TypeScript is never edited manually. Tests compile the declarations in `schemas.md` against generated types and send serialized Python fixture responses through the web validator.

Numeric controls and fixture values are unchanged. Domain services must still enforce position sums, funding feasibility, horizon ordering, temporal availability, ledger reference integrity, session isolation, idempotency and lifecycle transitions. `/meta` must include every feature flag; flags declared here are catalog defaults, not evidence that features are available in a deployment.

## Validation evidence — 2026-11-14

Verified on the working changes based on `86fa0cf`, Python 3.12.16 and Node.js 24.18.0:

| Check | Observed result |
|---|---|
| `npm run check` with uv offline | Passed: 81 Python tests, 72 web checks, strict TypeScript, lint, generated-file drift, 47 specification documents, three fixtures and numeric controls |
| Fresh source copy in `/tmp`, new Python/npm environments, locked installs from local caches | The same complete check passed; no existing project environment was reused |
| Three standalone reference scripts (`controls.py`, `rules_ctl.py`, `rate_ctl.py`) | All completed successfully against the unchanged starter CSVs |
| `git diff --check` | Passed |

The CI workflow is configured but has not been run on GitHub in this session. Node.js 22 is the configured CI runtime; the observed local run used 24.18.0. No application acceptance rows are claimed by these results.

## Next-track boundaries

T03 can build FastAPI routers/repositories with the request/response envelopes in `contracts/api.py` and extend the root Python manifest. T04–T12 import shared types and implement their domain checks. T13 can add the Next.js shell/API client to the existing npm workspace and use `validateContract` at response boundaries. T16 can use the root CI command as the deterministic integration gate and add actual application acceptance evidence separately.

The canonical fixtures remain labelled development data. Passing T01 does not mark any application acceptance row or AWS integration as passed. No cloud resources or external messages are created by this work.
