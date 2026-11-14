from concurrent.futures import ThreadPoolExecutor

import pytest
from aplomb.api.errors import Conflict, NotFound
from aplomb.api.repositories import CacheRepository, ProfileRepository, RunRepository
from aplomb.api.services import RunCoordinator, new_run_id
from aplomb.api.storage import FileStore, MemoryStore
from aplomb.contracts import api as a
from aplomb.contracts.models import Run

from .conftest import OTHER_SID, SID


def mutate(run, **changes):
    payload = run.to_wire()
    payload.update(changes)
    return Run.model_validate(payload)


@pytest.mark.parametrize("durable", [False, True])
def test_atomic_idempotency_concurrent(durable, tmp_path, queued_run, clock):
    path = tmp_path / "state.json"
    store = FileStore(path) if durable else MemoryStore()
    repository = RunRepository(store, clock)
    body = {"kind": "decision", "profileId": "robert"}

    def create(_):
        # Separate FileStore objects exercise inter-instance locking.
        repo = RunRepository(FileStore(path), clock) if durable else repository
        return repo.create(mutate(queued_run, runId=new_run_id(clock())), {}, 1, "same", body)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create, range(20)))
    assert len({record.run.run_id for record, _ in results}) == 1
    assert sum(created for _, created in results) == 1
    assert len(repository.list(SID)) == 1
    with pytest.raises(Conflict):
        repository.create(queued_run, {}, 1, "same", {"different": True})
    other, created = repository.create(mutate(queued_run, sessionId=OTHER_SID), {}, 1, "same", body)
    assert created
    assert other.run.session_id == OTHER_SID
    clock.advance(601)
    _, created = repository.create(
        mutate(queued_run, runId=new_run_id(clock())), {}, 1, "same", body
    )
    assert created  # explicit expiry check; no dependency on TTL cleanup timing


def test_profile_versions_isolation_and_cache(queued_run, clock):
    store = MemoryStore()
    profiles, cache = ProfileRepository(store), CacheRepository(store, clock)
    profiles.save(SID, "robert", {"threshold": 5}, None, overlay=True)
    assert profiles.get(OTHER_SID, "robert", overlay=True) is None
    with pytest.raises(Conflict):
        profiles.save(SID, "robert", {"threshold": 10}, None, overlay=True)
    profiles.save(SID, "robert", {"threshold": 10}, 1, overlay=True)
    dimensions = dict(
        session=SID,
        profileId="robert",
        profileVersion=2,
        snapshot=queued_run.data_version,
        currency="CAD",
        asOf=queued_run.as_of,
        window={"code": "full"},
        language="en",
        flags={},
        methodVersion="v1",
    )
    cache.put("brief", dimensions, {"run": "first"}, 60)
    assert cache.get("brief", dimensions) == {"run": "first"}
    assert cache.get("brief", {**dimensions, "session": OTHER_SID}) is None
    assert cache.get("brief", {**dimensions, "profileVersion": 3}) is None
    clock.advance(61)
    assert cache.get("brief", dimensions) is None
    with pytest.raises(ValueError):
        cache.key("brief", {"profileId": "robert"})


def test_duplicate_claim_stale_recovery_and_cancel(queued_run, clock):
    repo = RunRepository(MemoryStore(), clock, lease_seconds=10)
    repo.create(queued_run, {"pinned": True}, 1)
    with ThreadPoolExecutor(max_workers=8) as executor:
        claims = list(executor.map(lambda _: repo.claim(queued_run.run_id, 1), range(8)))
    claimed = next(c for c in claims if c)
    assert sum(c is not None for c in claims) == 1
    assert repo.claim(queued_run.run_id, 1) is None
    clock.advance(11)
    recovered = repo.claim(queued_run.run_id, 1)
    assert recovered.generation == 2
    assert recovered.owner != claimed.owner
    with pytest.raises(Conflict):
        repo.heartbeat(claimed)
    assert repo.heartbeat(recovered).revision == recovered.revision + 1
    current = repo.get(SID, queued_run.run_id)
    cancelled = repo.cancel(SID, queued_run.run_id)
    assert cancelled.status == "cancelled"
    with pytest.raises(Conflict):
        repo.heartbeat(current)
    with pytest.raises(Conflict):
        repo.cancel(SID, queued_run.run_id)
    assert repo.claim(queued_run.run_id, 2) is None
    with pytest.raises(NotFound):
        repo.get(OTHER_SID, queued_run.run_id)


