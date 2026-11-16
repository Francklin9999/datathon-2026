"""Bounded World Bank Worldwide Governance Indicators country-year capture."""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import publish, validate_row
from .transport import Transport

DATASET_ID = "world_wgi_political_stability_2024"
INDICATOR = "GOV_WGI_PV.SC"
SOURCE_URL = "https://api.worldbank.org/v2/source/3?format=json"
INDICATOR_URL = f"https://api.worldbank.org/v2/indicator/{INDICATOR}?format=json"
DATA_URL = (f"https://api.worldbank.org/v2/country/all/indicator/{INDICATOR}"
            "?format=json&date=2024&per_page=400&source=3")
LICENCE_URL = "https://datacatalog.worldbank.org/public-licenses"
URLS = (SOURCE_URL, INDICATOR_URL, DATA_URL, LICENCE_URL)


def _api(payload: bytes) -> tuple[dict, list]:
    body = json.loads(payload)
    if not isinstance(body, list) or len(body) != 2 or not isinstance(body[0], dict) or not isinstance(body[1], list):
        raise ValueError("Invalid World Bank API page")
    head, items = body
    if head.get("pages") not in (1, "1") or int(head.get("total", -1)) != len(items):
        raise ValueError("Incomplete World Bank API page")
    return head, items


def parse(source: bytes, indicator: bytes, data: bytes, licence: bytes, stamp: str) -> tuple[list[dict], dict]:
    _, sources = _api(source)
    _, indicators = _api(indicator)
    data_head, values = _api(data)
    if (len(sources) != 1 or sources[0].get("id") != "3" or sources[0].get("code") != "WGI"
            or len(indicators) != 1 or indicators[0].get("id") != INDICATOR
            or indicators[0].get("source", {}).get("id") != "3"
            or data_head.get("sourceid") != "3" or len(values) > 400):
        raise ValueError("Unexpected WGI source or indicator")
    if (b"default license for all Datasets produced by the World Bank" not in licence
            or b"Creative Commons Attribution 4.0" not in licence):
        raise ValueError("World Bank open data licence evidence missing")
    rows, seen, rejected = [], set(), 0
    for item in values:
        code, value = item.get("countryiso3code"), item.get("value")
        if not re.fullmatch(r"[A-Z]{3}", code or "") or isinstance(value, bool) or not isinstance(value, (int, float)):
            rejected += 1
            continue
        if (not math.isfinite(value) or not 0 <= value <= 100 or code in seen
                or item.get("date") != "2024" or item.get("indicator", {}).get("id") != INDICATOR):
            raise ValueError("Invalid WGI country score")
        seen.add(code)
        country = item["country"]["value"]
        row = base(DATASET_ID, f"{code}:2024", "macro",
                   f"{country} political stability governance score, 2024: {value:.1f} / 100",
                   DATA_URL, stamp, countryIso3=code, observedAt="2024-01-01", properties={
                       "attribution": "Source: World Bank, Worldwide Governance Indicators; adapted by Aplomb.",
                       "indicatorId": INDICATOR, "referenceYear": 2024, "score": value,
                       "unit": "governance score, 0-100", "sourceCountry": country,
                       "sourceLastUpdated": data_head.get("lastupdated"),
                       "temporalPrecision": "year; January 1 is a display anchor, not an observation date",
                       "geographicRole": "national_reporting_area",
                   })
        validate_row(row)
        rows.append(row)
    if len(rows) < 190:
        raise ValueError("Unexpectedly sparse WGI country coverage")
    return rows, {"sourceRows": len(values), "rejected": rejected, "coverageComplete": False,
                  "scope": "2024 political stability governance score for countries/territories with source ISO3 and numeric value; single WGI indicator and year.",
                  "sourceLastUpdated": data_head.get("lastupdated")}


def collect(directory: Path, fetch=None) -> dict:
    fetch = fetch or Transport(max_bytes=2_000_000)
    captures = [(url, fetch(url)) for url in URLS]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(*(payload for _, payload in captures), stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-147"],
        "name": "World Bank WGI political stability governance score, 2024",
        "sourceUrl": DATA_URL, "attribution": "Source: World Bank, Worldwide Governance Indicators; adapted by Aplomb.",
        "licence": "World Bank-produced open data default CC BY 4.0; attribution and modifications disclosed",
        "licenceUrl": LICENCE_URL, "frequency": "Annual reference year; manual capture",
        "limitations": [
            "One 2024 political stability score indicator, not the complete WGI source or a current stability event.",
            "Governance scores are composite estimates derived from source surveys and assessments; they are not observed incidents or a financial risk model.",
            "World Bank source update date is not an original historical publication vintage; capture-time availability gate applies.",
            "Country/territory reporting area only; no point, issuer, security or portfolio relationship is established.",
        ], **quality, "retrievedAt": stamp,
    }
    return publish(directory, rows, metadata, captures)


def main() -> int:
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--directory", type=Path, required=True)
    m = collect(p.parse_args().directory)
    print(json.dumps({"version": m["dataVersion"], "rows": m["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
