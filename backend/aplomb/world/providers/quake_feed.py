"""Capture a bounded USGS weekly M4.5-<6 earthquake GeoJSON feed."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .snapshot import DIRECTORY, publish, validate_row
from .transport import Transport

DATASET_ID = "world_usgs_geojson"
URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"


def _date(value: int) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Invalid USGS epoch time")
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    meta = body.get("metadata")
    features = body.get("features")
    if (body.get("type") != "FeatureCollection" or not isinstance(meta, dict)
            or meta.get("url") != URL or meta.get("status") != 200
            or meta.get("title") != "USGS Magnitude 4.5+ Earthquakes, Past Week"
            or not isinstance(features, list) or meta.get("count") != len(features)
            or len(features) > 500 or _date(meta["generated"]) > stamp):
        raise ValueError("Unexpected or incomplete USGS weekly feed")
    rows, rejected, excluded, seen = [], 0, 0, set()
    for feature in features:
        try:
            props = feature["properties"]
            mag = props["mag"]
            if props["type"] != "earthquake" or mag is None or not 4.5 <= mag < 6:
                excluded += 1
                continue
            ident = feature["id"]
            coords = feature["geometry"]["coordinates"]
            source_url = props["url"]
            parsed_url = urlsplit(source_url)
            if (feature["type"] != "Feature" or not isinstance(ident, str) or not ident
                    or ident in seen or feature["geometry"]["type"] != "Point"
                    or len(coords) < 2 or not all(isinstance(v, (int, float)) and math.isfinite(v)
                                                   for v in coords[:2])
                    or parsed_url.scheme != "https"
                    or parsed_url.hostname != "earthquake.usgs.gov"
                    or parsed_url.username or parsed_url.port):
                raise ValueError("Invalid USGS event identity, coordinate, or URL")
            seen.add(ident)
            occurred = _date(props["time"])
            updated = _date(props["updated"])
            if occurred > stamp or updated > stamp:
                raise ValueError("Future USGS event or update")
            row = {
                "id": f"{DATASET_ID}:{ident}", "sourceId": DATASET_ID, "category": "hazards",
                "title": props["title"], "sourceUrl": source_url,
                "retrievedAt": stamp, "availableAt": stamp, "observedAt": occurred,
                "publishedAt": None, "latitude": coords[1], "longitude": coords[0],
                "countryIso3": None,
                "properties": {
                    "magnitude": mag, "place": props.get("place"), "sourceStatus": props.get("status"),
                    "sourceUpdatedAt": updated, "depthKm": coords[2] if len(coords) > 2 else None,
                    "geographicRole": "earthquake_epicenter", "securityRelationship": None,
                },
            }
            validate_row(row)
            rows.append(row)
        except (KeyError, TypeError, ValueError, OverflowError):
            rejected += 1
    if not rows:
        raise ValueError("No valid M4.5-<6 earthquakes in weekly feed")
    return rows, {
        "sourceRows": len(features), "rejected": rejected, "excludedMagnitudeOrType": excluded,
        "coverageComplete": False, "scope": "Current USGS M4.5-<6 earthquake point epicenters "
        "from the weekly M4.5+ feed; M6+ excluded to avoid duplication with the baseline catalog.",
    }


def collect(directory: Path = DIRECTORY, fetch=None) -> dict:
    fetch = fetch or Transport(max_bytes=2_000_000)
    payload = fetch(URL)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, stamp)
    return publish(directory, rows, {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-171", "MASTER-066"],
        "name": "USGS weekly M4.5-<6 earthquake GeoJSON",
        "sourceUrl": URL, "licence": "US Geological Survey, United States Government public domain",
        "licenceUrl": "https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits",
        "frequency": "Current weekly feed; manual capture",
        "limitations": [
            "Only the latest weekly M4.5+ feed is requested; M6+ rows are excluded because the baseline catalog covers them.",
            "Epicenter point and magnitude are source reported and may be revised; affected area and damage are unknown.",
            "A nearby point does not establish exposure of an issuer, holding, facility or supply chain.",
            "Original historical feed vintages were not captured; availability is gated at capture time.",
        ],
        **quality, "retrievedAt": stamp,
    }, [(URL, payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
