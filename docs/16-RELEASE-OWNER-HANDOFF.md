# Release owner handoff

The user confirmed a teammate owns production deployment. This audit has not altered AWS settings or published code. Local baseline is `e27e0b62668752adafcdcee6b572d6d0a42a3b3c` plus the uncommitted hardening diff. Preserve the existing untracked `.playwright-mcp/` work and ignored `.env`; never package either.

## Immediate release blocker

The live dashboard offers custom dates, but these requests both return 422:

```text
GET /v1/profiles/robert/overview?window=custom&start=2024-01-01&end=2025-01-01
GET /v1/profiles/robert/performance?window=custom&start=2024-01-01&end=2025-01-01
```

The local backend includes custom-window support from the latest pull, plus a selected-period return fact consumed by the local KeyFigures component. Release them together. Current observed frontend: `e27e0b6`; backend stack revision: `9f10301`; worker version 2. Do not deploy a frontend that expects new facts against the old backend.

## Source and artifact preparation

Review the working diff, preserve teammates' changes, run the existing gates and commit the intended source before assigning the full SHA to a release. `APLOMB_BUILD_REVISION` now accepts a full 40-character Git SHA and is exposed as `X-Aplomb-Build`; CDK sets it when application.revision is a full SHA. No backend revision should be inferred from the frontend manifest.

```bash
UV_CACHE_DIR=/tmp/aplomb-uv-cache uv sync --locked
npm ci --cache /tmp/aplomb-npm-cache
npm --prefix infra ci --cache /tmp/aplomb-npm-cache
UV_CACHE_DIR=/tmp/aplomb-uv-cache npm run check
npm run build:web
UV_CACHE_DIR=/tmp/aplomb-uv-cache bash infra/scripts/package-backend.sh
```

The existing package script uses binary Linux/Python 3.12 wheels and checks native imports and actual handlers in the pinned AWS Lambda image. Include the packaged world bundle. Do not bundle the Tiingo key, `.env`, AWS files or local session state. The key is local-only and masked by Settings; public Tiingo redistribution has not been established by this audit.

## Paired release and rollback

Before changing routing, retain the prior complete template/configuration, API version, worker version 2 and its role/async delivery settings, snapshot identifiers and the previous frontend artifact with object version IDs. Use the existing official AWS MCP deployment procedure and the site workflow. Do not remove retained versions or apply a broad infrastructure rewrite.

Build a reviewed CloudFormation change set with the new immutable artifact and full source revision, inspecting changes for unintended replacement. Keep provider flags truthful. Preserve existing supported flags; sabotage/facilities/open-web/on-demand remain unavailable. Set sourceUserAgent to a descriptive contact URL (the existing project repository URL suffices for the reviewed transport) so official-source tools can register. Do not claim SEC/GDELT are operational: observed probes were 403/timeout.

After release, validate `/meta`, `X-Aplomb-Build`, frontend deployment SHA, the two custom-window requests, matching fact/chart period, Robert real decision and evidence, session 404, Time Machine/reveal immutability, already-met Amira goal, and a source-backed event brief. Read CloudWatch by discovered log-group names. Retain audited sentence removals; they are not successful factual assertions.

Rollback restores the previous API invocation target and its worker pin plus configuration, then republishes the previous complete frontend artifact and invalidates CloudFront. Keep DynamoDB/S3 state and prior immutable runs. No rollback drill was performed here; the release owner must confirm the stored artifacts and exact change set before publication.

## Test-only and incomplete features

Sabotage has real auditor tests but no honest runnable child workflow. Its current `briefBeforeAudit: Brief` schema requires a signed audit and cannot represent an unsigned attempt. A reviewed contract revision is necessary; do not fake a signature or advertise a controlled test as a live writer attempt.

Event handoff IDs are persisted through originalText as **untrusted context**; the backend does not attest the event/holding/source-run relationship. A future typed lineage contract is preferable. No causal stock-return impact is inferred.

The full connector inventory, local/live tests, known limits and demonstration status are in [the release report](12-RELEASE-HARDENING.md), [connector inventory](13-EXTERNAL-DATA-INVENTORY.md), [trust audit](14-TRUST-AUDIT.md) and [World handoff](15-WORLD-DECISION-HANDOFF.md).
