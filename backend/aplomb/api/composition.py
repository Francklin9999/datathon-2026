"""Repository factories, including lazy AWS construction without startup I/O."""

import threading

from .repositories import CacheRepository, ProfileRepository, RunRepository
from .settings import Settings
from .storage import DynamoStore, FileStore, MemoryStore, S3Blobs


class LazyAWSStore:
    def __init__(self, settings: Settings):
        self.settings, self._store = settings, None
        self._lock = threading.Lock()

    def _get_store(self):
        with self._lock:
            if self._store is None:
                import boto3
                from botocore.config import Config

                s = self.settings
                config = Config(
                    connect_timeout=3,
                    read_timeout=5,
                    retries={"mode": "standard", "max_attempts": 2},
                )
                session = boto3.Session(region_name=s.region)
                blobs = S3Blobs(session.client("s3", config=config), s.data_bucket, "evidence")
                self._store = DynamoStore(
                    session.client("dynamodb", config=config),
                    {
                        "runs": s.runs_table,
                        "profiles": s.profiles_table,
                        "cache": s.cache_table,
                    },
                    blobs,
                )
        return self._store

    def get(self, *args, **kwargs):
        return self._get_store().get(*args, **kwargs)

    def get_owned(self, *args, **kwargs):
        return self._get_store().get_owned(*args, **kwargs)

    def query(self, *args, **kwargs):
        return self._get_store().query(*args, **kwargs)

    def transact(self, *args, **kwargs):
        return self._get_store().transact(*args, **kwargs)


def create_store(settings: Settings):
    if settings.environment == "aws":
        return LazyAWSStore(settings)
    return FileStore(settings.local_state_file) if settings.local_state_file else MemoryStore()


def create_repositories(settings: Settings, store=None):
    store = store if store is not None else create_store(settings)
    return (
        ProfileRepository(store),
        RunRepository(
            store, hard_seconds=settings.run_hard_seconds, lease_seconds=settings.lease_seconds
        ),
        CacheRepository(store),
    )
