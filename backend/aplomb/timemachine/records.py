"""Point-in-time selector for source records with explicit, evidenced availability.

This is a narrow provider interface: no sources are fabricated or fetched here, and
callers must establish source rights and preserve original records separately. Unknown
availability is withheld; a retrieval timestamp is not an original publication time.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from aplomb.datastore.timeutil import boundary_for, normalize_ts, parse_date

KINDS = frozenset({"security", "fundamental", "news", "ownership", "filing"})


@dataclass(frozen=True)
class PointInTimeRecord:
    record_id: str
    revision_id: str
    kind: str
    observation_date: str
    published_at: str | None
    available_at: str | None
    retrieved_at: str
    dataset_version: str
    source_url: str
    content_hash: str
    payload: str

    def __post_init__(self):
        if self.kind not in KINDS or not self.record_id or not self.revision_id or not self.dataset_version:
            raise ValueError("invalid record identity")
        parse_date(self.observation_date, "observation_date")
        retrieved = normalize_ts(self.retrieved_at, "retrieved_at")
        published = normalize_ts(self.published_at, "published_at") if self.published_at else None
        available = normalize_ts(self.available_at, "available_at") if self.available_at else None
        if published and available and available < published:
            raise ValueError("availability precedes publication")
        if available and available > retrieved:
            raise ValueError("availability exceeds capture")
        if not self.source_url.startswith("https://") or "?" in self.source_url or "#" in self.source_url:
            raise ValueError("source URL must be HTTPS without query or fragment")
        if hashlib.sha256(self.payload.encode()).hexdigest() != self.content_hash:
            raise ValueError("source content hash mismatch")


class PointInTimeRecords:
    """Immutable versioned record bundle, with exact revision identity and a date gate."""

    def __init__(self, version: str, records: tuple[PointInTimeRecord, ...]):
        if not version or any(row.dataset_version != version for row in records):
            raise ValueError("dataset version mismatch")
        keys = [(row.kind, row.record_id, row.revision_id) for row in records]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate revision")
        self.version, self._records = version, tuple(records)

    def select(self, cutoff: str) -> tuple[PointInTimeRecord, ...]:
        day = parse_date(cutoff, "cutoff")
        boundary = boundary_for(day)
        selected: dict[tuple[str, str], PointInTimeRecord] = {}
        for row in self._records:
            if (date.fromisoformat(row.observation_date) > day or row.available_at is None
                    or normalize_ts(row.available_at) >= boundary):
                continue
            key = (row.kind, row.record_id)
            previous = selected.get(key)
            if previous and normalize_ts(previous.available_at) == normalize_ts(row.available_at):
                raise ValueError("ambiguous revisions at identical availability")
            if previous is None or normalize_ts(row.available_at) > normalize_ts(previous.available_at):
                selected[key] = row
        return tuple(selected[key] for key in sorted(selected))

    def digest(self) -> str:
        from dataclasses import asdict
        raw = json.dumps([asdict(row) for row in self._records], sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()
