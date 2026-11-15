"""World Explorer backend (track T11; see SPEC.md in this folder).

    dataset = BundleProvider()                       # integrity-checked bundle, loaded lazily
    world = WorldServiceImpl(profiles, snapshot, dataset)
    world.events(session_id, {"profileId": "robert"})

The bundle is produced by ``python -m aplomb.world.ingest`` from real public sources.
"""

from .dataset import BundleProvider, WorldDataError, WorldDataset, load_bundle
from .passports import WorldDatastoreService, world_passports
from .service import WorldServiceImpl

__all__ = ["BundleProvider", "WorldDataError", "WorldDataset", "WorldDatastoreService", "WorldServiceImpl",
           "load_bundle", "world_passports"]
