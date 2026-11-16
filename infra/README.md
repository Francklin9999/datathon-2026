# Automatic frontend delivery

Pushes to `main` deploy the static site after checks and build. See [pipeline setup, credentials, smoke checks and rollback](deploy/README.md). Backend releases retain their separate deployment process.

# Aplomb AWS handoff

Backend release (2026-11-15 06:28 UTC): `9f10301` deployed as API and worker version 2 with `bilingual`, `world_explorer`, `world_layer_hazards`, `time_machine` and `goal_requests` added to the enabled flags. Change set reviewed before execution; live goal and replay runs signed. [Evidence](evidence/release-9f10301-2026-11-15.json).

Backend release (2026-11-15 06:56 UTC): `a85beea` deployed as API and worker version 3, adding custom date windows on overview, performance and frontier (`70c5eda`); flags unchanged. [Evidence](evidence/release-a85beea-2026-11-15.json).

Backend release (2026-11-15 07:30 UTC): `cd20a9b` (backend of `4cd6ab2`) deployed as API and worker version 4 with `X-Aplomb-Build` release identity; flags unchanged. Live Robert decision, Amira goal, replay/reveal and session isolation passed. [Evidence](evidence/release-cd20a9b-2026-11-15.json).

Backend release (2026-11-15 14:18 UTC): `f098339` deployed as API and worker version 5: sabotage workflow code and contract 1.1.0 (`sabotage_demo` stays off) and a per-process read cache for overview and performance; flags unchanged. Live Robert decision, Amira goal, replay/reveal and session isolation passed. [Evidence](evidence/release-f098339-2026-11-15.json).

Backend release (2026-11-15 15:53 UTC): `42e2023` deployed as API and worker version 8 with `sabotage_demo` on. The sabotage child now inserts a code-built false sentence (the real writer declined to lie on AWS) and runs the real audit; all three modes were caught live in EN and FR. [Evidence](evidence/release-42e2023-2026-11-15.json).

Backend releases (2026-11-15 16:59-18:01 UTC): `8b0e373`, `d7d9fba` and `4a9c98e` deployed as API and worker versions 9-11 with `research_open_web` on. The configured source user agent gained its `https://` scheme, without which no research tool was registered. Live event briefs then had the researcher call `web.browse` through AgentCore Browser on Bank of Canada and Federal Reserve pages and cite verified quotes. Limits are recorded with the [evidence](evidence/release-4a9c98e-2026-11-15.json).

Backend release (2026-11-15 20:19 UTC): `4f42460`, the integration of every branch (main, the parallel baseline and agents 1-3), deployed as API and worker version 12: contract 1.4.0 on snapshot `snap-20261115-globalfx` (the sourced snapshot plus `fx_boc_global`); flags unchanged. A live Robert decision passed audit in 47 s and another session got 404. [Evidence](evidence/release-4f42460-2026-11-15.json).

Backend release (2026-11-15 23:48 UTC): `1307604` deployed as API and worker version 13 with Aymenead's standing strategies (contract 1.5.0); the site had already shipped the Strategies page, whose simulate call answered 404 on version 12. All three strategy kinds simulated live, and a Robert decision passed audit and was signed; snapshot and flags unchanged. [Evidence](evidence/release-1307604-2026-11-15.json).

