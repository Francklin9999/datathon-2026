"""Capture Climate TRACE's Canadian electricity-generation CO2 estimates for 2025.

Run: python -m aplomb.world.providers.climate_trace_extra --directory PATH
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

from .public import base
from .snapshot import DIRECTORY, publish, validate_row

DATASET_ID = "world_climate_trace_canada_electricity_co2"
METADATA_URL = "https://api.climatetrace.org/v7/metadata"
DATA_URL = ("https://api.climatetrace.org/v7/sources/emissions?"
            "year=2025&gas=co2&subsectors=electricity-generation&gadmId=CAN")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected Climate TRACE redirect")


def fetch(url: str) -> bytes:
    if url not in {METADATA_URL, DATA_URL}:
        raise ValueError("Unexpected Climate TRACE request")
    request = urllib.request.Request(url, headers={
        "User-Agent": "AplombDatathon/1.0 (bounded public research ingestion)",
        "Accept": "application/json",
    })
    opener = urllib.request.build_opener(_NoRedirect())
    for attempt in range(3):
        try:
            with opener.open(request, timeout=25) as response:
                started, size, chunks = time.monotonic(), 0, []
                while True:
                    chunk = response.read(min(65536, 1_000_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 1_000_000:
                        raise ValueError("Climate TRACE response exceeds byte cap")
                    if time.monotonic() - started > 25:
                        raise TimeoutError("Climate TRACE read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Climate TRACE retries exhausted")


def parse(payload: bytes, release: dict, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if body.get("location") != {"name": "Canada", "gadmId": "CAN", "country": "CAN"}:
        raise ValueError("Unexpected Climate TRACE location")
    series = body["subsectors"]["timeseries"]
    summaries = body["subsectors"]["summaries"]
    if (not isinstance(series, list) or len(series) != 12
            or not isinstance(summaries, list) or len(summaries) != 1):
        raise ValueError("Unexpected Climate TRACE series size")
    summary = summaries[0]
    if (summary.get("subsector") != "electricity-generation"
            or summary.get("sector") != "power" or summary.get("gas") != "co2"):
        raise ValueError("Unexpected Climate TRACE summary scope")
    rows, months = [], set()
    for item in series:
        month, quantity = item.get("month"), item.get("emissionsQuantity")
        if (item.get("year") != 2025 or type(month) is not int or not 1 <= month <= 12
                or month in months or item.get("gas") != "co2"
                or item.get("sector") != "power"
                or item.get("subsector") != "electricity-generation"
                or isinstance(quantity, bool) or not isinstance(quantity, (int, float))
                or not math.isfinite(quantity) or quantity < 0):
            raise ValueError("Unexpected Climate TRACE observation")
        months.add(month)
        period = f"2025-{month:02d}"
        row = base(DATASET_ID, period, "environment",
                   f"Canada electricity generation CO2 estimate, {period}", DATA_URL, stamp,
                   countryIso3="CAN", properties={
                       "period": period, "periodResolution": "month",
                       "emissionsQuantity": quantity, "unit": "tonnes CO2",
                       "gas": "co2", "sector": "power", "subsector": "electricity-generation",
                       "estimateType": "modeled", "dataRelease": release["dataVersion"],
                       "geographicRole": "national_aggregate",
                   })
        validate_row(row)
        rows.append(row)
    annual = summary.get("emissionsQuantity")
    if (isinstance(annual, bool) or not isinstance(annual, (int, float))
            or not math.isfinite(annual) or not math.isclose(
                sum(r["properties"]["emissionsQuantity"] for r in rows), annual,
                rel_tol=1e-9, abs_tol=1e-6)):
        raise ValueError("Climate TRACE monthly and annual quantities disagree")
    return rows, {"sourceRows": len(series), "rejected": 0, "coverageComplete": False,
                  "scope": "Canada, monthly 2025 CO2 from electricity-generation only."}


def collect(directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    before = fetcher(METADATA_URL)
    payload = fetcher(DATA_URL)
    after = fetcher(METADATA_URL)
    release = json.loads(before)
    if release != json.loads(after):
        raise ValueError("Climate TRACE release changed during capture")
    coverage = release.get("temporalCoverage")
    if (not isinstance(coverage, dict)
            or not isinstance(coverage.get("start"), str)
            or not isinstance(coverage.get("end"), str)
            or coverage.get("frequency") != "monthly"
            or release.get("dataVersion") != "v5.12.0"
            or not isinstance(release.get("releaseDate"), str)
            or coverage["start"] > "2025-01" or coverage["end"] < "2025-12"):
        raise ValueError("Unexpected Climate TRACE release metadata or coverage")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, release, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-226"],
        "name": "Climate TRACE Canada electricity generation CO2, 2025",
        "sourceUrl": DATA_URL,
        "attribution": (
            "Freeman, J., Rouzbeh Kargar, A., Couture, H., Jeyaratnam, J., Lewis, J., "
            "Alvara, M., Koenig, H., Nakano, T., Davitt, A., Lewis, C., McCormick, G., "
            "Christian, P., and Doctor, Z. (2026). Power sector: Emissions from Electricity "
            "Generation. WattTime, Pixel Scientia Labs and Global Energy Monitor, Climate "
            "TRACE Emissions Inventory. https://climatetrace.org [accessed " + stamp[:10]
            + "]. Adapted to monthly observations."
        ),
        "licence": "CC BY 4.0 for Climate TRACE emissions and metadata; listed external datasets have separate terms",
        "licenceUrl": "https://climatetrace.org/terms",
        "frequency": "Monthly estimates; manually captured release",
        "sourceRelease": release, "retrievedAt": stamp, **quality,
        "limitations": [
            "Only Canada electricity-generation CO2 for 2025 is included; it is not total power-sector or national emissions.",
            "Climate TRACE identifies country-level other-energy-use and other listed subsectors as external dataset exceptions. This query excludes those subsectors; the raw response is checked for the selected subsector.",
            "Emissions are modeled estimates based on multiple inputs and may be revised; monthly periods are estimates, not direct measurements.",
            "Release metadata is checked before and after the query; this cannot prove the upstream service was internally consistent during capture.",
            "Country identity is retained without geographic boundaries or coordinates; no facility or owner relationship is asserted.",
            "Original historical availability is unproven; capture-time gating applies.",
        ],
    }
    return publish(directory, rows, metadata,
                   [(METADATA_URL, before), (DATA_URL, payload), (METADATA_URL, after)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
