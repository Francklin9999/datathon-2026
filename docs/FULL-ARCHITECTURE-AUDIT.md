# Full architecture audit — 2026-11-14

**Assessment: 82/100, launchable with caveats for the fictional-investor demo.** This is an engineering review of the checked-out source and the Aplomb AWS deployment, not a formal security certification or a load-test result. A larger public service needs the recovery and admission-control work below. Remote CI cannot verify the current uncommitted worktree.

## Findings and upgrades

| Severity | Finding | Resolution |
|---|---|---|
| High | API Gateway and asynchronous dispatch invoked mutable Lambda code. A deployment could change a queued/resumed run's runtime. Shared mutable IAM could also revoke an older worker's required grants. | Published API/worker versions; pinned the worker version into private prepared state; restricted dispatch to numeric versions of this one project function; retained release-specific roles, policies, versions and delivery configurations. The API integration now points to a numbered API version. |
| Medium | Advertised execution budgets were not fully connected to execution: the worker used hard-coded time/call/revision caps. | Execution uses the repository deadline and validated configured limits, with fixed global ceilings. Optional research/revision preserves inference capacity for writing and review. Budget settings participate in cache identity. |
| Medium | A stale GSI membership could return an older profile's brief because cache lookup checked the grouping but not all current base-record dimensions. | Recheck session ownership, current profile/version, snapshot, manifest digest, window, language and runtime signature against the authoritative record. A stale-index regression test covers the race. |
| Medium | A worker could start a queued run after the browser's documented start deadline if nobody had polled it. | Apply the queued watchdog before claiming, and align Lambda asynchronous event age with the contract's 60-second queued-start deadline. This prevents spending inference on already-expired work; it does not add automatic recovery. |
| Medium | Artifact verification checked listed hashes but could miss extra unlisted files added after the runtime import probe. | Require a complete manifest inventory and reject symlinks or unlisted/missing files before synthesis. |
| Medium | Token telemetry discarded provider cache counters. | Preserve provider-reported usage per attempt and use the pinned SDK's cache-accounting rule to avoid counting cached prompt input twice. These counters are not a reconciled billing report. |
| Low | Focus cards reproduced whole brief sections, causing a duplicate wall of text on Home. | Each focus card now uses a short, surviving audited sentence; the complete brief remains available below it. |

No change weakens the code-owned quant/rule checks, numerical token grammar, required independent review, frozen output Guardrail, session ownership or immutable terminal runs.

## Boundary review

| Boundary | Evidence and conclusion |
|---|---|
| Browser and wire validation | Successful responses are checked against generated schemas. Polling backs off, pauses on hidden tabs and refetches a full terminal run. Struck sentences remain hidden in normal mode. Static deep routes and real 404s were exercised on CloudFront. |
| API and tenancy | Session capabilities are validated server-side; protected state is read through ownership checks. User-provided run/profile IDs are authorized again before nested use. Body size is bounded while streaming. Explicit CORS is present; it is not authentication. |
| Public access and quotas | This is an anonymous simulation with bearer capabilities, not authenticated financial accounts. Session quotas, API throttling and reserved concurrency limit work. Rotating session IDs can still saturate capacity; there is no global admission reservation. |
| Models and tool execution | Strands is pinned, implicit retries are disabled, schema repair is bounded and charged, and physical attempts are recorded. Computation names are enumerated; mandatory calculations and rules cannot be skipped by a model. Research remains disabled in the production composition. |
| Planning semantics | Production controls currently run their deterministic scenario set and do not honor arbitrary planner task arguments or scenario proposals. Planning can clarify inputs and propose revisions, but those proposals are not evidence of executed tools. `toolCalls` correctly remains zero for the mandatory code phases. This is a remaining design simplification opportunity. |
| Calculation provenance | The worker verifies the pinned manifest and reads through a temporal gate. Computed facts reference actual aligned-input hash receipts and hypothetical allocation assumptions. This is traceable lineage, not an independent reimplementation of every formula. Numeric controls and regression tests provide separate calculation checks. |
| Writing and audit | Models cannot supply authoritative formatted numbers. Reference resolution, numeric grammar, relation checks, provenance, rule assumptions and required model review precede signing. A digest provides integrity evidence; it is not an asymmetric digital signature. |
| Persistence | Revision-fenced transactions enforce leases, generation ownership, idempotency and terminal immutability. Larger ledgers remain atomic through aggregate documents and checksum-verified S3 spill. Base-table Query avoids redundant child reads; GSI rows still receive authoritative ownership rereads. |
| IAM | The worker no longer reads profile/cache tables or inherits unnecessary DynamoDB write actions; it receives the pinned profile in run state. The API IAM grant is limited to qualified ARNs of the project worker; dispatch code additionally restricts the qualifier to numeric versions. The API can invoke only the parsing/writing model. The worker has exact model/profile and snapshot/evidence permissions. No broad managed execution policy is attached. |
| Release and rollback | Versioned API integration and per-run worker routing preserve release identity. Release IAM and delivery resources are retained. Old versions must not be manually removed while runs reference them. Runtime-signature changes fail closed rather than silently mix incompatible execution configurations. |
| Operations | A retained encrypted failure destination, run-correlated EMF logs, custom outcome/token metrics, dashboard and alarms exist. There is no paging target, scheduled watchdog or demonstrated autonomous redrive. `/health` is liveness; it does not prove every dependency is healthy. |
| CI and dependencies | The locked install, Python checks, web contracts/type checking, numeric/spec checks, CDK assertions and runtime packaging probe run locally. Workflow configuration is present. Hosted CI for this uncommitted release, dependency-advisory scanning and an account-wide security review were not verified. |

