"""Default domain composition for the exported application (``aplomb.api.app:app``).

Wires the datastore (T04), profiles (T06) and deterministic checks (T05–T07) into ``Services``.
Nothing is read at import or app creation: the pinned snapshot opens on the first request that
needs it (local ``data/`` directory, or S3 objects cached under ``/tmp`` after checksum
verification). ``create_app(settings)`` without services keeps its provider-less behaviour.
Runs (T08 worker/preparer), parsing, world and replay providers are not wired here.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from aplomb.datastore import (
    CachedObjectStore,
    DatastoreError,
    LocalDataStore,
    Snapshot,
    SnapshotIntegrityError,
)

from .composition import create_repositories
from .errors import ServiceError
from .services import Services
from .settings import Settings

log = logging.getLogger(__name__)
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
            from botocore.exceptions import BotoCoreError, ClientError

            client = boto3.Session(region_name=s.region).client("s3")
            prefix = s.data_prefix.strip("/")

            def fetch(key: str) -> bytes:
                full = f"{prefix}/{key}" if prefix else key
                try:
                    return client.get_object(Bucket=s.data_bucket, Key=full)["Body"].read()
                except (BotoCoreError, ClientError) as exc:
                    # Key and error class only: no bucket, account or credential detail.
                    raise SnapshotIntegrityError(
                        f"{key}: object store read failed ({type(exc).__name__})"
                    ) from exc

            return CachedObjectStore(fetch, S3_CACHE_DIR)
        return LocalDataStore(Path(s.data_dir) if s.data_dir else REPO_DATA_DIR)

    def __call__(self) -> Snapshot:
        with self._lock:
            if self._snapshot is None:
                try:
                    snap = self._store().open(self.settings.data_version)
                except DatastoreError as exc:
                    raise ServiceError("upstream_unavailable", f"Pinned data snapshot unavailable: {exc}") from exc
                except Exception as exc:
                    # Client creation, credentials, region, a full cache disk or an unparsable
                    # manifest: an unreachable source, not an unexpected error (catalog §7).
                    log.error("Snapshot open failed", extra={"exception_type": type(exc).__name__})
                    raise ServiceError("upstream_unavailable",
                                       f"Pinned data snapshot unavailable: {type(exc).__name__}") from exc
                if snap.data_as_of != self.settings.data_as_of:
                    raise ServiceError("upstream_unavailable",
                                       f"Snapshot {snap.data_version} ends {snap.data_as_of}, but APLOMB_DATA_AS_OF is {self.settings.data_as_of}")
                self._snapshot = snap
            return self._snapshot


def world_provider(profile_repo, snapshot, profiles=None):
    """World service over the packaged bundle, or ``None`` when the bundle cannot be verified."""
    from aplomb.world import BundleProvider, WorldServiceImpl

    bundle = BundleProvider()
    if not bundle.available():
        return None
    if profiles is None:
        from aplomb.optimizer.services import build_domain_services

        profiles, _ = build_domain_services(profile_repo, snapshot)
    return WorldServiceImpl(profiles, snapshot, bundle)


def default_services(settings: Settings, store=None, gateway=None) -> Services:
    """Domain providers for a configured snapshot; empty ``Services`` when unconfigured.

    Wired: datastore (T04), profiles/checks (T05-T07), runs (T03 + T08 + T10, with T09 research
    tools), world (T11) and replay (T12). A capability is advertised only when its provider is
    present; each still needs its ``APLOMB_FEATURE_*`` flag. Runs need configured model IDs.
    """
    if settings.data_version == "unconfigured":
        return Services()
    from aplomb.optimizer.services import build_domain_services
    from aplomb.timemachine import ReplayServiceImpl
    from aplomb.world import BundleProvider, WorldDatastoreService

    from .runtime import build_run_services

    snapshot = SnapshotProvider(settings)
    profile_repo, run_repo, _ = create_repositories(settings, store)
    profiles, checks = build_domain_services(profile_repo, snapshot)
    world = world_provider(profile_repo, snapshot, profiles)
    runs, parser, find_brief = build_run_services(settings, run_repo, profiles, snapshot, world, gateway)
    profiles.brief_finder = find_brief
    capabilities = {"profile_creator", "frontier_chart", "goal_requests", "time_machine", "bilingual"}
    if world is not None:
        capabilities.add("world_explorer")
        if world.dataset().hazards:
            capabilities.add("world_layer_hazards")
    return Services(profiles=profiles, checks=checks, runs=runs, parser=parser, world=world,
                    replay=ReplayServiceImpl(snapshot), datastore=WorldDatastoreService(snapshot, BundleProvider()),
                    capabilities=capabilities)