def test_atomic_terminal_write_vs_cancel(queued_run, clock):
    repo = RunRepository(MemoryStore(), clock)
    repo.create(queued_run, {}, 1)
    claimed = repo.claim(queued_run.run_id, 1)
    failed = mutate(
        claimed.run,
        status="failed",
        error={
            "code": "upstream_unavailable",
            "message": "Synthetic worker failure",
            "requestId": "test",
        },
    )

    def finish():
        try:
            repo.checkpoint(queued_run.run_id, 1, claimed.owner, claimed.revision, failed)
            return "failed"
        except Conflict:
            return None

    def cancel():
        try:
            return repo.cancel(SID, queued_run.run_id).status
        except Conflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        a, b = executor.submit(finish), executor.submit(cancel)
        results = [a.result(), b.result()]
    assert sum(r is not None for r in results) == 1
    assert repo.get(SID, queued_run.run_id).run.status in {"cancelled", "failed"}
    with pytest.raises(Conflict):
        repo.heartbeat(claimed)


def test_answer_consumed_once_and_wait_expires(queued_run, clock):
    repo = RunRepository(MemoryStore(), clock)
    repo.create(queued_run, {"checkpoint": "plan"}, 1)
    claimed = repo.claim(queued_run.run_id, 1)
    question = {
        "questionId": "q1",
        "text": {"en": "Funding?", "fr": "Financement?"},
        "field": "funding",
        "options": [{"value": "cash", "label": {"en": "Cash", "fr": "Espèces"}}],
    }
    waiting = mutate(claimed.run, status="waiting_input", question=question)
    repo.checkpoint(queued_run.run_id, 1, claimed.owner, claimed.revision, waiting)
    with pytest.raises(Conflict):
        repo.answer(SID, queued_run.run_id, "wrong", "cash")
    with ThreadPoolExecutor(max_workers=2) as executor:

        def answer(_):
            try:
                return repo.answer(SID, queued_run.run_id, "q1", "cash")
            except Conflict:
                return None

        answers = list(executor.map(answer, range(2)))
    assert sum(a is not None for a in answers) == 1
    resumed = next(a for a in answers if a)
    assert resumed.private["answer"] == {"questionId": "q1", "value": "cash"}
    assert resumed.generation == 2
    assert repo.claim(queued_run.run_id, 1) is None
    resumed = repo.claim(queued_run.run_id, 2)
    repo.checkpoint(
        queued_run.run_id,
        resumed.generation,
        resumed.owner,
        resumed.revision,
        mutate(resumed.run, status="waiting_input", question=question),
    )
    clock.advance(1801)
    assert repo.get(SID, queued_run.run_id).run.status == "cancelled"


def test_queued_crash_window_and_running_hard_budget(queued_run, clock):
    repo = RunRepository(MemoryStore(), clock, hard_seconds=180)
    repo.create(queued_run, {}, 1)  # process dies before dispatch
    clock.advance(59)
    assert repo.get(SID, queued_run.run_id).run.status == "queued"
    clock.advance(1)
    assert repo.get(SID, queued_run.run_id).run.status == "failed"
    other = mutate(queued_run, runId=new_run_id(clock()))
    repo.create(other, {}, 1)
    claimed = repo.claim(other.run_id, 1)
    clock.advance(61)
    assert repo.get(SID, other.run_id).run.status == "running"  # not queued watchdog
    recovered = repo.claim(other.run_id, 1)
    assert recovered is not None
    clock.advance(120)
    assert repo.get(SID, other.run_id).run.status == "failed"
    with pytest.raises(Conflict):
        repo.heartbeat(claimed)


