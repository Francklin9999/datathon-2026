import io
import json
import threading

import boto3
import pytest
from aplomb.api.app import create_app
from aplomb.api.dispatcher import LambdaDispatcher, LocalDispatcher
from aplomb.api.errors import Conflict, ServiceError
from aplomb.api.repositories import RunRepository
from aplomb.api.services import PreparedRun, RunCoordinator, Services
from aplomb.api.settings import Settings
from aplomb.api.storage import DynamoStore, FileStore, S3Blobs, Write, canonical
from aplomb.contracts.models import Run
from botocore.stub import Stubber
from fastapi.testclient import TestClient

from .conftest import OTHER_SID, SID


class FakeS3:
    def __init__(self):
        self.data = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.data[(Bucket, Key)] = bytes(Body)

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.data[(Bucket, Key)])}


def test_s3_spill_content_addressed_and_verified():
    s3 = FakeS3()
    blobs = S3Blobs(s3, "private-bucket", "evidence")
    reference = blobs.put(b'{"signed":"bundle"}')
    assert reference["key"].startswith("evidence/run-bundles/")
    assert blobs.get(reference) == b'{"signed":"bundle"}'
    assert blobs.put(b'{"signed":"bundle"}') == reference
    s3.data[("private-bucket", reference["key"])] = b"tampered"
    with pytest.raises(ValueError, match="integrity"):
        blobs.get(reference)


def test_dynamo_revision_conditions_and_consistent_get():
    # Stubber validates real botocore request shapes; no AWS/network credentials.
    client = boto3.client(
        "dynamodb", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
    )
    store = DynamoStore(client, {"runs": "runs-table"}, S3Blobs(FakeS3(), "bucket", "evidence"))
    value = {"revision": 1, "fraction": 0.1, "type": "STATE"}
    item = {
        "pk": {"S": "RUN#test"},
        "sk": {"S": "STATE"},
        "revision": {"N": "1"},
        "document": {"S": canonical(value).decode()},
    }
    action = {
        "TableName": "runs-table",
        "ConditionExpression": "attribute_not_exists(#rev)",
        "ExpressionAttributeNames": {"#rev": "revision"},
        "Item": item,
    }
    with Stubber(client) as stub:
        stub.add_response("transact_write_items", {}, {"TransactItems": [{"Put": action}]})
        store.transact([Write("runs", "RUN#test", "STATE", value, None)])
        stub.add_response(
            "get_item",
            {"Item": item},
            {
                "TableName": "runs-table",
                "Key": {"pk": {"S": "RUN#test"}, "sk": {"S": "STATE"}},
                "ConsistentRead": True,
            },
        )
        assert store.get("runs", "RUN#test", "STATE") == value
        stub.add_client_error(
            "transact_write_items",
            "TransactionCanceledException",
            modeled_fields={"CancellationReasons": [{"Code": "ConditionalCheckFailed"}]},
        )
        with pytest.raises(Conflict):
            store.transact([Write("runs", "RUN#test", "STATE", value, None)])
        stub.assert_no_pending_responses()


def test_dynamo_many_medium_children_spill_below_aggregate_limit():
    calls = []

    class Client:
        def transact_write_items(self, **kwargs):
            calls.append(kwargs)

    s3 = FakeS3()
    store = DynamoStore(Client(), {"runs": "runs-table"}, S3Blobs(s3, "bucket", "evidence"))
    writes = [
        Write(
            "runs", "RUN#test", f"FACT#{i}", {"revision": 1, "data": str(i) + "x" * 100_000}, None
        )
        for i in range(97)
    ]
    store.transact(writes)
    assert len(s3.data) == 97
    assert len(canonical(calls[0])) < 3_500_000
    assert all("blob" in action["Put"]["Item"] for action in calls[0]["TransactItems"])
    with pytest.raises(ValueError):
        store.transact(writes * 2)


def test_dynamo_owner_checked_before_spilled_metadata_read():
    class Client:
        def get_item(self, **kwargs):
            return {"Item": {"ownerSession": {"S": SID}, "blob": {"S": "bad-reference"}}}

    class NoBlobReads:
        def get(self, reference):
            raise AssertionError("Unauthorized request reached blob storage")

    store = DynamoStore(Client(), {"runs": "runs-table"}, NoBlobReads())
    assert store.get_owned("runs", "RUN#test", "META", OTHER_SID) is None


def test_lambda_dispatch_exact_payload_and_enqueue_rejection():
    client = boto3.client(
        "lambda", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
    )
    dispatcher = LambdaDispatcher(client, "worker")
    expected = {
        "FunctionName": "worker",
        "InvocationType": "Event",
        "Payload": json.dumps({"runId": "run-test", "generation": 3}).encode(),
    }
    with Stubber(client) as stub:
        stub.add_response("invoke", {"StatusCode": 202}, expected)
        dispatcher.dispatch("run-test", 3)
        stub.add_response("invoke", {"StatusCode": 200}, expected)
        with pytest.raises(ServiceError):
            dispatcher.dispatch("run-test", 3)
        stub.assert_no_pending_responses()


def test_local_worker_survives_response_and_fresh_repository_reads(tmp_path, queued_run, clock):
    path = tmp_path / "local-state.json"
    repository = RunRepository(FileStore(path), clock)
    gate, done = threading.Event(), threading.Event()

    def worker(event):
        assert gate.wait(3)
        claimed = repository.claim(event["runId"], event["generation"])
        payload = claimed.run.to_wire()
        payload.update(
            status="failed",
            error={
                "code": "upstream_unavailable",
                "message": "Synthetic worker executed after response",
                "requestId": "local-test",
            },
        )
        repository.checkpoint(
            event["runId"],
            claimed.generation,
            claimed.owner,
            claimed.revision,
            Run.model_validate(payload),
            {"executed": True},
        )
        done.set()

    dispatcher = LocalDispatcher(worker)
    coordinator = RunCoordinator(
        repository,
        dispatcher,
        lambda sid, req: PreparedRun(
            queued_run.input.to_wire(), queued_run.as_of, queued_run.data_version, {}, 1
        ),
        clock,
    )
    app = create_app(Settings(data_version=queued_run.data_version), Services(runs=coordinator))
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/runs",
            headers={"X-Aplomb-Session": SID},
            json={
                "kind": "decision",
                "profileId": "robert",
                "lang": "en",
                "request": queued_run.input.request.to_wire(),
            },
        )
        assert response.status_code == 202
        rid = response.json()["runId"]
        assert repository.get(SID, rid).run.status == "queued"
        gate.set()  # worker starts only after the HTTP response was received
        assert done.wait(3)
        fresh = RunRepository(FileStore(path), clock).get(SID, rid)
        assert fresh.run.status == "failed"
        assert fresh.private == {"executed": True}
    finally:
        gate.set()
        dispatcher.close()
