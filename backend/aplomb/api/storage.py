"""Small atomic document store with equivalent local and DynamoDB semantics.

All writes carry a revision precondition. None means create-if-absent. A
transaction checks every precondition before making any document visible.
Documents are JSON, so DynamoDB decimal conversion cannot alter wire numbers.
"""

import copy
import fcntl
import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import Conflict


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


@dataclass(frozen=True)
class Write:
    table: str
    pk: str
    sk: str
    value: dict | None
    expected: int | None
    indexes: dict | None = None


class Store(Protocol):
    def get(self, table: str, pk: str, sk: str) -> dict | None: ...
    def get_owned(self, table: str, pk: str, sk: str, session_id: str) -> dict | None: ...
    def query(self, table: str, pk: str, index: str | None = None) -> list[dict]: ...
    def transact(self, writes: list[Write]) -> None: ...


class MemoryStore:
    def __init__(self):
        self._items: dict[str, dict] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(table: str, pk: str, sk: str) -> str:
        return json.dumps([table, pk, sk])

    @contextmanager
    def _access(self, write: bool = False):
        with self._lock:
            yield

    def get(self, table: str, pk: str, sk: str) -> dict | None:
        with self._access():
            item = self._items.get(self._key(table, pk, sk))
            return copy.deepcopy(item["value"]) if item else None

    def query(self, table: str, pk: str, index: str | None = None) -> list[dict]:
        with self._access():
            key = {"bySession": "sessionKey", "byProfile": "profileKey"}.get(index, "pk")
            result = [
                copy.deepcopy(item["value"])
                for item in self._items.values()
                if item["table"] == table and item.get(key) == pk
            ]
            return result

    def get_owned(self, table: str, pk: str, sk: str, session_id: str) -> dict | None:
        item = self.get(table, pk, sk)
        return item if item and item.get("run", {}).get("sessionId") == session_id else None

    def transact(self, writes: list[Write]) -> None:
        keys = [self._key(w.table, w.pk, w.sk) for w in writes]
        if len(set(keys)) != len(keys):
            raise ValueError("A transaction cannot target an item twice")
        with self._access(write=True):
            for w, key in zip(writes, keys, strict=True):
                old = self._items.get(key)
                revision = old["value"]["revision"] if old else None
                if revision != w.expected:
                    raise Conflict()
            for w, key in zip(writes, keys, strict=True):
                if w.value is None:
                    self._items.pop(key, None)
                else:
                    self._items[key] = {
                        "table": w.table,
                        "pk": w.pk,
                        "sk": w.sk,
                        "value": copy.deepcopy(w.value),
                        **(w.indexes or {}),
                    }


class FileStore(MemoryStore):
    """Process-safe JSON snapshots, locked and fsync/rename committed.

    The lock file has a stable inode while the data file is replaced. This is
    appropriate for local development on a local filesystem, not NFS/Lambda.
    """

    def __init__(self, path: str | Path):
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @contextmanager
    def _access(self, write: bool = False):
        with self._lock, self.lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                self._items = json.loads(self.path.read_text()) if self.path.exists() else {}
                yield
                if write:
                    fd, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".aplomb-")
                    try:
                        with os.fdopen(fd, "wb") as stream:
                            stream.write(canonical(self._items))
                            stream.flush()
                            os.fsync(stream.fileno())
                        os.replace(temp, self.path)
                        directory = os.open(self.path.parent, os.O_DIRECTORY)
                        try:
                            os.fsync(directory)
                        finally:
                            os.close(directory)
                    finally:
                        if os.path.exists(temp):
                            os.unlink(temp)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


class BlobStore(Protocol):
    def put(self, data: bytes) -> dict: ...
    def get(self, reference: dict) -> bytes: ...


class S3Blobs:
    """Content addressed immutable spill with integrity verification on reads."""

    def __init__(self, client, bucket: str, prefix: str = ""):
        self.client, self.bucket = client, bucket
        self.prefix = prefix.strip("/")

    def put(self, data: bytes) -> dict:
        digest = hashlib.sha256(data).hexdigest()
        key = "/".join(filter(None, [self.prefix, "run-bundles", digest + ".json"]))
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/json",
            Metadata={"sha256": digest},
        )
        return {"key": key, "sha256": digest, "bytes": len(data)}

    def get(self, reference: dict) -> bytes:
        # Never use caller-supplied bucket/URL; references are private repository data.
        data = self.client.get_object(Bucket=self.bucket, Key=reference["key"])["Body"].read()
        if (
            len(data) != reference["bytes"]
            or hashlib.sha256(data).hexdigest() != reference["sha256"]
        ):
            raise ValueError("Stored bundle integrity check failed")
        return data


