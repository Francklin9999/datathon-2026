"""Versioned snapshots and gated reads (track T04; see SPEC.md in this folder).

Typical use::

    store = LocalDataStore("data")
    snap = store.open(store.active_version())        # pin this version for the whole run
    gate = snap.gate(as_of="2026-11-12", mode="current")
    prices = gate.prices(["TSLA"], None, "2026-11-12")  # DataSlice with rows_read / rows_withheld
    frame = gate.price_frame(["TSLA", "SPY"])            # master-calendar PriceFrame for quant
    asset = gate.universe().get("TSLA").to_wire()        # schemas.md Asset

Ingestion (``aplomb.datastore.ingest``) and on-demand publication (``aplomb.datastore.ondemand``)
are not imported here: run contexts only need the readers below.
"""

from .errors import (
    DatasetMissing,
    DatasetNotFound,
    DatastoreError,
    IngestionError,
    InvalidGateRequest,
    SnapshotIntegrityError,
    UnknownSeries,
    UnknownTicker,
)
from .gate import TemporalGate
from .snapshot import CachedObjectStore, DataStore, LocalDataStore, Snapshot
from .types import (
    DatasetRead,
    DataSlice,
    FxSeries,
    GateMode,
    MasterCalendar,
    PriceFrame,
    merge_reads,
)
from .universe import AssetHistory, AssetRecord, Universe

__all__ = [
    "AssetHistory", "AssetRecord", "CachedObjectStore", "DataSlice", "DataStore", "DatasetMissing",
    "DatasetNotFound", "DatasetRead", "DatastoreError", "FxSeries", "GateMode", "IngestionError",
    "InvalidGateRequest", "LocalDataStore", "MasterCalendar", "PriceFrame", "Snapshot",
    "SnapshotIntegrityError", "TemporalGate", "Universe", "UnknownSeries", "UnknownTicker", "merge_reads",
]
