"""Capture five anonymous TED published-notice metadata records.

Run: python -m aplomb.world.providers.ted_extra --directory PATH
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import canonical, publish, timestamp, validate_row

DATASET_ID = "world_ted_published_notice_metadata"
DATA_URL = "https://api.ted.europa.eu/v3/notices/search"
TERMS_URL = "https://ted.europa.eu/en/legal-notice"
DOCS_URL = "https://docs.ted.europa.eu/api/latest/search.html"
SPEC_URL = "https://api.ted.europa.eu/api-v3.yaml"
URLS = (DATA_URL, TERMS_URL, DOCS_URL, SPEC_URL)
REQUEST = {
    "query": "publication-date >= 20261101 AND publication-date <= 20261115 SORT BY publication-date DESC",
    "fields": ["publication-number", "publication-date", "buyer-country"],
    "limit": 5, "page": 1, "scope": "ALL", "onlyLatestVersions": True,
}
ATTRIBUTION = "European Union, Publications Office, Tenders Electronic Daily (TED). Metadata projected and normalized by Aplomb."
SCOPE = ("Five published procurement notice metadata records from the first page of "
         "2026-11-01 through 2026-11-15; source-reported buyer countries only.")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected TED redirect")


def fetch(url: str) -> bytes:
    if url not in URLS:
        raise ValueError("Unexpected TED URL")
    headers = {"User-Agent": "AplombDatathon/1.0 (bounded public research ingestion)"}
    data = None
    if url == DATA_URL:
        headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        data = canonical(REQUEST)
    request = urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=25) as response:
                if url == DATA_URL and response.headers.get_content_type() != "application/json":
                    raise ValueError("Unexpected TED search content type")
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, 2_000_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError("TED payload exceeds byte cap")
                    if time.monotonic() - started > 25:
                        raise TimeoutError("TED read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("TED retry exhausted")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if (not isinstance(body, dict) or body.get("timedOut") is not False
            or not isinstance(body.get("notices"), list)
            or not 1 <= len(body["notices"]) <= REQUEST["limit"]):
        raise ValueError("Invalid or timed-out TED response")
    total = body.get("totalNoticeCount")
    if isinstance(total, bool) or not isinstance(total, int) or total < len(body["notices"]):
        raise ValueError("Invalid TED matching notice count")
    rows, seen = [], set()
    for notice in body["notices"]:
        if not isinstance(notice, dict) or set(notice) - {
            "publication-number", "publication-date", "buyer-country", "links"
        }:
            raise ValueError("Unexpected projected TED notice fields")
        number, publication = notice["publication-number"], notice["publication-date"]
        countries = notice["buyer-country"]
        if not isinstance(number, str) or not re.fullmatch(r"\d{1,8}-2026", number) or number in seen:
            raise ValueError("Invalid or duplicate TED publication number")
        if not isinstance(publication, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}[+-]\d{2}:\d{2}", publication):
            raise ValueError("Invalid TED publication date")
        day = date.fromisoformat(publication[:10])
        if not date(2026, 11, 1) <= day <= min(date(2026, 11, 15), timestamp(stamp).date()):
            raise ValueError("TED publication outside requested window")
        if (not isinstance(countries, list) or not countries
                or any(not isinstance(c, str) or not re.fullmatch(r"[A-Z]{3}", c) for c in countries)):
            raise ValueError("Invalid source-reported TED buyer countries")
        source_url = notice.get("links", {}).get("html", {}).get("ENG")
        expected_url = f"https://ted.europa.eu/en/notice/-/detail/{number}"
        if source_url != expected_url:
            raise ValueError("Unexpected TED notice permalink")
        seen.add(number)
        row = base(DATASET_ID, number, "trade", f"TED published procurement notice {number}",
                   source_url, stamp, countryIso3=countries[0] if len(set(countries)) == 1 else None,
                   properties={
                       "publicationNumber": number,
                       "publicationDate": day.isoformat(),
                       "sourcePublicationDate": publication,
                       "publicationDatePrecision": "day; source timezone offset retained",
                       "buyerCountries": countries,
                       "geographicRole": "source_reported_buyer_country; not place of performance",
                       "noticeStatus": "published on TED",
                       "attribution": ATTRIBUTION,
                   })
        validate_row(row)
        rows.append(row)
    return rows, {"sourceRows": len(rows), "rejected": 0, "coverageComplete": False,
                  "totalMatchingNotices": total}


def collect(directory: Path, fetcher=fetch) -> dict:
    captures = [(url, fetcher(url)) for url in URLS]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(captures[0][1], stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-145"],
        "name": "TED bounded published procurement notice metadata",
        "scope": SCOPE,
        "sourceUrl": DATA_URL, "retrievedAt": stamp,
        "requestMethod": "POST", "requestBody": REQUEST,
        "attribution": ATTRIBUTION,
        "licence": "TED published notices freely reusable for commercial or noncommercial purposes unless otherwise noted; SIMAP system metadata CC0 1.0",
        "licenceUrl": TERMS_URL, "frequency": "TED publication days; manual capture",
        "access": "Anonymous published-notice Search API; no key, account, or payment",
        "limitations": [
            "Five notices from first page of a fixed 2026-11-01 through 2026-11-15 publication window; incomplete coverage.",
            "Latest notice versions only; ordering among equal publication dates is upstream-dependent.",
            "Publication date has day precision. observedAt and publishedAt remain unset; availableAt gates at capture.",
            "Country identifies reported buyer location, not contract execution or performance geography; no coordinates.",
            "No buyer/winner names, contacts, company identities, amounts, tender descriptions, documents, or third-party works requested.",
            "Notice publication does not establish a contract award, realized spending, issuer relationship, exposure, or financial impact.",
            "TED legal notice allows reuse unless otherwise noted and excludes third-party material, logos, and industrial-property rights.",
        ],
        **quality,
    }
    return publish(directory, rows, metadata, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    manifest = collect(parser.parse_args().directory)
    print(json.dumps({"datasetId": DATASET_ID, "version": manifest["dataVersion"],
                      "rows": manifest["rowCount"], "matchingNotices": manifest["totalMatchingNotices"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
