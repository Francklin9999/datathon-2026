"""Batch ingestion of real, source-backed world events (world SPEC §3, §4).

    uv run python -m aplomb.world.ingest --start 2021-11-12 --end 2026-11-12

Fetches a bounded set of public feeds once, normalizes them and writes an immutable bundle
(``events.json``, ``hazards.json``, ``manifest.json``) that the API serves from disk. The API never
calls a third-party source. Nothing is invented: an item without a source URL, a verbatim title, a
date and a source-supported location is rejected and counted in the manifest; a source that
fails is recorded as failed. Parsers are pure functions so they are tested offline.

Sources (all public, no key): USGS earthquake catalog (point locations), Bank of Canada press
release feed, Federal Reserve monetary-policy press feed, and the Statistics Canada "The Daily"
pages already recorded in ``data/metadata/macro_release_dates.csv`` (country-level locations).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .geo import COUNTRIES, resolve_place_country

BUNDLE_DIR = Path(__file__).resolve().parent / "bundle"
REPO_ROOT = Path(__file__).resolve().parents[3]
USER_AGENT = "AplombResearchDemo/0.1 (university datathon project; batch ingestion, low volume)"

# Query parameters that only track a visitor; removed before hashing a URL into an eventId.
# Every other query parameter is kept because it may identify the document.
TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid",
})

# Explicit alias table (world SPEC §3). Only unambiguous corporate names: a bare "Apple",
# "Amazon", "Tesla" (the inventor), "Fortis" or "Alphabet" is not accepted as a company mention.
COMPANY_ALIASES: dict[str, tuple[str, ...]] = {
    "RY.TO": ("Royal Bank of Canada",),
    "TD.TO": ("Toronto-Dominion Bank", "TD Bank Group"),
    "MFC.TO": ("Manulife Financial", "Manulife"),
    "ENB.TO": ("Enbridge",),
    "CNQ.TO": ("Canadian Natural Resources",),
    "CNR.TO": ("Canadian National Railway",),
    "FTS.TO": ("Fortis Inc",),
    "ATD.TO": ("Alimentation Couche-Tard", "Couche-Tard"),
    "SHOP.TO": ("Shopify",),
    "CSU.TO": ("Constellation Software",),
    "AAPL": ("Apple Inc",),
    "MSFT": ("Microsoft",),
    "NVDA": ("Nvidia",),
    "GOOGL": ("Alphabet Inc",),
    "AMZN": ("Amazon.com",),
    "TSLA": ("Tesla Inc", "Tesla Motors"),
    "JPM": ("JPMorgan Chase", "JPMorgan"),
    "JNJ": ("Johnson & Johnson",),
    "PG": ("Procter & Gamble",),
    "XOM": ("Exxon Mobil", "ExxonMobil"),
}
# Team assumption (labelled as such wherever shown): a policy-rate announcement is tagged with the
# bond themes of its country. It is a proxy link, not evidence of an effect.
POLICY_THEMES = {"CAN": ("bonds_canada",), "USA": ("bonds_us", "long_treasuries")}
_POLICY_WORDS = re.compile(r"policy rate|interest rate|overnight rate|federal funds|fomc|monetary policy", re.I)


def canonical_url(url: str) -> str:
    """Lower-case scheme and host, no fragment, no tracking parameters, stable parameter order."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"not an absolute http(s) URL: {url!r}")
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(query), ""))


def event_id(url: str) -> str:
    return "evt_" + hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()[:12]


