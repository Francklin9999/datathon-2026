"""Capture anonymous openFDA aggregate drug enforcement counts.

Run: python -m aplomb.world.providers.fda_extra --directory PATH
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import publish, timestamp, validate_row

DATASET_ID = "world_fda_drug_enforcement_counts"
PERIOD_START = "2026-01-01"
PERIOD_END = "2026-11-15"
DATA_URL = (
    "https://api.fda.gov/drug/enforcement.json?"
    "search=report_date:%5B20260101+TO+20261115%5D&count=classification.exact"
)
SOURCE_URL = "https://open.fda.gov/apis/drug/enforcement/"
TERMS_URL = "https://open.fda.gov/terms/"
LICENSE_URL = "https://open.fda.gov/license/"
AUTH_URL = "https://open.fda.gov/apis/authentication/"
QUERY_URL = "https://open.fda.gov/apis/query-parameters/"
URLS = (DATA_URL, TERMS_URL, LICENSE_URL, AUTH_URL, SOURCE_URL, QUERY_URL)
CLASSIFICATIONS = {"Class I", "Class II", "Class III", "Not Yet Classified"}
ATTRIBUTION = "Data provided by the U.S. Food and Drug Administration (https://open.fda.gov). Adapted by Aplomb; no FDA endorsement."


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected openFDA redirect")


def fetch(url: str) -> bytes:
    if url not in URLS:
        raise ValueError("Unexpected openFDA URL")
    request = urllib.request.Request(url, headers={
        "User-Agent": "AplombDatathon/1.0 (bounded public research ingestion)",
        "Accept": "application/json" if url == DATA_URL else "text/html",
    })
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=25) as response:
        expected = "application/json" if url == DATA_URL else "text/html"
        if response.headers.get_content_type() != expected:
            raise ValueError("Unexpected openFDA content type")
        started, chunks, size = time.monotonic(), [], 0
        while True:
            chunk = response.read(min(65536, 2_000_001 - size))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
            if size > 2_000_000:
                raise ValueError("openFDA response exceeds byte cap")
            if time.monotonic() - started > 25:
                raise TimeoutError("openFDA read deadline exceeded")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if not isinstance(body, dict) or set(body) != {"meta", "results"}:
        raise ValueError("Unexpected openFDA aggregate envelope")
    meta, results = body["meta"], body["results"]
    if (not isinstance(meta, dict) or meta.get("terms") != TERMS_URL
            or meta.get("license") != LICENSE_URL
            or not isinstance(results, list) or not 1 <= len(results) <= 4):
        raise ValueError("Unexpected openFDA aggregation metadata")
    updated = date.fromisoformat(meta["last_updated"])
    if updated > timestamp(stamp).date() or date.fromisoformat(PERIOD_END) > timestamp(stamp).date():
        raise ValueError("Future source update or query window")
    rows, seen = [], set()
    for item in results:
        if not isinstance(item, dict) or set(item) != {"term", "count"}:
            raise ValueError("Unexpected openFDA count fields")
        term, count = item["term"], item["count"]
        if (term not in CLASSIFICATIONS or term in seen or isinstance(count, bool)
                or not isinstance(count, int) or count < 1):
            raise ValueError("Invalid openFDA classification count")
        seen.add(term)
        key = term.lower().replace(" ", "_")
        row = base(DATASET_ID, key, "health",
                   f"FDA drug enforcement records: {term}, {count} in report-date window",
                   SOURCE_URL, stamp, properties={
                       "classification": term, "recordCount": count,
                       "unit": "matching drug enforcement records",
                       "queryDateField": "report_date",
                       "queryPeriodStart": PERIOD_START, "queryPeriodEnd": PERIOD_END,
                       "sourceLastUpdated": meta["last_updated"],
                       "geographicRole": "regulatory_dataset_scope; no product distribution geography",
                       "attribution": ATTRIBUTION,
                       "publicRecallAlert": False,
                       "recallLifecycleTracking": False,
                       "medicalDecisionSupport": False,
                   })
        validate_row(row)
        rows.append(row)
    return rows, {
        "sourceRows": len(results), "rejected": 0, "coverageComplete": False,
        "matchingRecordCount": sum(r["properties"]["recordCount"] for r in rows),
        "scope": "Drug enforcement records grouped by classification within a fixed report-date window; not unique recall events.",
    }


def collect(directory: Path, fetcher=fetch) -> dict:
    captures = [(url, fetcher(url)) for url in URLS]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(captures[0][1], stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-239"],
        "name": "openFDA aggregate drug enforcement classification counts",
        "sourceUrl": DATA_URL, "retrievedAt": stamp,
        "attribution": ATTRIBUTION,
        "licence": "Public domain / CC0 1.0 for numeric FDA aggregate counts; openFDA service terms apply",
        "licenceUrl": TERMS_URL, "frequency": "Source updated weekly; manual capture",
        "access": "Anonymous HTTPS request; no API key or login used",
        "limitations": [
            "Fixed 2026-01-01 through 2026-11-15 report-date window; incomplete present-day/global coverage.",
            "Counts represent enforcement records, not unique recall events, affected patients, incidence, safety rates, or public attention.",
            "No product text, GMDN content, company identities, patient data, distribution geography, or coordinates are captured.",
            "FDA says this endpoint should not issue public recall alerts or track recall lifecycles; it is unsuitable for medical decisions.",
            "Source may correct prior records. No historical replay or original availability is established; capture-time gate applies.",
            "Authentication documentation says keys are required yet lists anonymous limits: 240 requests/minute and 1,000/day/IP. Anonymous capture succeeded.",
            "No issuer relationship, causation, exposure, or financial impact is established.",
        ],
        **quality,
    }
    return publish(directory, rows, metadata, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"datasetId": DATASET_ID, "version": manifest["dataVersion"],
                      "rows": manifest["rowCount"],
                      "matchingRecords": manifest["matchingRecordCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
