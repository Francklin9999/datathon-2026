"""Immutable snapshots and the stores that open them (datastore SPEC §2–§3).

``DataStore.open(version)`` verifies the manifest and every dataset checksum, rejects unknown
schemas, and returns a ``Snapshot``. ``Snapshot.gate(as_of, mode)`` is the only run-visible
reader; the snapshot exposes no unfiltered row accessor.
"""

from __future__ import annotations

import csv
import io
import json
import os
import secrets
import stat
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Protocol

from .constants import CONTRACT_VERSION, DATASET_IDS
from .errors import DatasetMissing, DatasetNotFound, SnapshotIntegrityError
from .integrity import VERSION_RE, sha256_hex
from .passports import build_passports, traps
from .schemas import MANIFEST_SCHEMA_VERSION, NORMALIZED, NormalizedSchema
from .timeutil import parse_date
from .types import GATE_MODES

if TYPE_CHECKING:
    from .gate import TemporalGate

_NULLABLE = frozenset({"gics_sector", "country", "source_url", "published_at", "vintage_at"})
AVAIL_KEYS = {"current": "available_at", "historical": "available_at_historical"}


class DataStore(Protocol):
    def open(self, data_version: str) -> "Snapshot": ...


@dataclass(frozen=True)
class _Table:
    schema: NormalizedSchema
    rows: tuple[dict, ...]
    by: dict  # index name -> mapping


def _parse_table(dataset_id: str, payload: bytes) -> _Table:
    schema = NORMALIZED[dataset_id]
    text = payload.decode("utf-8")
    if '"' not in text and "\r" not in text:
        # Fast path: our writer only quotes fields containing commas, quotes or newlines.
        lines = text.split("\n")
        header = tuple(lines[0].split(",")) if lines and lines[0] else ()
        records = [line.split(",") for line in lines[1:] if line]
    else:
        reader = csv.reader(io.StringIO(text, newline=""))
        header = tuple(next(reader, ()))
        records = list(reader)
    if header != schema.names:
        raise SnapshotIntegrityError(f"{dataset_id}: normalized header {header} does not match schema v{schema.schema_version}")
    width = len(header)
    for rec in records:
        if len(rec) != width:
            raise SnapshotIntegrityError(f"{dataset_id}: malformed normalized row {rec}")
    # Column-wise conversion (much faster than per-cell branching on 40k-row tables).
    columns = list(zip(*records)) if records else [() for _ in header]
    converted = []
    for col, values in zip(schema.columns, columns):
        if col.name.startswith("available_at"):
            converted.append(values)
        elif col.type == "number":
            converted.append(tuple(map(float, values)))
        elif col.type == "boolean":
            converted.append(tuple(v == "true" for v in values))
        elif col.name in _NULLABLE:
            converted.append(tuple(v or None for v in values))
        else:
            converted.append(values)
    rows = [dict(zip(header, vals)) for vals in zip(*converted)]
    return _Table(schema, tuple(rows), _index(dataset_id, rows))


def _index(dataset_id: str, rows: list[dict]) -> dict:
    """Group rows by their natural key, each group sorted by date, with a parallel date list."""
    key = {"prices_daily": "ticker", "macro_rates": "series_id", "corporate_actions": "ticker",
           "asset_themes": "ticker", "assets_universe": "ticker", "macro_release_dates": "series_id",
           "fx_boc_global": "currency"}.get(dataset_id)
    date_col = NORMALIZED[dataset_id].date_column
    out: dict = {}
    if key:
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            groups[r[key]].append(r)
        if date_col:
            for g in groups.values():
                g.sort(key=lambda r: r[date_col])
        out["group"] = {k: (tuple(r[date_col] for r in g) if date_col else (), tuple(g)) for k, g in groups.items()}
    if date_col:
        ordered = sorted(rows, key=lambda r: r[date_col])
        out["all"] = (tuple(r[date_col] for r in ordered), tuple(ordered))
    return out


