# T03 HTTP and persistence handoff

T03 implements HTTP and durable execution boundaries. Portfolio calculations,
profile defaults, model workflows, research, ledger signing, world feeds and
historical execution still require T04–T12. Missing P0 providers return typed
`503 upstream_unavailable`; gated features return `501 feature_disabled`. No
shared fixture is an application provider.

## Local entry points

From the repository root, run `uv sync --locked`, then:

```bash
APLOMB_DATA_VERSION=snap-20261113-starter \
APLOMB_LOCAL_STATE_FILE=/tmp/aplomb-local-state.json \
uv run uvicorn aplomb.api.app:app --reload --port 8000
```

Base URL: `http://localhost:8000/v1`. `/health` has no dependencies. Configured
`/meta` reports snapshot identity, zero assets until datastore injection, and
disabled capabilities. Without a pinned snapshot `/meta` returns 503. The
[environment example](../.env.example) is documentation, not an implicit dotenv
loader. Set actual deployment/model configuration explicitly; never store keys.

HTTP factory: `aplomb.api.app:create_app(settings, services=None)`; conventional
export: `aplomb.api.app:app`; AWS HTTP v2/REST adapter:
`aplomb.api.lambda_handler:handler` (Mangum). Imports and application creation
perform no AWS/model calls. AWS clients are constructed lazily on first storage
operation. Every data endpoint requires the session bearer capability header;
this is not login. HTTP OpenAPI is disabled; `app.openapi()` is available offline.

## Domain composition

`aplomb.api.services.Services` defines explicit ProfileService, CheckService,
DataService, ParserService, WorldService and ReplayService protocols. Methods take
session IDs and shared models, never FastAPI requests. Set `capabilities` only
after verifying a provider; a feature also needs its matching Settings flag.
Facilities/hazards additionally need the parent `world_explorer` capability.

Use `ServiceError(code, message, details=None)`, `Conflict`, or `NotFound` from
`aplomb.api.errors`. Missing optional error details are omitted. Unexpected
exceptions are sanitized. Every error, validation, CORS rejection and oversize
rejection includes request/data-version headers. Batch items preserve order and
fail independently. Queries retain repeated category/country/origin as lists,
validate limits/dates/bbox/profile IDs, and default `lang` from Accept-Language.
Providers own remaining domain constraints and source/cursor validation.

T04 supplies datastore/manifest loading. T05/T06 supply deterministic checks,
default profiles, overlay merging and derivation. Routes authorize profile/draft
references before mutations; domain services must enforce ownership when workers
call them directly. T11/T12 supply world/historical providers. T10 may replace
`fact_resolver`; its default only projects actual stored sentence/rule references
and one-level inputs. It does not create facts or interpretations.

T08 provides a `RunPreparer(session_id, CreateRunRequest) -> PreparedRun` and real
worker. `PreparedRun` contains authorized shared RunInput wire data with resolved
window/fields, as-of/data version, private pinned profile/manifest/context and
effective profile version. Preparation does not invoke models.

```python
from aplomb.api.app import create_app
from aplomb.api.composition import create_repositories
from aplomb.api.dispatcher import LocalDispatcher
from aplomb.api.services import RunCoordinator, Services

profile_repo, run_repo, cache = create_repositories(settings)
dispatcher = LocalDispatcher(worker_callable)  # worker_callable(event_dict)
runs = RunCoordinator(run_repo, dispatcher, prepare_callable)
services = Services(profiles=profile_service, checks=check_service, runs=runs)
application = create_app(settings, services)
```

For AWS use `LambdaDispatcher(injected_lambda_client, worker_function)`; payload
is exactly `{runId, generation}`. The planned `aplomb.agents.worker:handler`
remains T08-owned. Default composition never dispatches an absent worker.

Optional `RunCoordinator.cached_brief(session_id, request)` resolves an already
persisted succeeded portfolio brief. Its provider must verify the effective
profile/version, snapshot, language and window. The same-context cache callback
resolves through the same atomic idempotency reservations as newly-created runs.

## Worker protocol and races

`RunRepository.claim(run_id, generation)` returns `RunRecord` or None. Records
carry run/revision/generation/owner/lease_until/started_at/private/profile_version.
Duplicate active delivery is a no-op. Stale-lease recovery increments generation;
use the generation returned by claim, not the original event generation.