def related_tickers(title: str) -> list[str]:
    """Tickers whose explicit alias appears as whole words in the source title."""
    found = []
    for ticker, aliases in COMPANY_ALIASES.items():
        if any(re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", title, re.I) for alias in aliases):
            found.append(ticker)
    return found


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _country_location(iso3: str) -> dict:
    c = COUNTRIES[iso3]
    return {"lat": c.lat, "lon": c.lon, "countryIso3": iso3, "placeName": c.en, "precision": "country"}


def _event(*, url: str, title: str, category: str, occurred: str, published: str | None, location: dict, origin: str,
           publisher: str, source_type: str, lang: str = "en") -> dict:
    title = " ".join(html.unescape(title).split())
    if not title:
        raise ValueError("empty title")
    date.fromisoformat(occurred)
    iso3 = location["countryIso3"]
    themes = list(POLICY_THEMES.get(iso3, ())) if category == "monetary_policy" else []
    return {
        "eventId": event_id(url), "title": title, "category": category, "occurredAt": occurred, "publishedAt": published,
        "location": location, "origin": origin,
        "sources": [{"publisher": publisher, "title": title, "url": url.strip(), "publishedAt": published,
                     "sourceType": source_type, "lang": lang}],
        "sourceCount": 1, "importance": 0.0, "relatedTickers": related_tickers(title), "relatedThemes": themes,
        "relatedCountries": [iso3] if iso3 else [],
    }


# Parsers (pure) -------------------------------------------------------------------------------


def parse_usgs(payload: bytes) -> tuple[list[dict], list[dict], int]:
    """USGS GeoJSON -> (events, hazards, rejected). Coordinates are the catalog's epicentre."""
    events, hazards, rejected = [], [], 0
    for feature in json.loads(payload).get("features", []):
        try:
            p = feature["properties"]
            lon, lat = float(feature["geometry"]["coordinates"][0]), float(feature["geometry"]["coordinates"][1])
            when = datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc)
            url, title = p["url"], p["title"]
            if not (-90 <= lat <= 90 and -180 <= lon <= 180) or p.get("type") != "earthquake":
                raise ValueError("unsupported feature")
            location = {"lat": lat, "lon": lon, "countryIso3": resolve_place_country(p.get("place")),
                        "placeName": p.get("place"), "precision": "point"}
            events.append(_event(url=url, title=title, category="natural_disaster", occurred=when.date().isoformat(),
                                 published=None, location=location, origin="usgs", publisher="U.S. Geological Survey",
                                 source_type="data"))
            hazards.append({"hazardId": f"usgs_{feature['id']}", "type": "earthquake", "occurredAt": _iso_datetime(when),
                            "lat": lat, "lon": lon, "magnitude": float(p["mag"]) if p.get("mag") is not None else None,
                            "title": " ".join(str(title).split()), "origin": "usgs", "sourceUrl": url})
        except (KeyError, TypeError, ValueError):
            rejected += 1
    return events, hazards, rejected


def _text(node, *names: str) -> str | None:
    for child in node:
        if child.tag.rsplit("}", 1)[-1] in names and child.text and child.text.strip():
            return child.text.strip()
    return None


def parse_feed(payload: bytes, *, publisher: str, iso3: str, default_category: str) -> tuple[list[dict], int]:
    """RSS 2.0 or RDF press-release feed of an official body -> (events, rejected).

    The event is placed at the issuing country's centroid with ``precision = "country"``.
    A title naming the policy/interest rate is ``monetary_policy``; otherwise ``default_category``.
    """
    root = ET.fromstring(payload.lstrip(b"\xef\xbb\xbf"))
    events, rejected = [], 0
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] != "item":
            continue
        try:
            title, link = _text(item, "title"), _text(item, "link")
            stamp = _text(item, "date", "pubDate")
            if not title or not link or not stamp:
                raise ValueError("missing field")
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                when = parsedate_to_datetime(stamp)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            category = "monetary_policy" if _POLICY_WORDS.search(title) else default_category
            events.append(_event(url=link, title=title, category=category, occurred=when.astimezone(timezone.utc).date().isoformat(),
                                 published=_iso_datetime(when), location=_country_location(iso3), origin="official",
                                 publisher=publisher, source_type="official"))
        except (ValueError, TypeError):
            rejected += 1
    return events, rejected


def parse_html_title(payload: bytes) -> str | None:
    match = re.search(rb"<title[^>]*>(.*?)</title>", payload, re.I | re.S)
    if not match:
        return None
    title = " ".join(html.unescape(match.group(1).decode("utf-8", "replace")).split())
    return title or None


def statcan_event(row: dict, page: bytes) -> dict:
    """One Statistics Canada release already listed in ``macro_release_dates`` (real release date)."""
    title = parse_html_title(page)
    if not title or "301 moved" in title.lower() or "not found" in title.lower():
        raise ValueError("no usable page title")
    title = re.sub(r"^The Daily\s*[—–-]\s*", "", title).strip()
    return _event(url=row["sourceUrl"], title=title, category="macro_release", occurred=row["publishedAt"],
                  published=None, location=_country_location("CAN"), origin="official", publisher="Statistics Canada",
                  source_type="official")


# Normalization --------------------------------------------------------------------------------


