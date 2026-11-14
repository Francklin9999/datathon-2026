"""Default domain composition for the exported application (``aplomb.api.app:app``).

Wires the datastore (T04), profiles (T06) and deterministic checks (T05–T07) into ``Services``.
Nothing is read at import or app creation: the pinned snapshot opens on the first request that
needs it (local ``data/`` directory, or S3 objects cached under ``/tmp`` after checksum
verification). ``create_app(settings)`` without services keeps its provider-less behaviour.
Runs (T08 worker/preparer), parsing, world and replay providers are not wired here.
"""

from __future__ import annotations

import threading
from pathlib import Path

from aplomb.datastore import CachedObjectStore, DatastoreError, LocalDataStore, Snapshot

from .composition import create_repositories
from .errors import ServiceError
from .services import Services
from .settings import Settings

REPO_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
S3_CACHE_DIR = Path("/tmp/aplomb-data")


class SnapshotProvider:
    """Opens the pinned snapshot once, lazily; failures surface as ``upstream_unavailable``."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._snapshot: Snapshot | None = None
        self._lock = threading.Lock()

    def _store(self):
        s = self.settings
        if s.environment == "aws" or (s.data_bucket and not s.data_dir):
            import boto3

            client = boto3.Session(region_name=s.region).client("s3")
            prefix = s.data_prefix.strip("/")

            def fetch(key: str) -> bytes:
                full = f"{prefix}/{key}" if prefix else key
                return client.get_object(Bucket=s.data_bucket, Key=full)["Body"].read()

            return CachedObjectStore(fetch, S3_CACHE_DIR)
        return LocalDataStore(Path(s.data_dir) if s.data_dir else REPO_DATA_DIR)

    def __call__(self) -> Snapshot:
        with self._lock:
            if self._snapshot is None:
                try:
                    snap = self._store().open(self.settings.data_version)
                except DatastoreError as exc:
                    raise ServiceError("upstream_unavailable", f"Pinned data snapshot unavailable: {exc}") from exc
                if snap.data_as_of != self.settings.data_as_of:
                    raise ServiceError("upstream_unavailable",
                                       f"Snapshot {snap.data_version} ends {snap.data_as_of}, but APLOMB_DATA_AS_OF is {self.settings.data_as_of}")
                self._snapshot = snap
            return self._snapshot


def default_services(settings: Settings, store=None) -> Services:
    """Domain providers for a configured snapshot; empty ``Services`` when unconfigured."""
    if settings.data_version == "unconfigured":
        return Services()
    from aplomb.datastore.service import DatastoreService
    from aplomb.optimizer.services import build_domain_services

    snapshot = SnapshotProvider(settings)
    profile_repo, _, _ = create_repositories(settings, store)
    profiles, checks = build_domain_services(profile_repo, snapshot)
    # Advertise only flags whose provider is implemented and tested here.
    return Services(profiles=profiles, checks=checks, datastore=DatastoreService(snapshot), capabilities={"profile_creator"})
