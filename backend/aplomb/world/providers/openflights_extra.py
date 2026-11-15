"""OpenFlights static airport reference for six countries; no aircraft movements.

The captured data and its normalized derivative are licensed separately under
ODbL 1.0 / DbCL 1.0. The application code is not part of this database.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, validate_row
from .transport import Transport

DATASET_ID = "world_openflights_airport_reference"
DATA_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
RIGHTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data.php"
LICENCE_URL = "https://opendatacommons.org/licenses/odbl/1-0/"
COUNTRIES = {
    "United Kingdom": "GBR", "France": "FRA", "Japan": "JPN",
    "Australia": "AUS", "South Africa": "ZAF", "United Arab Emirates": "ARE",
}
ATTRIBUTION = (
    "Contains information from OpenFlights, https://openflights.org/data.php, "
    "made available under the Open Database License (ODbL) 1.0. "
    "Individual database contents: Database Contents License (DbCL) 1.0. "
    "Adapted by Aplomb: selected six countries, airport facilities with IATA identifiers, "
    "validated coordinates and normalized fields. This derived database is ODbL 1.0."
)


def parse(payload: bytes, rights: bytes, stamp: str) -> tuple[list[dict], dict]:
    if (b"Open Database License" not in rights or b"Database Contents License" not in rights
            or b"https://opendatacommons.org/licenses/odbl/1-0/" not in rights):
        raise ValueError("OpenFlights database licence evidence is missing")
    records = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
    if not 1 <= len(records) <= 20000 or any(len(record) != 14 for record in records):
        raise ValueError("Unexpected OpenFlights airport schema or size")
    rows, seen, rejected, selected = [], set(), 0, 0
    for item in records:
        if item[3] not in COUNTRIES or item[12] != "airport" or item[4] == r"\N":
            continue
        selected += 1
        try:
            key, name, city, country, iata, icao = item[:6]
            if not key.isdecimal() or not name.strip() or not re.fullmatch("[A-Z0-9]{3}", iata):
                raise ValueError("Invalid airport identity")
            if key in seen:
                raise ValueError("Duplicate airport ID")
            lat, lon = float(item[6]), float(item[7])
            row = base(DATASET_ID, key, "aviation", f"{name} ({iata}) · static airport reference",
                       DATA_URL, stamp, latitude=lat, longitude=lon, countryIso3=COUNTRIES[country],
                       properties={
                           "airportId": key, "iata": iata, "icao": None if icao == r"\N" else icao,
                           "sourceCountry": country, "sourceCity": city,
                           "sourceRecordOrigin": item[13], "timezone": item[11],
                           "geographicRole": "airport_reference", "aircraftTracking": False,
                           "operationalStatus": None, "attribution": ATTRIBUTION,
                       })
            validate_row(row)
            seen.add(key)
            rows.append(row)
        except (ValueError, TypeError, OverflowError):
            rejected += 1
    if not rows:
        raise ValueError("No validated airport references")
    return rows, {
        "sourceRows": len(records), "selectedSourceRows": selected, "rejected": rejected,
        "coverageComplete": False,
        "scope": "Static airport references with IATA codes in GBR, FRA, JPN, AUS, ZAF and ARE; not global airport or aviation coverage.",
    }


def collect(directory: Path = DIRECTORY, fetch=None) -> dict:
    fetch = fetch or Transport(max_bytes=2_000_000)
    captures = [(url, fetch(url)) for url in (DATA_URL, RIGHTS_URL)]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(captures[0][1], captures[1][1], stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-217"],
        "name": "OpenFlights static airport reference · six-country sample",
        "sourceUrl": DATA_URL, "licence": "Derived database ODbL 1.0; individual contents DbCL 1.0",
        "licenceUrl": LICENCE_URL, "attribution": ATTRIBUTION,
        "frequency": "Sporadically updated static repository snapshot; manual capture",
        "limitations": [
            "Static airport reference only; no aircraft tracking, flight schedule, current operational status or traffic.",
            "Selected six countries and IATA-coded airport facilities; incomplete worldwide coverage.",
            "Coordinates and identifiers are provider reference values; country codes map exact source country labels.",
            "Source publication/update dates are unknown; capture time is first proven availability, excluded from earlier replay.",
            "No issuer, operating-company, security, portfolio exposure or financial-impact relationship is established.",
            ATTRIBUTION,
        ], **quality, "retrievedAt": stamp,
    }
    return publish(directory, rows, metadata, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    manifest = collect(parser.parse_args().directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
