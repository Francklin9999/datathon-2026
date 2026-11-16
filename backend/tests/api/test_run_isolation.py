"""Run listing is strictly per session (QA 6.5: not a leak; the Evidence list is this browser's session).

Pins the three layers: list_runs reads only the caller's session, its profileId/kind/cursor filters
only narrow that list, and DynamoStore drops index hits whose base item belongs to another session.
"""

import copy

from aplomb.api.app import create_app
from aplomb.api.repositories import RunRepository, timestamp
from aplomb.api.services import RunCoordinator, Services, new_run_id
from aplomb.api.settings import Settings
from aplomb.api.storage import DynamoStore, MemoryStore, canonical
from aplomb.contracts.models import Run
from fastapi.testclient import TestClient

from .conftest import OTHER_SID, SID

SETTINGS = Settings(data_version="snap-20261113-starter")


def _run(fixture_payload, clock, session_id, profile_id, kind="decision"):
    clock.advance(1)
    payload = copy.deepcopy(fixture_payload)
    payload.update(
        runId=new_run_id(clock()),
        sessionId=session_id,
        profileId=profile_id,
        createdAt=timestamp(clock()),
        updatedAt=timestamp(clock()),
    )
    if kind == "portfolio_brief":
        payload.update(
            kind=kind,
            input={"kind": "portfolio_brief", "window": {"code": "full"}},
            status="queued",
            steps=[],
            facts={},
            evidence={},
            result=None,
            error=None,
            question=None,
        )
    return Run.model_validate(payload)


def _ids(response):
    assert response.status_code == 200, response.text
    return [item["runId"] for item in response.json()["items"]]


def test_run_list_is_isolated_per_session_with_filters_and_cursor(fixture_payload, clock):
    repo = RunRepository(MemoryStore(), clock)
    # The other session's run is the oldest, so a replayed cursor would reach it if it leaked.
    other = _run(fixture_payload, clock, OTHER_SID, "robert")
    mine = [
        _run(fixture_payload, clock, SID, "robert"),
        _run(fixture_payload, clock, SID, "mateo", "portfolio_brief"),
        _run(fixture_payload, clock, SID, "robert"),
    ]
    for run in (other, *mine):
        repo.create(run, {}, 1)
    client = TestClient(create_app(SETTINGS, Services(runs=RunCoordinator(repo, None, None, clock))))
    me, them = {"X-Aplomb-Session": SID}, {"X-Aplomb-Session": OTHER_SID}
    newest_first = [r.run_id for r in reversed(mine)]

    assert _ids(client.get("/v1/runs", headers=me)) == newest_first
    assert _ids(client.get("/v1/runs", headers=them)) == [other.run_id]
    assert _ids(client.get("/v1/runs?profileId=mateo", headers=me)) == [mine[1].run_id]
    assert _ids(client.get("/v1/runs?profileId=mateo", headers=them)) == []
    assert _ids(client.get("/v1/runs?profileId=robert", headers=them)) == [other.run_id]
    assert _ids(client.get("/v1/runs?kind=portfolio_brief", headers=me)) == [mine[1].run_id]
    assert _ids(client.get("/v1/runs?kind=portfolio_brief", headers=them)) == []

    page = client.get("/v1/runs?limit=1", headers=me).json()
    assert [i["runId"] for i in page["items"]] == newest_first[:1]
    cursor = page["nextCursor"]
    assert cursor
    assert _ids(client.get(f"/v1/runs?limit=5&cursor={cursor}", headers=me)) == newest_first[1:]
    # A cursor is only a position: replayed by another session it still lists that session's runs only.
    assert _ids(client.get(f"/v1/runs?limit=5&cursor={cursor}", headers=them)) == [other.run_id]

    assert client.get(f"/v1/runs/{mine[0].run_id}", headers=them).status_code == 404
    assert client.get(f"/v1/runs/{other.run_id}", headers=me).status_code == 404


def test_dynamo_session_index_drops_items_owned_by_another_session():
    owners = {"RUN#mine": SID, "RUN#theirs": OTHER_SID}

    class Client:
        def query(self, **kwargs):
            assert kwargs["IndexName"] == "bySession"
            assert kwargs["ExpressionAttributeValues"] == {":pk": {"S": f"SESSION#{SID}"}}
            # A stale or corrupt index entry points at another session's run.
            return {"Items": [{"pk": {"S": pk}, "sk": {"S": "META"}} for pk in owners]}

        def get_item(self, **kwargs):
            pk = kwargs["Key"]["pk"]["S"]
            document = {"revision": 1, "type": "META", "run": {"runId": pk, "sessionId": owners[pk]}}
            return {"Item": {"pk": {"S": pk}, "sk": {"S": "META"}, "ownerSession": {"S": owners[pk]},
                             "document": {"S": canonical(document).decode()}}}

    store = DynamoStore(Client(), {"runs": "runs-table"}, None)
    items = store.query("runs", f"SESSION#{SID}", "bySession")
    assert [item["run"]["runId"] for item in items] == ["RUN#mine"]
