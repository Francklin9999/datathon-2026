"""Bounded captures of official ECB press metadata and UK sanctions update notes.

Run: python -m aplomb.world.providers.feeds_extra --source ecb --source uk_sanctions
Only captured metadata is exposed; the live provider is never called by the API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

from .snapshot import DIRECTORY, publish, timestamp

ECB_URL = "https://www.ecb.europa.eu/rss/press.html"
UK_URL = "https://www.gov.uk/api/content/government/publications/the-uk-sanctions-list"
UK_PAGE = "https://www.gov.uk/government/publications/the-uk-sanctions-list"
HOSTS = frozenset({"www.ecb.europa.eu", "www.gov.uk"})


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _check_url(url: str) -> None:
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in HOSTS or p.username or p.password or p.port:
        raise ValueError("Feed URL outside allowlist")


def fetch(url: str, *, timeout: float = 20, max_bytes: int = 2_000_000) -> bytes:
    """Fetch one fixed-host document with a byte cap, deadline and bounded retries."""
    _check_url(url)
    opener = urllib.request.build_opener(_Redirect())
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AplombDatathon/1.0 (public research capture)",
                                                        "Accept": "application/rss+xml,application/json"})
            with opener.open(req, timeout=timeout) as response:
                _check_url(response.url)
                started, chunks, size = time.monotonic(), [], 0
                while True:
                    chunk = response.read(min(65536, max_bytes + 1 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("Feed exceeds byte cap")
                    if time.monotonic() - started > timeout:
                        raise TimeoutError("Feed read deadline exceeded")
                    chunks.append(chunk)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(min(4, 2 ** attempt))
    raise RuntimeError("Feed retry exhausted")


def _row(source: str, key: str, title: str, url: str, published: str, stamp: str, **properties) -> dict:
    return {"id": source + ":" + key, "sourceId": source, "category": "policy", "title": title,
            "sourceUrl": url, "publishedAt": published, "observedAt": None, "retrievedAt": stamp,
            "availableAt": stamp, "latitude": None, "longitude": None, "countryIso3": None,
            "properties": properties}


def ecb(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    # The RSS format contains titles/links only. Do not republish authored documents.
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("XML declarations with DTD/entity are not accepted")
    root = ET.fromstring(payload)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Unexpected ECB RSS structure")
    items = root.findall("./channel/item")
    rows, seen, rejected = [], set(), 0
    for item in items[:100]:
        title, link, published = ((item.findtext(key) or "").strip() for key in ("title", "link", "pubDate"))
        try:
            parts = urlsplit(link)
            date = parsedate_to_datetime(published)
            if date.tzinfo is None or not title or parts.scheme != "https" or parts.hostname != "www.ecb.europa.eu":
                raise ValueError("Invalid item")
            if parts.username or parts.password or parts.port or "/press/pr/" not in parts.path:
                raise ValueError("Not ECB press release")
            if date > timestamp(stamp):
                raise ValueError("Future release")
            if link in seen:
                raise ValueError("Duplicate link")
            seen.add(link)
            rows.append(_row("world_ecb_press", hashlib.sha256(link.encode()).hexdigest()[:24], title, link,
                             date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), stamp,
                             publisher="European Central Bank", geographicRole="regional_institution",
                             attribution="Source: European Central Bank; feed metadata adapted by Aplomb."))
        except (ValueError, TypeError, OverflowError):
            rejected += 1
    return rows, {"scope": "Current ECB RSS press releases only; no complete archive or authored documents.",
                  "coverageComplete": False, "quality": {"inputRows": len(items), "examinedRows": min(100, len(items)),
                               "acceptedRows": len(rows), "rejectedRows": rejected,
                               "truncated": len(items) > 100}}


def uk_sanctions(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    data = json.loads(payload)
    if data.get("base_path") != "/government/publications/the-uk-sanctions-list":
        raise ValueError("Unexpected UK sanctions page")
    items = data["details"]["change_history"]
    if not isinstance(items, list):
        raise ValueError("Invalid change history")
    rows, seen, rejected = [], set(), 0
    for item in items[:50]:
        try:
            title, published = item["note"].strip(), item["public_timestamp"]
            if not title or timestamp(published) > timestamp(stamp):
                raise ValueError("Missing or future update")
            key = hashlib.sha256((published + "\n" + title).encode()).hexdigest()[:24]
            if key in seen:
                raise ValueError("Duplicate update")
            seen.add(key)
            rows.append(_row("world_uk_sanctions_updates", key, title, UK_PAGE, published, stamp,
                             publisher="UK Foreign, Commonwealth & Development Office",
                             geographicRole="national_jurisdiction", attribution="Contains public sector information licensed under the Open Government Licence v3.0; adapted by Aplomb.",
                             legalAuthority="Update note only; consult the current UK Sanctions List and applicable law."))
        except (KeyError, ValueError, TypeError, AttributeError):
            rejected += 1
    return rows, {"scope": "First 50 UK Sanctions List publication change notes; not the designated persons list.",
                  "coverageComplete": False, "quality": {"inputRows": len(items), "examinedRows": min(50, len(items)),
                               "acceptedRows": len(rows), "rejectedRows": rejected,
                               "truncated": len(items) > 50}}


SOURCES = {
    "ecb": {"datasetId": "world_ecb_press", "sourceIds": ["SRC-105", "MASTER-047"],
            "name": "European Central Bank press releases", "sourceUrl": ECB_URL,
            "licence": "ECB free use with accurate reproduction and attribution; modified information identified; additional conditions apply to sold documents and business links",
            "licenceUrl": "https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html",
            "frequency": "Current bounded RSS page, manually captured",
            "limitations": ["Only press release titles, dates and links; speeches and interviews excluded.",
                            "Feed page is not a complete archive; no proven historical vintage.",
                            "Regional institution; no country coordinates or issuer relationships inferred."], "parser": ecb},
    "uk_sanctions": {"datasetId": "world_uk_sanctions_updates", "sourceIds": ["SRC-139"],
                     "name": "UK Sanctions List publication update notes", "sourceUrl": UK_URL,
                     "licence": "Open Government Licence v3.0; contains public sector information; adapted by Aplomb",
                     "licenceUrl": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
                     "frequency": "First 50 publication change notes, manually captured",
                     "limitations": ["Update notes, not the current list of designated persons, vessels or entities.",
                                     "UK jurisdiction only; sanctions regimes named in notes are not location or issuer links.",
                                     "Incomplete change history and no proven historical vintage; consult current official list."],
                     "parser": uk_sanctions},
}


def collect(name: str, fetcher=fetch, stamp: str | None = None, directory: Path = DIRECTORY) -> dict:
    source = SOURCES[name]
    payload = fetcher(source["sourceUrl"])
    if stamp is None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = source["parser"](payload, stamp)
    metadata = {key: value for key, value in source.items() if key != "parser"}
    return publish(directory, rows, {**metadata, **quality, "retrievedAt": stamp}, [(source["sourceUrl"], payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", choices=sorted(SOURCES), action="append", required=True)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    results = []
    for name in dict.fromkeys(args.source):
        try:
            manifest = collect(name, directory=args.directory)
            results.append({"source": name, "status": "captured", "version": manifest["dataVersion"], "rows": manifest["rowCount"]})
        except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as exc:
            results.append({"source": name, "status": "failed", "error": str(exc)})
    print(json.dumps(results, indent=2))
    return int(any(result["status"] == "failed" for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
