# T02/T03 integration evidence — 2026-11-14

T02 and T03 were implemented concurrently by two Sol agents at medium reasoning, with root review and shared dependency/CI integration. T01 was pushed as `8a85f67`. Before this handoff, root fast-forwarded to the team's `ca5250e`, including T04 datastore implementation, and verified the combined work.

## Observed checks

| Check | Result |
|---|---|
| Root `npm run check`, Python 3.12.16 / Node 24.18.0 | Passed: 213 Python tests, 73 web checks, five infra tests, strict TypeScript, lint, generation drift, fixture/reference/numeric checks and offline CDK synth |
| Fresh source copy, new uv/npm environments, installs from locked caches | T02/T03 check passed: 114 Python tests, 73 web checks and five infra tests; this copy preceded the teammate's T04 merge |
| Incoming T04 datastore tests | 99 passed; import ordering, unused imports and a type-only forward declaration were corrected for the shared lint gate |
| API composition | All 39 documented method/path pairs are registered; actual ASGI and API Gateway v2 health/meta/error responses match wire contracts |
| Cross-language boundary | Actual FastAPI JSON is validated by the web consumer, including unavailable and disabled paths |
| CloudFormation preflight | AWS `ValidateTemplate` accepted the foundation template; hash and sanitized response are in the preflight evidence |

The root command is the configured GitHub Actions command. GitHub CI execution was not verified: the connector returned invalid credentials and the public API could not read this repository. Local validation is the evidence above. Installed Starlette/httpx and Mangum emitted deprecation warnings; tests did not skip or fail because of them.

## Genuine AWS observations

The official AWS MCP executed bounded Converse calls in `us-east-1`: Sonnet 4.6 and Haiku 5.5 returned `APLOMB_OK` with actual token usage. The initial Fable 5.2 candidate failed with a retention-mode configuration error; no account policy was changed. A project-only Guardrail was created in DRAFT, blocked a test trading promise and allowed educational risk text. The built-in Browser started and stopped a session; navigation and citations were not tested.

The [sanitized preflight record](../infra/evidence/preflight-2026-11-14.json) preserves actual outputs and limitations. Application flags remain disabled until their providers and acceptance paths are verified. No application stack, snapshot upload, web export or real persisted investment-analysis run was deployed by this work. The isolated Guardrail remains retained.

## Remaining integration gates

The [API handoff](T03-HANDOFF.md) describes domain service injection, repository checkpoints, ownership, idempotency and local execution. The [AWS handoff](../infra/README.md) describes artifact packaging, IAM, deployment and evidence capture.

T08 must provide the real worker and composition; T05–T12 must provide remaining calculations, profiles, ledger and other domain providers. T04 is present in the merged tree but is not automatically injected into the default API. T13 must build the web application. Native Lambda packaging deliberately fails while the worker is absent. Live DynamoDB/S3/Lambda persistence, deployed HTTP/CORS/deep links, full model/Guardrail integration and application acceptance remain unverified.
