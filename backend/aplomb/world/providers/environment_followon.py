"""Capture a bounded EPA ECHO facility search sample.

Run: python -m aplomb.world.providers.environment_followon --directory PATH
"""
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
from .snapshot import publish, validate_row

DATASET_ID = "world_epa_echo_facilities"
URL = ("https://echodata.epa.gov/echo/echo_rest_services.get_facilities"
       "?output=JSON&tablelist=Y&maplist=Y&responseset=100&queryset=1000&p_zip=10004")
DETAIL_URL = "https://echo.epa.gov/detailed-facility-report?fid="


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected EPA redirect")


def fetch(url: str) -> bytes:
    if url != URL:
        raise ValueError("Unexpected EPA request")
    request = urllib.request.Request(url, headers={"User-Agent": "AplombDatathon/1.0 (bounded public research ingestion)",
                                                   "Accept": "application/json"})
    opener = urllib.request.build_opener(_NoRedirect())
    for attempt in range(3):
        try:
            with opener.open(request, timeout=25) as response:
                started, size, chunks = time.monotonic(), 0, []
                while True:
                    chunk = response.read(min(65536, 2_000_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError("EPA response exceeds byte cap")
                    if time.monotonic() - started > 25:
                        raise TimeoutError("EPA read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {409, 429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("EPA retries exhausted")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    result = json.loads(payload)["Results"]
    if result.get("Message") != "Success" or result.get("PageNo") != "1":
        raise ValueError("EPA ECHO search did not succeed on first page")
    facilities = result.get("Facilities")
    mapping = result.get("MapOutput", {}).get("MapData")
    count = int(result["QueryRows"])
    if (not isinstance(facilities, list) or not 1 <= len(facilities) <= 100
            or count < len(facilities) or not isinstance(mapping, list)):
        raise ValueError("Unexpected EPA result counts")
    locations = {}
    for item in mapping:
        key = item.get("PUV")
        if not isinstance(key, str) or not re.fullmatch(r"\d{12}", key):
            continue  # ECHO also returns non-FRS map identifiers.
        if key in locations:
            raise ValueError("Ambiguous EPA map identity")
        locations[key] = item
    rows, seen = [], set()
    for item in facilities:
        key, name = item.get("RegistryID"), item.get("FacName")
        if (not isinstance(key, str) or not re.fullmatch(r"\d{12}", key) or key in seen
                or not isinstance(name, str) or not name.strip()
                or item.get("FacState") != "NY"):
            raise ValueError("Unexpected EPA facility identity or search scope")
        seen.add(key)
        mapped = locations.get(key)
        lat, lon = None, None
        if mapped is not None:
            if mapped.get("TYPE") != "Facility" or mapped.get("NAME") != name:
                raise ValueError("EPA map and table facility mismatch")
            lat, lon = float(mapped["LAT"]), float(mapped["LON"])
            if not math.isfinite(lat) or not math.isfinite(lon):
                raise ValueError("Invalid EPA coordinates")
        row = base(DATASET_ID, key, "environment", name, DETAIL_URL + key, stamp,
                   latitude=lat, longitude=lon, countryIso3="USA", properties={
                       "registryId": key, "city": item.get("FacCity"), "state": item.get("FacState"),
                       "zip": item.get("FacZip"), "complianceStatus": item.get("FacComplianceStatus"),
                       "significantNoncomplianceFlag": item.get("FacSNCFlg"),
                       "accuracyMeters": item.get("FacAccuracyMeters"),
                       "geographicRole": "source_facility_coordinate" if mapped else "no_coordinate",
                   })
        validate_row(row)
        rows.append(row)
    return rows, {"sourceRows": count, "returnedRows": len(facilities), "rejected": 0,
                  "coverageComplete": False,
                  "scope": "First 100 results of EPA ECHO facility search for ZIP 10004; map locations matched by FRS RegistryID."}


def collect(directory: Path, fetcher=fetch) -> dict:
    payload = fetcher(URL)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-220", "MASTER-091"],
        "name": "EPA ECHO facility search, ZIP 10004 sample", "sourceUrl": URL,
        "attribution": "US Environmental Protection Agency, Enforcement and Compliance History Online (ECHO)",
        "licence": "EPA-produced geospatial data are public domain unless otherwise specified; other content may have separate rights",
        "licenceUrl": "https://www.epa.gov/web-policies-and-procedures/epa-disclaimers",
        "frequency": "Current ECHO search; manual capture",
        "limitations": [
            "Only the first 100 results of a ZIP 10004 search are included; ECHO may return facilities with a different displayed ZIP. This is not a complete ECHO or New York inventory.",
            "EPA coordinates are source facility map positions and may be inaccurate or differ from mailing ZIP; accuracy is source-reported where present.",
            "Compliance status reflects EPA source records and does not establish current legal compliance or prove an absence of violations.",
            "Records may be incomplete or updated; original historical availability is unproven and capture-time gating applies.",
            "No ownership, issuer, investment exposure, emissions, or facility boundaries are established.",
        ], **quality, "retrievedAt": stamp,
    }
    return publish(directory, rows, metadata, [(URL, payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
