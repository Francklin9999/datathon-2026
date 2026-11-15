"""Anonymous NASA CMR MODIS granule metadata; no authenticated imagery download."""
from __future__ import annotations

import argparse
import json
import math
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, timestamp, validate_row

DATASET_ID = "world_nasa_cmr_modis_granules"
COLLECTION = "C2565791013-LPCLOUD"
COLLECTION_URL = "https://cmr.earthdata.nasa.gov/search/collections.json?concept_id=" + COLLECTION
DATA_URL = (
    "https://cmr.earthdata.nasa.gov/search/granules.json?"
    "collection_concept_id=" + COLLECTION +
    "&page_size=5&sort_key=-start_date&bounding_box=-5,40,5,50"
)
TERMS_URL = "https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected NASA CMR redirect")


def fetch(url: str) -> bytes:
    if url not in {COLLECTION_URL, DATA_URL}:
        raise ValueError("Unexpected NASA CMR request")
    for attempt in range(3):
        request = urllib.request.Request(url, headers={
            "User-Agent": "AplombDatathon/1.0 (bounded anonymous metadata capture)",
            "Accept": "application/json",
        })
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=25) as response:
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, 500_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > 500_000:
                        raise ValueError("NASA CMR metadata exceeds byte cap")
                    chunks.append(chunk)
                    if time.monotonic() - started > 25:
                        raise TimeoutError("NASA CMR read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("NASA CMR retries exhausted")


def parse(collection_payload: bytes, payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    collections = json.loads(collection_payload)["feed"]["entry"]
    if len(collections) != 1:
        raise ValueError("Missing or ambiguous NASA collection")
    collection = collections[0]
    if (collection.get("id") != COLLECTION or collection.get("entry_id") != "MOD14A1_061"
            or collection.get("version_id") != "061"):
        raise ValueError("Unexpected NASA collection or version")
    entries = json.loads(payload)["feed"]["entry"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 5:
        raise ValueError("NASA CMR page must contain one to five granules")
    rows, seen = [], set()
    for item in entries:
        identifier = item.get("id")
        if (not isinstance(identifier, str) or not re.fullmatch(r"G\d+-LPCLOUD", identifier)
                or identifier in seen or item.get("collection_concept_id") != COLLECTION
                or item.get("data_center") != "LPCLOUD"
                or not isinstance(item.get("producer_granule_id"), str)
                or not item["producer_granule_id"].startswith("MOD14A1.")):
            raise ValueError("Invalid NASA granule identity")
        seen.add(identifier)
        start, end, updated = (timestamp(item[key]) for key in ("time_start", "time_end", "updated"))
        if start > end or updated > timestamp(stamp) or end > timestamp(stamp):
            raise ValueError("Invalid NASA granule chronology")
        polygons = item.get("polygons")
        if not isinstance(polygons, list) or not polygons:
            raise ValueError("NASA granule lacks polygon coverage")
        rings = []
        for polygon in polygons:
            if not isinstance(polygon, list) or len(polygon) != 1 or not isinstance(polygon[0], str):
                raise ValueError("Unsupported NASA polygon structure")
            values = [float(value) for value in polygon[0].split()]
            if len(values) < 8 or len(values) % 2:
                raise ValueError("Invalid NASA polygon coordinates")
            ring = [[lon, lat] for lat, lon in zip(values[::2], values[1::2])]
            if ring[0] != ring[-1] or any(
                not math.isfinite(lon) or not math.isfinite(lat)
                or not -180 <= lon <= 180 or not -90 <= lat <= 90 for lon, lat in ring
            ):
                raise ValueError("Invalid NASA polygon extent")
            # The selected European search cannot justify rendering a polygon
            # across the dateline; reject that geometry instead of guessing.
            if any(abs(a[0] - b[0]) > 180 for a, b in zip(ring, ring[1:])):
                raise ValueError("NASA polygon crosses dateline")
            rings.append([ring])
        geometry = ({"type": "Polygon", "coordinates": rings[0]} if len(rings) == 1 else
                    {"type": "MultiPolygon", "coordinates": rings})
        row = base(DATASET_ID, identifier, "environment",
                   "NASA MODIS fire-product granule: " + item["producer_granule_id"],
                   "https://search.earthdata.nasa.gov/search/granules?p=" + COLLECTION, stamp,
                   observedAt=item["time_start"], properties={
                       "granuleId": identifier, "producerGranuleId": item["producer_granule_id"],
                       "collectionId": COLLECTION, "collectionVersion": "061",
                       "product": collection["dataset_id"],
                       "observationPeriodStart": item["time_start"],
                       "observationPeriodEnd": item["time_end"],
                       "metadataUpdatedAt": item["updated"], "geometry": geometry,
                       "geographicRole": "satellite_granule_coverage_polygon",
                       "coordinateOrder": "GeoJSON longitude, latitude; converted from CMR latitude, longitude",
                       "temporalPrecision": "eight-day product interval",
                       "fireDetectionsLoaded": False, "rasterLoaded": False,
                       "attribution": "NASA Terra MODIS / LP DAAC; metadata via NASA CMR",
                   })
        validate_row(row)
        rows.append(row)
    return rows, {
        "sourceRows": len(entries), "rejected": 0, "coverageComplete": False,
        "scope": "First five latest-start-date MOD14A1.061 granules intersecting longitude -5..5 and latitude 40..50; metadata only.",
    }


def collect(directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    collection_payload = fetcher(COLLECTION_URL)
    time.sleep(0.5)
    payload = fetcher(DATA_URL)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(collection_payload, payload, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-158"],
        "name": "NASA CMR MODIS Terra granule coverage metadata",
        "sourceUrl": DATA_URL, "licenceUrl": TERMS_URL,
        "licence": "NASA data-use guidance: NASA metadata generally not copyrighted; NASA-led mission data CC0; NASA attribution provided",
        "attribution": "NASA Terra MODIS / LP DAAC; metadata via NASA CMR",
        "frequency": "Eight-day source products; manually captured metadata snapshot",
        "retrievedAt": stamp, **quality,
        "modifications": [
            "Five source metadata records normalized into coverage observations.",
            "CMR latitude-longitude polygon pairs converted to GeoJSON longitude-latitude.",
            "No representative point, country assignment, imagery, fire pixels or download credentials retained.",
        ],
        "limitations": [
            "Granule coverage does not establish fire presence, intensity, damage or issuer exposure.",
            "Eight-day start and end are product coverage dates; start is the display time anchor.",
            "One first page intersecting a European bounding box; not complete global or regional coverage.",
            "Anonymous CMR metadata only; downloading underlying imagery may require Earthdata login and is set aside.",
            "No imagery, third-party media or scientific pixel measurements are captured.",
            "Metadata revision time is not an original publication date; availability is gated at capture.",
        ],
    }
    return publish(directory, rows, metadata, [(COLLECTION_URL, collection_payload), (DATA_URL, payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    manifest = collect(parser.parse_args().directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
