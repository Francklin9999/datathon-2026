"""Bounded World Bank WDI SDMX 2.1 capture with indicator-specific reuse evidence.

Run: python -m aplomb.world.providers.sdmx_extra
IMF and OECD are not enabled: their current reuse terms could not be established.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, validate_row

DATASET_ID = "world_bank_sdmx_gdp_2024"
COUNTRIES = {"CAN": "Canada", "JPN": "Japan", "BRA": "Brazil"}
ROOT = "https://api.worldbank.org/v2/sdmx/rest/data/WDI/"
URLS = {country: ROOT + f"A.NY_GDP_MKTP_CD.{country}/?startperiod=2024&endPeriod=2024"
        for country in COUNTRIES}
RIGHTS_URL = "https://www.worldbank.org/ext/en/legal/terms-conditions/datasets"
METADATA_URL = "https://api.worldbank.org/v2/sources/2/series/NY.GDP.MKTP.CD/metadata?format=json"
ATTRIBUTION = (
    "Source: World Bank, World Development Indicators, NY.GDP.MKTP.CD, CC BY 4.0 "
    "with World Bank additional dataset terms. Underlying sources: national statistical "
    "organizations and central banks, OECD national accounts files, and World Bank staff estimates. "
    "Aplomb selected and normalized three annual observations; numerical values unchanged. "
    "No World Bank endorsement."
)
NS = {"m": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message",
      "g": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected SDMX capture redirect")


def fetch(url: str) -> bytes:
    if url not in {*URLS.values(), RIGHTS_URL, METADATA_URL}:
        raise ValueError("Unexpected SDMX capture URL")
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "AplombDatathon/1.0 (bounded anonymous SDMX capture)",
                "Accept": "application/xml,application/json,text/html",
            })
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=20) as response:
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, 300001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > 300000 or time.monotonic() - started > 20:
                        raise ValueError("SDMX payload exceeds byte or read-time cap")
                    chunks.append(chunk)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 1:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == 1:
                raise
        time.sleep(1)
    raise RuntimeError("SDMX retries exhausted")


def verify_rights(legal: bytes, metadata: bytes) -> dict[str, str]:
    if b"Creative Commons Attribution 4.0" not in legal or b"Exceptions for Some Third-Party Data" not in legal:
        raise ValueError("World Bank current dataset terms not verified")
    document = json.loads(metadata)
    if document.get("pages") != 1 or len(document.get("source", [])) != 1:
        raise ValueError("Incomplete World Bank series metadata")
    source = document["source"][0]
    if source["id"] != "2" or source["name"] != "World Development Indicators":
        raise ValueError("Unexpected World Bank metadata source")
    variables = source["concept"][0]["variable"]
    if len(variables) != 1 or variables[0]["id"] != "NY.GDP.MKTP.CD":
        raise ValueError("Unexpected licensed indicator")
    fields = {item["id"]: item["value"] for item in variables[0]["metatype"]}
    if fields.get("License_Type") != "CC BY-4.0" or fields.get("Unitofmeasure") != "current US$":
        raise ValueError("Indicator licence or unit differs from approved scope")
    return fields


def parse(payload: bytes, country: str, stamp: str) -> list[dict]:
    if country not in COUNTRIES or len(payload) > 300000:
        raise ValueError("Unexpected country or oversized XML")
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("XML declarations are not permitted")
    document = ET.fromstring(payload)
    if document.tag != f"{{{NS['m']}}}GenericData":
        raise ValueError("Expected SDMX 2.1 GenericData")
    sender = document.find("m:Header/m:Sender", NS)
    if sender is None or sender.get("id") != "WB" or document.findtext("m:Header/m:ID", namespaces=NS) != "WDI":
        raise ValueError("Unexpected SDMX source identity")
    datasets = document.findall("m:DataSet", NS)
    if len(datasets) != 1 or datasets[0].get("structureRef") != "WB_WDI_1_0":
        raise ValueError("Unexpected WDI data structure")
    series = datasets[0].findall("g:Series", NS)
    if len(series) != 1:
        raise ValueError("Expected one country/indicator series")
    dimensions = {node.get("id"): node.get("value") for node in series[0].findall("g:SeriesKey/g:Value", NS)}
    if dimensions != {"REF_AREA": country, "SERIES": "NY_GDP_MKTP_CD", "FREQ": "A"}:
        raise ValueError("WDI series dimensions differ from requested scope")
    points = series[0].findall("g:Obs", NS)
    if len(points) != 1:
        raise ValueError("Expected one bounded 2024 observation")
    point = points[0]
    period, value_node = point.find("g:ObsDimension", NS), point.find("g:ObsValue", NS)
    attrs = {node.get("id"): node.get("value") for node in point.findall("g:Attributes/g:Value", NS)}
    if period is None or period.get("value") != "2024" or attrs.get("UNIT_MULT") != "0":
        raise ValueError("Unexpected reference year or scaling")
    if value_node is None:
        raise ValueError("Missing WDI observation value")
    value = float(value_node.attrib["value"])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Invalid GDP value")
    row = base(DATASET_ID, f"{country}:2024", "macro",
               f"World Bank SDMX: {COUNTRIES[country]} 2024 GDP (current US$): {value:,.2f}",
               URLS[country], stamp, countryIso3=country, observedAt="2024-01-01",
               properties={
                   "indicator": "NY.GDP.MKTP.CD", "sdmxSeries": "NY_GDP_MKTP_CD",
                   "referenceYear": 2024, "value": value, "unit": "current US$",
                   "unitMultiplier": 0, "frequency": "annual",
                   "geographicRole": "national_statistical_area",
                   "temporalPrecision": "annual; first day is only a display anchor",
                   "attribution": ATTRIBUTION,
               })
    validate_row(row)
    return [row]


def collect(*, directory: Path = DIRECTORY, fetcher=fetch, stamp: str | None = None) -> dict:
    legal, metadata = fetcher(RIGHTS_URL), fetcher(METADATA_URL)
    fields = verify_rights(legal, metadata)
    captures = [(RIGHTS_URL, legal), (METADATA_URL, metadata)]
    for url in URLS.values():
        time.sleep(0.5)
        captures.append((url, fetcher(url)))
    stamp = stamp or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = [row for country, (_, payload) in zip(COUNTRIES, captures[2:], strict=True)
            for row in parse(payload, country, stamp)]
    return publish(directory, rows, {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-090"],
        "name": "World Bank SDMX 2024 GDP, three-country sample",
        "sourceUrl": ROOT, "licence": "CC BY 4.0 with World Bank additional dataset terms",
        "licenceUrl": RIGHTS_URL, "indicatorLicenceUrl": fields["License_URL"],
        "attribution": ATTRIBUTION, "retrievedAt": stamp, "frequency": "Annual; manual bounded capture",
        "sourceRows": len(rows), "rejected": 0, "coverageComplete": False,
        "scope": "Canada, Japan, Brazil; NY.GDP.MKTP.CD; calendar year 2024; current US dollars",
        "limitations": [
            "Three annual national observations only; incomplete World Bank SDMX country and series coverage.",
            "GDP at current prices in US dollars; not real growth, purchasing power parity or a forecast.",
            "National compilation methods can differ and annual estimates may be revised.",
            "Reference-year start is a display anchor; publication time is not supplied per observation.",
            "SDMX Prepared/Extracted timestamps are response generation times, not observation publication.",
            "Original vintage availability is unproven; historical replay is excluded before retrieval.",
            "National aggregates have no point coordinates, documented issuer links or modeled financial impact.",
            "World Bank CC BY 4.0 dataset terms include attribution, additional dispute terms and no endorsement.",
        ],
    }, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    try:
        manifest = collect(directory=args.directory)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "captured", "version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
