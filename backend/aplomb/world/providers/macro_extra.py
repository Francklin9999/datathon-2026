"""Bounded Eurostat country emissions capture; no runtime requests.

Run: python -m aplomb.world.providers.macro_extra --directory PATH
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from .public import base
from .snapshot import publish, timestamp, validate_row
from .transport import Transport

DATASET_ID = "world_eurostat_ghg"
COUNTRIES = {"DE": "DEU", "ES": "ESP", "FR": "FRA", "IT": "ITA", "PL": "POL", "SE": "SWE"}
URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sdg_13_10?" + urlencode([
    ("lang", "en"), ("freq", "A"), ("src_crf", "TOTX4_MEMO"), ("unit", "T_HAB"),
    *(("geo", code) for code in COUNTRIES), ("sinceTimePeriod", "2018"),
])
METADATA = {
    "datasetId": DATASET_ID,
    "sourceIds": ["SRC-095"],
    "name": "Eurostat domestic greenhouse gas emissions per capita",
    "sourceUrl": URL,
    "licence": "European Union/Eurostat data; attribution required and modifications indicated; source EEA",
    "licenceUrl": "https://commission.europa.eu/legal-notice_en#copyright-notice",
    "frequency": "Annual, manual snapshot",
    "limitations": [
        "Selected six EU countries from 2018 onward, not all countries or full history.",
        "Annual national estimates exclude land use, land-use change, forestry and memo items; not facility emissions.",
        "Year start is a display anchor for the annual period, not an event or exact measurement time.",
        "Values may be revised; original historical availability is unknown and snapshots are gated at retrieval.",
        "No issuer, exposure or financial relationship is established.",
    ],
}


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if body.get("class") != "dataset" or body.get("source") != "ESTAT" or body.get("extension", {}).get("id") != "SDG_13_10":
        raise ValueError("Unexpected Eurostat dataset")
    ids, sizes = body.get("id"), body.get("size")
    if not isinstance(ids, list) or set(ids) != {"freq", "src_crf", "unit", "geo", "time"} or len(ids) != 5:
        raise ValueError("Unexpected JSON-stat dimensions")
    if not isinstance(sizes, list) or len(sizes) != len(ids) or any(type(n) is not int or n < 1 for n in sizes):
        raise ValueError("Invalid dimension sizes")
    if math.prod(sizes) > 600:
        raise ValueError("Eurostat response exceeds bounded scope")
    dimensions = {}
    labels = {}
    for dim, size in zip(ids, sizes, strict=True):
        category = body["dimension"][dim]["category"]
        index = category["index"]
        if (not isinstance(index, dict) or len(index) != size or
                any(type(i) is not int for i in index.values()) or set(index.values()) != set(range(size))):
            raise ValueError("Invalid JSON-stat category indices")
        dimensions[dim] = {position: code for code, position in index.items()}
        labels[dim] = category.get("label", {})
    for dim, expected in (("freq", {"A"}), ("src_crf", {"TOTX4_MEMO"}), ("unit", {"T_HAB"}),
                          ("geo", set(COUNTRIES))):
        if set(dimensions[dim].values()) != expected:
            raise ValueError(f"Unexpected {dim} categories")
    years = list(dimensions["time"].values())
    if any(not isinstance(year, str) or len(year) != 4 or not year.isascii() or not year.isdigit()
           or int(year) < 2018 or int(year) > timestamp(stamp).year for year in years):
        raise ValueError("Unexpected reference year")
    updated = timestamp(body["updated"])
    if updated > timestamp(stamp):
        raise ValueError("Dataset update is later than capture")
    values = body.get("value")
    status = body.get("status", {})
    if not isinstance(values, dict) or not isinstance(status, dict):
        raise ValueError("Unexpected JSON-stat values or statuses")
    rows, seen = [], set()
    for key, value in values.items():
        if not isinstance(key, str) or not key.isascii() or not key.isdigit() or str(int(key)) != key:
            raise ValueError("Invalid observation index")
        offset = int(key)
        if offset >= math.prod(sizes) or offset in seen:
            raise ValueError("Observation index outside dimensions")
        seen.add(offset)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Invalid emissions value")
        positions = {}
        for dim, size in reversed(list(zip(ids, sizes, strict=True))):
            offset, position = divmod(offset, size)
            positions[dim] = dimensions[dim][position]
        geo, year = positions["geo"], positions["time"]
        country_name = labels["geo"].get(geo)
        if not isinstance(country_name, str) or not country_name.strip():
            raise ValueError("Missing country label")
        flags = status.get(key)
        if flags is not None and not isinstance(flags, str):
            raise ValueError("Invalid Eurostat status flag")
        row = base(DATASET_ID, f"{geo}:{year}", "environment",
                   f"{country_name} annual greenhouse gas emissions, {year}: {value:g} tonnes CO₂ equivalent per capita",
                   URL, stamp, countryIso3=COUNTRIES[geo], observedAt=f"{year}-01-01", properties={
                       "countryCodeEurostat": geo, "year": year, "tonnesCo2EquivalentPerCapita": value,
                       "sector": "Total excluding LULUCF and memo items", "unit": "tonnes CO2 equivalent per capita",
                       "sourceStatus": flags, "datasetUpdatedAt": updated.isoformat(),
                       "geographicRole": "national_reporting_area", "temporalPrecision": "annual; January 1 is a display anchor",
                   })
        validate_row(row)
        rows.append(row)
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate country/year observation")
    return rows, {"sourceRows": len(values), "rejected": 0, "missingCells": math.prod(sizes) - len(values),
                  "coverageComplete": False,
                  "scope": "Selected six EU countries since 2018; annual domestic greenhouse gas emissions per capita excluding LULUCF and memo items."}


def collect(fetch, *, directory: Path, stamp: str | None = None) -> dict:
    payload = fetch(URL)
    if stamp is None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, stamp)
    return publish(directory, rows, {**METADATA, **quality, "retrievedAt": stamp}, [(URL, payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = collect(Transport(max_bytes=2_000_000), directory=args.directory)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "captured", "version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
