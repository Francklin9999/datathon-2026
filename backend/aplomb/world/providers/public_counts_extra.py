"""Bounded anonymous Wikimedia topic pageview capture, served from saved data.

Run: python -m aplomb.world.providers.public_counts_extra
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, timestamp, validate_row

DATASET_ID = "world_wikimedia_topic_pageviews"
TOPICS = ("Canada", "Japan", "Brazil")
ROOT = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/user/"
URLS = {topic: ROOT + topic + "/daily/2026100100/2026100700" for topic in TOPICS}
LICENCE_URL = "https://dumps.wikimedia.org/legal.html"
ALLOWED_URLS = frozenset((*URLS.values(), LICENCE_URL))
METADATA = {
    "datasetId": DATASET_ID, "sourceIds": ["SRC-126"],
    "name": "Wikimedia English Wikipedia country-topic pageviews",
    "sourceUrl": "https://wikitech.wikimedia.org/wiki/Data_Platform/AQS/Pageviews",
    "licence": "Wikimedia Analytics datasets: CC0 1.0 unless otherwise specified; numeric analytics only",
    "licenceUrl": LICENCE_URL, "frequency": "Daily counts, manual bounded capture",
    "attribution": "Source: Wikimedia Analytics API; selected numeric counts adapted by Aplomb.",
    "limitations": [
        "Only Canada, Japan and Brazil English Wikipedia article counts, 2026-10-01 through 2026-10-07.",
        "Counts are pageviews, not unique people, sentiment, event confirmation or investor interest.",
        "User-agent classification excludes identified spiders and automated requests; classification is imperfect.",
        "Article topic does not establish reader location or any event location; country and coordinates remain absent.",
        "Daily midnight UTC is a reporting-period anchor, not a publication or event timestamp.",
        "No original historical vintage or issuer/exposure relationship is established; gated at capture.",
    ],
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected Wikimedia capture redirect")


def fetch(url: str) -> bytes:
    """Four fixed URLs, at most two attempts, 20 second reads and 500 kB each."""
    if url not in ALLOWED_URLS:
        raise ValueError("Unexpected Wikimedia capture URL")
    opener = urllib.request.build_opener(_NoRedirect())
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "AplombDatathon/1.0 (bounded public research capture)",
                "Accept": "application/json,text/html",
            })
            with opener.open(req, timeout=20) as response:
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, 500001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > 500000:
                        raise ValueError("Wikimedia capture exceeds byte cap")
                    if time.monotonic() - started > 20:
                        raise TimeoutError("Wikimedia read deadline exceeded")
                    chunks.append(chunk)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 1:
                raise
        time.sleep(1)
    raise RuntimeError("Wikimedia retries exhausted")


def parse(payload: bytes, topic: str, stamp: str) -> list[dict]:
    if topic not in URLS:
        raise ValueError("Unexpected article topic")
    body = json.loads(payload)
    if not isinstance(body, dict):
        raise ValueError("Expected pageview response object")
    items = body.get("items")
    if not isinstance(items, list) or len(items) != 7:
        raise ValueError("Expected seven daily pageview observations")
    rows, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Expected pageview observation object")
        if any(item.get(key) != value for key, value in {
            "project": "en.wikipedia", "article": topic, "granularity": "daily",
            "access": "all-access", "agent": "user",
        }.items()):
            raise ValueError("Unexpected pageview dimensions")
        day = item["timestamp"]
        if day not in {f"2026100{i}00" for i in range(1, 8)} or day in seen:
            raise ValueError("Duplicate or out-of-scope pageview date")
        seen.add(day)
        views = item["views"]
        if type(views) is not int or views < 0:
            raise ValueError("Invalid pageview count")
        observed = f"{day[:4]}-{day[4:6]}-{day[6:8]}T00:00:00Z"
        if timestamp(observed) >= timestamp(stamp):
            raise ValueError("Reporting period is not complete")
        row = base(DATASET_ID, topic + ":" + day, "news",
                   f"English Wikipedia {topic} topic: {views:,} pageviews, {observed[:10]}",
                   URLS[topic], stamp, observedAt=observed, properties={
                       "article": topic, "project": "en.wikipedia", "views": views,
                       "referenceDate": observed[:10], "access": "all-access", "agent": "user",
                       "geographicRole": "article_topic_only_no_observation_location",
                       "temporalPrecision": "daily UTC reporting period",
                       "attribution": METADATA["attribution"],
                   })
        validate_row(row)
        rows.append(row)
    return rows


def collect(fetcher=fetch, *, directory: Path = DIRECTORY, stamp: str | None = None) -> dict:
    captures = []
    for url in URLS.values():
        if captures:
            time.sleep(0.5)
        captures.append((url, fetcher(url)))
    # Save the analytics-specific rights statement with the same immutable capture.
    time.sleep(0.5)
    legal = fetcher(LICENCE_URL)
    if b"All Analytics datasets are available under" not in legal or b"CC0" not in legal:
        raise ValueError("Wikimedia Analytics reuse statement could not be verified")
    captures.append((LICENCE_URL, legal))
    stamp = stamp or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = [row for topic, (_, payload) in zip(TOPICS, captures[:3], strict=True)
            for row in parse(payload, topic, stamp)]
    return publish(directory, rows, {
        **METADATA, "retrievedAt": stamp, "scope": "Three English Wikipedia topic pages for seven UTC days.",
        "coverageComplete": False, "sourceRows": len(rows), "rejected": 0,
    }, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    try:
        manifest = collect(directory=args.directory)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "captured", "version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
