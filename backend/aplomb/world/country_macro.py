"""World Bank WDI annual indicators: bounded capture and immutable country snapshot.

WDI may revise annual observations. The provider does not supply publication timestamps per
row, so the first moment this application can establish availability is capture time. These
records are explicitly current-only, not historical vintages. The World Bank datasets page
identifies WDI as CC BY 4.0; terms include attribution and provider-specific exceptions.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": ("GDP growth (annual %)", "Croissance du PIB (% annuel)", "pct"),
    "FP.CPI.TOTL.ZG": ("Consumer price inflation (annual %)", "Inflation des prix à la consommation (% annuel)", "pct"),
    "SP.POP.TOTL": ("Population, total", "Population totale", "count"),
    "NY.GDP.MKTP.CD": ("GDP (current US dollars)", "PIB (dollars américains courants)", "usd"),
}
SOURCE_ID = "world_bank_indicators"
TERMS_URL = "https://datacatalog.worldbank.org/public-licenses"
CATALOG_URL = "https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators"
API_DOC_URL = "https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures"


def parse_countries(payload: bytes) -> set[str]:
    """Accept World Bank country/territory IDs; discard aggregate geographic groups."""
    body = json.loads(payload)
    if not isinstance(body, list) or len(body) != 2 or not isinstance(body[0], dict) or not isinstance(body[1], list):
        raise ValueError("Malformed World Bank country catalog")
    meta, entries = body
    if meta.get("page") != 1 or meta.get("pages") != 1 or meta.get("total") != len(entries):
        raise ValueError("Incomplete World Bank country catalog")
    countries = set()
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("Malformed country row")
        region, code = row.get("region"), row.get("id")
        if not isinstance(region, dict) or not isinstance(code, str):
            raise ValueError("Missing country region or identifier")
        if region.get("id") != "NA" and re.fullmatch(r"[A-Z]{3}", code):
            countries.add(code)
    if not countries:
        raise ValueError("No usable countries")
    return countries


def parse_indicator(payload: bytes, indicator: str, *, retrieved_at: datetime, countries: set[str]) -> tuple[list[dict], dict]:
    """Validate one WDI API page; emit latest completed-year observation per provider country ID.

    The query requests two latest nonempty years; current/future years and aggregate regions
    are omitted. This is deliberately not a full historical series or a securities resolver.
    """
    if indicator not in INDICATORS or retrieved_at.tzinfo is None or not countries:
        raise ValueError("Invalid WDI indicator or naive retrieval timestamp")
    body = json.loads(payload)
    if not isinstance(body, list) or len(body) != 2 or not isinstance(body[0], dict) or not isinstance(body[1], list):
        raise ValueError("Malformed World Bank API response")
    metadata, entries = body
    if metadata.get("page") != 1 or metadata.get("pages") != 1:
        raise ValueError("World Bank response incomplete or paginated")
    if metadata.get("total") != len(entries):
        raise ValueError("World Bank response row count mismatch")
    last_updated = metadata.get("lastupdated")
    if last_updated is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(last_updated)):
        raise ValueError("Invalid source update date")
    stamp = retrieved_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    chosen = {}
    rejected = 0
    for row in entries:
        try:
            if not isinstance(row, dict) or row["indicator"]["id"] != indicator:
                raise ValueError("Wrong indicator")
            iso3, year, value = row["countryiso3code"], row["date"], row["value"]
            if iso3 not in countries:  # excludes World Bank regional/income aggregates
                continue
            if not isinstance(year, str) or not re.fullmatch(r"\d{4}", year) or int(year) >= retrieved_at.year:
                raise ValueError("Invalid or incomplete calendar year")
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Invalid observation")
            if indicator in {"SP.POP.TOTL", "NY.GDP.MKTP.CD"} and value < 0:
                raise ValueError("Negative population or GDP")
            candidate = {"countryIso3": iso3, "indicatorId": indicator, "value": value,
                         "observationYear": int(year), "observedAt": f"{year}-12-31",
                         "publishedAt": None, "availableAt": stamp, "retrievedAt": stamp}
            previous = chosen.get(iso3)
            if previous is None or candidate["observationYear"] > previous["observationYear"]:
                chosen[iso3] = candidate
            elif candidate["observationYear"] == previous["observationYear"] and candidate["value"] != previous["value"]:
                raise ValueError("Conflicting duplicates")
        except (KeyError, TypeError, ValueError):
            rejected += 1
    return sorted(chosen.values(), key=lambda x: x["countryIso3"]), {
        "indicatorId": indicator, "lastUpdated": last_updated, "sourceRows": len(entries),
        "accepted": len(chosen), "rejected": rejected,
        "contentSha256": hashlib.sha256(payload).hexdigest(), "retrievedAt": stamp,
    }


def collect_indicators(fetch: Callable[[str], bytes], *, retrieved_at: datetime) -> tuple[list[dict], dict]:
    """Collect fixed indicators. A missing/invalid response aborts the snapshot, preserving old data."""
    rows, sources = [], []
    country_url = "https://api.worldbank.org/v2/country?format=json&per_page=1000"
    country_payload = fetch(country_url)
    countries = parse_countries(country_payload)
    sources.append({"indicatorId": "country_catalog", "url": country_url,
                    "contentSha256": hashlib.sha256(country_payload).hexdigest(),
                    "accepted": len(countries),
                    "retrievedAt": retrieved_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    for indicator in INDICATORS:
        url = f"https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&mrnev=2&per_page=1000"
        parsed, meta = parse_indicator(fetch(url), indicator, retrieved_at=retrieved_at, countries=countries)
        if not parsed:
            raise ValueError(f"No usable observations for {indicator}")
        rows.extend(parsed)
        sources.append({**meta, "url": url})
    return sorted(rows, key=lambda r: (r["countryIso3"], r["indicatorId"])), {
        "sources": sources, "retrievedAt": retrieved_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datasetId": SOURCE_ID, "licence": "World Bank WDI, CC BY 4.0 with additional terms; third-party rights may apply",
        "licenceUrl": TERMS_URL, "catalogUrl": CATALOG_URL, "apiDocUrl": API_DOC_URL,
    }


def serialize_snapshot(rows: list[dict], metadata: dict) -> tuple[str, str]:
    """Canonical data + manifest, with content-addressed version and SHA-256."""
    if not rows:
        raise ValueError("Refusing to publish empty WDI snapshot")
    text = json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    digest = hashlib.sha256(text.encode()).hexdigest()
    stamp = metadata["retrievedAt"]
    version = "snap-" + stamp[:10].replace("-", "") + "-wdi-" + digest[:12]
    years = [r["observationYear"] for r in rows]
    manifest = {**metadata, "dataVersion": version, "sha256": digest, "rowCount": len(rows),
                "countryCount": len({r["countryIso3"] for r in rows}),
                "coverage": {"start": f"{min(years)}-01-01", "end": f"{max(years)}-12-31"},
                "availabilityRule": "Observed year is not publication date. Original availability is unknown; retrievedAt is the earliest proven availability. No historical replay."}
    return text, json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def load_snapshot(directory: Path) -> tuple[tuple[dict, ...], dict | None]:
    """Verify payload hash and counts. No sidecar means unavailable, not an empty dataset."""
    data, meta = directory / "country_macro.json", directory / "country_macro_manifest.json"
    if not data.exists() and not meta.exists():
        return (), None
    if not data.exists() or not meta.exists():
        raise ValueError("Incomplete World Bank country snapshot")
    content = data.read_bytes()
    manifest = json.loads(meta.read_text(encoding="utf-8"))
    if hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest() != manifest["sha256"]:
        raise ValueError("World Bank snapshot checksum mismatch")
    rows = json.loads(content)
    if not isinstance(rows, list) or len(rows) != manifest["rowCount"]:
        raise ValueError("World Bank snapshot count mismatch")
    return tuple(rows), manifest
