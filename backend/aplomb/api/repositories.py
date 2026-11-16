"""Session-scoped repositories and conditional durable worker checkpoints."""

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Callable

from aplomb.contracts.models import Run

from .errors import Conflict, NotFound, unavailable
from .storage import Store, Write, canonical

TERMINAL = frozenset({"succeeded", "failed", "cancelled"})
# Identical portfolio briefs share one run: the lock outlives the longest possible run by this much.
BRIEF_LOCK_SK = "LOCK"
BRIEF_LOCK_GRACE_SECONDS = 60


def brief_lock_key(identity: list) -> str:
    """Cache-table key of the in-flight lock for one brief identity (session, profile and its
    version, data version, manifest digest, brief runtime identity, window, language)."""
    return "BRIEF#" + hashlib.sha256(canonical(identity)).hexdigest()


def timestamp(epoch: float) -> str:
    from datetime import UTC, datetime

    return (
        datetime.fromtimestamp(epoch, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )


def _close_running_steps(payload: dict, now: float) -> None:
    """A terminal run keeps no step in progress: the stale worker can no longer close it."""
    from datetime import datetime

    for step in payload["steps"]:
        if step["status"] != "running":
            continue
        started = datetime.fromisoformat(step["startedAt"].replace("Z", "+00:00")).timestamp()
        step.update(
            status="failed",
            endedAt=timestamp(now),
            durationMs=max(0, (now - started) * 1000),
            summary={
                "en": f"Step {step['type']} interrupted before completion.",
                "fr": f"Étape {step['type']} interrompue avant la fin.",
            },
        )


@dataclass
class RunRecord:
    run: Run
    revision: int
    generation: int
    owner: str | None
    lease_until: float
    started_at: float | None
    private: dict
    profile_version: int | None = None


class RunRepository:
    def __init__(
        self,
        store: Store,
        clock: Callable[[], float] = time.time,
        hard_seconds: int = 180,
        lease_seconds: int = 30,
    ):
        self.store, self.clock = store, clock
        self.hard_seconds, self.lease_seconds = hard_seconds, lease_seconds

    @staticmethod
    def _indexes(record: RunRecord) -> dict:
        run = record.run
        sort = f"{run.created_at}#{run.run_id}"
        indexes = {"sessionKey": f"SESSION#{run.session_id}", "sessionSort": sort}
        if run.profile_id:
            indexes.update(
                profileKey=(
                    f"SESSION#{run.session_id}#PROFILE#{run.profile_id}"
                    f"#V{record.profile_version}#{run.kind}#{run.data_version}"
                ),
                profileSort=sort,
            )
        return indexes

    def _writes(self, record: RunRecord, previous: RunRecord | None) -> list[Write]:
        run = record.run.to_wire()
        pk = f"RUN#{record.run.run_id}"
        old_rev = previous.revision if previous else None
        writes = []
        for field, prefix in (("steps", "STEP"), ("facts", "FACT"), ("evidence", "EVID")):
            entries = run.pop(field)
            old_entries = (
                getattr(previous.run, field) if previous else ([] if field == "steps" else {})
            )
            if field == "steps":
                entries = {f"{s['seq']:04d}": s for s in entries}
                old_entries = {f"{s.seq:04d}": s.to_wire() for s in old_entries}
            else:
                old_entries = {key: value.to_wire() for key, value in old_entries.items()}
            if not set(old_entries) <= set(entries):
                raise Conflict("Checkpoints cannot delete prior steps, facts or evidence")
            for key, value in entries.items():
                if key in old_entries and value == old_entries[key]:
                    continue
                if key in old_entries:
                    if field != "steps" or old_entries[key]["status"] != "running":
                        raise Conflict("Completed steps, facts and evidence are immutable")
                    # Every child retains its own last-write revision.
                    stored = self.store.get("runs", pk, f"{prefix}#{key}")
                    expected = stored["revision"] if stored else None
                else:
                    expected = None
                writes.append(
                    Write(
                        "runs",
                        pk,
                        f"{prefix}#{key}",
                        {"revision": record.revision, "type": prefix, "value": value},
                        expected,
                    )
                )
        writes.extend(
            [
                Write(
                    "runs",
                    pk,
                    "META",
                    {"revision": record.revision, "type": "META", "run": run},
                    old_rev,
                    self._indexes(record),
                ),
                Write(
                    "runs",
                    pk,
                    "STATE",
                    {
                        "revision": record.revision,
                        "type": "STATE",
                        "generation": record.generation,
                        "owner": record.owner,
                        "leaseUntil": record.lease_until,
                        "startedAt": record.started_at,
                        "private": record.private,
                        "profileVersion": record.profile_version,
                    },
                    old_rev,
                ),
            ]
        )
        if len(writes) > 99:
            # Atomically publish a large ledger as one document (S3-spilled by DynamoStore).
            # This retains the same revision fence and immutability checks above instead
            # of exposing partially written batches or exceeding DynamoDB's item limit.
            old_bundle = self.store.get("runs", pk, "LEDGER")
            writes = [w for w in writes if w.value["type"] not in {"FACT", "EVID"}]
            writes.append(Write("runs", pk, "LEDGER", {
                "revision": record.revision, "type": "LEDGER",
                "facts": {k: v.to_wire() for k, v in record.run.facts.items()},
                "evidence": {k: v.to_wire() for k, v in record.run.evidence.items()},
            }, old_bundle["revision"] if old_bundle else None))
        return writes

    def _read(self, run_id: str, session_id: str | None = None) -> RunRecord:
        pk = f"RUN#{run_id}"
        for _ in range(8):
            meta = (
                self.store.get_owned("runs", pk, "META", session_id)
                if session_id is not None
                else self.store.get("runs", pk, "META")
            )
            if not meta or (session_id is not None and meta["run"]["sessionId"] != session_id):
                raise NotFound()
            children = self.store.query("runs", pk)
            after = self.store.get("runs", pk, "META")
            if not after or after["revision"] != meta["revision"]:
                continue
            state = next(item for item in children if item["type"] == "STATE")
            if state["revision"] != meta["revision"]:
                continue
            payload = dict(meta["run"])
            payload["steps"] = sorted(
                [i["value"] for i in children if i["type"] == "STEP"], key=lambda s: s["seq"]
            )
            payload["facts"] = {
                i["value"]["id"]: i["value"] for i in children if i["type"] == "FACT"
            }
            payload["evidence"] = {
                i["value"]["id"]: i["value"] for i in children if i["type"] == "EVID"
            }
            for item in children:
                if item["type"] == "LEDGER":
                    payload["facts"].update(item["facts"])
                    payload["evidence"].update(item["evidence"])
            return RunRecord(
                Run.model_validate(payload),
                meta["revision"],
                state["generation"],
                state["owner"],
                state["leaseUntil"],
                state["startedAt"],
                state["private"],
                state["profileVersion"],
            )
        raise unavailable("Run snapshot; retry polling")

    def create(
        self,
        run: Run,
        private: dict,
        profile_version: int | None,
        idempotency_key: str | None = None,
        request_body: dict | None = None,
        brief_lock: str | None = None,
    ) -> tuple[RunRecord, bool]:
        """Persist a new run, or return ``(existing, False)``.

        ``brief_lock`` (a ``BRIEF#…`` key from ``brief_lock_key``) is written in the same transaction
        as the run. When another creation holds it with a run that is not finished, that run is
        returned instead, so concurrent identical briefs (two tabs, a double Refresh) share one run."""
        if idempotency_key is not None and not 1 <= len(idempotency_key) <= 128:
            from .errors import ServiceError

            raise ServiceError("validation_error", "Idempotency-Key must contain 1–128 characters")
        reservation_pk = (
            "IDEMPOTENCY#"
            + hashlib.sha256(canonical([run.session_id, "POST /runs", idempotency_key])).hexdigest()
        )
        digest = hashlib.sha256(canonical(request_body)).hexdigest()
        for _ in range(12):
            prior = (
                self.store.get("cache", reservation_pk, "RESERVATION") if idempotency_key else None
            )
            if prior and prior["expiresAt"] > self.clock():
                if prior["digest"] != digest:
                    raise Conflict("Idempotency-Key was already used with a different request")
                return self._read(prior["runId"], run.session_id), False
            lock = self.store.get("cache", brief_lock, BRIEF_LOCK_SK) if brief_lock else None
            if lock and lock["expiresAt"] > self.clock():
                held = self._held(run.session_id, lock["runId"])
                if held is not None and held.run.status not in TERMINAL:
                    return held, False
            record = RunRecord(run, 1, 1, None, 0, None, private, profile_version)
            writes = self._writes(record, None)
            if brief_lock:
                expected_lock = lock["revision"] if lock else None
                held_until = int(self.clock()) + self.hard_seconds + BRIEF_LOCK_GRACE_SECONDS
                writes.append(
                    Write(
                        "cache",
                        brief_lock,
                        BRIEF_LOCK_SK,
                        {"revision": (expected_lock or 0) + 1, "runId": run.run_id, "expiresAt": held_until},
                        expected_lock,
                        {"expiresAt": held_until},
                    )
                )
            if idempotency_key:
                expected = prior["revision"] if prior else None
                reservation = {
                    "revision": (expected or 0) + 1,
                    "digest": digest,
                    "runId": run.run_id,
                    "expiresAt": int(self.clock()) + 600,
                }
                writes.append(
                    Write(
                        "cache",
                        reservation_pk,
                        "RESERVATION",
                        reservation,
                        expected,
                        {"expiresAt": reservation["expiresAt"]},
                    )
                )
            try:
                self.store.transact(writes)
                return record, True
            except Conflict:
                if not idempotency_key and not brief_lock:
                    raise
        raise Conflict("Concurrent run creation; retry with the same key")

    def _held(self, session_id: str, run_id: str) -> RunRecord | None:
        try:
            return self.get(session_id, run_id)
        except NotFound:
            return None

    def held_brief(self, session_id: str, brief_lock: str) -> RunRecord | None:
        """The run that holds an unexpired brief lock of this session, in its current state (the
        queue and hard-budget watchdogs apply), or None."""
        lock = self.store.get("cache", brief_lock, BRIEF_LOCK_SK)
        if not lock or lock["expiresAt"] <= self.clock():
            return None
        return self._held(session_id, lock["runId"])

    def idempotent(self, session_id: str, key: str | None, body: dict) -> RunRecord | None:
        """Resolve a retry before preparing mutable profile/data dependencies."""
        if key is None:
            return None
        if not 1 <= len(key) <= 128:
            from .errors import ServiceError

            raise ServiceError("validation_error", "Idempotency-Key must contain 1–128 characters")
        pk = "IDEMPOTENCY#" + hashlib.sha256(canonical([session_id, "POST /runs", key])).hexdigest()
        prior = self.store.get("cache", pk, "RESERVATION")
        if prior and prior["expiresAt"] > self.clock():
            if prior["digest"] != hashlib.sha256(canonical(body)).hexdigest():
                raise Conflict("Idempotency-Key was already used with a different request")
            return self.get(session_id, prior["runId"])
        return None

    def get(self, session_id: str, run_id: str) -> RunRecord:
        record = self._read(run_id, session_id)
        now = self.clock()
        run = record.run
        age = (
            now
            - __import__("datetime")
            .datetime.fromisoformat(run.updated_at.replace("Z", "+00:00"))
            .timestamp()
        )
        expired_queue = run.status == "queued" and age >= 60
        expired_wait = run.status == "waiting_input" and age >= 1800
        expired_running = (
            run.status == "running"
            and record.started_at is not None
            and now - record.started_at >= self.hard_seconds
        )
        if expired_queue or expired_wait or expired_running:
            payload = run.to_wire()
            payload.update(
                status="cancelled" if expired_wait else "failed",
                question=None,
                result=None,
                updatedAt=timestamp(now),
            )
            if not expired_wait:
                payload["error"] = (
                    unavailable("Worker start" if expired_queue else "Worker hard budget")
                    .envelope("worker-watchdog")
                    .error.to_wire()
                )
            _close_running_steps(payload, now)
            updated = RunRecord(
                Run.model_validate(payload),
                record.revision + 1,
                record.generation + 1,
                None,
                0,
                record.started_at,
                record.private,
                record.profile_version,
            )
            try:
                self.store.transact(self._writes(updated, record))
                record = updated
            except Conflict:
                record = self._read(run_id, session_id)
        return record

    def reserve_existing(
        self, session_id: str, run_id: str, key: str | None, body: dict
    ) -> RunRecord:
        """Reserve an already-persisted cache hit under the same idempotency rules."""
        record = self.get(session_id, run_id)
        if key is None:
            return record
        pk = "IDEMPOTENCY#" + hashlib.sha256(canonical([session_id, "POST /runs", key])).hexdigest()
        for _ in range(12):
            existing = self.idempotent(session_id, key, body)
            if existing is not None:
                return existing
            prior = self.store.get("cache", pk, "RESERVATION")
            expected = prior["revision"] if prior else None
            if prior and prior["expiresAt"] > self.clock():
                continue
            value = {
                "revision": (expected or 0) + 1,
                "runId": run_id,
                "digest": hashlib.sha256(canonical(body)).hexdigest(),
                "expiresAt": int(self.clock()) + 600,
            }
            try:
                self.store.transact(
                    [
                        Write(
                            "cache",
                            pk,
                            "RESERVATION",
                            value,
                            expected,
                            {"expiresAt": value["expiresAt"]},
                        )
                    ]
                )
                return record
            except Conflict:
                continue
        raise Conflict("Concurrent cache reservation; retry with the same key")

    def list(self, session_id: str) -> list[Run]:
        records = self.store.query("runs", f"SESSION#{session_id}", "bySession")
        return sorted(
            [
                self.get(session_id, item["run"]["runId"]).run
                for item in records
                if item["type"] == "META" and item["run"]["sessionId"] == session_id
            ],
            key=lambda run: (run.created_at, run.run_id),
            reverse=True,
        )

    def claim(self, run_id: str, generation: int) -> RunRecord | None:
        record = self._read(run_id)
        now = self.clock()
        if record.generation != generation or record.run.status in TERMINAL | {"waiting_input"}:
            return None
        if record.run.status == "queued":
            # Apply the same queued-start deadline whether or not a browser polls.
            record = self.get(record.run.session_id, run_id)
            if record.run.status in TERMINAL:
                return None
        if record.run.status == "running" and record.lease_until > now:
            return None
        if record.run.status == "running":
            # Recovery invalidates every write by the expired worker.
            record_generation = record.generation + 1
        else:
            record_generation = record.generation
        if record.started_at is not None and now - record.started_at >= self.hard_seconds:
            self.get(record.run.session_id, run_id)
            return None
        payload = record.run.to_wire()
        payload.update(status="running", updatedAt=timestamp(now))
        claimed = RunRecord(
            Run.model_validate(payload),
            record.revision + 1,
            record_generation,
            secrets.token_hex(16),
            now + self.lease_seconds,
            record.started_at if record.started_at is not None else now,
            record.private,
            record.profile_version,
        )
        try:
            self.store.transact(self._writes(claimed, record))
            return claimed
        except Conflict:
            return None

    def checkpoint(
        self,
        run_id: str,
        generation: int,
        owner: str,
        revision: int,
        run: Run,
        private: dict | None = None,
    ) -> RunRecord:
        record = self._read(run_id)
        now = self.clock()
        if (
            record.revision != revision
            or record.generation != generation
            or record.owner != owner
            or record.run.status != "running"
            or record.lease_until <= now
        ):
            raise Conflict("Worker lease or checkpoint is stale")
        if record.started_at is not None and now - record.started_at >= self.hard_seconds:
            self.get(record.run.session_id, run_id)
            raise Conflict("Worker hard budget expired")
        before, after = record.run.to_wire(), run.to_wire()
        for key in (
            "runId",
            "sessionId",
            "profileId",
            "kind",
            "parentRunId",
            "lang",
            "asOf",
            "dataVersion",
            "input",
            "flags",
            "createdAt",
        ):
            if before[key] != after[key]:
                raise Conflict(f"Pinned {key} cannot change")
        if run.status not in {"running", "waiting_input", "succeeded", "failed"}:
            raise Conflict("Invalid worker transition")
        if run.status == "succeeded" and run.result is None:
            raise Conflict("Success requires an audited result")
        if run.status == "waiting_input" and run.question is None:
            raise Conflict("Waiting input requires a question")
        if run.status == "failed" and run.error is None:
            raise Conflict("Failure requires an error")
        if (
            (run.status != "succeeded" and run.result is not None)
            or (run.status != "waiting_input" and run.question is not None)
            or (run.status != "failed" and run.error is not None)
        ):
            raise Conflict("Run result, question and error must match its status")
        after["updatedAt"] = timestamp(now)
        updated = RunRecord(
            Run.model_validate(after),
            record.revision + 1,
            generation,
            owner if run.status == "running" else None,
            now + self.lease_seconds if run.status == "running" else 0,
            record.started_at,
            record.private if private is None else private,
            record.profile_version,
        )
        self.store.transact(self._writes(updated, record))
        return updated

    def heartbeat(self, record: RunRecord) -> RunRecord:
        return self.checkpoint(
            record.run.run_id, record.generation, record.owner, record.revision, record.run
        )

    def cancel(self, session_id: str, run_id: str) -> Run:
        for _ in range(8):
            record = self.get(session_id, run_id)
            if record.run.status in TERMINAL:
                raise Conflict("A terminal run is immutable")
            now = self.clock()
            payload = record.run.to_wire()
            payload.update(
                status="cancelled",
                question=None,
                result=None,
                error=None,
                updatedAt=timestamp(now),
            )
            _close_running_steps(payload, now)
            updated = RunRecord(
                Run.model_validate(payload),
                record.revision + 1,
                record.generation + 1,
                None,
                0,
                record.started_at,
                record.private,
                record.profile_version,
            )
            try:
                self.store.transact(self._writes(updated, record))
                return updated.run
            except Conflict:
                continue
        raise Conflict()

    def answer(self, session_id: str, run_id: str, question_id: str, value: str) -> RunRecord:
        record = self.get(session_id, run_id)
        if record.run.status != "waiting_input" or record.run.question.question_id != question_id:
            raise Conflict("This question is no longer awaiting an answer")
        options = record.run.question.options
        if options is not None and value not in {option.value for option in options}:
            from .errors import ServiceError

            raise ServiceError("validation_error", "Answer must be one of the question options")
        if not value or len(value) > 2000:
            from .errors import ServiceError

            raise ServiceError("validation_error", "Answer must contain 1–2000 characters")
        payload = record.run.to_wire()
        # Wire contract says running; ownerless running may be claimed immediately.
        payload.update(status="running", question=None, updatedAt=timestamp(self.clock()))
        private = dict(record.private)
        private["answer"] = {"questionId": question_id, "value": value}
        updated = RunRecord(
            Run.model_validate(payload),
            record.revision + 1,
            record.generation + 1,
            None,
            0,
            self.clock(),
            private,
            record.profile_version,
        )
        self.store.transact(self._writes(updated, record))
        return updated

    def dispatch_failed(self, session_id: str, run_id: str, generation: int) -> None:
        record = self.get(session_id, run_id)
        if record.generation != generation or record.run.status in TERMINAL:
            return
        # A worker that already claimed the run owns its fate even if invoke timed out.
        if record.owner is not None:
            return
        now = self.clock()
        payload = record.run.to_wire()
        payload.update(
            status="failed",
            question=None,
            result=None,
            error=unavailable("Worker dispatch").envelope("worker-dispatch").error.to_wire(),
            updatedAt=timestamp(now),
        )
        _close_running_steps(payload, now)
        updated = RunRecord(
            Run.model_validate(payload),
            record.revision + 1,
            generation + 1,
            None,
            0,
            record.started_at,
            record.private,
            record.profile_version,
        )
        try:
            self.store.transact(self._writes(updated, record))
        except Conflict:
            pass


class ProfileRepository:
    """T06 persists overlays/custom profiles; defaults remain T06's responsibility."""

    def __init__(self, store: Store):
        self.store = store

    def get(self, session_id: str, profile_id: str, overlay: bool = False) -> dict | None:
        return self.store.get(
            "profiles",
            f"SESSION#{session_id}",
            f"{'OVERLAY' if overlay else 'PROFILE'}#{profile_id}",
        )

    def list(self, session_id: str) -> list[dict]:
        return self.store.query("profiles", f"SESSION#{session_id}")

    def save(
        self,
        session_id: str,
        profile_id: str,
        value: dict,
        expected_version: int | None,
        overlay: bool = False,
    ) -> dict:
        saved = {
            "revision": (expected_version or 0) + 1,
            "value": value,
            "profileId": profile_id,
            "overlay": overlay,
        }
        self.store.transact(
            [
                Write(
                    "profiles",
                    f"SESSION#{session_id}",
                    f"{'OVERLAY' if overlay else 'PROFILE'}#{profile_id}",
                    saved,
                    expected_version,
                )
            ]
        )
        return saved

    def delete(self, session_id: str, profile_id: str, expected_version: int) -> None:
        self.store.transact(
            [
                Write(
                    "profiles",
                    f"SESSION#{session_id}",
                    f"PROFILE#{profile_id}",
                    None,
                    expected_version,
                )
            ]
        )
