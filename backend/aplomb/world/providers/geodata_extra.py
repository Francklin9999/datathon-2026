"""Capture the pinned geoBoundaries 2022 metropolitan France ADM1 sample.

Run: python -m aplomb.world.providers.geodata_extra --directory PATH
The API consumes saved snapshots only; infrastructure observations display source polygons.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .snapshot import DIRECTORY, publish, validate_row

META_URL = "https://www.geoboundaries.org/api/current/gbOpen/FRA/ADM1/"
GITHUB_URL = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/FRA/ADM1/geoBoundaries-FRA-ADM1_simplified.geojson"
DATA_URL = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/9469f09/releaseData/gbOpen/FRA/ADM1/geoBoundaries-FRA-ADM1_simplified.geojson"
DEFAULT_DIRECTORY = DIRECTORY
DATASET = "world_geoboundaries_fra_adm1"


def _check_url(url: str) -> None:
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in {"www.geoboundaries.org", "media.githubusercontent.com"} or p.username or p.password or p.port:
        raise ValueError("geoBoundaries URL outside allowlist")


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, *, timeout: float = 25, max_bytes: int = 4_000_000) -> bytes:
    _check_url(url)
    opener = urllib.request.build_opener(_Redirect())
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AplombDatathon/1.0 (public research capture)", "Accept": "application/json"})
            with opener.open(request, timeout=timeout) as response:
                _check_url(response.url)
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, max_bytes + 1 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("geoBoundaries payload exceeds byte cap")
                    chunks.append(chunk)
                    if time.monotonic() - started > timeout:
                        raise TimeoutError("geoBoundaries read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(min(4, 2 ** attempt))
    raise RuntimeError("geoBoundaries retry exhausted")


def _validate_geometry(geometry: dict) -> None:
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind not in {"Polygon", "MultiPolygon"} or not isinstance(coords, list) or not coords:
        raise ValueError("Expected nonempty polygon geometry")
    polygons = [coords] if kind == "Polygon" else coords
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError("Empty polygon")
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("Invalid polygon ring")
            for point in ring:
                if (not isinstance(point, list) or len(point) != 2
                    or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in point)
                    or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90):
                    raise ValueError("Invalid longitude or latitude")


def parse(meta_payload: bytes, geometry_payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    meta, collection = json.loads(meta_payload), json.loads(geometry_payload)
    expected = {"boundaryISO": "FRA", "boundaryType": "ADM1", "boundaryYearRepresented": "2022",
                "boundaryLicense": "Etalab Open License 2.0", "simplifiedGeometryGeoJSON": GITHUB_URL}
    if any(meta.get(key) != value for key, value in expected.items()):
        raise ValueError("geoBoundaries metadata changed; review release and license before recapture")
    if collection.get("type") != "FeatureCollection" or not isinstance(collection.get("features"), list):
        raise ValueError("Invalid geoBoundaries feature collection")
    features = collection["features"]
    if len(features) != int(meta["admUnitCount"]) or len(features) != 13:
        raise ValueError("Unexpected region count")
    rows, seen = [], set()
    for feature in features:
        properties, geometry = feature["properties"], feature["geometry"]
        name, key = properties["shapeName"], properties["shapeID"]
        if (feature.get("type") != "Feature" or not isinstance(name, str) or not name.strip()
            or not isinstance(key, str) or not key.strip() or key in seen
            or properties.get("shapeGroup") != "FRA" or properties.get("shapeType") != "ADM1"):
            raise ValueError("Invalid or duplicate administrative unit")
        _validate_geometry(geometry)
        seen.add(key)
        row = {"id": DATASET + ":" + key, "sourceId": DATASET, "category": "geography", "title": name,
               "sourceUrl": META_URL, "retrievedAt": stamp, "availableAt": stamp, "observedAt": None,
               "publishedAt": None, "latitude": None, "longitude": None, "countryIso3": "FRA",
               "properties": {"shapeId": key, "shapeIso": properties.get("shapeISO"),
                              "geometry": geometry, "geographicRole": "administrative_boundary",
                              "representedYear": 2022, "simplified": True,
                              "attribution": "IGN-F, 2022; geoBoundaries (Runfola et al., 2020), CC BY 4.0; simplified and normalized by Aplomb."}}
        validate_row(row)
        rows.append(row)
    return rows, {"sourceRows": len(features), "rejected": 0, "coverageComplete": False,
                  "scope": "13 metropolitan France regions in the pinned 2022 ADM1 release; overseas regions excluded."}


def collect(fetcher=fetch, stamp: str | None = None, directory: Path = DEFAULT_DIRECTORY) -> dict:
    captures = [(META_URL, fetcher(META_URL)), (DATA_URL, fetcher(DATA_URL))]
    if stamp is None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(captures[0][1], captures[1][1], stamp)
    metadata = {"datasetId": DATASET, "sourceIds": ["SRC-154", "MASTER-059"], "name": "geoBoundaries France ADM1 simplified boundaries",
                "attribution": "IGN-F, 2022; geoBoundaries (Runfola et al., 2020), CC BY 4.0; simplified and normalized by Aplomb.",
                "sourceUrl": META_URL, "licence": "geoBoundaries CC BY 4.0; underlying IGN-F data Etalab Open License 2.0; attribution and changes indicated",
                "licenceUrl": "https://www.geoboundaries.org/index.html", "frequency": "Pinned 2022 release, manually captured",
                "limitations": ["Only 13 metropolitan France regions; overseas regions excluded.",
                                "Simplified geometry is unsuitable for surveying or legal boundary decisions.",
                                "No historical publication vintage; availability gated at capture."],
                **quality, "retrievedAt": stamp}
    return publish(directory, rows, metadata, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    try:
        manifest = collect(directory=args.directory)
        print(json.dumps({"status": "captured", "version": manifest["dataVersion"], "rows": manifest["rowCount"]}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