def merge_events(events: list[dict]) -> list[dict]:
    """Merge items sharing a canonical URL (same ``eventId``); never merge on a headline alone.

    The first item is the primary source and keeps the identity; other publishers are appended.
    ``sourceCount`` counts distinct publishers, not copies."""
    merged: dict[str, dict] = {}
    for ev in events:
        prior = merged.get(ev["eventId"])
        if prior is None:
            merged[ev["eventId"]] = json.loads(json.dumps(ev))
            continue
        seen = {(s["publisher"], canonical_url(s["url"])) for s in prior["sources"]}
        for src in ev["sources"]:
            key = (src["publisher"], canonical_url(src["url"]))
            if key not in seen:  # a syndicated copy from the same publisher is not a new source
                seen.add(key)
                prior["sources"].append(src)
        prior["relatedTickers"] = sorted(set(prior["relatedTickers"]) | set(ev["relatedTickers"]))
    out = list(merged.values())
    for ev in out:
        ev["sourceCount"] = len({s["publisher"] for s in ev["sources"]})
    return out


def importance(event: dict, build_date: date) -> float:
    """``M_EVENT_IMPORTANCE`` (world SPEC §4), fixed at dataset build time. Display priority only."""
    official = 1.0 if any(s["sourceType"] in ("official", "data", "filing") for s in event["sources"]) else 0.0
    age_days = (build_date - date.fromisoformat(event["occurredAt"])).days
    recency = max(0.0, 1.0 - max(age_days, 0) / 30.0)
    score = 0.45 * official + 0.35 * min(event["sourceCount"], 5) / 5.0 + 0.20 * recency
    return round(min(1.0, score), 6)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def build_bundle(events: list[dict], hazards: list[dict], sources: list[dict], *, built_at: datetime, start: str, end: str) -> dict[str, str]:
    """File name -> content of an immutable bundle. Deterministic for the same inputs and clock."""
    version = f"snap-{built_at.strftime('%Y%m%d')}-world"
    events = [e for e in merge_events(events) if start <= e["occurredAt"] <= end]
    for ev in events:
        ev["importance"] = importance(ev, built_at.date())
        ev["datasetId"], ev["dataVersion"] = "world_events", version
    events.sort(key=lambda e: (e["occurredAt"], e["eventId"]))
    by_id = {h["hazardId"]: h for h in hazards if start <= h["occurredAt"][:10] <= end}
    hazards = sorted(by_id.values(), key=lambda h: (h["occurredAt"], h["hazardId"]))
    files = {"events.json": dump(events), "hazards.json": dump(hazards)}

    def span(dates: list[str]) -> dict | None:
        return {"start": min(dates), "end": max(dates)} if dates else None

    manifest = {
        "worldVersion": version, "builtAt": _iso_datetime(built_at), "requestedWindow": {"start": start, "end": end},
        "files": {name: {"sha256": content_hash(text)} for name, text in files.items()},
        "events": {"count": len(events), "coverage": span([e["occurredAt"] for e in events]),
                   "byOrigin": _count(events, "origin"), "byCategory": _count(events, "category")},
        "hazards": {"count": len(hazards), "coverage": span([h["occurredAt"][:10] for h in hazards])},
        "sources": sources,
        "notIngested": [
            {"source": "GDELT", "reason": "Article index returned no usable batch on the build date and its items carry no "
                                          "source-supported event location; not loaded (O-07)."},
            {"source": "ECCC / EPA facility emissions", "reason": "Facility layer not loaded (cut-list item 2)."},
            {"source": "NASA FIRMS wildfires", "reason": "Requires a key; not loaded."},
        ],
        "method": {"importance": "min(1, 0.45*official + 0.35*min(distinctPublishers,5)/5 + 0.20*max(0, 1-ageDays/30)) at builtAt",
                   "eventId": "evt_ + first 12 hex of SHA-1 of the canonical source URL",
                   "trackingParamsRemoved": sorted(TRACKING_PARAMS)},
    }
    files["manifest.json"] = dump(manifest)
    return files


