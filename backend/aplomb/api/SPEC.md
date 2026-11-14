# API, repositories and asynchronous dispatch

**Track:** T03. **Tier:** P0; optional endpoints follow their flags. **Authority:** [HTTP contract](../../../contracts/api.md), [types](../../../contracts/schemas.md), [lifecycle](../../../contracts/run-events.md).

## 1. HTTP boundary

Implement all P0 routes including `/check/batch`; add P1 routes behind the exact catalog flags. Routers: service, assets, profiles, checks, runs, world, replay, datasets. Route functions only validate inputs, resolve session context, invoke services and serialize outputs. Numbers and verdicts come from services, never route-specific logic.

Generate request IDs, validate `X-Aplomb-Session` as `s_` + UUIDv4, attach data version headers on errors too, and use a single exception mapper. `/health` and `/meta` are session-free. Every other route validates ownership before looking up subordinate facts/evidence or invoking a worker. Cross-session resources return 404. CORS is an explicit origin allow-list; bearer session capability is not user authentication and has no CORS-based authorization shortcut.

## 2. Service interfaces

```python
class CheckService(Protocol):
    def check(self, session_id: str, request: CheckRequest) -> CheckResult: ...

class RunService(Protocol):
    def create(self, session_id: str, request: RunCreate,
               idempotency_key: str | None) -> RunAccepted: ...
    def get(self, session_id: str, run_id: str, since: int | None = None) -> Run: ...
    def answer(self, session_id: str, run_id: str, answer: RunAnswer) -> RunAccepted: ...
    def cancel(self, session_id: str, run_id: str) -> RunStatusResponse: ...

class Dispatcher(Protocol):
    def dispatch(self, run_id: str, generation: int) -> None: ...
```

Profile CRUD delegates to [ProfileService](../profiles/SPEC.md). World/historical routes delegate to their modules. Batch check preserves item order, max five, converts per-item failures to `ApiError`, does not abort successful items. Parser calls the fast model; parser unavailability must leave manual form usable.

## 3. Create, claim and terminal writes

1. Resolve effective profile, window, data manifest and feature eligibility. Persist pinned inputs in private run state with queued metadata.
2. Reserve idempotency key atomically under session + endpoint, TTL 10 minutes, with canonical request digest. Same key and body returns original run; changed body returns 409. Concurrent identical creations cannot dispatch separate runs.
3. Invoke worker asynchronously with only `{runId, generation}`. If enqueue fails, persist failed metadata and expose 503; never leave an apparently healthy queued run without recovery.
4. Worker claims queued state with a conditional update, owner token and heartbeat/lease. Duplicate delivery while lease active is a no-op. Stale lease recovery resumes a checkpoint with a new generation; old workers cannot write.
5. Each checkpoint atomically advances revision/generation and updatedAt. A terminal conditional write requires current ownership and running state. Cancellation wins over later stale writes. Check cancellation between steps/tools.

Use an outbox/queued-run recovery scan if a crash between persistence and enqueue is supported; otherwise the poll watchdog marks an unstarted run failed after 60 s per the lifecycle. Explicitly test this failure window. A running run uses worker heartbeat and hard-budget watchdog, not the queued timer. An expired waiting-input run is cancelled on access and by scheduled cleanup when available.

## 4. Storage and cache keys

| Table | Keys / use |
|---|---|
| `aplomb-profiles` | `SESSION#sid` / `PROFILE#pid` or `OVERLAY#pid`; condition on version |
| `aplomb-runs` | `RUN#rid` / `META`, `STATE`, `STEP#0001`, `FACT#F-001`, `EVID#E-001` |
| `aplomb-cache` | namespace + SHA-256 canonical key; value/reference, createdAt, expiresAt, source/data version |

Run `bySession` GSI uses `SESSION#sid` + timestamp/run ID. The `byProfile` GSI must include **session ID**, effective profile version, kind and data version (override the earlier unscoped shorthand in lifecycle). Query and verify ownership even after using an index. Read-after-write polls use consistent base-table reads as needed; GSIs can lag.

Cache key dimensions: session, effective profile ID/version, snapshot, currency, asOf, window, language, relevant flags and method version. Immutable dataset caches may be shared; user edits, drafts, briefs and request-specific ledgers may not. Cache deterministic calculations separately from model prose. DynamoDB items must stay below service limits: store large signed bundles/documents in S3 with integrity hash; full API responses are assembled after authorization.

## 5. Polling and browser behavior

`since` is a completed-step watermark, **not the highest observed running step**. A step appears as running then updates under the same seq; advancing before done would lose completion. Server deltas include newly completed/running steps above watermark and their referenced facts/evidence; client upserts by seq and ID. On terminal transition client fetches one full run to get the complete signed result. See lifecycle correction. Full response without `since` always remains available.

Enforce per-session limits with an atomic limiter; API Gateway aggregate throttling alone does not implement session quotas. Keep 1-second polls below configured limits. Oversize inputs fail before model/network calls.

## 6. Acceptance and handoff

API-01 errors/validation match envelope and required headers. API-02 session isolation on all nested resources. API-03 concurrent idempotency and body mismatch. API-04 duplicate invocation/lease race. API-05 cancellation versus terminal write. API-06 waiting answer is versioned and only consumed once. API-07 two sessions editing Robert get different brief caches. API-08 deltas preserve completed updates and final fetch. API-09 large bundle spill and hash validation. API-10 every disabled feature returns 501 and UI agrees.

Provide T08 repository and dispatcher fakes before AWS integration; provide web owners a local API plus representative error responses. Done means all P0 endpoints validate against shared models, with no fixture data returned as genuine execution.
