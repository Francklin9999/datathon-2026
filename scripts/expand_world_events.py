"""Capture additional USGS events and build a verified expansion of the existing world bundle.

The prior official releases and earthquake archive are retained. Every captured earthquake is a
hazard; the event feed keeps only USGS earthquakes of magnitude 6.0 or more (``ingest.FEED_RULE``).
A new output directory is required so the capture can be checked before replacing the packaged bundle.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from aplomb.contracts.models import Hazard, WorldEvent
from aplomb.world.dataset import load_bundle
from aplomb.world.ingest import (
    BUNDLE_DIR,
    REPO_ROOT,
    build_bundle,
    http_get,
    parse_usgs,
    write_bundle,
)


def expand(base: Path, out: Path, capture_dir: Path, start: str, end: str, minimum: float) -> dict:
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if not 0 <= (last - first).days <= 366 or not 4.5 <= minimum <= 10:
        raise ValueError("Use an ordered window of at most 366 days and magnitude between 4.5 and 10")
    if out.exists():
        raise ValueError("Output directory already exists; choose a fresh directory")
    old = load_bundle(base)
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query?" + urlencode({
        "format": "geojson", "eventtype": "earthquake", "starttime": start,
        "endtime": end + "T23:59:59", "minmagnitude": minimum, "orderby": "time-asc", "limit": 20000,
    })
    payload = http_get(url, timeout=30)
    body = json.loads(payload)
    if len(body.get("features", [])) >= 20000:
        raise ValueError("Source result reached the record cap; narrow the date window")
    fresh, hazards, rejected = parse_usgs(payload)
    if not fresh:
        raise ValueError("No accepted events; the existing bundle is unchanged")
    now = datetime.now(timezone.utc)
    digest = hashlib.sha256(payload).hexdigest()
    capture_dir.mkdir(parents=True, exist_ok=True)
    raw = capture_dir / f"usgs-{start}-{end}-m{minimum:g}-{digest[:12]}.json.gz"
    compressed = gzip.compress(payload, mtime=0)
    if raw.exists() and raw.read_bytes() != compressed:
        raise ValueError("Raw capture identity conflicts with existing evidence")
    if not raw.exists():
        raw.write_bytes(compressed)
    prior = next(source for source in old.manifest["sources"] if source["id"] == "usgs_earthquakes")
    source = {
        **prior, "url": url, "retrievedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "ok",
        "filter": f"Magnitude >= {minimum:g} during {start} to {end}; prior earthquake archive retained",
        "parsedItems": len(fresh), "rejected": rejected, "payloadSha256": digest,
        "rawCapture": str(raw.relative_to(REPO_ROOT)) if raw.is_relative_to(REPO_ROOT) else str(raw),
        "previousCaptures": prior.get("previousCaptures", []) + [{
            key: prior[key] for key in ("url", "retrievedAt", "filter", "payloadSha256", "rawCapture") if key in prior
        }],
    }
    sources = [source if item["id"] == source["id"] else item for item in old.manifest["sources"]]
    files = build_bundle(
        fresh + list(old.events), list(old.hazards) + hazards, sources,
        built_at=now, start=min(old.manifest["requestedWindow"]["start"], start),
        end=max(old.manifest["requestedWindow"]["end"], end), version_suffix="-expanded-" + digest[:8],
    )
    events = json.loads(files["events.json"])
    for event in events:
        WorldEvent.model_validate(event)
    for hazard in json.loads(files["hazards.json"]):
        Hazard.model_validate(hazard)
    # build_bundle applies the event feed rule (USGS earthquakes of magnitude 6.0 or more only) and
    # records each source's kept items; notIngested keeps its per-source reasons.
    write_bundle(files, out)
    verified = load_bundle(out)
    return {
        "previousEvents": len(old.events), "events": len(verified.events),
        "addedEvents": len(verified.events) - len(old.events), "hazards": len(verified.hazards),
        "sourceRecords": len(fresh), "rejected": rejected, "version": verified.version,
        "sourceUrl": url, "rawCapture": str(raw), "output": str(out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BUNDLE_DIR)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, default=REPO_ROOT / "data/inputs/world-events")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--min-magnitude", type=float, default=5.0)
    args = parser.parse_args()
    try:
        result = expand(args.base, args.out, args.capture_dir, args.start, args.end, args.min_magnitude)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Expansion failed: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
