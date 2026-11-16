# AWS CDK deployment and operational handoff

**Track:** T02, the designated AWS teammate (D-09). **Tier:** P0. Other contributors can implement locally without organizer credentials. Cloud resources are specifications here, not deployed infrastructure.

## Service responsibilities

| Resource | Concrete function |
|---|---|
| CloudFront + private S3 web bucket | Serve Next.js static export; origin access restricted |
| API Gateway + HTTP Lambda | Validate requests, deterministic preview, run creation/polling |
| Worker Lambda, same backend artifact | Execute asynchronous Strands/Bedrock workflow with pinned inputs |
| S3 data/evidence bucket | Immutable snapshots, source documents and large signed bundles |
| DynamoDB profiles/runs/cache | Session overlays, durable steps/facts and caches/idempotency |
| Bedrock | Actual reasoning/writing/review model calls |
| Bedrock Guardrail when verified | Additional input/output policy, never numeric truth checker |
| CloudWatch | Correlated request/run/step logs, failure/latency metrics |

One CDK stack can contain these resources. Separate API and worker functions avoid a long HTTP request while preserving one FastAPI app/codebase. API persists then invokes worker with InvocationType Event; worker conditionally claims the run. [AWS documents async retries](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html), so exactly-once execution must come from application storage logic, not assumptions about invocation.

## First deployment preflight

Confirm region, model IDs and account quotas by a genuine Bedrock smoke request. Test both strong/fast IDs; do not assume named Claude versions are enabled. Verify Guardrail creation/application separately (O-01, O-03). Record official model/API documentation and actual result. The AgentCore Browser (O-02) was verified, then removed from the application: known-site fetch (`web.fetch`) reads the allow-listed pages, and no role has AgentCore permissions. [Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html) adds policy filtering; ledger audit remains mandatory.

Choose a supported Python runtime and compatible architecture; build native dependencies for Lambda, not from an incompatible laptop wheel. Package data loader, code and model SDK; large CSVs load from versioned S3. Test cold start and ephemeral cache. Default engineering settings: API 30-second function budget subject to actual Gateway limit, worker 210-second function timeout with application hard deadline 180 seconds and shutdown persistence reserve. Configure finite worker concurrency to keep within Bedrock quota; measure and adjust, never guess unlimited throughput.

## Environment contract

| Variable | Meaning / local behavior |
|---|---|
| `APLOMB_ENV` | local or aws |
| `AWS_REGION` | Region selected by operator; SDK-standard variable |
| `APLOMB_DATA_VERSION` | Immutable snapshot ID |
| `APLOMB_DATA_AS_OF` | The snapshot manifest's `dataAsOf`; any other snapshot date answers 503 (stack input `dataAsOf`) |
| `APLOMB_DATA_DIR` | Local starter/normalized snapshot root; in AWS, the `/tmp` cache directory for S3 snapshot objects |
| `APLOMB_DATA_BUCKET`, `APLOMB_DATA_PREFIX` | AWS snapshot/evidence location |
| `APLOMB_PROFILES_TABLE`, `APLOMB_RUNS_TABLE`, `APLOMB_CACHE_TABLE` | DynamoDB names |
| `APLOMB_WORKER_FUNCTION` | Async worker name/ARN |
| `APLOMB_MODEL_STRONG`, `APLOMB_MODEL_FAST` | Actual Bedrock model/profile IDs |
| `APLOMB_GUARDRAIL_ID`, `APLOMB_GUARDRAIL_VERSION` | Both required when flag on |
| `APLOMB_ALLOWED_ORIGINS` | Comma-separated exact web/local origins |
| `APLOMB_SOURCE_USER_AGENT` | Approved descriptive public-source user agent naming a contact (an `https://` URL or an email); without one no research tool is registered |
| `APLOMB_FEATURE_<UPPERCASE_CATALOG_FLAG>` | Explicit bool override per feature |
| `APLOMB_RUN_HARD_SECONDS` | Default 180 (the 90 s target is a design aim, not a setting) |
| `APLOMB_MAX_REVISE`, `APLOMB_MAX_LLM_CALLS`, `APLOMB_MAX_RESEARCH_CALLS` | Defaults 2/12/12 |
| `NEXT_PUBLIC_APLOMB_API_BASE` | Browser-visible base ending `/v1`; never credentials |
| `NEXT_PUBLIC_APLOMB_FIXTURES` | false in actual submission/live build |

Credentials use operator-approved AWS profiles/roles; do not store keys in env examples, generated JS or Git. Use least-privilege role policies restricted to project buckets/prefixes/tables/model resources where supported. HTTP role can dispatch only this worker; worker cannot deploy infrastructure. Protect document fetch from metadata/private network access at the application layer.

## Deployment sequence

T02 creates CDK project/lockfile and documented commands. Proposed stages: synth → inspect IAM/diff → package backend → deploy stack → upload validated data snapshot → configure verified model IDs/flags → build web against output API URL → upload export/invalidate cache → run deployed smoke. A failed later stage does not imply previous artifacts are ready; maintain a deployment manifest with revision and outputs.

Static Next.js has [no runtime server](https://nextjs.org/docs/app/guides/static-exports). Configure trailing-slash route objects and CloudFront rewrite to each exported route's index; test deep links and refresh, assets excluded from rewrite. Browser API calls go to API Gateway. CloudFront serves actual exported not-found behavior; avoid caching API responses as HTML. Restrict CORS to current CloudFront + localhost.

## Verification and shutdown

INF-01 synth and least-privilege diff reviewed. INF-02 API health/meta/deep links/CORS. INF-03 worker retries do not duplicate results. INF-04 real model invocation and guardrail if enabled. INF-05 S3 manifest/hash and DynamoDB checkpoints. INF-06 timeouts/quota errors and logs visible. INF-07 no secrets in export/logs. INF-08 capture before shutdown.

Export stack outputs (site URL, API base, data version, region, deployed revision) to team documentation without secret values. Before Monday 13:59 EST capture real run ID/model usage, Lambda logs, S3 manifest, DynamoDB record and UI video. Retain sanitized artifacts; do not promise a live service after the organizer account closes. Teardown follows operator/organizer policy; no automatic destructive cleanup is part of this spec pack.
