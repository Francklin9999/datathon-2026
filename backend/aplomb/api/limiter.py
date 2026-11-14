"""Session quotas reserved atomically in the same store on every HTTP process."""

import hashlib
import time
from typing import Callable

from .errors import Conflict, ServiceError
from .storage import Store, Write


class SessionLimiter:
    def __init__(self, store: Store, clock: Callable[[], float] = time.time):
        self.store, self.clock = store, clock

    def take(self, session: str, bucket: str, limit: int, seconds: int) -> None:
        now = self.clock()
        # Sliding window, not fixed buckets that permit 2x bursts at a boundary.
        pk = "LIMIT#" + hashlib.sha256(f"{session}:{bucket}".encode()).hexdigest()
        for _ in range(12):
            prior = self.store.get("cache", pk, "WINDOW")
            revision = prior["revision"] if prior else None
            times = [t for t in prior["times"] if t > now - seconds] if prior else []
            if len(times) >= limit:
                raise ServiceError(
                    "rate_limited",
                    "Session request limit exceeded",
                    {"retryAfterSeconds": max(1, int(times[0] + seconds - now) + 1)},
                )
            item = {
                "revision": (revision or 0) + 1,
                "times": times + [now],
                "expiresAt": int(now) + seconds + 1,
            }
            try:
                self.store.transact(
                    [Write("cache", pk, "WINDOW", item, revision, {"expiresAt": item["expiresAt"]})]
                )
                return
            except Conflict:
                continue
        raise ServiceError("rate_limited", "Session request contention; retry shortly")
