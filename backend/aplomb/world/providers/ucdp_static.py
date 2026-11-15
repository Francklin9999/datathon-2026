"""Capture a bounded Ukraine 2025 sample from the UCDP GED 26.1 archive.

Run: python -m aplomb.world.providers.ucdp_static --directory PATH
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import io
import json
import math
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, validate_row

DATASET_ID = "world_ucdp_ged_ukraine_2025"
ARCHIVE_URL = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
CODEBOOK_URL = "https://ucdp.uu.se/downloads/ged/ged261.pdf"
ARCHIVE_HASH = "8c941d84954e555ee2e54f40fa04d9203bf1e2f962203d0a9930966c4947c667"
CODEBOOK_HASH = "f767380ebbf365aec7586f98b6d100cafb69fb54010a908604d53bd9ad655972"
LIMIT = 100


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected UCDP redirect")


def fetch(url: str, cap: int) -> bytes:
    if url not in {ARCHIVE_URL, CODEBOOK_URL}:
        raise ValueError("Unexpected UCDP URL")
    # A distinct query avoids intermediary caches serving a prior partial response.
    request = urllib.request.Request(url + "?capture=full", headers={"User-Agent": "AplombDatathon/1.0 (research capture)"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=120) as response:
        if response.status != 200:
            raise ValueError("UCDP returned a partial response")
        payload = response.read(cap + 1)
        if len(payload) > cap:
            raise ValueError("UCDP response exceeds byte cap")
        return payload


def verified(payload: bytes, digest: str) -> None:
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("UCDP version checksum mismatch")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    verified(payload, ARCHIVE_HASH)
    candidates: list[tuple[date, int, dict]] = []
    seen: set[int] = set()
    examined = matched = rejected = 0
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        files = archive.infolist()
        if len(files) != 1 or files[0].filename != "GEDEvent_v26_1.csv" or files[0].file_size > 300_000_000:
            raise ValueError("Unexpected GED archive structure")
        with archive.open(files[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            required = {"id", "year", "country", "latitude", "longitude", "date_start", "date_end",
                        "where_prec", "date_prec", "type_of_violence", "best", "low", "high", "conflict_name"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError("Unexpected GED schema")
            for item in reader:
                examined += 1
                if item["country"] != "Ukraine" or item["year"] != "2025":
                    continue
                matched += 1
                try:
                    key = int(item["id"])
                    start = date.fromisoformat(item["date_start"][:10])
                    end = date.fromisoformat(item["date_end"][:10])
                    lat, lon = float(item["latitude"]), float(item["longitude"])
                    where, when, kind = int(item["where_prec"]), int(item["date_prec"]), int(item["type_of_violence"])
                    best, low, high = (int(item[field]) for field in ("best", "low", "high"))
                    if (key <= 0 or key in seen or start > end or start.year != 2025 or end.year != 2025
                            or not math.isfinite(lat) or not math.isfinite(lon)
                            or not -90 <= lat <= 90 or not -180 <= lon <= 180
                            or where not in range(1, 8) or when not in range(1, 6)
                            or kind not in (1, 2, 3) or not 0 <= low <= best <= high
                            or not item["conflict_name"].strip()):
                        raise ValueError("Invalid GED event")
                    seen.add(key)
                    row = base(DATASET_ID, str(key), "conflict", item["conflict_name"], ARCHIVE_URL, stamp,
                               observedAt=start.isoformat() + "T00:00:00Z", latitude=lat, longitude=lon,
                               countryIso3="UKR", properties={
                                   "datasetVersion": "26.1", "eventId": str(key), "country": "Ukraine",
                                   "dateStart": start.isoformat(), "dateEnd": end.isoformat(),
                                   "datePrecision": when, "locationPrecision": where,
                                   "violenceType": kind, "fatalitiesBest": best,
                                   "fatalitiesLow": low, "fatalitiesHigh": high,
                                   "geographicRole": "ucdp_coded_event_location",
                               })
                    validate_row(row)
                    entry = (end, key, row)
                    if len(candidates) < LIMIT:
                        heapq.heappush(candidates, entry)
                    elif entry[:2] > candidates[0][:2]:
                        heapq.heapreplace(candidates, entry)
                except (ValueError, TypeError, OverflowError):
                    rejected += 1
    rows = [entry[2] for entry in sorted(candidates, key=lambda x: (x[0], x[1]), reverse=True)]
    return rows, {"scope": "Ukraine, 2025, 100 valid records with latest date_end; ties broken by descending event ID.",
                  "coverageComplete": False, "quality": {"archiveRows": examined, "scopeRows": matched,
                  "rejectedRows": rejected, "acceptedRows": len(rows), "truncated": matched - rejected > LIMIT}}


def collect(directory: Path, archive: bytes, codebook: bytes) -> dict:
    verified(codebook, CODEBOOK_HASH)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(archive, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-130", "MASTER-052"],
        "name": "UCDP GED 26.1 Ukraine 2025 event sample", "sourceUrl": ARCHIVE_URL,
        "attribution": "Uppsala Conflict Data Program, UCDP Georeferenced Event Dataset, version 26.1; adapted by Aplomb. Cite Davies, Pettersson and Öberg (2026), and Sundberg and Melander (2013). UCDP is part of and funded by DEMSCORE, Swedish Research Council grant 2021-00162.",
        "licence": "Creative Commons Attribution 4.0 International", "licenceUrl": "https://creativecommons.org/licenses/by/4.0/",
        "frequency": "Version 26.1 static release; manual capture", "retrievedAt": stamp,
        "limitations": [
            "A 100-record Ukraine 2025 sample ordered by event end date and ID; not a complete conflict inventory or a real-time feed.",
            "GED documents organized lethal violence subject to its definitions, thresholds and source coverage; fatalities are estimates.",
            "Coordinates represent the coded event location and have varying precision; location and date precision codes and date range are retained.",
            "observedAt is midnight UTC on the earliest possible source date, not an exact event time; original availability is unproven and capture-time gating applies.",
        ], **quality,
    }
    return publish(directory, rows, metadata, [(ARCHIVE_URL, archive), (CODEBOOK_URL, codebook)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    parser.add_argument("--archive", type=Path, help="Use a previously downloaded, checksum-verified archive")
    parser.add_argument("--codebook", type=Path, help="Use a previously downloaded, checksum-verified codebook")
    args = parser.parse_args()
    archive = args.archive.read_bytes() if args.archive else fetch(ARCHIVE_URL, 40_000_000)
    codebook = args.codebook.read_bytes() if args.codebook else fetch(CODEBOOK_URL, 2_000_000)
    manifest = collect(args.directory, archive, codebook)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
