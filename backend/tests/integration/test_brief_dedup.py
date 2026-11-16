"""Server-side de-duplication of identical portfolio briefs (QA 2d).

Identity = session, profile and its version, data version, manifest digest, brief runtime identity,
window and language. Without an Idempotency-Key, and with force=true, an identical brief that is still
in progress is returned; force=true within 60 s of an identical succeeded brief returns that brief.
The real preparer, repository and worker are used; only the model text is synthetic."""

import time
import uuid

import pytest
from aplomb.agents.worker import make_handler
from aplomb.api.repositories import (
    BRIEF_LOCK_GRACE_SECONDS,
    ProfileRepository,
    RunRepository,
    brief_lock_key,
)
from aplomb.api.runtime import RunPreparerImpl, build_agent_services
from aplomb.api.services import RunCoordinator
from aplomb.api.settings import Settings
from aplomb.api.storage import MemoryStore
from aplomb.contracts import api as a
from aplomb.datastore import LocalDataStore
from aplomb.optimizer.services import build_domain_services
from tests.integration.test_agent_runtime import SyntheticText
from tests.unit.datastore._support import STARTER_VERSION, starter_root


class Capture:
    def __init__(self):
        self.events = []

    def dispatch(self, run_id, generation):
        self.events.append({"runId": run_id, "generation": generation})


class Rig:
    def __init__(self):
        self.shift = 0.0
        self.settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()))
        self.store = MemoryStore()
        self.runs = RunRepository(self.store, clock=self.clock, hard_seconds=self.settings.run_hard_seconds)
        self.profiles, _ = build_domain_services(ProfileRepository(self.store), self.snapshot)
        self.dispatch = Capture()
        prepare = RunPreparerImpl(self.profiles, self.snapshot, models_configured=True, settings=self.settings)
        self.coordinator = RunCoordinator(self.runs, self.dispatch, prepare, clock=self.clock)
        self.sid = "s_" + str(uuid.uuid4())

    def clock(self) -> float:
        return time.time() + self.shift

    @staticmethod
    def snapshot():
        return LocalDataStore(starter_root()).open(STARTER_VERSION)

    def brief(self, key=None, **fields):
        body = a.CreatePortfolioBriefRunRequest.model_validate(
            {"kind": "portfolio_brief", "profileId": "robert", "lang": "en", **fields})
        return self.coordinator.create(self.sid, body, key)

    def finish(self, run_id):
        worker = make_handler(build_agent_services(self.settings, self.runs, self.snapshot, None, SyntheticText()))
        event = next(e for e in self.dispatch.events if e["runId"] == run_id)
        worker(event)
        run = self.runs.get(self.sid, run_id).run
        assert run.status == "succeeded", run.error
        return run


@pytest.fixture
def rig():
    return Rig()


def test_identical_briefs_in_progress_share_one_run_with_or_without_force(rig):
    first = rig.brief()
    assert first.status == "queued"
    assert rig.brief().run_id == first.run_id                     # no key, second tab
    assert rig.brief(force=True).run_id == first.run_id           # Refresh while it is being written
    assert rig.brief("brief-key", force=True).run_id == first.run_id
    assert [e["runId"] for e in rig.dispatch.events] == [first.run_id]


def test_another_window_or_language_is_another_brief(rig):
    first = rig.brief()
    assert rig.brief(window={"code": "3y"}).run_id != first.run_id
    assert rig.brief(lang="fr").run_id != first.run_id
    assert len(rig.dispatch.events) == 3


def test_force_within_a_minute_of_an_identical_success_returns_it(rig):
    first = rig.brief()
    rig.finish(first.run_id)
    again = rig.brief(force=True)
    assert again.run_id == first.run_id and again.status == "succeeded"
    rig.shift += 61                                               # more than a minute after it succeeded
    later = rig.brief(force=True)
    assert later.run_id != first.run_id and later.status == "queued"
    assert len(rig.dispatch.events) == 2


def test_a_failed_brief_is_never_reused(rig):
    first = rig.brief()
    rig.shift += 61                                               # never started: the queue watchdog fails it
    assert rig.runs.get(rig.sid, first.run_id).run.status == "failed"
    retry = rig.brief()
    assert retry.run_id != first.run_id and retry.status == "queued"


def test_the_lock_is_written_with_the_run_and_expires_after_the_hard_budget(rig):
    first = rig.brief()
    locks = [item for item in rig.store._items.values() if item["table"] == "cache" and item["pk"].startswith("BRIEF#")]
    assert len(locks) == 1 and locks[0]["value"]["runId"] == first.run_id
    expires = locks[0]["value"]["expiresAt"]
    assert expires - rig.clock() == pytest.approx(rig.settings.run_hard_seconds + BRIEF_LOCK_GRACE_SECONDS, abs=2)
    # A concurrent creation that lost the race finds the lock in the repository and gets that run back.
    held = rig.runs.held_brief(rig.sid, locks[0]["pk"])
    assert held is not None and held.run.run_id == first.run_id
    loser = held.run.model_copy(update={"run_id": "run_" + "0" * 26})
    record, created = rig.runs.create(loser, held.private, held.profile_version, brief_lock=locks[0]["pk"])
    assert created is False and record.run.run_id == first.run_id
    # Another session never sees this session's lock.
    assert rig.runs.held_brief("s_" + str(uuid.uuid4()), locks[0]["pk"]) is None


def test_lock_key_depends_on_every_identity_part():
    base = ["s", "robert", 1, "v1", "m", "r", {"code": "1y"}, "en"]
    keys = {brief_lock_key(base)}
    for index, value in enumerate(["t", "amira", 2, "v2", "n", "q", {"code": "3y"}, "fr"]):
        changed = list(base)
        changed[index] = value
        keys.add(brief_lock_key(changed))
    assert len(keys) == len(base) + 1