Deployment update (2026-11-14): `Aplomb` reached `UPDATE_COMPLETE` in us-east-1 after pulling `b0e6a15` and applying the AWS architecture changes. [Live site](https://d1r325uzu5fe7x.cloudfront.net); [API health](https://tf6efr54nd.execute-api.us-east-1.amazonaws.com/v1/health). The frontend uses the real API with fixtures disabled and snapshot `snap-20261114-sourced`. Live portfolio briefs and decisions completed planner → quant → risk → writer → audit → sign, using GPT-6 Astra, Claude Opus 5.5 and Standard-tier Guardrail version 3. Profile creation/frontier/Guardrails are enabled; other optional capabilities remain disabled.

The worker has a retained encrypted SQS failure destination. `Aplomb-operations` displays actual workflow outcomes, token use, latency and platform delivery failures. Alarms have no paging target. [Architecture guide](../docs/AWS-ARCHITECTURE.md) and [sanitized live evidence](evidence/aws-architecture-2026-11-14.json) document the proof and limits; the historical handoff below describes the original T02 state.

The deployment used official AWS MCP CloudFormation calls and presigned S3 uploads. The synthesized deployment copy removed unused CDK bootstrap checks/metadata, replaced Lambda asset locations with the uploaded data-bucket artifact and pinned its S3 object version. The source CDK template remains unchanged.

This project synthesizes **foundation-only** infrastructure by default. It creates no fake API or worker. No stack has been deployed by T02. Model/Guardrail/Browser preflight evidence is in [evidence/preflight-2026-11-14.json](evidence/preflight-2026-11-14.json); it does not prove the application works.

## Reproduce locally

From the repository root:

```sh
npm --cache /tmp/aplomb-npm-cache --prefix infra ci
npm --prefix infra run check
```

Pinned infra-local dependencies and lock are independent of the root workspace. Check runs the offline assertion tests and CDK synth, including agreement with the shared feature catalog. Output is `infra/cdk.out/Aplomb.template.json`; synth performs no AWS lookups. Unit fixtures contain empty handlers solely for template tests; they are removed and never used by the application build.

The foundation contains retained, versioned, encrypted S3 buckets; HTTPS-only bucket policies; private CloudFront OAC; route rewrite to exported `index.html`; actual 404 responses; three retained encrypted on-demand/PITR DynamoDB tables. Cache TTL is `expiresAt`; application expiry checks remain mandatory. Runs use lowercase `pk`/`sk` and `bySession(sessionKey, sessionSort)` / `byProfile(profileKey, profileSort)`. Only META items populate GSIs. Index key values and ownership remain T03 responsibilities.

## Package application

Run `infra/scripts/package-backend.sh` after T03 API and T08 worker exist and root dependencies are frozen. It deliberately fails if either handler is absent. It exports locked runtime requirements, installs only binary Python 3.12 Linux x86_64 wheels using uv platform `x86_64-manylinux_2_28`, copies backend modules, and imports native modules plus both handlers in the Lambda Python 3.12 x86_64 container. Host-installed native wheels never enter the artifact. [AWS packaging guidance](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html) specifies manylinux_2_28 for Python 3.12+ on Amazon Linux 2023 (glibc 2.34); the installed uv help confirms this platform spelling. Docker and a reviewed image digest are required for a release; the script pins the AWS Python 3.12 image digest used by the deployment import check. The runtime probe checks the locked Pydantic native extension, Strands, API/worker handlers, domain-service imports and the packaged world bundle. The current quant implementation uses the standard library; NumPy/SciPy are not runtime dependencies. No CSV snapshot is bundled: the price snapshot is read from S3. The script also copies the captured rate and positioning inputs read by `/v1/risk/source-inputs` (`data/inputs/risk-nyfed`, `risk-cftc`, `risk-treasury`, the `CAPTURE_FOLDERS` of `backend/aplomb/datastore/financial_inputs_api.py`) to `data/inputs/` in the artifact, where the route finds them as `/var/task/data/inputs`; the probe fails if any of those five captures reports `capture_unavailable`. The route's rights note (public access does not establish redistribution rights) still applies to these captures.

The successful probe writes a manifest with file hashes. CDK requires that manifest, verifies hashes, and checks handler/dependency presence. Artifact integrity is a packaging safeguard; it cannot establish that unfinished handlers execute a real workflow. The human review still checks T08 implementation and end-to-end smoke.

Set `APLOMB_INFRA_CONFIG` to a JSON file containing `application` with:

```json
{
  "application": {
    "artifact": "/absolute/path/to/infra/.build/lambda",
    "dataVersion": "snap-20261114-starter",
    "dataAsOf": "2026-11-12",
    "dataPrefix": "snapshots/snap-20261114-starter/",
    "strongModel": "us.anthropic.claude-sonnet-4-6",
    "fastModel": "us.anthropic.claude-haiku-5-5",
    "sourceUserAgent": "Aplomb research (https://approved-team-contact.example)",
    "revision": "reviewed-git-revision",
    "allowedOrigins": ["http://localhost:3000"],
    "modelResourceArns": [
      "arn:aws:bedrock:us-east-1:010526248118:inference-profile/us.anthropic.claude-sonnet-4-6",
      "arn:aws:bedrock:us-east-1:010526248118:inference-profile/us.anthropic.claude-haiku-5-5",
      "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-6",
      "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-sonnet-4-6",
      "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-6",
      "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-haiku-5-5",
      "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-haiku-5-5",
      "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-haiku-5-5"
    ]
  }
}
```

`dataAsOf` must be the `dataAsOf` of the snapshot manifest named by `dataVersion` (`data/manifests/<dataVersion>.json`): the API refuses any other snapshot date with `503 upstream_unavailable`. When `dataAsOf` is omitted, synthesis reads it from that manifest in the repository (and fails when the manifest is absent). `sourceUserAgent` should name a contact, an `https://` URL or an email, in at least 15 characters (the rule of `contact_user_agent` in `backend/aplomb/research/core.py`): without one the worker registers no research tool, so synthesis prints a warning, and fails when `research_open_web` is listed.

Optional `"features": ["bilingual", "world_explorer", "world_layer_hazards", "time_machine", "profile_creator", "goal_requests", "frontier_chart"]` sets those `APLOMB_FEATURE_*` variables to `true` on both functions; every flag not listed stays `false`, and an unknown name fails synthesis. `/v1/meta` advertises a listed flag only when its provider is available (`default_services` in `backend/aplomb/api/domain.py`). Those seven need only the snapshot (the two world flags also the world bundle packaged with the backend); `world_layer_facilities` needs the facility capture packaged in the same bundle. `sabotage_demo` needs the two model IDs. `research_open_web` needs a contact `sourceUserAgent`, and listing it grants the worker the AgentCore browser actions below. `guardrails` needs a frozen `guardrail` (synthesis fails without one). `on_demand_tickers` is never available in AWS: it needs a Tiingo token and a writable local data directory. List a flag only after its acceptance path passed in the deployed stack; the release records above name the live checks behind each flag.

Those exact profile/destination ARNs were returned by `GetInferenceProfile`; rediscover before deploying to another account. Never broaden model names or regions to `*` to bypass a denial. The stack defaults region to us-east-1. Do not set Lambda's reserved `AWS_REGION` manually; Lambda supplies it.

Application mode adds the actual API and worker handlers, API Gateway HTTP API, CORS, aggregate throttling (100/s, burst 200), one-week retained logs, errors/throttles alarms, worker async max age one minute and one retry. API timeout is 30 seconds; worker is 210 with application hard limit 180. API concurrency is five; worker two. Gateway timeout/cold-start and Bedrock quotas still need deployed measurement. Alarms have no notification target configured; operator must inspect them. Delivery failures need application watchdog/recovery; async retries are not exactly-once execution.

All catalog flags are explicitly false until integrated providers pass acceptance tests. The HTTP role dispatches only the stack worker. Worker can read profiles and mutate runs/cache; API can mutate project tables. Both can invoke the two exact models, read only the selected snapshot prefix and read/write `evidence/*`. T03 spills bundles under `evidence/run-bundles/{sha256}.json`. No role can deploy or enumerate unrelated buckets/tables. Only with `research_open_web` does the worker (never the API) get `bedrock-agentcore:StartBrowserSession`, `StopBrowserSession` and `ConnectBrowserAutomationStream` on the AWS-managed browser `aws.browser.v1`; disabled Guardrail/Browser have no application IAM permissions. Explicit Lambda execution roles grant only CreateLogStream/PutLogEvents on each function’s own log group; no AWSLambdaBasicExecutionRole managed policy is attached.

## Environment

The stack supplies the variables documented in [SPEC.md](SPEC.md): `APLOMB_ENV=aws`, snapshot ID/data date/bucket/prefix, `/tmp/aplomb-data` cache directory, all three table names, worker function, model IDs, source user agent, exact CloudFront/localhost origins, the 180 second hard run budget and 2/12/12 revise/model/research limits. Both functions receive the worker name without a self-reference cycle. CORS allows GET/POST/PUT/PATCH/DELETE/OPTIONS and content-type, session, idempotency, request ID and accept-language headers, and exposes the request ID, data version, build and `Retry-After` response headers (API Gateway replaces the backend's own CORS headers).

Guardrail ID/version are deliberately absent while disabled. To enable, freeze a version, implement and test model output application, add only `bedrock:ApplyGuardrail` on its exact ARN, pass both env fields and change the flag after review. Browser navigation, content extraction and citation capture were verified live on 2026-11-15 ([evidence](evidence/agentcore-browser-2026-11-15.json)). To enable open web, add `research_open_web` to the release's `features`: the stack then grants the worker the three browser actions above and sets the flag.

## Deployment and evidence sequence

1. Complete T03/T08 and native packaging, then synth application mode. Inspect the exact template/IAM with root before deployment. Preserve artifact hashes, revision and data version.
2. All AWS operations use the official AWS MCP `run_script`/`call_boto3`, not shell AWS CLI or `cdk deploy`. Discover only Aplomb resources. Do not inspect organizer stack outputs/parameters. Bootstrap/asset upload and CloudFormation deploy are still operator work: publish the generated asset via MCP S3 presigned upload and provide its bucket/key/version to the template, or use an operator-reviewed CDK publishing path. Do not submit an unresolved CDK asset parameter or claim synth is deployment.
3. Upload validated immutable snapshot and manifest/hash using MCP S3 access. Verify GetObject bytes and hash; record S3 version ID. Confirm API default persona data can load; this foundation does not manufacture data.
4. Build the actual Next static export with `NEXT_PUBLIC_APLOMB_API_BASE=<output>/v1` and `NEXT_PUBLIC_APLOMB_FIXTURES=false`. Upload export preserving MIME types, invalidate only this distribution, test every deep route and missing route. Never upload fixture output as live.
5. Record `/health`, `/v1/meta`, CORS, session-isolation, idempotency/duplicate worker delivery, cancellation, quota errors and a real persisted model run. Save sanitized request/run IDs, model/token counts, manifest/hash, DynamoDB checkpoints, correlated logs and UI recording before shutdown. The release records at the top of this file hold that proof for each backend release.

Retain previous web object versions/artifact/revision for rollback; avoid incompatible DynamoDB item changes. A previous signed run stays immutable. To disable a broken capability update the flag and deploy reviewed config. No automated teardown or destructive bucket cleanup is configured; all persistent resources are retained. Organizer shutdown policy controls final cleanup.

## Known checks and blockers

The infra tests plus offline synth pass. AWS CloudFormation ValidateTemplate also accepted the generated foundation template (no IAM capabilities, BootstrapVersion parameter); its hash is recorded in preflight evidence. API/worker integration, the native package runtime probe, snapshot upload, real worker persistence and the deployed web smoke were later completed in AWS (see the release records); the test fixtures do not satisfy them. The isolated preflight Guardrail remains retained in DRAFT. Its denied-topic probe blocked and educational probe passed; it is not a numeric truth checker.

The pinned latest CDK library 2.277.0 audit reports moderate minimatch glob-parts amplification advisory GHSA-g3hv-75wg-m249 in its bundled development tooling. No untrusted glob expressions are accepted here. No automatic dependency downgrade/force fix was applied; review a supported upstream fix before exposing synth to untrusted input.

## Full architecture audit release

The follow-up release publishes API and worker version 1. API Gateway invokes the published API; every new run privately pins the worker ARN used for creation and resume. The worker role, inline policy and version-specific async delivery configuration are retained per release. Queue event age is now 60 seconds, matching the binding queued-start watchdog. The worker only reads/writes the runs table; API Bedrock access is limited to the parser model. See the [live evidence](evidence/full-architecture-audit-2026-11-14.json). No transactional outbox, scheduled recovery or global capacity reservation is claimed.
