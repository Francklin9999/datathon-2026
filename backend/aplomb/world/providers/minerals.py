"""Bounded USGS Mineral Commodity Summaries 2026 country production capture."""
from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .snapshot import DIRECTORY, publish
from .transport import Transport

ITEM_URL = "https://www.sciencebase.gov/catalog/item/696a75d5d4be0228872d3bf8?format=json"
FILE_NAME = "MCS2026_Commodities_Data.csv"
DATASET_ID = "world_usgs_minerals"
CHAPTERS = {
    "LITHIUM", "COBALT", "COPPER", "RARE EARTHS", "NICKEL", "GRAPHITE (NATURAL)",
}
COUNTRIES = {
    "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT", "Brazil": "BRA",
    "Burma": "MMR", "Canada": "CAN", "Chile": "CHL", "China": "CHN",
    "Congo (Kinshasa)": "COD", "Cuba": "CUB", "Germany": "DEU",
    "Greenland": "GRL", "India": "IND", "Indonesia": "IDN", "Japan": "JPN",
    "Kazakhstan": "KAZ", "Korea, North": "PRK", "Korea, Republic of": "KOR",
    "Madagascar": "MDG", "Malaysia": "MYS", "Mali": "MLI", "Mexico": "MEX",
    "Mozambique": "MOZ", "New Caledonia": "NCL", "Nigeria": "NGA",
    "Norway": "NOR", "Papua New Guinea": "PNG", "Peru": "PER",
    "Philippines": "PHL", "Poland": "POL", "Portugal": "PRT",
    "Russia": "RUS", "South Africa": "ZAF", "Sri Lanka": "LKA",
    "Tanzania": "TZA", "Thailand": "THA", "Turkey": "TUR",
    "Ukraine": "UKR", "United States": "USA", "Vietnam": "VNM",
    "Zambia": "ZMB", "Zimbabwe": "ZWE",
}


def parse(item_payload: bytes, csv_payload: bytes, stamp: str) -> tuple[list[dict], dict, str]:
    item = json.loads(item_payload)
    if (item.get("id") != "696a75d5d4be0228872d3bf8"
            or item.get("title") != "Mineral Commodity Summaries 2026 Data Release"
            or "CC0-1.0" not in item.get("rights", "")):
        raise ValueError("Unexpected USGS item metadata or rights")
    files = [f for f in item["files"] if f.get("name") == FILE_NAME]
    if len(files) != 1:
        raise ValueError("USGS commodity CSV missing or ambiguous")
    file_url = files[0]["downloadUri"]
    parsed = urlsplit(file_url)
    if parsed.scheme != "https" or parsed.hostname != "www.sciencebase.gov" or parsed.username or parsed.port:
        raise ValueError("Unexpected USGS CSV host")
    if len(csv_payload) != files[0]["size"]:
        raise ValueError("Incomplete USGS CSV")
    reader = csv.DictReader(io.StringIO(csv_payload.decode("cp1252")))
    expected = {
        "MCS chapter", "Section", "Commodity", "Country", "Statistics",
        "Statistics_detail", "Unit", "Year", "Value", "Notes",
    }
    if not expected.issubset(reader.fieldnames or ()):
        raise ValueError("USGS CSV schema changed")
    rows, selected, rejected, unknown = [], 0, 0, set()
    for record in reader:
        if (record["MCS chapter"] not in CHAPTERS
                or not record["Section"].startswith("World Mine")
                or record["Statistics"] != "Production"
                or record["Statistics_detail"] != "Mine production"
                or record["Year"] != "2025"):
            continue
        selected += 1
        country = record["Country"]
        if country == "Other countries":
            rejected += 1
            continue
        iso3 = COUNTRIES.get(country)
        if iso3 is None:
            unknown.add(country)
            rejected += 1
            continue
        unit = record["Unit"]
        if unit not in {"metric tons", "thousand metric tons"}:
            raise ValueError("Unexpected USGS production unit")
        raw = record["Value"].strip().replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            rejected += 1
            continue
        if not 0 <= value < 1_000_000_000:
            raise ValueError("Invalid USGS production value")
        chapter = record["MCS chapter"]
        rows.append({
            "id": f"{DATASET_ID}:{chapter}:{iso3}:2025",
            "sourceId": DATASET_ID, "category": "energy",
            "title": f"{chapter.title()} mine production, {country}, 2025",
            "sourceUrl": ITEM_URL, "retrievedAt": stamp, "availableAt": stamp,
            "observedAt": None, "publishedAt": None,
            "latitude": None, "longitude": None, "countryIso3": iso3,
            "properties": {
                "commodity": chapter, "country": country, "referenceYear": 2025,
                "sourcePublicationDate": "2026-02-06",
                "value": value, "unit": unit, "sourceValue": record["Value"],
                "notes": record["Notes"] or None, "geographicRole": "country",
                "mineLocation": None, "securityRelationship": None,
            },
        })
    if selected < 70 or len(rows) < 50 or unknown:
        raise ValueError(f"Incomplete USGS sample or unmapped countries: {sorted(unknown)}")
    return rows, {
        "sourceRows": selected, "rejected": rejected, "coverageComplete": False,
        "scope": "Six selected minerals, numeric 2025 country mine-production rows only; "
                 "withheld, missing, aggregate and nonnumeric values excluded; no mine locations.",
    }, file_url


def collect(directory: Path = DIRECTORY, fetch=None) -> dict:
    fetch = fetch or Transport(max_bytes=5_000_000)
    item_payload = fetch(ITEM_URL)
    item = json.loads(item_payload)
    files = [f for f in item.get("files", []) if f.get("name") == FILE_NAME]
    if len(files) != 1:
        raise ValueError("USGS commodity CSV missing or ambiguous")
    csv_url = files[0]["downloadUri"]
    parsed = urlsplit(csv_url)
    if parsed.scheme != "https" or parsed.hostname != "www.sciencebase.gov" or parsed.username or parsed.port:
        raise ValueError("Unexpected USGS CSV host")
    csv_payload = fetch(csv_url)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality, file_url = parse(item_payload, csv_payload, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-199", "MASTER-086"],
        "name": "USGS Mineral Commodity Summaries 2026 Data Release",
        "sourceUrl": ITEM_URL,
        "licence": "CC0 1.0 public domain dedication; USGS attribution provided",
        "licenceUrl": "https://creativecommons.org/publicdomain/zero/1.0/",
        "frequency": "2026 publication, 2025 annual estimates; manual capture",
        "limitations": [
            "Six selected minerals and numeric country production rows only; not the full USGS release.",
            "Country totals are not mine locations, company output or issuer exposures.",
            "Withheld, missing and other-country aggregate values are excluded, not treated as zero.",
            "USGS estimates can be revised; original historical CSV vintages were not captured.",
        ],
        **quality, "retrievedAt": stamp,
    }
    return publish(directory, rows, metadata, [(ITEM_URL, item_payload), (file_url, csv_payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    result = collect(args.directory)
    print(json.dumps({"version": result["dataVersion"], "rows": result["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
