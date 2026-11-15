"""Bounded anonymous BLS CPI capture; no registration or runtime source requests."""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, timestamp, validate_row

DATASET_ID = "world_bls_us_cpi_2024"
SERIES_ID = "CUUR0000SA0"
DATA_URL = f"https://api.bls.gov/publicAPI/v2/timeseries/data/{SERIES_ID}?startyear=2024&endyear=2024"
SOURCE_URL = "https://www.bls.gov/cpi/data.htm"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected BLS redirect")


def fetch(url: str) -> bytes:
    if url != DATA_URL:
        raise ValueError("Unexpected BLS request")
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, headers={"Accept": "application/json",
        "User-Agent": "AplombDatathon/1.0 (one bounded anonymous BLS series)"})
    for attempt in range(3):
        try:
            with opener.open(request, timeout=20) as response:
                started, chunks, size = time.monotonic(), [], 0
                while True:
                    chunk = response.read(min(65536, 100_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 100_000:
                        raise ValueError("BLS response exceeds byte cap")
                    if time.monotonic() - started > 20:
                        raise TimeoutError("BLS response read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("BLS retries exhausted")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if body.get("status") != "REQUEST_SUCCEEDED" or body.get("message"):
        raise ValueError("BLS request did not succeed without warnings")
    series = body.get("Results", {}).get("series")
    if not isinstance(series, list) or len(series) != 1 or series[0].get("seriesID") != SERIES_ID:
        raise ValueError("BLS series identity mismatch")
    points = series[0].get("data")
    if not isinstance(points, list) or not 1 <= len(points) <= 12:
        raise ValueError("Unexpected BLS point count")
    rows, seen = [], set()
    for point in points:
        period = point.get("period", "")
        if point.get("year") != "2024" or period not in {f"M{i:02}" for i in range(1, 13)}:
            raise ValueError("Unexpected BLS reference period")
        month = "2024-" + period[1:]
        reference = date.fromisoformat(month + "-01")
        value = float(point["value"])
        if month in seen or reference > timestamp(stamp).date() or not math.isfinite(value) or value <= 0:
            raise ValueError("Invalid BLS index observation")
        if point.get("periodName") != reference.strftime("%B"):
            raise ValueError("BLS period name mismatch")
        footnotes = point.get("footnotes", [])
        if not isinstance(footnotes, list) or not all(isinstance(note, dict) for note in footnotes):
            raise ValueError("Invalid BLS footnotes")
        seen.add(month)
        row = base(DATASET_ID, month, "macro",
            f"US all-items consumer price index, {month}: {value:g}", SOURCE_URL, stamp,
            countryIso3="USA", observedAt=reference.isoformat(), properties={
                "seriesId": SERIES_ID, "referenceMonth": month, "index": value,
                "unit": "index, 1982-84=100", "seasonalAdjustment": "not seasonally adjusted",
                "population": "all urban consumers", "area": "U.S. city average",
                "footnotes": [note for note in footnotes if note],
                "attribution": "Source: U.S. Bureau of Labor Statistics, CPI-U series CUUR0000SA0; adapted by Aplomb. No government endorsement.",
                "temporalPrecision": "month; first day is a display anchor",
                "geographicRole": "national_statistical_area",
            })
        validate_row(row)
        rows.append(row)
    return rows, {"sourceRows": len(points), "rejected": 0, "coverageComplete": False,
        "scope": "2024 monthly CPI-U all-items U.S. city average only; bounded single-series capture."}


def collect(directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    payload = fetcher(DATA_URL)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, stamp)
    metadata = {"datasetId": DATASET_ID, "sourceIds": ["SRC-098"],
        "name": "BLS 2024 U.S. monthly consumer price index",
        "sourceUrl": DATA_URL,
        "attribution": "Source: U.S. Bureau of Labor Statistics, CPI-U series CUUR0000SA0; adapted by Aplomb. No government endorsement.",
        "licence": "U.S. federal government statistical data, public domain; attribution provided",
        "licenceUrl": "https://www.bls.gov/bls/linksite.htm",
        "frequency": "Monthly series; manual fixed-year capture",
        "limitations": [
            "One 2024 series; no complete BLS, world, or current-month coverage.",
            "CPI-U is an index, 1982-84=100, not an inflation rate; U.S. city average, not seasonally adjusted.",
            "Monthly dates use the first day only as a display anchor; source publication time is not established.",
            "Original vintage availability is unproven; current capture is excluded before retrieval and is not historical replay.",
            "No point coordinates, issuer linkage, or modeled financial impact."],
        **quality, "retrievedAt": stamp}
    return publish(directory, rows, metadata, [(DATA_URL, payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
