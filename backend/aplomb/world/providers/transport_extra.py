"""Bounded anonymous ADS-B reports and NOAA annual AIS raster samples.

The ADS-B captured and derived databases are ODbL 1.0. NOAA's official
MarineCadastre repository dedicates its content under CC0 1.0.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from .public import base
from .snapshot import DIRECTORY, publish, timestamp, validate_row
from .transport import Transport

ADSB_ID = "world_adsblol_heathrow_positions"
ADSB_URL = "https://api.adsb.lol/v2/lat/51.47/lon/-0.4543/dist/20"
ADSB_RIGHTS = "https://www.adsb.lol/docs/open-data/api/"
ODBL = "https://opendatacommons.org/licenses/odbl/1.0/"
ADSB_ATTRIBUTION = (
    "Contains information from ADS-B.lol, https://www.adsb.lol/, made available "
    "under the Open Database License (ODbL) 1.0. Adapted by Aplomb: bounded "
    "Heathrow-area capture, validated source positions and normalized fields. "
    "This derived database is ODbL 1.0; the raw and derived databases are available "
    "in the versioned provider capture."
)
MARINE_ID = "trade_marinecadastre_ais_2024_samples"
MARINE_URL = "https://coast.noaa.gov/arcgis/rest/services/MarineCadastre/AISVesselTransitCounts2024/MapServer"
MARINE_RIGHTS = "https://raw.githubusercontent.com/NOAA-OCM/ocm-marinecadastre-ais-vessel-traffic/master/README.md"
MARINE_ATTRIBUTION = (
    "NOAA Office for Coastal Management, BOEM and U.S. Coast Guard, "
    "MarineCadastre AIS Vessel Transit Counts 2024. Repository content CC0 1.0. "
    "Adapted by Aplomb: three fixed raster queries; sample locations are query "
    "anchors and do not identify vessel positions or named facilities."
)
SAMPLES = (("ny_harbor", -74.035, 40.65), ("la_harbor", -118.25, 33.70),
           ("sf_bay", -122.40, 37.80))


def _json(payload: bytes) -> dict:
    if payload.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
            payload = stream.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError("Decompressed source exceeds byte cap")
    body = json.loads(payload)
    if not isinstance(body, dict):
        raise ValueError("Expected source object")
    return body


def adsb_parse(payload: bytes, rights: bytes, stamp: str) -> tuple[list[dict], dict]:
    if b"ODbL 1.0" not in rights or b"https://opendatacommons.org/licenses/odbl/1.0/" not in rights:
        raise ValueError("ADS-B API database licence evidence is missing")
    body = _json(payload)
    items = body.get("ac")
    if body.get("msg") != "No error" or not isinstance(items, list) or not 1 <= len(items) <= 5000:
        raise ValueError("Unexpected ADS-B source status, schema or bounded size")
    now = body.get("now")
    if isinstance(now, bool) or not isinstance(now, (float, int)) or not math.isfinite(now):
        raise ValueError("Missing ADS-B snapshot timestamp")
    source_time = datetime.fromtimestamp(now / 1000, timezone.utc)
    if source_time > timestamp(stamp):
        raise ValueError("Source timestamp is later than retrieval")
    rows, seen, rejected = [], set(), 0
    for item in items:
        try:
            key = item["hex"].lower()
            if not re.fullmatch(r"~?[0-9a-f]{6}", key) or key in seen:
                raise ValueError("Invalid or duplicate aircraft report ID")
            age = item["seen_pos"]
            if isinstance(age, bool) or not isinstance(age, (int, float)) or not math.isfinite(age) or not 0 <= age <= 60:
                raise ValueError("Missing or stale source position")
            # now is milliseconds; seen_pos is the source-reported position age in seconds.
            observed = datetime.fromtimestamp(now / 1000 - age, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            row = base(ADSB_ID, key, "aviation", f"ADS-B report {key} · captured Heathrow area",
                       ADSB_URL, stamp, latitude=item["lat"], longitude=item["lon"],
                       observedAt=observed, properties={
                           "sourceHex": key, "positionType": item.get("type"),
                           "callsign": (item.get("flight") or "").strip() or None,
                           "positionAgeSeconds": age, "providerSnapshotAt": source_time.isoformat().replace("+00:00", "Z"),
                           "geographicRole": "aircraft_reported_position", "aircraftTracking": True,
                           "continuousTracking": False, "attribution": ADSB_ATTRIBUTION,
                       })
            validate_row(row)
            seen.add(key)
            rows.append(row)
        except (KeyError, ValueError, TypeError, OverflowError):
            rejected += 1
    if not rows:
        raise ValueError("No validated fresh-position aircraft reports")
    return rows, {"sourceRows": len(items), "sourceReportedTotal": body.get("total"),
                  "rejected": rejected, "coverageComplete": False,
                  "scope": "One snapshot of source reports within 20 nautical miles of 51.47,-0.4543; positions aged at most 60 seconds."}


def marine_query(lon: float, lat: float) -> str:
    return MARINE_URL + "/identify?" + urlencode({
        "f": "json", "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
        "sr": 4326, "layers": "all:0", "tolerance": 0,
        "mapExtent": f"{lon-.2},{lat-.15},{lon+.2},{lat+.15}",
        "imageDisplay": "1000,1000,96", "returnGeometry": "true",
    })


def marine_parse(captures: list[tuple[str, bytes]], rights: bytes, stamp: str) -> tuple[list[dict], dict]:
    if b"CC0 1.0 Universal public domain dedication" not in rights or MARINE_URL.encode() not in rights:
        raise ValueError("NOAA AIS raster licence/source evidence is missing")
    if len(captures) != len(SAMPLES):
        raise ValueError("Missing bounded raster query responses")
    rows, rejected = [], 0
    for (key, lon, lat), (url, payload) in zip(SAMPLES, captures):
        try:
            if url != marine_query(lon, lat):
                raise ValueError("Unexpected raster query location")
            body = _json(payload)
            results = body.get("results")
            if "error" in body or not isinstance(results, list) or len(results) != 1:
                raise ValueError("Missing or ambiguous raster sample")
            item = results[0]
            if item.get("layerId") != 0 or item.get("layerName") != "AIS Vessel Transit Counts 2024":
                raise ValueError("Unexpected NOAA annual raster layer")
            geom = item["geometry"]
            if item.get("geometryType") != "esriGeometryPoint" or geom["spatialReference"].get("latestWkid", geom["spatialReference"].get("wkid")) != 4326:
                raise ValueError("Unexpected raster response coordinate system")
            if abs(geom["x"] - lon) > 0.000001 or abs(geom["y"] - lat) > 0.000001:
                raise ValueError("Raster sample query/response coordinate mismatch")
            value = item["attributes"]["UniqueValue.Pixel Value"]
            if not isinstance(value, str) or not value.isdecimal():
                raise ValueError("Raster cell is missing or not a count")
            row = base(MARINE_ID, key, "trade",
                       f"NOAA AIS 2024 raster sample · {key} · {int(value)} transits",
                       url, stamp, latitude=lat, longitude=lon, countryIso3="USA",
                       properties={"referenceYear": 2024, "referencePeriod": "2024-01-01/2024-12-31",
                                   "vesselTransitCount": int(value), "unit": "annual raster cell transits",
                                   "geographicRole": "raster_query_point",
                                   "locationIsVesselPosition": False, "attribution": MARINE_ATTRIBUTION})
            validate_row(row)
            rows.append(row)
        except (KeyError, ValueError, TypeError, OverflowError):
            rejected += 1
    if not rows:
        raise ValueError("No valid annual AIS raster samples")
    return rows, {"sourceRows": len(captures), "rejected": rejected, "coverageComplete": False,
                  "scope": "Three fixed coastal raster samples (New York Harbor, Los Angeles Harbor, San Francisco Bay); annual 2024 grid-cell counts only."}


def collect(directory: Path = DIRECTORY, fetch=None) -> list[dict]:
    fetch = fetch or Transport(max_bytes=2_000_000, retries=1, interval=1)
    adsb_captures = [(u, fetch(u)) for u in (ADSB_URL, ADSB_RIGHTS)]
    stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    rows, quality = adsb_parse(adsb_captures[0][1], adsb_captures[1][1], stamp)
    manifests = [publish(directory, rows, {
        "datasetId": ADSB_ID, "sourceIds": ["SRC-213"],
        "name": "ADS-B.lol Heathrow-area captured aircraft positions",
        "sourceUrl": ADSB_URL, "licence": "Captured and derived databases ODbL 1.0",
        "licenceUrl": ODBL, "attribution": ADSB_ATTRIBUTION,
        "frequency": "Manual single snapshot; anonymous source quota 500 requests/day/IP",
        "retrievedAt": stamp, **quality,
        "limitations": [
            "One captured snapshot only; no continuous monitoring, flight trajectories, global coverage or historical tracking.",
            "Source positions include ADS-B and multilateration reports, with source-reported uncertainty and incomplete receiver coverage.",
            "Aircraft report identifiers/callsigns do not establish operator, owner, public issuer or portfolio relationships.",
            "Source snapshot time minus position age gives observedAt; first proven availability is retrieval, excluded from earlier replay.",
            ADSB_ATTRIBUTION,
        ],
    }, adsb_captures)]
    rights = (MARINE_RIGHTS, fetch(MARINE_RIGHTS))
    captures = [(marine_query(lon, lat), fetch(marine_query(lon, lat))) for _, lon, lat in SAMPLES]
    stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    rows, quality = marine_parse(captures, rights[1], stamp)
    manifests.append(publish(directory, rows, {
        "datasetId": MARINE_ID, "sourceIds": ["SRC-209", "MASTER-079"],
        "name": "NOAA MarineCadastre AIS annual 2024 raster samples",
        "sourceUrl": MARINE_URL, "licence": "CC0 1.0 Universal public domain dedication",
        "licenceUrl": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution": MARINE_ATTRIBUTION, "frequency": "Annual derivative; manual three-query sample",
        "retrievedAt": stamp, **quality,
        "limitations": [
            "Three fixed annual raster samples; incomplete U.S. coastal and worldwide traffic coverage.",
            "Coordinates are selected raster query anchors, not vessel observations, port boundaries or facility coordinates.",
            "Annual grid-cell transit counts cannot be summed as distinct vessels or interpreted as current traffic or cargo volumes.",
            "Reference year 2024 is a period, not an observation timestamp; observedAt and publishedAt remain unknown.",
            "Source publication time is unproven; capture time gates historical availability.",
            "No operator, issuer, security, portfolio exposure or financial-impact relationship is established.",
            MARINE_ATTRIBUTION,
        ],
    }, [rights, *captures]))
    return manifests


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    manifests = collect(parser.parse_args().directory)
    print(json.dumps([{"datasetId": m["datasetId"], "version": m["dataVersion"],
                       "rows": m["rowCount"]} for m in manifests]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
