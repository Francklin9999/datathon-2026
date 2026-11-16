"""Read side of the world bundle: integrity-checked, immutable, loaded once per process."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

from .country_macro import load_snapshot
from .geo import present_event, present_name, present_rows
from .ingest import BUNDLE_DIR, content_hash


class WorldDataError(RuntimeError):
    """The bundle is absent or does not match its manifest."""


@dataclass(frozen=True)
class WorldDataset:
    version: str
    built_at: str
    events: tuple[dict, ...]
    hazards: tuple[dict, ...]
    manifest: dict
    country_macro: tuple[dict, ...] = ()
    country_macro_manifest: dict | None = None

    @property
    def coverage(self) -> dict | None:
        return self.manifest["events"]["coverage"]

    def event(self, event_id: str) -> dict | None:
        return self._index().get(event_id)

    def _index(self) -> dict[str, dict]:
        index = self.__dict__.get("_by_id")
        if index is None:
            index = {e["eventId"]: e for e in self.events}
            object.__setattr__(self, "_by_id", index)
        return index


def load_bundle(directory: Path | str = BUNDLE_DIR) -> WorldDataset:
    """Verify every file hash against the manifest; a mismatch is an error, never a partial load."""
    directory = Path(directory)
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        loaded = {}
        for name, meta in manifest["files"].items():
            text = (directory / name).read_text(encoding="utf-8")
            if content_hash(text) != meta["sha256"]:
                raise WorldDataError(f"{name} does not match the manifest checksum")
            loaded[name] = json.loads(text)
    except (OSError, KeyError, ValueError) as exc:
        raise WorldDataError(f"World bundle unavailable: {exc}") from exc
    events, hazards = loaded.get("events.json", []), loaded.get("hazards.json", [])
    if len(events) != manifest["events"]["count"] or len(hazards) != manifest["hazards"]["count"]:
        raise WorldDataError("World bundle row counts differ from the manifest")
    try:
        country_macro, country_macro_manifest = load_snapshot(directory)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise WorldDataError(f"World Bank snapshot unavailable: {exc}") from exc
    # Team decision (geo.PRESENTED_AS), applied once here after every checksum passed: ISR, Israel,
    # West Bank and Gaza are presented as PSE / Palestine. Where the World Bank has both an ISR and a
    # PSE series for an indicator, its own PSE series is served and the ISR rows are withheld.
    events = [present_event(event) for event in events]
    hazards = [dict(hazard, title=present_name(hazard["title"])) for hazard in hazards]
    country_macro = tuple(present_rows(country_macro, lambda row: row["indicatorId"])[0])
    return WorldDataset(manifest["worldVersion"], manifest["builtAt"], tuple(events), tuple(hazards), manifest,
                        country_macro, country_macro_manifest)


class BundleProvider:
    """Lazy, cached loader; a failed load is retried on the next call rather than cached."""

    def __init__(self, directory: Path | str = BUNDLE_DIR) -> None:
        self.directory = Path(directory)
        self._dataset: WorldDataset | None = None
        self._lock = threading.Lock()

    def __call__(self) -> WorldDataset:
        with self._lock:
            if self._dataset is None:
                self._dataset = load_bundle(self.directory)
            return self._dataset

    def available(self) -> bool:
        try:
            self()
            return True
        except WorldDataError:
            return False