class DynamoStore:
    """Low-level injected boto3 client. No SDK calls until an operation occurs."""

    def __init__(
        self, client, tables: dict[str, str], blobs: BlobStore, spill_bytes: int = 240_000
    ):
        self.client, self.tables, self.blobs = client, tables, blobs
        self.spill_bytes = spill_bytes

    def _encode(self, w: Write, spill_bytes: int | None = None) -> dict:
        data = canonical(w.value)
        # Revision and indexes stay in DynamoDB for atomic conditions and queries.
        item = {"pk": {"S": w.pk}, "sk": {"S": w.sk}, "revision": {"N": str(w.value["revision"])}}
        if w.value.get("type") == "META":
            item["ownerSession"] = {"S": w.value["run"]["sessionId"]}
        for key, value in (w.indexes or {}).items():
            item[key] = {"N": str(value)} if isinstance(value, int) else {"S": value}
        if len(data) > (self.spill_bytes if spill_bytes is None else spill_bytes):
            item["blob"] = {"S": canonical(self.blobs.put(data)).decode()}
        else:
            item["document"] = {"S": data.decode()}
        return item

    def _decode(self, item: dict) -> dict:
        if "blob" in item:
            data = self.blobs.get(json.loads(item["blob"]["S"]))
        else:
            data = item["document"]["S"]
        return json.loads(data)

    def get(self, table: str, pk: str, sk: str) -> dict | None:
        result = self.client.get_item(
            TableName=self.tables[table],
            Key={"pk": {"S": pk}, "sk": {"S": sk}},
            ConsistentRead=True,
        )
        return self._decode(result["Item"]) if "Item" in result else None

    def get_owned(self, table: str, pk: str, sk: str, session_id: str) -> dict | None:
        result = self.client.get_item(
            TableName=self.tables[table],
            Key={"pk": {"S": pk}, "sk": {"S": sk}},
            ConsistentRead=True,
        )
        item = result.get("Item")
        if not item or item.get("ownerSession", {}).get("S") != session_id:
            return None
        return self._decode(item)

    def query(self, table: str, pk: str, index: str | None = None) -> list[dict]:
        attribute = {"bySession": "sessionKey", "byProfile": "profileKey"}.get(index, "pk")
        kwargs = {
            "TableName": self.tables[table],
            "KeyConditionExpression": "#pk = :pk",
            "ExpressionAttributeNames": {"#pk": attribute},
            "ExpressionAttributeValues": {":pk": {"S": pk}},
            "ConsistentRead": index is None,
        }
        if index:
            kwargs["IndexName"] = index
        items = []
        while True:
            page = self.client.query(**kwargs)
            # Re-read base items: ownership, revision and blobs must be current.
            for item in page.get("Items", []):
                if index:
                    session_id = pk.removeprefix("SESSION#").split("#PROFILE#")[0]
                    current = self.get_owned(table, item["pk"]["S"], item["sk"]["S"], session_id)
                else:
                    # Base-table Query is already strongly consistent. RunRepository's
                    # before/after META revision fence handles multi-page checkpoints;
                    # a GetItem per child adds latency and read cost without isolation.
                    current = self._decode(item)
                if current is not None:
                    items.append(current)
            if "LastEvaluatedKey" not in page:
                return items
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def transact(self, writes: list[Write]) -> None:
        if not writes or len(writes) > 100:
            raise ValueError("DynamoDB transaction requires 1–100 items")
        actions = []
        for w in writes:
            action = {
                "TableName": self.tables[w.table],
                "ConditionExpression": "attribute_not_exists(#rev)"
                if w.expected is None
                else "#rev = :expected",
                "ExpressionAttributeNames": {"#rev": "revision"},
            }
            if w.expected is not None:
                action["ExpressionAttributeValues"] = {":expected": {"N": str(w.expected)}}
            if w.value is None:
                action["Key"] = {"pk": {"S": w.pk}, "sk": {"S": w.sk}}
                actions.append({"Delete": action})
            else:
                # Reserve headroom for escaping, keys, metadata and expressions
                # under the 4 MB transaction limit, even with many medium items.
                action["Item"] = self._encode(w, min(self.spill_bytes, 1_500_000 // len(writes)))
                actions.append({"Put": action})
        if len(canonical(actions)) > 3_500_000:
            raise ValueError("Encoded transaction exceeds safe DynamoDB aggregate size")
        try:
            self.client.transact_write_items(TransactItems=actions)
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = response.get("Error", {}).get("Code")
            reasons = response.get("CancellationReasons", [])
            if code == "ConditionalCheckFailedException" or (
                code == "TransactionCanceledException"
                and any(
                    r.get("Code") in {"ConditionalCheckFailed", "TransactionConflict"}
                    for r in reasons
                )
            ):
                raise Conflict() from exc
            raise