Persist with `checkpoint(run_id, generation, owner, revision, run, private=None)`
and retain the returned record. `heartbeat(record)` renews its lease and revision.
Default leases last 30 seconds; renew well before expiry and check cancellation
between tools. Conditional revision/generation/ownership/state writes reject
stale workers. Cancellation invalidates generations. All terminal states are
immutable; completed steps, facts and evidence cannot be changed/deleted. Running
steps can update under their existing sequence number.

Answers consume a waiting question once, persist private answer state and dispatch
a new generation. Waiting runs cancel after 30 minutes on access. Queued runs
fail when polled after 60 seconds without a start, covering a crash between
persistence and enqueue. Running runs use the 180-second hard budget. There is
no outbox, scheduled cleanup or automatic stale-worker redispatch here; T08/an
operator may explicitly redispatch stale leases. Enqueue failures persist failed
runs and return 503. Worker exceptions must checkpoint their own durable errors.

Run creation reserves session+endpoint+key and canonical validated body digest
atomically for ten minutes. Existing reservations resolve before mutable
preparation. Concurrent identical creates dispatch once; changed bodies conflict.
An active/cancelled idempotent retry replays the original queued acceptance;
GET is authoritative for current status. Poll deltas use completed-step watermarks
and include referenced/transitive input facts and referenced evidence. Upsert by
sequence, and fetch a full run at terminal status. Stored-run/fact responses keep
their pinned data-version header after snapshot changes.

## Storage and infra agreement

MemoryStore, FileStore and DynamoStore share revision-conditioned transactions.
FileStore uses flock, fsync and atomic rename for local filesystems, not NFS.
DynamoDB keys are lowercase string `pk`/`sk`:

| Table | Partition/sort |
| --- | --- |
| runs | `RUN#rid` / META, STATE, STEP#0001, FACT#F-001, EVID#E-001 |
| profiles | `SESSION#sid` / PROFILE#pid or OVERLAY#pid |
| cache | IDEMPOTENCY#digest / RESERVATION, cache and limiter namespaces |

META alone owns GSIs. `bySession`: sessionKey/sessionSort; `byProfile`:
profileKey/profileSort. Profile partition:
`SESSION#sid#PROFILE#pid#Vversion#kind#dataVersion`; sorts: `createdAt#rid`.
Verify ownership after indexes. Polls use consistent base reads and a stable
revision retry. GSI lists may lag; polling the returned run ID is authoritative.

Each checkpoint atomically writes META/STATE plus changed children. At most 97
children may change per checkpoint; larger writes fail before transaction
mutation, so workers must checkpoint smaller batches. Large records spill to
private S3 `evidence/run-bundles/{sha256}.json`, with hash/length checks on reads.
Dynamic spill thresholds and a conservative 3.5 MB encoded transaction cap protect
the DynamoDB aggregate limit. A failed CAS can leave an unreferenced immutable S3
object; lifecycle cleanup is operational. Authorization precedes blob reads.

Profile repository revisions provide optimistic versions. User-cache dimensions
require session, effective profile ID/version, snapshot, currency, as-of, window,
language, flags and method version. Expiry is checked in code; TTL is cleanup.
Sliding session quotas use atomic store transactions across HTTP processes;
Gateway aggregate throttling does not replace session limits.

## Verification and remaining gates

Run `.venv/bin/pytest backend/tests/api -q` or `uv run pytest backend/tests/api`.
Tests cover races/isolation/idempotency, lease recovery/cancellation/answers,
watchdogs, deltas, profile/cache versions, HTTP errors/CORS/limits, quotas,
Lambda v2, real botocore request-shape stubs, S3 integrity/aggregate spill and a
local worker finishing after its HTTP response with a fresh FileStore reader.
Examples are explicitly synthetic test data; no test makes real AWS/model calls.

Live DynamoDB/S3/Lambda remains an opt-in integration gate for T02/T08. Installed
Starlette TestClient warns about deprecated httpx support; Mangum warns about
legacy event-loop initialization. These warnings do not skip tests. Real `/check`,
worker signing, manifests and remaining P0 domain acceptance still require their
owners and cannot be claimed complete from these boundary checks.
