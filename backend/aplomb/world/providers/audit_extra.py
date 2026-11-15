"""Capture a bounded Statistics Canada monthly CPI series with its metadata.

Run: python -m aplomb.world.providers.audit_extra --directory PATH
"""
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
from .snapshot import publish, timestamp, validate_row

DATASET_ID = "world_statcan_cpi"
ROOT = "https://www150.statcan.gc.ca/t1/wds/rest/"
TABLE_URL = "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401"
DATA_URL = ROOT + "getDataFromVectorsAndLatestNPeriods"
SERIES_URL = ROOT + "getSeriesInfoFromVector"
CODES_URL = ROOT + "getCodeSets"
VECTOR = 41690973
REQUESTS = [(DATA_URL, [{"vectorId": VECTOR, "latestN": 12}]),
            (SERIES_URL, [{"vectorId": VECTOR}]), (CODES_URL, None)]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected Statistics Canada redirect")


def fetch(url: str, body: list | None) -> bytes:
    if (url, body) not in REQUESTS:
        raise ValueError("Unexpected Statistics Canada request")
    request = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
        headers={"User-Agent": "AplombDatathon/1.0 (bounded public research ingestion)",
                 "Accept": "application/json", "Content-Type": "application/json"})
    opener = urllib.request.build_opener(_NoRedirect())
    for attempt in range(3):
        try:
            with opener.open(request, timeout=25) as response:
                started, chunks, size = time.monotonic(), [], 0
                while True:
                    chunk = response.read(min(65536, 2_000_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError("Statistics Canada response exceeds byte cap")
                    if time.monotonic() - started > 25:
                        raise TimeoutError("Statistics Canada read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {409, 429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Statistics Canada retries exhausted")


def _one(payload: bytes) -> dict:
    body = json.loads(payload)
    if not isinstance(body, list) or len(body) != 1 or body[0].get("status") != "SUCCESS":
        raise ValueError("Unexpected Statistics Canada response")
    obj = body[0].get("object")
    if not isinstance(obj, dict) or obj.get("responseStatusCode") != 0:
        raise ValueError("Statistics Canada returned a response error")
    return obj


def parse(data: bytes, series: bytes, codes: bytes, stamp: str) -> tuple[list[dict], dict]:
    meta, result = _one(series), _one(data)
    expected = {"productId": 18100004, "coordinate": "2.2.0.0.0.0.0.0.0.0", "vectorId": VECTOR}
    if any(meta.get(k) != v or result.get(k) != v for k, v in expected.items()):
        raise ValueError("Unexpected Statistics Canada series identity")
    if (meta.get("SeriesTitleEn") != "Canada;All-items" or meta.get("memberUomCode") != 17
            or meta.get("frequencyCode") != 6 or meta.get("scalarFactorCode") != 0):
        raise ValueError("Unexpected series metadata")
    code_body = json.loads(codes)
    if code_body.get("status") != "SUCCESS":
        raise ValueError("Statistics Canada code set unavailable")
    units = [x for x in code_body["object"]["uom"] if x.get("memberUomCode") == 17]
    if len(units) != 1 or units[0].get("memberUomEn") != "2002=100":
        raise ValueError("Unexpected CPI index base")
    points = result.get("vectorDataPoint")
    if not isinstance(points, list) or not 1 <= len(points) <= 12:
        raise ValueError("Invalid CPI point count")
    rows, seen = [], set()
    for point in points:
        ref = point["refPer"]
        parsed = date.fromisoformat(ref)
        value = point["value"]
        if (parsed.day != 1 or parsed > timestamp(stamp).date() or ref in seen
                or point.get("refPerRaw") != ref or point.get("refPer2") not in ("", None)
                or point.get("frequencyCode") != 6 or point.get("scalarFactorCode") != 0
                or point.get("securityLevelCode") != 0
                or isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError("Unexpected CPI datapoint")
        seen.add(ref)
        row = base(DATASET_ID, ref, "macro", f"Canada all-items consumer price index, {ref[:7]}: {value:g}",
                   TABLE_URL, stamp, countryIso3="CAN", observedAt=ref, properties={
                       "attribution": f"Adapted from Statistics Canada, Consumer Price Index, monthly, not seasonally adjusted, {ref[:7]}. This does not constitute an endorsement by Statistics Canada of this product.",
                       "vectorId": VECTOR, "referenceMonth": ref[:7], "index": value,
                       "unit": "index, 2002=100", "seasonalAdjustment": "not seasonally adjusted",
                       "symbolCode": point.get("symbolCode"), "statusCode": point.get("statusCode"),
                       "sourceReleaseTime": point.get("releaseTime"),
                       "temporalPrecision": "month; first day is a display anchor",
                       "geographicRole": "national_reporting_area",
                   })
        validate_row(row)
        rows.append(row)
    return rows, {"sourceRows": len(points), "rejected": 0, "coverageComplete": False,
                  "scope": "Most recent 12 available monthly observations for Canada all-items CPI only."}


def collect(directory: Path, fetcher=fetch) -> dict:
    captures = [(url, fetcher(url, body)) for url, body in REQUESTS]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(*(payload for _, payload in captures), stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-096"],
        "name": "Statistics Canada monthly all-items consumer price index",
        "sourceUrl": DATA_URL, "attribution": f"Source: Statistics Canada, Consumer Price Index, monthly, not seasonally adjusted, {min(r["properties"]["referenceMonth"] for r in rows)} to {max(r["properties"]["referenceMonth"] for r in rows)}. Reproduced and distributed on an \"as is\" basis with the permission of Statistics Canada.", "licence": "Statistics Canada Open Licence; attribution required, no endorsement",
        "licenceUrl": "https://www.statcan.gc.ca/en/terms-conditions/open-licence",
        "frequency": "Monthly; manual capture", "requestBodies": {url: body for url, body in REQUESTS if body is not None},
        "limitations": ["Canada all-items CPI only; latest 12 available months, not a global or full historical series.",
                        "CPI is an index (2002=100), not a monthly or annual inflation rate; it is not seasonally adjusted.",
                        "Values may be revised; original historical availability is not established; capture-time gate applies.",
                        "No coordinates, issuer, exposure, or financial relationship established."],
        **quality, "retrievedAt": stamp,
    }
    return publish(directory, rows, metadata, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
