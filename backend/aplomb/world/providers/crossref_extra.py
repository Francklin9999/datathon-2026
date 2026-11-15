"""Bounded anonymous Crossref bibliographic metadata capture.

Run: python -m aplomb.world.providers.crossref_extra --directory PATH
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
from urllib.parse import quote, urlencode

from .public import base
from .snapshot import DIRECTORY, publish

DATASET_ID = "world_crossref_climate_bibliography"
TERMS_URL = "https://www.crossref.org/documentation/retrieve-metadata/rest-api/"
ACCESS_URL = TERMS_URL + "access-and-authentication/"
DATA_URL = "https://api.crossref.org/works?" + urlencode({
    "filter": "type:journal-article,from-pub-date:2024-01-01,until-pub-date:2024-12-31",
    "query.title": "climate change", "rows": 5,
    "select": "DOI,title,published,type",
})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected Crossref redirect")


def fetch(url: str) -> tuple[bytes, dict]:
    if url != DATA_URL:
        raise ValueError("Unexpected Crossref request")
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "AplombDatathon/1.0 (bounded Crossref metadata capture)",
    })
    for attempt in range(3):
        try:
            with opener.open(request, timeout=25) as response:
                payload = response.read(100_001)
                if len(payload) > 100_000:
                    raise ValueError("Crossref payload exceeds byte cap")
                headers = {key: response.headers.get(key) for key in (
                    "x-rate-limit-limit", "x-rate-limit-interval",
                    "x-concurrency-limit", "x-api-pool",
                )}
                return payload, headers
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            retry = exc.headers.get("Retry-After", "")
            if retry.isdigit() and int(retry) > 60:
                raise
            delay = max(2 ** (attempt + 1), int(retry) if retry.isdigit() else 0)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            delay = 2 ** (attempt + 1)
        time.sleep(delay)
    raise RuntimeError("Crossref retries exhausted")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if body.get("status") != "ok" or body.get("message-type") != "work-list":
        raise ValueError("Unexpected Crossref response")
    message = body["message"]
    items = message.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 5:
        raise ValueError("Unexpected Crossref item count")
    rows, seen = [], set()
    for item in items:
        if set(item) - {"DOI", "title", "published", "type"}:
            raise ValueError("Unexpected unprojected Crossref fields")
        doi, titles = item.get("DOI"), item.get("title")
        if (not isinstance(doi, str) or not re.fullmatch(r"10\.\d{4,9}/\S+", doi)
                or doi.lower() in seen or item.get("type") != "journal-article"
                or not isinstance(titles, list) or not titles
                or any(not isinstance(title, str) or not title.strip() for title in titles)):
            raise ValueError("Invalid Crossref bibliographic identity")
        seen.add(doi.lower())
        parts = item.get("published", {}).get("date-parts")
        if (not isinstance(parts, list) or len(parts) != 1
                or not isinstance(parts[0], list) or not 1 <= len(parts[0]) <= 3
                or any(type(value) is not int for value in parts[0])
                or parts[0][0] != 2024):
            raise ValueError("Invalid source publication date")
        values = parts[0]
        date(values[0], values[1] if len(values) > 1 else 1,
             values[2] if len(values) > 2 else 1)
        rows.append(base(
            DATASET_ID, doi.lower(), "research", titles[0],
            "https://doi.org/" + quote(doi, safe="/"), stamp,
            properties={
                "doi": doi, "titles": titles, "workType": item["type"],
                "publicationDateParts": values,
                "publicationDateResolution": ("year", "month", "day")[len(values) - 1],
                "dateRole": "Crossref member-deposited publication date",
                "geographicRole": "none",
                "attribution": "Crossref bibliographic metadata",
            },
        ))
    return rows, {
        "sourceRows": len(items), "sourceTotalResults": message.get("total-results"),
        "rejected": 0, "coverageComplete": False,
        "scope": "First five relevance-ranked 2024 journal records matching the title query climate change; no pagination.",
    }


def collect(directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    payload, headers = fetcher(DATA_URL)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-236"],
        "name": "Crossref climate change bibliography, bounded 2024 metadata sample",
        "sourceUrl": DATA_URL, "licenceUrl": TERMS_URL,
        "licence": "Crossref REST documentation permits bibliographic metadata use for any purpose; abstracts may be copyrighted and are excluded.",
        "attribution": "Crossref bibliographic metadata",
        "accessDocumentationUrl": ACCESS_URL, "responseLimits": headers,
        "frequency": "Manual immutable capture; upstream member metadata can change",
        "retrievedAt": stamp, **quality,
        "modifications": [
            "API select projects DOI, title, published and type only; no abstracts, authors, full text, references or affiliations.",
            "First title is the display title; all returned title variants and publication date parts are retained.",
            "No geographical coordinates, country, company or security associations are inferred.",
        ],
        "limitations": [
            "Title search is relevance ranked and does not establish subject classification, scientific validity or climate exposure.",
            "Publication dates are deposited metadata with variable precision; top-level publishedAt and observedAt remain unset.",
            "Capture-time availability gates apply; historical availability and historical API ranking are unproven.",
            "The five records are an incomplete sample, not global research coverage; query results may change.",
            "Anonymous public access is permitted; no contact email is invented to obtain the optional polite pool.",
            "This permission statement is not a Creative Commons or public-domain licence assertion for linked publications.",
        ],
    }
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
