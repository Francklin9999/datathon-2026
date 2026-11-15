"""Capture a small, fixed UN Comtrade annual export sample.

Run from the backend directory: python -m aplomb.world.providers.trade_extra
UN Comtrade controls reuse; see the accompanying TRADE-EXTRA report before distribution.
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
from urllib.parse import urlencode, urlsplit

from .snapshot import DIRECTORY, publish

DATASET_ID = "trade_un_comtrade_exports"
PERIOD = "2023"
REPORTERS = {
    76: ("BRA", "Brazil"),
    124: ("CAN", "Canada"),
    156: ("CHN", "China"),
    276: ("DEU", "Germany"),
    356: ("IND", "India"),
    710: ("ZAF", "South Africa"),
}
URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS?" + urlencode({
    "period": PERIOD, "reporterCode": ",".join(map(str, REPORTERS)),
    "cmdCode": "TOTAL", "flowCode": "X", "partnerCode": "0",
})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected UN Comtrade redirect")


def fetch() -> bytes:
    """One fixed public API request; bounded retries, read size and timeout."""
    parsed = urlsplit(URL)
    if parsed.scheme != "https" or parsed.hostname != "comtradeapi.un.org":
        raise ValueError("Unexpected UN Comtrade endpoint")
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(URL, headers={
        "User-Agent": "AplombDatathon/1.0 (bounded public research ingestion)",
        "Accept": "application/json",
    })
    for attempt in range(3):
        try:
            with opener.open(request, timeout=25) as response:
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, 2_000_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError("UN Comtrade response exceeds byte cap")
                    if time.monotonic() - started > 25:
                        raise TimeoutError("UN Comtrade total read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("UN Comtrade retry exhausted")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if (not isinstance(body, dict) or body.get("error") or not isinstance(body.get("data"), list)
            or isinstance(body.get("count"), bool) or body.get("count") != len(body["data"])
            or len(body["data"]) > len(REPORTERS)):
        raise ValueError("Invalid or incomplete UN Comtrade response")
    rows, seen = [], set()
    for item in body["data"]:
        code = item["reporterCode"]
        value = item["primaryValue"]
        if (isinstance(code, bool) or code not in REPORTERS or code in seen
                or item["period"] != PERIOD or item["refYear"] != int(PERIOD)
                or item["typeCode"] != "C" or item["freqCode"] != "A"
                or item["flowCode"] != "X" or item["partnerCode"] != 0
                or item["partner2Code"] != 0 or item["cmdCode"] != "TOTAL"
                or item["customsCode"] != "C00" or item["motCode"] != 0
                or isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0
                or not isinstance(item["isReported"], bool)
                or not isinstance(item["isAggregate"], bool)):
            raise ValueError("UN Comtrade record does not match the fixed query")
        seen.add(code)
        iso3, name = REPORTERS[code]
        rows.append({
            "id": f"{DATASET_ID}:{code}:{PERIOD}:X:0:TOTAL",
            "sourceId": DATASET_ID, "category": "trade",
            "title": f"{name} merchandise exports to the world, {PERIOD}",
            "sourceUrl": URL, "retrievedAt": stamp, "availableAt": stamp,
            "observedAt": None, "publishedAt": None,
            "latitude": None, "longitude": None, "countryIso3": iso3,
            "properties": {
                "reporterCode": code, "reporterName": name, "referenceYear": int(PERIOD),
                "temporalPrecision": "year", "partnerCode": 0, "partnerName": "World",
                "commodityCode": "TOTAL", "flowCode": "X", "valueUsd": value,
                "valuation": "export value as supplied by UN Comtrade; see source methodology",
                "classificationCode": item["classificationCode"],
                "isReported": item["isReported"], "isAggregate": item["isAggregate"],
                "geographicRole": "reporting_country", "securityRelationship": None,
            },
        })
    return rows, {
        "sourceRows": len(body["data"]), "rejected": 0, "coverageComplete": False,
        "requestedReporterCodes": list(REPORTERS),
        "missingReporterCodes": sorted(set(REPORTERS) - seen),
        "scope": "2023 annual merchandise total exports to World for six selected reporters only; "
                 "missing reporters are not zero. No geographic point or company link.",
    }


def collect(directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    payload = fetcher()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-112", "SRC-206", "MASTER-077"],
        "name": "UN Comtrade annual merchandise export sample", "sourceUrl": URL,
        "licence": "UN Comtrade copyright; limited free visualization and small-data reuse "
                   "subject to the UN Comtrade license and re-dissemination rules; Source: UN Comtrade",
        "licenceUrl": "https://uncomtrade.org/docs/re-dissemination-of-data/",
        "frequency": "fixed annual 2023 sample; manual capture",
        "limitations": [
            "Six requested reporters; missing rows are not zero and no global coverage is implied.",
            "UN Comtrade preview results may be revised; source publication date is unavailable.",
            "Annual merchandise exports to World are not port activity or issuer exposure.",
            "Country-level records have no source coordinates and must not be shown as observed points.",
            "Reuse is conditional: commercial APIs/streaming require a distribution arrangement.",
        ],
        **quality, "retrievedAt": stamp,
    }
    return publish(directory, rows, metadata, [(URL, payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"],
                      "missingReporterCodes": manifest["missingReporterCodes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
