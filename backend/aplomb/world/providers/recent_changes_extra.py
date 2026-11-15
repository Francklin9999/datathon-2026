"""Bounded Wikipedia edit metadata; no article text, editor names or comments.

Run: python -m aplomb.world.providers.recent_changes_extra
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from .snapshot import DIRECTORY, publish, timestamp

DATASET_ID = "world_wikipedia_recent_changes"
URL = "https://en.wikipedia.org/w/api.php?" + urlencode({
    "action": "query", "list": "recentchanges", "rcprop": "title|timestamp|ids|sizes",
    "rclimit": 10, "rcnamespace": 0, "rctype": "edit|new", "format": "json",
})
TERMS_URL = "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
METADATA = {
    "datasetId": DATASET_ID, "sourceIds": ["SRC-127"],
    "name": "English Wikipedia Recent Changes edit metadata",
    "sourceUrl": URL, "frequency": "Ten newest article changes; manual captured page",
    "licence": "Factual edit metadata; Wikimedia Terms of Use §7 permits free reuse of contributed facts; article text excluded",
    "licenceUrl": TERMS_URL,
    "attribution": "Source: English Wikipedia / Wikimedia; factual edit metadata adapted by Aplomb.",
    "limitations": [
        "Ten newest article edits/new pages only; continuation is deliberately not followed.",
        "Edit activity is not confirmation of a news event, sentiment, popularity or investment relevance.",
        "No article text, edit comments, editor identities or IP addresses are requested or stored.",
        "An article title does not establish event location, issuer identity or a holding relationship.",
        "Edit timestamp is not the publication or observation time of a real-world event.",
        "Current capture only; original historical availability is unproven and gated at retrieval.",
    ],
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected Recent Changes redirect")


def fetch(url: str) -> bytes:
    if url not in {URL, TERMS_URL}:
        raise ValueError("Recent Changes URL outside fixed allowlist")
    opener = urllib.request.build_opener(_NoRedirect())
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "AplombDatathon/1.0 (bounded public research capture)",
                "Accept": "application/json,text/html",
            })
            with opener.open(req, timeout=20) as response:
                started, chunks, size = time.monotonic(), [], 0
                while True:
                    chunk = response.read(min(65536, 500001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > 500000:
                        raise ValueError("Recent Changes payload exceeds byte cap")
                    if time.monotonic() - started > 20:
                        raise TimeoutError("Recent Changes read deadline exceeded")
                    chunks.append(chunk)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 1:
                raise
        time.sleep(1)
    raise RuntimeError("Recent Changes retries exhausted")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    data = json.loads(payload)
    items = data["query"]["recentchanges"]
    if not isinstance(items, list) or len(items) > 10:
        raise ValueError("Unexpected Recent Changes page size")
    rows, seen, rejected = [], set(), 0
    for item in items:
        try:
            if item["type"] not in {"edit", "new"} or item["ns"] != 0:
                raise ValueError("Unexpected change kind or namespace")
            ids = [item[field] for field in ("pageid", "revid", "old_revid", "rcid")]
            sizes = [item[field] for field in ("oldlen", "newlen")]
            if any(type(value) is not int or value < 0 for value in ids + sizes) or not all(ids[i] > 0 for i in (0, 1, 3)):
                raise ValueError("Invalid identifiers or byte lengths")
            title, edited = item["title"], item["timestamp"]
            if not isinstance(title, str) or not title.strip() or timestamp(edited) > timestamp(stamp):
                raise ValueError("Invalid title or future edit")
            if ids[3] in seen:
                raise ValueError("Duplicate Recent Changes identifier")
            seen.add(ids[3])
            page_url = "https://en.wikipedia.org/w/index.php?oldid=" + str(ids[1])
            rows.append({
                "id": DATASET_ID + ":" + str(ids[3]), "sourceId": DATASET_ID,
                "category": "news", "title": "Wikipedia edit activity: " + title,
                "sourceUrl": page_url, "publishedAt": None, "observedAt": edited,
                "retrievedAt": stamp, "availableAt": stamp, "latitude": None,
                "longitude": None, "countryIso3": None,
                "properties": {
                    "articleTitle": title, "articleUrl": "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
                    "pageId": ids[0], "revisionId": ids[1], "previousRevisionId": ids[2],
                    "changeId": ids[3], "changeType": item["type"],
                    "oldBytes": sizes[0], "newBytes": sizes[1],
                    "geographicRole": "unlocated_article_edit",
                    "attribution": METADATA["attribution"],
                },
            })
        except (KeyError, TypeError, ValueError):
            rejected += 1
    return rows, {
        "scope": "Ten newest main-namespace English Wikipedia edits/new pages; no continuation requests.",
        "coverageComplete": False,
        "quality": {"inputRows": len(items), "acceptedRows": len(rows), "rejectedRows": rejected,
                    "continuationAvailable": "continue" in data, "paginationFollowed": False},
    }


def collect(directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    payload = fetcher(URL)
    terms = fetcher(TERMS_URL)
    if b"facts you contribute to the projects may be reused freely" not in terms:
        raise ValueError("Wikimedia factual reuse statement missing; review current terms")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, stamp)
    return publish(directory, rows, {**METADATA, **quality, "retrievedAt": stamp},
                   [(URL, payload), (TERMS_URL, terms)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"datasetId": DATASET_ID, "rows": manifest["rowCount"],
                      "version": manifest["dataVersion"], "sha256": manifest["sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