def test_steps_delta_keeps_running_update_and_full_ledger(queued_run, fixture_payload, clock):
    repo = RunRepository(MemoryStore(), clock)
    repo.create(queued_run, {}, 1)
    claimed = repo.claim(queued_run.run_id, 1)
    # Use a schema example only as test data for persistence.
    step = fixture_payload["steps"][0]
    step.update(status="running", endedAt=None, durationMs=None, factIds=["F-001"])
    run = mutate(claimed.run, steps=[step], facts={"F-001": fixture_payload["facts"]["F-001"]})
    running = repo.checkpoint(run.run_id, 1, claimed.owner, claimed.revision, run)
    coordinator = RunCoordinator(repo, None, None, clock)
    assert coordinator.get(SID, run.run_id, 0).steps[0].status == "running"
    step.update(status="done", endedAt=run.updated_at, durationMs=1)
    done = repo.checkpoint(
        run.run_id, 1, running.owner, running.revision, mutate(run, steps=[step])
    )
    delta = coordinator.get(SID, run.run_id, 0)
    assert delta.steps[0].status == "done"
    assert set(delta.facts) == {"F-001"}
    assert coordinator.get(SID, run.run_id, 1).steps == []
    assert coordinator.get(SID, run.run_id).steps[0].status == "done"
    with pytest.raises(Conflict):
        repo.checkpoint(run.run_id, 1, done.owner, done.revision, mutate(done.run, steps=[]))
    with pytest.raises(Conflict):
        changed = dict(fixture_payload["facts"]["F-001"], value=999)
        repo.checkpoint(
            run.run_id, 1, done.owner, done.revision, mutate(done.run, facts={"F-001": changed})
        )


def test_dispatch_failure_is_persisted_and_idempotent_retry_skips_prepare(queued_run, clock):
    from aplomb.api.errors import ServiceError
    from aplomb.api.services import PreparedRun

    repo = RunRepository(MemoryStore(), clock)
    dispatched = []

    class Dispatcher:
        fail = False

        def dispatch(self, run_id, generation):
            dispatched.append(run_id)
            if self.fail:
                raise OSError("synthetic transport failure")

    dispatcher = Dispatcher()
    prepared_calls = []

    def prepare(session, body):
        prepared_calls.append(body)
        if len(prepared_calls) > 1:
            raise RuntimeError("profile provider disappeared")
        return PreparedRun(
            queued_run.input.to_wire(),
            queued_run.as_of,
            queued_run.data_version,
            {"profile": "pinned"},
            1,
        )

    coordinator = RunCoordinator(repo, dispatcher, prepare, clock)
    request = a.CreateDecisionRunRequest(
        kind="decision", profile_id="robert", lang="en", request=queued_run.input.request
    )
    result = coordinator.create(SID, request, "stable")
    assert coordinator.create(SID, request, "stable").run_id == result.run_id
    with pytest.raises(Conflict):
        coordinator.create(SID, request.model_copy(update={"profile_id": "mateo"}), "stable")
    assert len(prepared_calls) == len(dispatched) == 1
    dispatcher.fail = True
    coordinator.prepare = lambda sid, body: PreparedRun(
        queued_run.input.to_wire(), queued_run.as_of, queued_run.data_version, {}, 1
    )
    with pytest.raises(ServiceError, match="Worker dispatch"):
        coordinator.create(SID, request, "failed")
    failed_id = dispatched[-1]
    assert repo.get(SID, failed_id).run.status == "failed"
    assert repo.get(SID, failed_id).run.error.code == "upstream_unavailable"


def test_cached_existing_run_reservation_is_session_scoped(fixture_payload, clock):
    repo = RunRepository(MemoryStore(), clock)
    run = Run.model_validate(fixture_payload)
    repo.create(run, {}, 1)
    reserved = repo.reserve_existing(SID, run.run_id, "cached", {"kind": "portfolio_brief"})
    assert reserved.run.run_id == run.run_id
    assert repo.idempotent(SID, "cached", {"kind": "portfolio_brief"}).run.run_id == run.run_id
    with pytest.raises(Conflict):
        repo.reserve_existing(SID, run.run_id, "cached", {"kind": "decision"})
    with pytest.raises(NotFound):
        repo.reserve_existing(OTHER_SID, run.run_id, "cached", {"kind": "portfolio_brief"})
