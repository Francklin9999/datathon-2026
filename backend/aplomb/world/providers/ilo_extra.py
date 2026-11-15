"""Bounded anonymous ILOSTAT country unemployment capture, with saved CC BY terms.

Acquisition uses ILO's official CSV API; this does not claim SDMX transport coverage.
Run: python -m aplomb.world.providers.ilo_extra
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, validate_row

DATASET_ID = "world_ilo_unemployment_2024"
COUNTRIES = {"CAN": "Canada", "JPN": "Japan", "BRA": "Brazil"}
INDICATOR = "UNE_DEAP_SEX_AGE_RT"
ROOT = "https://rplumber.ilo.org/data/indicator/"
URLS = {country: ROOT + "?id=UNE_DEAP_SEX_AGE_RT_A&ref_area=" + country
        + "&sex=SEX_T&classif1=AGE_YTHADULT_YGE15&timefrom=2024&timeto=2024"
        for country in COUNTRIES}
RIGHTS_URL = "https://www.ilo.org/rights-and-permissions"
ATTRIBUTION = (
    "Source: International Labour Organization (ILO), ILOSTAT. CC BY 4.0. "
    "Selected 2024 national unemployment observations normalized by Aplomb. "
    "This is an adaptation of a copyrighted work of the International Labour Organization (ILO). "
    "This adaptation has not been prepared, reviewed or endorsed by the ILO and should not be "
    "considered an official ILO adaptation. The ILO disclaims all responsibility for its content "
    "and accuracy. Responsibility rests solely with Aplomb."
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected ILO capture redirect")


def fetch(url: str) -> bytes:
    if url not in {*URLS.values(), RIGHTS_URL}:
        raise ValueError("Unexpected ILO capture URL")
    opener = urllib.request.build_opener(_NoRedirect())
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "AplombDatathon/1.0",
                "Accept": "application/json,text/csv,text/html",
            })
            with opener.open(request, timeout=20) as response:
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, 250001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > 250000:
                        raise ValueError("ILO capture exceeds byte cap")
                    if time.monotonic() - started > 20:
                        raise TimeoutError("ILO read deadline exceeded")
                    chunks.append(chunk)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 1:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == 1:
                raise
        time.sleep(1)
    raise RuntimeError("ILO retries exhausted")


def parse(payload: bytes, country: str, stamp: str) -> list[dict]:
    if country not in COUNTRIES:
        raise ValueError("Unexpected ILO country")
    points = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    if len(points) != 1:
        raise ValueError("Expected exactly one annual country unemployment observation")
    point = points[0]
    expected = {"ref_area": country, "indicator": INDICATOR, "sex": "SEX_T",
                "classif1": "AGE_YTHADULT_YGE15", "time": "2024"}
    if any(point.get(key) != value for key, value in expected.items()):
        raise ValueError("ILO observation dimensions do not match the requested series")
    value = float(point["obs_value"])
    if not math.isfinite(value) or not 0 <= value <= 100 or not point.get("source"):
        raise ValueError("Invalid ILO unemployment value or source identity")
    if datetime.fromisoformat(stamp.replace("Z", "+00:00")).year <= 2024:
        raise ValueError("Reference year is not complete")
    row = base(DATASET_ID, country + ":2024", "macro",
               f"{COUNTRIES[country]} 2024 unemployment rate, age 15+: {value:g}%",
               URLS[country], stamp, countryIso3=country, observedAt="2024-01-01",
               properties={
                   "sourceCountry": COUNTRIES[country], "indicator": INDICATOR,
                   "referenceYear": 2024, "unemploymentRate": value, "unit": "percent",
                   "sex": "total", "age": "15 years and over",
                   "sourceSurveyCode": point["source"], "observationStatus": point.get("obs_status"),
                   "noteClassif": point.get("note_classif"), "noteIndicator": point.get("note_indicator"),
                   "noteSource": point.get("note_source"), "attribution": ATTRIBUTION,
                   "temporalPrecision": "annual; first day is only a display anchor",
                   "geographicRole": "national_statistical_area",
               })
    validate_row(row)
    return [row]


def collect(*, directory: Path = DIRECTORY, fetcher=fetch, stamp: str | None = None) -> dict:
    legal = fetcher(RIGHTS_URL)
    if (b"databases and datasets together with the accompanying referential metadata" not in legal
            or b"CC BY 4.0" not in legal or b"3 May 2023" not in legal):
        raise ValueError("ILO dataset-specific open licence could not be verified")
    captures = [(RIGHTS_URL, legal)]
    for url in URLS.values():
        time.sleep(0.5)
        captures.append((url, fetcher(url)))
    stamp = stamp or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = [row for country, (_, payload) in zip(COUNTRIES, captures[1:], strict=True)
            for row in parse(payload, country, stamp)]
    return publish(directory, rows, {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-108"],
        "name": "ILOSTAT 2024 national unemployment rates, three-country sample",
        "sourceUrl": ROOT, "licence": "CC BY 4.0; ILO datasets published after 3 May 2023",
        "licenceUrl": RIGHTS_URL, "attribution": ATTRIBUTION,
        "frequency": "Annual observations; manual bounded fixed-year capture",
        "retrievedAt": stamp, "sourceRows": len(rows), "rejected": 0,
        "coverageComplete": False, "scope": "Canada, Japan, Brazil; 2024; total sex; ages 15+",
        "limitations": [
            "Three national annual observations only; no complete ILO or current labor-market coverage.",
            "Official ILOSTAT CSV API acquisition; SDMX transport integration is not established.",
            "Source survey codes and notes are retained; national survey methods need not be identical.",
            "Percent unemployed among the labor force, not a share of the entire population.",
            "Annual first-day display anchors are not exact observation or publication dates.",
            "2024 completed-year statistical values necessarily became available after the ILO open-data policy began.",
            "Original vintage availability is unproven; historical replay is excluded before retrieval.",
            "National statistical areas have no point coordinates, issuer linkage or modeled financial impact.",
        ],
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
