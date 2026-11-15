"""Bounded anonymous Copernicus activation centroids and NASA MODIS detections."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, validate_row

CEMS = "world_copernicus_activation_centroids"
FIRMS = "world_firms_modis_europe"
CEMS_URL = "https://mapping.emergency.copernicus.eu/activations/api/activations/?limit=5&offset=0"
CEMS_TERMS = "https://mapping.emergency.copernicus.eu/terms-and-conditions/"
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Europe_24h.csv"
NASA_TERMS = "https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Hazard capture redirected; authorization must be reviewed")


def fetch(url: str) -> bytes:
    if url not in {CEMS_URL, CEMS_TERMS, FIRMS_URL, NASA_TERMS}:
        raise ValueError("Unexpected hazards endpoint")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AplombDatathon/1.0 (bounded anonymous capture)"})
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=25) as response:
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, 500001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 500000:
                        raise ValueError("Hazards payload exceeds byte cap")
                    if time.monotonic() - started > 25:
                        raise TimeoutError("Hazards read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("Hazard retries exhausted")


def copernicus(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    document = json.loads(payload)
    items = document["results"]
    if not isinstance(items, list) or not 1 <= len(items) <= 5 or int(document["count"]) < len(items):
        raise ValueError("Invalid Copernicus page")
    rows, seen = [], set()
    for item in items:
        code = item["code"]
        if not re.fullmatch(r"EMS[RN]\d+", code) or code in seen:
            raise ValueError("Invalid or duplicate Copernicus activation")
        seen.add(code)
        point = re.fullmatch(r"POINT \(([-+0-9.eE]+) ([-+0-9.eE]+)\)", item["centroid"])
        if point is None:
            raise ValueError("Unsupported Copernicus centroid")
        lon, lat = map(float, point.groups())
        activation = datetime.fromisoformat(item["activationTime"])
        updated = datetime.fromisoformat(item["lastUpdate"])
        # Source timestamps omit a timezone; retain them verbatim, never invent UTC.
        capture_date = datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
        if activation.date() > capture_date or updated.date() > capture_date or updated < activation:
            raise ValueError("Invalid Copernicus chronology")
        if not isinstance(item["closed"], bool) or not item["name"].strip():
            raise ValueError("Invalid Copernicus activation fields")
        row = base(CEMS, code, "hazards", "Copernicus activation: " + item["name"],
                   "https://mapping.emergency.copernicus.eu/activations/" + code + "/", stamp,
                   latitude=lat, longitude=lon, properties={
                       "activationCode": code, "event": item["category"]["name"],
                       "activationTimeSource": item["activationTime"], "lastUpdateSource": item["lastUpdate"],
                       "sourceTimestampTimezone": "not stated; display anchored at capture",
                       "sourceCountries": [country["short_name"] for country in item["countries"]],
                       "closed": item["closed"], "areaOfInterestCount": int(item["n_aois"]),
                       "productCount": int(item["n_products"]), "geographicRole": "activation_centroid",
                       "damageAssessmentLoaded": False, "satelliteImageryLoaded": False,
                   })
        validate_row(row)
        rows.append(row)
    return rows, {"sourceRows": int(document["count"]), "returnedRows": len(items), "rejected": 0,
                  "coverageComplete": False, "scope": "First five public Copernicus EMS activation metadata records; source centroids only."}


def firms(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    required = {"latitude", "longitude", "brightness", "scan", "track", "acq_date", "acq_time",
                "satellite", "confidence", "version", "bright_t31", "frp", "daynight"}
    if set(reader.fieldnames or []) != required:
        raise ValueError("Unexpected MODIS CSV schema")
    items = list(reader)
    if not 1 <= len(items) <= 3000:
        raise ValueError("Invalid MODIS bounded row count")
    rows, seen = [], set()
    captured = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    for item in items:
        lat, lon = float(item["latitude"]), float(item["longitude"])
        if item["satellite"] not in {"A", "T"} or item["version"] != "6.1NRT" or item["daynight"] not in {"D", "N"}:
            raise ValueError("Unexpected MODIS mission/version")
        clock = item["acq_time"].zfill(4)
        if not re.fullmatch(r"\d{4}", clock):
            raise ValueError("Invalid MODIS UTC acquisition time")
        observed = datetime.strptime(item["acq_date"] + clock, "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
        if observed > captured or (captured - observed).total_seconds() > 3 * 86400:
            raise ValueError("MODIS rolling feed chronology outside bounded window")
        numbers = {key: float(item[key]) for key in ("brightness", "bright_t31", "scan", "track", "frp", "confidence")}
        if any(not math.isfinite(value) for value in numbers.values()) or not 0 <= numbers["confidence"] <= 100:
            raise ValueError("Invalid MODIS measurements")
        if numbers["scan"] <= 0 or numbers["track"] <= 0 or numbers["frp"] < 0:
            raise ValueError("Invalid MODIS pixel dimensions or radiative power")
        key = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:24]
        if key in seen:
            raise ValueError("Duplicate MODIS detection")
        seen.add(key)
        row = base(FIRMS, key, "hazards", "NASA MODIS thermal anomaly / active-fire detection",
                   "https://firms.modaps.eosdis.nasa.gov/active_fire/", stamp, latitude=lat, longitude=lon,
                   observedAt=observed.isoformat().replace("+00:00", "Z"), properties={
                       "event": "satellite thermal anomaly / active-fire detection",
                       "satellite": "Aqua" if item["satellite"] == "A" else "Terra",
                       "instrument": "MODIS", "collection": item["version"], "dayNight": item["daynight"],
                       "brightnessKelvin": numbers["brightness"], "band31BrightnessKelvin": numbers["bright_t31"],
                       "fireRadiativePowerMw": numbers["frp"], "confidencePercent": numbers["confidence"],
                       "pixelScanKm": numbers["scan"], "pixelTrackKm": numbers["track"],
                       "geographicRole": "satellite_detection_pixel_center",
                   })
        validate_row(row)
        rows.append(row)
    return rows, {"sourceRows": len(items), "rejected": 0, "coverageComplete": False,
                  "scope": "Official MODIS Collection 6.1 near-real-time Europe rolling 24-hour CSV; captured feed only."}


def collect(source: str, directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    if source not in {"copernicus", "firms"}:
        raise ValueError("Unknown hazards source")
    url, rights_url, parser = (CEMS_URL, CEMS_TERMS, copernicus) if source == "copernicus" else (FIRMS_URL, NASA_TERMS, firms)
    payload = fetcher(url)
    time.sleep(0.5)
    rights = fetcher(rights_url)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parser(payload, stamp)
    if source == "copernicus":
        if b"(a) reproduction" not in rights or b"(b) distribution" not in rights:
            raise ValueError("Copernicus reuse terms changed")
        metadata = {
            "datasetId": CEMS, "sourceIds": ["SRC-187", "MASTER-071"],
            "name": "Copernicus EMS public activation centroids",
            "licence": "Copernicus EMS On-Demand Mapping terms permit reproduction, distribution and adaptation with source attribution; EU ownership retained",
            "attribution": "European Union, Copernicus Emergency Management Service, On-Demand Mapping; activation metadata normalized by Aplomb",
            "limitations": [
                "Five activation metadata records from a paginated catalogue; not a complete global hazard inventory.",
                "A centroid identifies the mapping activation area, not the disaster epicenter, affected boundary or damage extent.",
                "Source activation and revision timestamps omit timezone and remain verbatim properties; display time is capture time.",
                "No disaster narrative, casualty count, third-party imagery or product damage assessment is reproduced.",
                "Restricted products and third-party linked information are excluded; no account or registration used.",
                "Current capture cannot establish original historical availability, issuer exposure or financial impact.",
            ],
        }
    else:
        if b"Creative Commons Zero" not in rights:
            raise ValueError("NASA open-data licence guidance changed")
        metadata = {
            "datasetId": FIRMS, "sourceIds": ["SRC-174", "MASTER-067"],
            "name": "NASA FIRMS MODIS Europe thermal detections",
            "licence": "NASA-led Terra/Aqua mission data: CC0 under NASA Earthdata guidance unless marked restricted; no restriction in selected CSV",
            "attribution": "NASA FIRMS / LANCE, MODIS Collection 6.1 Terra and Aqua near-real-time active-fire data; no NASA endorsement",
            "limitations": [
                "Europe regional rolling 24-hour feed only; incomplete detection coverage due to clouds, orbital revisit and sensor resolution.",
                "Thermal anomalies can include industrial heat or volcanoes; a detection is not confirmation of a wildfire.",
                "Coordinates are satellite pixel centers, not exact fire boundaries; scan/track dimensions are retained in kilometres.",
                "Fire radiative power is an instantaneous source measurement, not damage, area burned or financial loss.",
                "Near-real-time data may be revised or replaced by science-quality products; this immutable version retains the captured feed.",
                "Anonymous current file download is usable; area API still requires MAP_KEY and historical archive authentication is set aside.",
                "Original historical availability is unproven; replay gates at capture and issuer exposure is not established.",
            ],
        }
    return publish(directory, rows, {**metadata, **quality, "sourceUrl": url, "licenceUrl": rights_url,
                                    "frequency": "Manual bounded current capture", "retrievedAt": stamp},
                   [(url, payload), (rights_url, rights)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", choices=["copernicus", "firms"], required=True)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    result = collect(args.source, args.directory)
    print(json.dumps({"version": result["dataVersion"], "rows": result["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