def validate_manifest(manifest: dict, data_version: str) -> None:
    if manifest.get("manifestSchemaVersion") != MANIFEST_SCHEMA_VERSION:
        raise SnapshotIntegrityError(f"{data_version}: unknown manifest schema {manifest.get('manifestSchemaVersion')!r}")
    if str(manifest.get("contractVersion", "")).split(".")[0] != CONTRACT_VERSION.split(".")[0]:
        raise SnapshotIntegrityError(f"{data_version}: contract {manifest.get('contractVersion')!r} incompatible with {CONTRACT_VERSION}")
    if manifest.get("dataVersion") != data_version:
        raise SnapshotIntegrityError(f"manifest names {manifest.get('dataVersion')!r}, expected {data_version!r}")
    if not manifest.get("createdAt"):
        raise SnapshotIntegrityError(f"{data_version}: manifest lacks createdAt")
    datasets =manifest.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise SnapshotIntegrityError(f"{data_version}: manifest lists no datasets")
    for ds_id, meta in datasets.items():
        schema = NORMALIZED.get(ds_id)
        if schema is None:
            raise SnapshotIntegrityError(f"{data_version}: unknown dataset {ds_id!r} in manifest")
        if meta.get("schemaVersion") != schema.schema_version:
            raise SnapshotIntegrityError(f"{data_version}/{ds_id}: unknown schema version {meta.get('schemaVersion')!r}")
        for k in ("path", "sha256", "rowCount"):
            if k not in meta:
                raise SnapshotIntegrityError(f"{data_version}/{ds_id}: manifest entry lacks {k}")
    for ds_id in ("assets_universe", "prices_daily", "fx_usdcad_daily"):
        if ds_id not in datasets:
            raise SnapshotIntegrityError(f"{data_version}: partial snapshot, {ds_id} missing")


class Snapshot:
    """A verified, immutable data version. Read through ``gate()`` only."""

    def __init__(self, manifest: dict, payloads: dict[str, bytes]) -> None:
        version = manifest.get("dataVersion", "")
        validate_manifest(manifest, version)
        tables: dict[str, _Table] = {}
        for ds_id, meta in manifest["datasets"].items():
            payload = payloads.get(ds_id)
            if payload is None:
                raise SnapshotIntegrityError(f"{version}/{ds_id}: file missing")
            if sha256_hex(payload) != meta["sha256"]:
                raise SnapshotIntegrityError(f"{version}/{ds_id}: checksum does not match the manifest")
            table = _parse_table(ds_id, payload)
            if len(table.rows) != meta["rowCount"]:
                raise SnapshotIntegrityError(f"{version}/{ds_id}: {len(table.rows)} rows, manifest says {meta['rowCount']}")
            tables[ds_id] = table
        self._manifest_json = json.dumps(manifest, sort_keys=True)
        self._tables = tables
        self.data_version: str = version
        self.data_as_of: str = manifest["dataAsOf"]
        self._passports = {p["datasetId"]: p for p in build_passports(manifest)}

    # Metadata ---------------------------------------------------------------------------------

    @property
    def manifest(self) -> dict:
        """A copy of the manifest (mutating it cannot alter the snapshot)."""
        return json.loads(self._manifest_json)

    @property
    def loaded_datasets(self) -> tuple[str, ...]:
        return tuple(ds for ds in DATASET_IDS if ds in self._tables)

    def passports(self) -> list[dict]:
        return [json.loads(json.dumps(self._passports[ds])) for ds in DATASET_IDS]

    def passport(self, dataset_id: str) -> dict:
        if dataset_id not in self._passports:
            raise DatasetNotFound(f"unknown dataset {dataset_id!r}")
        return json.loads(json.dumps(self._passports[dataset_id]))

    def traps(self) -> list[dict]:
        return traps()

    def datasets_response(self) -> dict:
        """Body of ``GET /datasets`` (api.md §8.1)."""
        return {"items": self.passports(), "traps": self.traps()}

    # Reads ------------------------------------------------------------------------------------

    def gate(self, as_of: date | str, mode: str = "current") -> "TemporalGate":
        from .gate import TemporalGate

        return TemporalGate(self, as_of, mode)

    def _table(self, dataset_id: str) -> _Table:
        if dataset_id not in self._tables:
            if dataset_id in DATASET_IDS:
                raise DatasetMissing(f"{dataset_id} is not loaded in {self.data_version}")
            raise DatasetNotFound(f"unknown dataset {dataset_id!r}")
        return self._tables[dataset_id]


# --- Stores ------------------------------------------------------------------------------------