## Highest-value next upgrades

1. **Transactional dispatch outbox.** Write a dispatch record in the same DynamoDB transaction as run creation/resume, then deliver it through a filtered DynamoDB Streams consumer. That closes the persist-before-invoke crash window. Keep generation fences and numeric-version routing; use conditional acknowledgement, bounded retry and the existing failure destination. Prove it by crashing after persistence, redelivering the same outbox event, and checking that only one worker owns the run. No outbox or stream consumer is claimed in the current release.
2. **Admission control and load evidence.** Reserved concurrency is two workers while a session may create six runs per minute. Long-running bursts can exceed the queued-start deadline. Reserve global capacity before accepting work, return a clear retry response when full, and test bursts across multiple sessions. Do not infer throughput guarantees from the successful individual live runs.
3. **Make planner proposals operational or simplify the planner.** Either execute a deliberately small, typed set of bounded scenario proposals through code controls with traceable outputs, or remove unused planning options for confirmed requests. Do not add more agent roles until each changes a verifiable decision.
4. **Operational readiness for a public service.** Add an owned paging destination, targeted readiness checks, retention/cleanup procedures for retained releases and evidence blobs, and a tested recovery exercise. For real personal data, introduce authenticated identities and bind server-side tenancy to them.

## Release operating rules

- Roll back by restoring the previous complete application template and its pinned S3 code version; keep the retained worker version/role/policy/delivery configuration available for old runs. Repoint the API integration to a retained API version only after checking compatibility with persisted data.
- The first migration from the previous unqualified deployment was checked for active work before promotion. Future runs carry a numeric worker ARN in private state. The Lambda function's reserved concurrency is shared by its versions, so retaining versions does not increase the concurrency budget.
- Bump the runtime contract marker when calculation/audit semantics change; the cache also includes model, policy, feature, budget and data-prefix dimensions. Do not reinterpret an old signed result under a new contract.
- Lambda versions and retained IAM policies are operationally frozen by deployment convention, not protected against a trusted administrator changing IAM manually.
- A clarification answer currently starts a new wall-clock segment while inference/revision counters remain cumulative. If cumulative active wall time across human pauses becomes a requirement, persist consumed active time explicitly.

See [architecture and demo guide](AWS-ARCHITECTURE.md), the [previous live evidence](../infra/evidence/aws-architecture-2026-11-14.json), and the [live audit-release evidence](../infra/evidence/full-architecture-audit-2026-11-14.json), and the [structured audit report](evidence/full-architecture-audit-20261114.json).