def _count(items: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        out[item[key]] = out.get(item[key], 0) + 1
    return dict(sorted(out.items()))


# Network (only used by the CLI) ---------------------------------------------------------------


def http_get(url: str, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https sources
        return response.read(20_000_000)


def collect(start: str, end: str, *, fetch: Callable[[str], bytes] = http_get, release_csv: Path | None = None,
            now: Callable[[], datetime] = lambda: datetime.now(timezone.utc), min_magnitude: float = 6.0,
            pause: float = 0.4, log: Callable[[str], None] = print) -> tuple[list[dict], list[dict], list[dict]]:
    events: list[dict] = []
    hazards: list[dict] = []
    sources: list[dict] = []

    def attempt(source_id: str, name: str, url: str, terms: str, handler) -> None:
        record = {"id": source_id, "name": name, "url": url, "terms": terms, "retrievedAt": _iso_datetime(now())}
        try:
            record.update(handler())
            record["status"] = "ok"
        except Exception as exc:  # a failed source is recorded, never replaced by invented rows
            record.update({"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}", "items": 0})
        log(f"{source_id}: {record['status']} ({record.get('items', 0)} item(s))")
        sources.append(record)

    usgs_url = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&eventtype=earthquake"
                f"&starttime={start}&endtime={end}T23:59:59&minmagnitude={min_magnitude}&orderby=time-asc")

    def usgs():
        found, haz, rejected = parse_usgs(fetch(usgs_url))
        events.extend(found)
        hazards.extend(haz)
        return {"items": len(found), "rejected": rejected, "filter": f"magnitude >= {min_magnitude}"}

    attempt("usgs_earthquakes", "USGS Earthquake Catalog (FDSN event service)", usgs_url,
            "U.S. Government work, public domain; https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits", usgs)

    for source_id, name, url, publisher, iso3, terms in (
        ("boc_press", "Bank of Canada press releases (RSS)", "https://www.bankofcanada.ca/content_type/press-releases/feed/",
         "Bank of Canada", "CAN", "https://www.bankofcanada.ca/terms/"),
        ("fed_monetary", "Federal Reserve Board monetary policy press releases (RSS)",
         "https://www.federalreserve.gov/feeds/press_monetary.xml", "Federal Reserve Board", "USA",
         "U.S. Government work; https://www.federalreserve.gov/disclaimer.htm"),
    ):
        def feed(url=url, publisher=publisher, iso3=iso3):
            found, rejected = parse_feed(fetch(url), publisher=publisher, iso3=iso3,
                                         default_category="monetary_policy" if iso3 == "USA" else "other")
            events.extend(found)
            return {"items": len(found), "rejected": rejected, "note": "feed lists recent releases only"}

        attempt(source_id, name, url, terms, feed)

    release_csv = release_csv or REPO_ROOT / "data" / "metadata" / "macro_release_dates.csv"

    def statcan():
        with open(release_csv, encoding="utf-8", newline="") as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("sourceUrl") and r.get("publishedAt")]
        kept = failed = 0
        for row in rows:
            if not start <= row["publishedAt"] <= end:
                continue
            try:
                events.append(statcan_event(row, fetch(row["sourceUrl"])))
                kept += 1
            except Exception:
                failed += 1
            time.sleep(pause)
        if kept == 0:
            raise RuntimeError(f"no release page could be read ({failed} failed)")
        return {"items": kept, "rejected": failed, "note": "release dates from data/metadata/macro_release_dates.csv (T04)"}

    attempt("statcan_daily", "Statistics Canada, The Daily (Consumer Price Index releases)",
            "https://www.statcan.gc.ca/dai-quo/index-eng.htm", "Statistics Canada Open Licence; https://www.statcan.gc.ca/en/terms-conditions/open-licence",
            statcan)
    return events, hazards, sources


def write_bundle(files: dict[str, str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        tmp = out_dir / (name + ".tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(out_dir / name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", required=True, help="first event date (ISO)")
    parser.add_argument("--end", required=True, help="last event date (ISO); use the price snapshot's data date")
    parser.add_argument("--out", type=Path, default=BUNDLE_DIR)
    parser.add_argument("--min-magnitude", type=float, default=6.0)
    args = parser.parse_args(argv)
    date.fromisoformat(args.start), date.fromisoformat(args.end)
    built_at = datetime.now(timezone.utc)
    events, hazards, sources = collect(args.start, args.end, min_magnitude=args.min_magnitude)
    if not events:
        print("No event could be ingested; the existing bundle is left unchanged.", file=sys.stderr)
        return 1
    files = build_bundle(events, hazards, sources, built_at=built_at, start=args.start, end=args.end)
    write_bundle(files, args.out)
    manifest = json.loads(files["manifest.json"])
    print(f"Wrote {manifest['events']['count']} event(s) and {manifest['hazards']['count']} hazard(s) to {args.out} "
          f"as {manifest['worldVersion']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
