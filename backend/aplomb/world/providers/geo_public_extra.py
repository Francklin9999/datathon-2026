"""Bounded public OSM landmark, cached Nominatim lookup and NASA GIBS tile captures.

ODbL derivatives remain separate downloadable databases in the capture directories.
Nominatim is a single cached lookup, never an autocomplete or bulk service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .snapshot import DIRECTORY, load_provider_snapshots, publish, timestamp, validate_row

OSM_URL = "https://api.openstreetmap.org/api/0.6/way/5013364/full.json"
OSM_RIGHTS = "https://www.openstreetmap.org/copyright"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search?q=Eiffel%20Tower%2C%20Paris%2C%20France&format=jsonv2&limit=1&addressdetails=1"
NOMINATIM_POLICY = "https://operations.osmfoundation.org/policies/nominatim/"
GIBS_CAPABILITIES = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/1.0.0/WMTSCapabilities.xml"
GIBS_LAYER = "MODIS_Terra_CorrectedReflectance_TrueColor"
GIBS_DAY = "2026-11-14"
GIBS_TILE = f"https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/{GIBS_LAYER}/default/{GIBS_DAY}/250m/0/0/0.jpg"
NASA_RIGHTS = (
    "https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance"
)
GIBS_RIGHTS = "https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api"
OSM_ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0 (https://opendatacommons.org/licenses/odbl/1-0/); selected and normalized by Aplomb. This separate derived database is available under ODbL 1.0."
NASA_ATTRIBUTION = "NASA Terra MODIS. We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS). Tile footprint derived from WMTS metadata by Aplomb."
DATASETS = {
    "osm": "world_osm_eiffel_tower",
    "nominatim": "world_nominatim_eiffel_lookup",
    "gibs": "world_nasa_gibs_modis_tile",
}
URLS = {
    "osm": (OSM_URL, OSM_RIGHTS),
    "nominatim": (NOMINATIM_URL, OSM_RIGHTS, NOMINATIM_POLICY),
    "gibs": (GIBS_CAPABILITIES, GIBS_TILE, NASA_RIGHTS, GIBS_RIGHTS),
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected geospatial provider redirect")


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


def fetch(url: str) -> bytes:
    if url not in {u for urls in URLS.values() for u in urls}:
        raise ValueError("URL outside exact geospatial request allowlist")
    # No repeated public geocoder requests, including retries, within one capture.
    time.sleep(1.05)
    cap = 6_000_000 if url == GIBS_CAPABILITIES else 500_000
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AplombDatathon/1.0 (https://github.com/francklin99/datathon-2026; single cached landmark lookup)",
            "Accept": "*/*",
        },
    )
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=25) as response:
        chunks, size, started = [], 0, time.monotonic()
        while True:
            chunk = response.read(min(65536, cap + 1 - size))
            if not chunk:
                return b"".join(chunks)
            size += len(chunk)
            if size > cap:
                raise ValueError("Geospatial response exceeds byte cap")
            chunks.append(chunk)
            if time.monotonic() - started > 25:
                raise TimeoutError("Geospatial response read deadline exceeded")


def _row(
    source: str,
    key: str,
    title: str,
    url: str,
    stamp: str,
    props: dict,
    *,
    lat=None,
    lon=None,
    observed=None,
) -> dict:
    row = {
        "id": DATASETS[source] + ":" + key,
        "sourceId": DATASETS[source],
        "category": "environment" if source == "gibs" else "infrastructure",
        "title": title,
        "sourceUrl": url,
        "retrievedAt": stamp,
        "availableAt": stamp,
        "observedAt": observed,
        "publishedAt": None,
        "latitude": lat,
        "longitude": lon,
        "countryIso3": None if source == "gibs" else "FRA",
        "properties": props,
    }
    validate_row(row)
    return row


def parse_osm(payload: bytes, stamp: str) -> list[dict]:
    source = json.loads(payload)
    if (
        source.get("version") != "0.6"
        or not isinstance(source.get("elements"), list)
        or not 1 <= len(source["elements"]) <= 250
    ):
        raise ValueError("Unexpected bounded OSM response")
    nodes, ways = {}, []
    for e in source["elements"]:
        if e.get("type") == "node":
            if e["id"] in nodes:
                raise ValueError("Duplicate OSM node")
            nodes[e["id"]] = [e["lon"], e["lat"]]
        elif e.get("type") == "way":
            ways.append(e)
        else:
            raise ValueError("Unexpected OSM element type")
    if (
        len(ways) != 1
        or ways[0].get("id") != 5013364
        or ways[0].get("tags", {}).get("name") != "Tour Eiffel"
    ):
        raise ValueError("OSM landmark identity changed")
    way = ways[0]
    geometry = {"type": "Polygon", "coordinates": [[nodes[k] for k in way["nodes"]]]}
    _validate_geometry(geometry)
    if any(
        not (2.29 <= p[0] <= 2.30 and 48.85 <= p[1] <= 48.87) for p in geometry["coordinates"][0]
    ):
        raise ValueError("OSM landmark moved outside approved Paris scope")
    edited = way["timestamp"]
    if timestamp(edited) > timestamp(stamp):
        raise ValueError("Future OSM edit")
    return [
        _row(
            "osm",
            "way-5013364",
            "Tour Eiffel — OSM mapped footprint",
            "https://www.openstreetmap.org/way/5013364",
            stamp,
            {
                "geometry": geometry,
                "geographicRole": "mapped_landmark_footprint",
                "osmId": 5013364,
                "osmType": "way",
                "osmVersion": way["version"],
                "sourceLastEditedAt": edited,
                "attribution": OSM_ATTRIBUTION,
            },
        )
    ]


def parse_nominatim(payload: bytes, stamp: str) -> list[dict]:
    items = json.loads(payload)
    if not isinstance(items, list) or len(items) != 1:
        raise ValueError("Expected one cached geocoder result")
    item = items[0]
    if (
        item.get("osm_type") != "way"
        or item.get("osm_id") != 5013364
        or item.get("name") != "Tour Eiffel"
        or item.get("address", {}).get("country_code") != "fr"
        or "ODbL" not in item.get("licence", "")
    ):
        raise ValueError("Nominatim identity, country or license changed")
    lat, lon = float(item["lat"]), float(item["lon"])
    if not (48.85 <= lat <= 48.87 and 2.29 <= lon <= 2.30):
        raise ValueError("Nominatim landmark moved")
    return [
        _row(
            "nominatim",
            "way-5013364",
            "Tour Eiffel — cached Nominatim lookup",
            "https://www.openstreetmap.org/way/5013364",
            stamp,
            {
                "geographicRole": "geocoder_lookup_point",
                "osmType": "way",
                "osmId": 5013364,
                "displayName": item["display_name"],
                "attribution": OSM_ATTRIBUTION,
                "lookupScope": "One exact Eiffel Tower, Paris, France search; no autocomplete or bulk geocoding.",
            },
            lat=lat,
            lon=lon,
        )
    ]


def _jpeg_size(payload: bytes) -> tuple[int, int]:
    if not payload.startswith(b"\xff\xd8") or not payload.endswith(b"\xff\xd9"):
        raise ValueError("Invalid JPEG markers")
    i = 2
    while i + 4 <= len(payload):
        if payload[i] != 255:
            raise ValueError("Invalid JPEG segment")
        marker = payload[i + 1]
        length = int.from_bytes(payload[i + 2 : i + 4], "big")
        if length < 2 or i + 2 + length > len(payload):
            raise ValueError("Invalid JPEG segment length")
        if marker in {0xC0, 0xC1, 0xC2}:
            return int.from_bytes(payload[i + 7 : i + 9], "big"), int.from_bytes(
                payload[i + 5 : i + 7], "big"
            )
        i += 2 + length
    raise ValueError("Missing JPEG dimensions")


def parse_gibs(capabilities: bytes, tile: bytes, stamp: str) -> list[dict]:
    ns = {"w": "http://www.opengis.net/wmts/1.0", "o": "http://www.opengis.net/ows/1.1"}
    root = ET.fromstring(capabilities)
    layers = [
        e
        for e in root.findall(".//w:Layer", ns)
        if e.findtext("o:Identifier", namespaces=ns) == GIBS_LAYER
    ]
    if len(layers) != 1:
        raise ValueError("Missing or ambiguous NASA Terra MODIS layer")
    layer = layers[0]
    if (
        layer.findtext("w:Format", namespaces=ns) != "image/jpeg"
        or layer.findtext("w:TileMatrixSetLink/w:TileMatrixSet", namespaces=ns) != "250m"
    ):
        raise ValueError("NASA imagery format or matrix changed")
    intervals = [e.text for e in layer.findall("w:Dimension/w:Value", ns)]
    if not any(
        x and len(x.split("/")) == 3 and x.split("/")[0] <= GIBS_DAY <= x.split("/")[1]
        for x in intervals
    ):
        raise ValueError("NASA imagery day outside advertised time intervals")
    sets = [
        e
        for e in root.findall(".//w:Contents/w:TileMatrixSet", ns)
        if e.findtext("o:Identifier", namespaces=ns) == "250m"
    ]
    if (
        len(sets) != 1
        or sets[0].findtext("o:SupportedCRS", namespaces=ns) != "urn:ogc:def:crs:OGC:1.3:CRS84"
    ):
        raise ValueError("Unexpected NASA tile coordinate system")
    matrices = [
        e
        for e in sets[0].findall("w:TileMatrix", ns)
        if e.findtext("o:Identifier", namespaces=ns) == "0"
    ]
    if len(matrices) != 1:
        raise ValueError("Missing NASA tile matrix zero")
    matrix = matrices[0]
    if matrix.findtext("w:TopLeftCorner", namespaces=ns) != "-180 90" or _jpeg_size(tile) != (
        512,
        512,
    ):
        raise ValueError("NASA tile origin or JPEG dimensions changed")
    if any(
        matrix.findtext("w:" + k, namespaces=ns) != v
        for k, v in {
            "TileWidth": "512",
            "TileHeight": "512",
            "MatrixWidth": "2",
            "MatrixHeight": "1",
        }.items()
    ):
        raise ValueError("Unexpected NASA matrix dimensions")
    span = (
        float(matrix.findtext("w:ScaleDenominator", namespaces=ns))
        * 0.00028
        / 111319.49079327358
        * 512
    )
    if not math.isclose(span, 288, abs_tol=1e-6):
        raise ValueError("Unexpected NASA geographic tile span")
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-180, -90], [108, -90], [108, 90], [-180, 90], [-180, -90]]],
    }
    _validate_geometry(geometry)
    return [
        _row(
            "gibs",
            GIBS_DAY + ":250m-0-0-0",
            "NASA Terra MODIS true color — one captured overview tile",
            GIBS_TILE,
            stamp,
            {
                "geometry": geometry,
                "geographicRole": "imagery_tile_footprint",
                "layerId": GIBS_LAYER,
                "temporalPrecision": "day",
                "imageDay": GIBS_DAY,
                "tileMatrixSet": "250m",
                "tileMatrix": 0,
                "tileRow": 0,
                "tileColumn": 0,
                "tileWidth": 512,
                "tileHeight": 512,
                "imageSha256": hashlib.sha256(tile).hexdigest(),
                "attribution": NASA_ATTRIBUTION,
                "footprintDerivation": "CRS84 matrix scale and 512-pixel tile; clipped to Earth extent. Footprint is not observed cloud-free coverage.",
            },
            observed=GIBS_DAY,
        )
    ]


def collect(
    source: str, *, fetcher=fetch, stamp: str | None = None, directory: Path = DIRECTORY
) -> dict:
    if source not in DATASETS:
        raise ValueError("Unknown geospatial source")
    # Persistent caching keeps the public geocoder out of runtime and repeated jobs.
    if source == "nominatim":
        _, manifests = load_provider_snapshots(directory)
        existing = next((m for m in manifests if m["datasetId"] == DATASETS[source]), None)
        if existing:
            return existing
    captures = [(u, fetcher(u)) for u in URLS[source]]
    stamp = stamp or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if source == "osm":
        rows = parse_osm(captures[0][1], stamp)
    elif source == "nominatim":
        rows = parse_nominatim(captures[0][1], stamp)
    else:
        rows = parse_gibs(captures[0][1], captures[1][1], stamp)
    osm = source != "gibs"
    if osm:
        rights = captures[1][1].decode("utf-8")
        if "Open Database License" not in rights or "OpenStreetMap" not in rights:
            raise ValueError("OSM licence evidence changed; review before publication")
        if source == "nominatim" and "1 request per second" not in captures[2][1].decode("utf-8"):
            raise ValueError("Nominatim usage policy changed; review before publication")
    else:
        if "Creative Commons Zero (CC0)" not in captures[2][1].decode("utf-8"):
            raise ValueError("NASA mission data guidance changed; review before publication")
        if "We acknowledge the use of imagery" not in captures[3][1].decode("utf-8"):
            raise ValueError("GIBS acknowledgement guidance changed; review before publication")
    licence = (
        "ODbL 1.0; attribution and share-alike apply to this separate derived database"
        if osm
        else "NASA Terra MODIS data, CC0 under NASA Earthdata unmarked NASA-led mission data guidance; NASA/GIBS acknowledgement retained"
    )
    limitations = (
        [
            "Single mapped Paris landmark; not a comprehensive infrastructure database or verified operator relationship.",
            "OSM edit time is not an event or publication time; first proven availability is capture time.",
        ]
        if osm
        else [
            "One 512×512 matrix-zero tile for 2026-11-14; overview browse imagery, not native 250m scientific pixels.",
            "Footprint describes tile extent, not guaranteed observed or cloud-free coverage; other tiles are excluded.",
            "API exposes imagery reference and footprint; a full satellite raster overlay is not implemented.",
        ]
    )
    if source == "nominatim":
        limitations += [
            "One permanently cached lookup; no public geocoder autocomplete, bulk collection or per-request API calls."
        ]
    metadata = {
        "datasetId": DATASETS[source],
        "sourceIds": {
            "osm": ["SRC-148", "MASTER-060"],
            "nominatim": ["SRC-151", "MASTER-061"],
            "gibs": ["SRC-157", "MASTER-063"],
        }[source],
        "name": rows[0]["title"],
        "sourceUrl": URLS[source][0],
        "licence": licence,
        "licenceUrl": "https://opendatacommons.org/licenses/odbl/1-0/" if osm else NASA_RIGHTS,
        "attribution": OSM_ATTRIBUTION if osm else NASA_ATTRIBUTION,
        "frequency": "Manually pinned immutable sample",
        "retrievedAt": stamp,
        "scope": limitations[0],
        "limitations": limitations,
        "coverageComplete": False,
        "sourceRows": len(rows),
        "rejected": 0,
    }
    return publish(directory, rows, metadata, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", choices=DATASETS, required=True)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    manifest = collect(args.source, directory=args.directory)
    print(
        json.dumps(
            {"dataVersion": manifest["dataVersion"], "rowCount": manifest["rowCount"]}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
