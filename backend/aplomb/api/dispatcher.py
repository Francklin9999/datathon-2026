"""Dispatch implementations independent of HTTP response background tasks."""

import json
import logging
import re
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Protocol

from .errors import unavailable

log = logging.getLogger(__name__)


class Dispatcher(Protocol):
    def dispatch(self, run_id: str, generation: int) -> None: ...


class LocalDispatcher:
    """A bounded process executor; workers checkpoint the shared repository.

    Not tied to a request, asyncio loop or FastAPI BackgroundTasks. FileStore
    allows reload/restart polling. Persist/enqueue crash recovery is the queued
    watchdog; active stale leases are recovered by explicit redispatch/claim.
    """

    def __init__(
        self, worker: Callable[[dict], object], max_workers: int = 2, max_pending: int = 32
    ):
        import threading

        self.worker = worker
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="aplomb")
        self.slots = threading.BoundedSemaphore(max_pending)

    def dispatch(self, run_id: str, generation: int) -> None:
        if not self.slots.acquire(blocking=False):
            raise unavailable("Local worker queue capacity")
        try:
            future = self.executor.submit(self.worker, {"runId": run_id, "generation": generation})
        except Exception:
            self.slots.release()
            raise
        future.add_done_callback(self._finished)

    def _finished(self, future: Future) -> None:
        self.slots.release()
        if future.exception() is not None:
            # No user payload or exception text in logs; worker owns durable error details.
            log.error(
                "Local worker failed", extra={"exception_type": type(future.exception()).__name__}
            )

    def close(self) -> None:
        self.executor.shutdown(wait=True)


class LambdaDispatcher:
    def __init__(self, client, function_name: str, repository=None):
        self.client, self.function_name = client, function_name
        self.repository = repository

    def dispatch(self, run_id: str, generation: int) -> None:
        target = self.function_name
        if self.repository is not None:
            # The API, not request JSON, pins this private field at creation. Reuse it
            # for a resumed generation even after a newer release is deployed.
            target = self.repository._read(run_id).private.get("workerFunction") or target
            pattern = r"arn:aws:lambda:[a-z0-9-]+:[0-9]{12}:function:[A-Za-z0-9_-]+:[1-9][0-9]*"
            if (not re.fullmatch(pattern, target) or not re.fullmatch(pattern, self.function_name)
                    or target.rsplit(":", 1)[0] != self.function_name.rsplit(":", 1)[0]):
                raise unavailable("Pinned worker version")
        response = self.client.invoke(
            FunctionName=target,
            InvocationType="Event",
            Payload=json.dumps({"runId": run_id, "generation": generation}).encode(),
        )
        if response.get("StatusCode") != 202:
            raise unavailable("Worker dispatch")