def _check_version_label(data_version: str) -> None:
    if not VERSION_RE.match(data_version or ""):
        raise SnapshotIntegrityError(f"invalid data version {data_version!r}")


class LocalDataStore:
    """Snapshots under a local data root (``data/`` in the repository, or a Lambda copy)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self._cache: dict[str, Snapshot] = {}
        self._lock = threading.Lock()

    def active_version(self) -> str:
        path = self.root / "manifests" / "active.json"
        if not path.is_file():
            raise SnapshotIntegrityError(f"no active snapshot: {path} missing")
        version = json.loads(path.read_text(encoding="utf-8")).get("dataVersion", "")
        _check_version_label(version)
        return version

    def open(self, data_version: str) -> Snapshot:
        _check_version_label(data_version)
        with self._lock:
            cached = self._cache.get(data_version)
            if cached is not None:
                return cached
            manifest_path = self.root / "manifests" / f"{data_version}.json"
            if not manifest_path.is_file():
                raise SnapshotIntegrityError(f"unknown data version {data_version}: {manifest_path} missing")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            validate_manifest(manifest, data_version)
            payloads = {}
            for ds_id, meta in manifest["datasets"].items():
                path = self.root / meta["path"]
                if not path.is_file():
                    raise SnapshotIntegrityError(
                        f"{data_version}/{ds_id}: {path} missing (run the ingestion CLI to materialize it)")
                payloads[ds_id] = path.read_bytes()
            snap = Snapshot(manifest, payloads)
            self._cache[data_version] = snap
            return snap


Fetch = Callable[[str], bytes]


class CachedObjectStore:
    """Snapshot reader over an object store (S3) with a local checksum-verified cache.

    ``fetch(key)`` returns the bytes of an object key relative to the snapshot prefix
    (``manifests/<v>.json``, ``normalized/<v>/<id>.csv``); T02/T03 inject a boto3-backed
    callable. Cached files are named by checksum, written to a temporary file, renamed
    atomically and made read-only. The cache (e.g. Lambda ``/tmp``) is an optimization only:
    the manifest and checksums decide what is valid.
    """

    def __init__(self, fetch: Fetch, cache_dir: Path | str) -> None:
        self._fetch = fetch
        self.cache_dir = Path(cache_dir)
        self._cache: dict[str, Snapshot] = {}
        self._lock = threading.Lock()

    def active_version(self) -> str:
        version = json.loads(self._fetch("manifests/active.json").decode("utf-8")).get("dataVersion", "")
        _check_version_label(version)
        return version

    def open(self, data_version: str) -> Snapshot:
        _check_version_label(data_version)
        with self._lock:
            cached = self._cache.get(data_version)
            if cached is not None:
                return cached
            manifest = json.loads(self._fetch(f"manifests/{data_version}.json").decode("utf-8"))
            validate_manifest(manifest, data_version)
            payloads = {ds_id: self._cached_object(data_version, meta) for ds_id, meta in manifest["datasets"].items()}
            snap = Snapshot(manifest, payloads)
            self._cache[data_version] = snap
            return snap

    def _cached_object(self, data_version: str, meta: dict) -> bytes:
        folder = self.cache_dir / data_version
        target = folder / f"{meta['sha256']}-{Path(meta['path']).name}"
        if target.is_file():
            data = target.read_bytes()
            if sha256_hex(data) == meta["sha256"]:
                return data
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            target.unlink()
        data = self._fetch(meta["path"])
        if sha256_hex(data) != meta["sha256"]:
            raise SnapshotIntegrityError(f"{meta['path']}: downloaded object does not match the manifest checksum")
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f".{target.name}.{secrets.token_hex(4)}.tmp"
        tmp.write_bytes(data)
        os.replace(tmp, target)
        os.chmod(target, stat.S_IREAD)
        return data


def validate_gate_args(as_of: date | str, mode: str) -> tuple[date, str]:
    from .errors import InvalidGateRequest

    if mode not in GATE_MODES:
        raise InvalidGateRequest(f"mode must be one of {GATE_MODES}, got {mode!r}")
    try:
        return parse_date(as_of, "as_of"), mode
    except ValueError as exc:
        raise InvalidGateRequest(str(exc)) from exc
