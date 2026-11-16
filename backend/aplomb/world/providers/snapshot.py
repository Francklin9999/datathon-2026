"""Immutable, content addressed provider captures with conservative temporal gates."""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1] / "bundle" / "providers"


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return parsed


def validate_row(row: dict) -> None:
    for field in ("id", "sourceId", "category", "title", "sourceUrl"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise ValueError(f"Missing observation {field}")
    if not row["sourceUrl"].startswith("https://"):
        raise ValueError("Source URL must use HTTPS")
    for field in ("retrievedAt", "availableAt"):
        timestamp(row[field])
    if timestamp(row["availableAt"]) < timestamp(row["retrievedAt"]):
        raise ValueError("Original availability unproven: gate at capture")
    lat, lon = row.get("latitude"), row.get("longitude")
    if (lat is None) != (lon is None):
        raise ValueError("Both coordinates are required")
    if lat is not None:
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in (lat, lon)):
            raise ValueError("Invalid coordinates")
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("Coordinates outside Earth")
    if row.get("countryIso3") is not None and not re.fullmatch(r"[A-Z]{3}", row["countryIso3"]):
        raise ValueError("Invalid ISO3")


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False) + "\n").encode()


def publish(directory: Path, rows: list[dict], metadata: dict, captures: list[tuple[str, bytes]]) -> dict:
    """Write a new directory; repeat identical publication is idempotent, conflicts fail."""
    if not rows:
        raise ValueError("Refusing empty provider publication")
    for row in rows:
        validate_row(row)
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate provider identifiers")
    rows = sorted(rows, key=lambda r: r["id"])
    content = canonical(rows)
    digest = hashlib.sha256(content).hexdigest()
    source = metadata["datasetId"]
    if not re.fullmatch(r"[a-z][a-z0-9_]+", source):
        raise ValueError("Invalid dataset identifier")
    if any(row["sourceId"] != source or row["retrievedAt"] != metadata["retrievedAt"] for row in rows):
        raise ValueError("Provider source or capture timestamp mismatch")
    if not captures:
        raise ValueError("Raw capture evidence is required")
    version = f"{source}-{metadata['retrievedAt'][:10]}-{digest[:16]}"
    raw_files = {f"raw-{i:03d}.bin": payload for i, (_, payload) in enumerate(captures)}
    manifest = {
        **metadata, "dataVersion": version, "rowCount": len(rows), "sha256": digest,
        "rawCaptures": [{"file": name, "url": captures[i][0], "sha256": hashlib.sha256(payload).hexdigest()}
                        for i, (name, payload) in enumerate(raw_files.items())],
        "historicalReplay": False,
        "availabilityRule": "Latest captured values; original historical availability is unproven. Gate at retrievedAt.",
    }
    files = {**raw_files, "observations.json": content, "manifest.json": canonical(manifest)}
    target = directory / version
    if target.exists():
        if any(not (target / name).exists() or (target / name).read_bytes() != body for name, body in files.items()):
            raise ValueError("Immutable provider version already exists with different content")
        return manifest
    staging_root = directory / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=version + "-", dir=staging_root))
    try:
        for name, body in files.items():
            (staging / name).write_bytes(body)
        staging.rename(target)
    except BaseException:
        # Never delete an existing version; only this unpublished temporary capture.
        shutil.rmtree(staging)
        raise
    return manifest


_VERSION_DIR = re.compile(r"([a-z][a-z0-9_]+)-\d{4}-\d{2}-\d{2}-[0-9a-f]{16}")


def _failed_source(path: Path) -> str:
    """Dataset ID of a damaged capture directory: its manifest's, else the one in its version name."""
    try:
        source = json.loads(path.read_bytes())["datasetId"]
        if isinstance(source, str) and source:
            return source
    except (ValueError, OSError, KeyError, TypeError):
        pass
    match = _VERSION_DIR.fullmatch(path.parent.name)
    return match.group(1) if match else path.parent.name


def load_provider_snapshots(directory: Path = DIRECTORY, *, as_of: str | None = None,
                            errors: list[tuple[str, str]] | None = None) -> tuple[tuple[dict, ...], tuple[dict, ...]]:
    """Latest valid version per source, with raw/normalized integrity and availability checks.

    An absent directory is unavailable. Corruption raises by default; callers isolate optional failures.
    With ``errors`` (a list), a damaged capture is recorded there as ``(datasetId, message)`` and its
    whole source is skipped, never replaced by an older version; other sources still load.
    Passing as_of gates at capture, never at an earlier observation/reference date.
    """
    if not directory.exists():
        return (), ()
    latest = {}
    failed: set[str] = set()
    for path in sorted(directory.glob("*/manifest.json")):
        if errors is None:
            _load_capture(path, as_of, latest)
            continue
        try:
            _load_capture(path, as_of, latest)
        except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:  # JSONDecodeError is a ValueError
            source = _failed_source(path)
            failed.add(source)
            errors.append((source, str(exc) or type(exc).__name__))
    for source in failed:
        latest.pop(source, None)
    return tuple(row for rows, _ in latest.values() for row in rows), tuple(m for _, m in latest.values())


def _load_capture(path: Path, as_of: str | None, latest: dict) -> None:
    """Validate one capture directory and keep it in ``latest`` when it is the newest for its source."""
    manifest = json.loads(path.read_bytes())
    content = (path.parent / "observations.json").read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest["sha256"]:
        raise ValueError("Provider observation checksum mismatch")
    rows = json.loads(content)
    if not isinstance(rows, list) or len(rows) != manifest["rowCount"]:
        raise ValueError("Provider row count mismatch")
    seen = set()
    for row in rows:
        validate_row(row)
        if (row["sourceId"] != manifest["datasetId"] or row["id"] in seen
                or row["retrievedAt"] != manifest["retrievedAt"]):
            raise ValueError("Provider source identity or duplicate mismatch")
        seen.add(row["id"])
    for raw in manifest["rawCaptures"]:
        name = raw["file"]
        if not re.fullmatch(r"raw-\d{3}\.bin", name):
            raise ValueError("Invalid raw capture path")
        if hashlib.sha256((path.parent / name).read_bytes()).hexdigest() != raw["sha256"]:
            raise ValueError("Provider raw capture checksum mismatch")
    captured = timestamp(manifest["retrievedAt"])
    if as_of is not None and captured > timestamp(as_of):
        return
    source = manifest["datasetId"]
    if source not in latest or captured > timestamp(latest[source][1]["retrievedAt"]):
        latest[source] = (rows, manifest)
