"""Regressions for the API persistence audit: idempotent retry of a failed run, local worker
capacity, steps of cancelled or watchdog-failed runs, the local FileStore, and snapshot open
failures. Composed app on the starter snapshot with the scripted test gateway; no network, AWS
or model call. Every test uses its own sessions."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import uuid
from types import SimpleNamespace

import pytest
from aplomb.api import domain, storage
from aplomb.api.app import create_app
from aplomb.api.dispatcher import LocalDispatcher
from aplomb.api.domain import SnapshotProvider, default_services
from aplomb.api.errors import Conflict, ServiceError
from aplomb.api.settings import Settings
from aplomb.api.storage import FileStore, MemoryStore, Write, canonical
from aplomb.contracts.catalog import FeatureFlag
from aplomb.contracts.registry import adapter
from fastapi.testclient import TestClient
from tests.integration._scripted import ScriptedGateway
from tests.unit.datastore._support import STARTER_VERSION, starter_root

TSLA_25 = {"type": "move", "move": {"ticker": "TSLA", "sizePct": 25, "funding": {"mode": "pro_rata"}}}
DECISION = {"kind": "decision", "profileId": "robert", "lang": "en", "request": TSLA_25}
BRIEF = {"kind": "portfolio_brief", "profileId": "robert", "lang": "en", "window": {"code": "3y"}}
TERMINAL = {"succeeded", "failed", "cancelled"}


def settings(**over) -> Settings:
    features = {flag: True for flag in FeatureFlag}
    features[FeatureFlag.GUARDRAILS] = False
    return Settings(**{"data_version": STARTER_VERSION, "data_dir": str(starter_root()), "features": features, **over})


def compose(gateway, store=None):
    cfg = settings()
    services = default_services(cfg, store, gateway=gateway)
    return TestClient(create_app(cfg, services), raise_server_exceptions=False), services


def session() -> dict:
    return {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}


def fetch(client, headers, run_id) -> dict:
    response = client.get(f"/v1/runs/{run_id}", headers=headers)
    assert response.status_code == 200, response.text
    return adapter("Run").validate_json(response.content).to_wire()


def wait_terminal(client, headers, run_id) -> dict:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        run = fetch(client, headers, run_id)
        if run["status"] in TERMINAL:
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


class BlockingGateway(ScriptedGateway):
    """Holds every planner call until ``gate`` is set, so a run stays in its plan step."""

    def __init__(self) -> None:
        super().__init__()
        self.gate, self.entered = threading.Event(), threading.Semaphore(0)

    def generate(self, role, schema, messages, tools, limits):
        if role == "planner":
            self.entered.release()
            assert self.gate.wait(60)
        return super().generate(role, schema, messages, tools, limits)


@pytest.fixture()
def blocked():
    gateway = BlockingGateway()
    client, services = compose(gateway, MemoryStore())
    try:
        yield client, services, gateway
    finally:
        gateway.gate.set()
        services.runs.dispatcher.close()


# Findings 11 and 47: idempotent retry of a failed run ------------------------------------------


def test_idempotent_retry_of_a_failed_run_answers_the_same_run_id():
    client, _ = compose(ScriptedGateway(fail_role="writer"))
    headers = {**session(), "Idempotency-Key": "brief-robert-v1-3y-en"}
    first = client.post("/v1/runs", json=BRIEF, headers=headers)
    assert first.status_code == 202, first.text
    run_id = first.json()["runId"]
    assert wait_terminal(client, headers, run_id)["status"] == "failed"

    retry = client.post("/v1/runs", json=BRIEF, headers=headers)
    assert retry.status_code == 202, retry.text
    assert adapter("QueuedRunResponse").validate_json(retry.content).to_wire()["runId"] == run_id
    polled = fetch(client, headers, run_id)      # GET is authoritative: the stored failure
    assert (polled["status"], polled["error"]["code"]) == ("failed", "upstream_unavailable")
    assert len(client.get("/v1/runs", headers=headers).json()["items"]) == 1
    # A different body under the same key still conflicts.
    assert client.post("/v1/runs", json={**BRIEF, "lang": "fr"}, headers=headers).status_code == 409


def test_dispatch_failure_answers_503_first_then_the_persisted_failed_run_on_retry():
    client, services = compose(ScriptedGateway())

    class Refusing:
        def dispatch(self, run_id, generation):
            raise OSError("synthetic transport failure")

    services.runs.dispatcher.close()
    services.runs.dispatcher = Refusing()
    headers = {**session(), "Idempotency-Key": "k"}
    first = client.post("/v1/runs", json=DECISION, headers=headers)
    assert first.status_code == 503 and first.json()["error"]["code"] == "upstream_unavailable"
    items = client.get("/v1/runs", headers=headers).json()["items"]
    assert [item["status"] for item in items] == ["failed"]

    retry = client.post("/v1/runs", json=DECISION, headers=headers)
    assert retry.status_code == 202 and retry.json()["runId"] == items[0]["runId"]
    polled = fetch(client, headers, items[0]["runId"])
    assert (polled["status"], polled["error"]["code"]) == ("failed", "upstream_unavailable")


# Finding 13: local worker capacity -------------------------------------------------------------


def test_three_concurrent_local_runs_all_start(blocked):
    client, _, gateway = blocked
    runs = []
    for _ in range(3):
        headers = session()
        created = client.post("/v1/runs", json=DECISION, headers=headers)
        assert created.status_code == 202, created.text
        runs.append((headers, created.json()["runId"]))
    for _ in runs:
        assert gateway.entered.acquire(timeout=30)      # three workers are inside the plan step
    assert [fetch(client, headers, run_id)["status"] for headers, run_id in runs] == ["running"] * 3
    gateway.gate.set()
    assert [wait_terminal(client, headers, run_id)["status"] for headers, run_id in runs] == ["succeeded"] * 3


def test_a_run_no_local_worker_can_start_is_refused_at_post_not_left_queued(blocked):
    client, services, gateway = blocked
    services.runs.dispatcher.close()
    services.runs.dispatcher = LocalDispatcher(services.runs.dispatcher.worker, max_workers=2)
    accepted = []
    for _ in range(2):
        headers = session()
        created = client.post("/v1/runs", json=DECISION, headers=headers)
        assert created.status_code == 202, created.text
        accepted.append((headers, created.json()["runId"]))
        assert gateway.entered.acquire(timeout=30)

    headers = session()
    refused = client.post("/v1/runs", json=DECISION, headers=headers)
    assert refused.status_code == 503 and refused.json()["error"]["code"] == "upstream_unavailable"
    items = client.get("/v1/runs", headers=headers).json()["items"]
    assert [item["status"] for item in items] == ["failed"]      # never an accepted run left queued

    gateway.gate.set()
    assert [wait_terminal(client, h, run_id)["status"] for h, run_id in accepted] == ["succeeded"] * 2
    again = client.post("/v1/runs", json=DECISION, headers=session())      # a freed slot accepts again
    assert again.status_code == 202, again.text


def test_local_dispatcher_slots_follow_the_worker_count():
    gate, started = threading.Event(), threading.Semaphore(0)

    def worker(event):
        started.release()
        assert gate.wait(30)

    dispatcher = LocalDispatcher(worker, max_workers=2)
    try:
        dispatcher.dispatch("run-a", 1)
        dispatcher.dispatch("run-b", 1)
        assert started.acquire(timeout=10) and started.acquire(timeout=10)
        with pytest.raises(ServiceError) as refused:
            dispatcher.dispatch("run-c", 1)
        assert (refused.value.code, refused.value.status) == ("upstream_unavailable", 503)
    finally:
        gate.set()
        dispatcher.close()
    # An explicit backlog stays available to callers that want one.
    queued = LocalDispatcher(lambda event: None, max_workers=1, max_pending=4)
    try:
        for index in range(4):
            queued.dispatch(f"run-{index}", 1)
    finally:
        queued.close()


# Finding 48: no step left running on a terminal run ---------------------------------------------


def assert_interrupted(step: dict) -> None:
    assert step["status"] == "failed"
    assert step["endedAt"] is not None and step["durationMs"] >= 0
    assert step["summary"] == {"en": f"Step {step['type']} interrupted before completion.",
                               "fr": f"Étape {step['type']} interrompue avant la fin."}


def test_cancel_closes_the_step_in_progress(blocked):
    client, _, gateway = blocked
    headers = session()
    run_id = client.post("/v1/runs", json=DECISION, headers=headers).json()["runId"]
    assert gateway.entered.acquire(timeout=30)
    before = fetch(client, headers, run_id)
    assert [(s["type"], s["status"]) for s in before["steps"]] == [("plan", "running")]

    assert client.post(f"/v1/runs/{run_id}/cancel", headers=headers).status_code == 200
    cancelled = fetch(client, headers, run_id)
    assert cancelled["status"] == "cancelled" and len(cancelled["steps"]) == 1
    assert_interrupted(cancelled["steps"][0])

    gateway.gate.set()      # the stale worker resumes; its writes must stay rejected
    time.sleep(0.5)
    assert fetch(client, headers, run_id) == cancelled


def test_hard_budget_watchdog_closes_the_step_in_progress(blocked):
    client, services, gateway = blocked
    repository = services.runs.repository
    headers = session()
    run_id = client.post("/v1/runs", json=DECISION, headers=headers).json()["runId"]
    assert gateway.entered.acquire(timeout=30)
    assert fetch(client, headers, run_id)["steps"][0]["status"] == "running"

    real = repository.clock
    repository.clock = lambda: real() + repository.hard_seconds + 1
    try:
        failed = fetch(client, headers, run_id)
    finally:
        repository.clock = real
    assert (failed["status"], failed["error"]["code"]) == ("failed", "upstream_unavailable")
    assert_interrupted(failed["steps"][0])

    gateway.gate.set()
    time.sleep(0.5)
    assert fetch(client, headers, run_id) == failed


# Finding 2: local FileStore ----------------------------------------------------------------------


def row(revision: int, text: str = "x") -> dict:
    return {"revision": revision, "type": "FACT", "value": {"id": "F", "text": text}}


def test_file_store_parses_once_and_reencodes_only_changed_rows(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    seed = FileStore(path)
    for index in range(40):
        seed.transact([Write("runs", f"RUN#{index % 4}", f"FACT#{index}", row(1), None)])

    parses, encodes = [], []
    monkeypatch.setattr(storage, "json", SimpleNamespace(
        loads=lambda data: parses.append(1) or json.loads(data), dumps=json.dumps))
    monkeypatch.setattr(storage, "canonical", lambda value: encodes.append(1) or canonical(value))

    store = FileStore(path)
    for index in range(40):
        assert store.get("runs", f"RUN#{index % 4}", f"FACT#{index}") == row(1)
    assert len(store.query("runs", "RUN#1")) == 10
    store.transact([Write("runs", "RUN#0", "FACT#0", row(2, "y"), 1)])      # first commit encodes all rows
    assert len(parses) == 1

    encodes.clear()
    store.transact([Write("runs", "RUN#0", "FACT#0", row(3, "z"), 2)])
    store.transact([Write("runs", "RUN#9", "FACT#new", row(1), None)])
    with pytest.raises(Conflict):
        store.transact([Write("runs", "RUN#0", "FACT#0", row(9), 1)])
    assert store.get("runs", "RUN#0", "FACT#0") == row(3, "z")
    assert len(parses) == 1          # own commits and a refused transaction do not force a re-read
    assert len(encodes) == 4         # key and row of each changed row only

    monkeypatch.undo()
    # The file is still one canonical JSON document, readable by a fresh store.
    assert path.read_bytes() == canonical(json.loads(path.read_bytes()))
    assert FileStore(path).get("runs", "RUN#9", "FACT#new") == row(1)
    assert not list(tmp_path.glob(".aplomb-*"))


def test_file_store_instances_see_each_other_even_for_same_size_commits(tmp_path):
    path = tmp_path / "state.json"
    first, second = FileStore(path), FileStore(path)
    assert second.get("runs", "RUN#1", "FACT#F") is None      # cached "no file yet"
    first.transact([Write("runs", "RUN#1", "FACT#F", row(1, "a"), None)])
    assert second.get("runs", "RUN#1", "FACT#F") == row(1, "a")
    # Same byte length, back to back: the commit must still be seen by the other instance.
    for revision in range(2, 10):
        writer, reader = (first, second) if revision % 2 else (second, first)
        text = "abcdefghij"[revision]
        writer.transact([Write("runs", "RUN#1", "FACT#F", row(revision, text), revision - 1)])
        assert reader.get("runs", "RUN#1", "FACT#F") == row(revision, text)
        # The same instance writing twice in a row, read by the other one in between.
        writer.transact([Write("runs", "RUN#1", "FACT#G", row(revision, text), None if revision == 2 else revision - 1)])
        assert reader.get("runs", "RUN#1", "FACT#G") == row(revision, text)
    with pytest.raises(Conflict):
        first.transact([Write("runs", "RUN#1", "FACT#F", row(5), 1)])
    first.transact([Write("runs", "RUN#1", "FACT#F", None, 9), Write("runs", "RUN#1", "FACT#G", None, 9)])
    assert second.get("runs", "RUN#1", "FACT#F") is None
    assert second.query("runs", "RUN#1") == []


def test_file_store_sees_a_commit_of_another_process(tmp_path):
    path = tmp_path / "state.json"
    store = FileStore(path)
    store.transact([Write("runs", "RUN#1", "FACT#F", row(1, "a"), None)])
    assert store.get("runs", "RUN#1", "FACT#F") == row(1, "a")
    script = (
        "import sys\n"
        "from aplomb.api.storage import FileStore, Write\n"
        "store = FileStore(sys.argv[1])\n"
        "value = store.get('runs', 'RUN#1', 'FACT#F')\n"
        "value['value']['text'] = 'b'\n"
        "value['revision'] = 2\n"
        "store.transact([Write('runs', 'RUN#1', 'FACT#F', value, 1)])\n"
    )
    subprocess.run([sys.executable, "-c", script, str(path)], check=True, timeout=120)
    assert store.get("runs", "RUN#1", "FACT#F") == row(2, "b")
    with pytest.raises(Conflict):      # the stale revision held before the other process wrote
        store.transact([Write("runs", "RUN#1", "FACT#F", row(2, "c"), 1)])
    store.transact([Write("runs", "RUN#1", "FACT#F", row(3, "c"), 2)])
    assert FileStore(path).get("runs", "RUN#1", "FACT#F") == row(3, "c")


def test_file_store_never_serves_rows_of_a_commit_that_failed(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    store = FileStore(path)
    store.transact([Write("runs", "RUN#1", "FACT#F", row(1, "kept"), None)])
    before = path.read_bytes()

    not_json = {"revision": 2, "type": "FACT", "value": {"id": "F", "text": float("nan")}}
    with pytest.raises(ValueError):      # refused while encoding, after memory was changed
        store.transact([Write("runs", "RUN#1", "FACT#F", not_json, 1)])
    assert store.get("runs", "RUN#1", "FACT#F") == row(1, "kept")

    def refuse(source, target):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(storage.os, "replace", refuse)
    with pytest.raises(OSError):
        store.transact([Write("runs", "RUN#1", "FACT#F", row(2, "lost"), 1)])
    monkeypatch.undo()
    assert store.get("runs", "RUN#1", "FACT#F") == row(1, "kept")
    assert path.read_bytes() == before and not list(tmp_path.glob(".aplomb-*"))
    store.transact([Write("runs", "RUN#1", "FACT#F", row(2, "next"), 1)])      # the old revision still holds
    assert FileStore(path).get("runs", "RUN#1", "FACT#F") == row(2, "next")


# Findings 15 and 38: snapshot open failures -------------------------------------------------------


class FakeS3:
    def __init__(self, answer) -> None:
        self.answer, self.keys = answer, []

    def get_object(self, Bucket, Key):
        self.keys.append((Bucket, Key))
        return {"Body": SimpleNamespace(read=lambda: self.answer(Key))}


def aws_settings() -> Settings:
    return settings(environment="aws", data_dir=None, data_bucket="private-bucket-name", data_prefix="snapshots/x/",
                    profiles_table="p", runs_table="r", cache_table="c", worker_function="w",
                    source_user_agent="aplomb-tests (https://example.org/contact)")


def s3_failures():
    from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

    def raising(error):
        def answer(key):
            raise error
        return answer

    return {
        "denied": (raising(ClientError({"Error": {"Code": "AccessDenied", "Message": "private-bucket-name"}}, "GetObject")),
                   "object store read failed (ClientError)"),
        "missing": (raising(ClientError({"Error": {"Code": "NoSuchKey", "Message": "no key"}}, "GetObject")),
                    "object store read failed (ClientError)"),
        "unreachable": (raising(EndpointConnectionError(endpoint_url="https://s3.invalid")),
                        "object store read failed (EndpointConnectionError)"),
        "no-credentials": (raising(NoCredentialsError()), "object store read failed (NoCredentialsError)"),
        "unparsable-manifest": (lambda key: b"{not json", "JSONDecodeError"),
    }


@pytest.mark.parametrize("case", ["denied", "missing", "unreachable", "no-credentials", "unparsable-manifest"])
def test_s3_snapshot_failures_answer_503_upstream_unavailable(case, tmp_path, monkeypatch):
    import boto3

    answer, expected = s3_failures()[case]
    fake = FakeS3(answer)
    monkeypatch.setattr(boto3, "Session", lambda **kwargs: SimpleNamespace(client=lambda name, **kw: fake))
    monkeypatch.setattr(domain, "S3_CACHE_DIR", tmp_path)
    cfg = aws_settings()
    client = TestClient(create_app(cfg, default_services(cfg, MemoryStore())), raise_server_exceptions=False)

    for path in ("/v1/meta", "/v1/assets", "/v1/datasets"):
        response = client.get(path, headers=session())
        assert response.status_code == 503, (path, response.text)
        error = adapter("ApiError").validate_json(response.content).to_wire()["error"]
        assert error["code"] == "upstream_unavailable"
        assert error["message"].startswith("Pinned data snapshot unavailable: ") and expected in error["message"]
        assert "private-bucket-name" not in error["message"]
    assert fake.keys[0] == ("private-bucket-name", f"snapshots/x/manifests/{STARTER_VERSION}.json")


def test_snapshot_provider_maps_unexpected_open_failures_and_retries_later(monkeypatch):
    calls = []

    class Store:
        def open(self, version):
            calls.append(version)
            if len(calls) == 1:
                raise PermissionError("cache directory is read-only: /secret/path")
            return SnapshotProvider(settings())()

    provider = SnapshotProvider(settings())
    monkeypatch.setattr(provider, "_store", lambda: Store())
    with pytest.raises(ServiceError) as failed:
        provider()
    assert (failed.value.code, failed.value.status) == ("upstream_unavailable", 503)
    assert failed.value.message == "Pinned data snapshot unavailable: PermissionError"
    assert provider().data_version == STARTER_VERSION      # the failure is not cached


def test_local_unparsable_manifest_answers_503(tmp_path):
    (tmp_path / "manifests").mkdir()
    (tmp_path / "manifests" / f"{STARTER_VERSION}.json").write_text("{not json", encoding="utf-8")
    cfg = settings(data_dir=str(tmp_path))
    client = TestClient(create_app(cfg, default_services(cfg, MemoryStore())), raise_server_exceptions=False)
    response = client.get("/v1/meta")
    assert response.status_code == 503 and response.json()["error"]["code"] == "upstream_unavailable"
