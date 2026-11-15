"""Capture fixed WITS fuel-export and UNCTAD concentration samples.

Run from the repository root: PYTHONPATH=backend python -m aplomb.world.providers.trade_followon
WITS identifies the underlying source as UN Comtrade; its redistribution rules apply.
The UNCTAD capture requires the 7z executable.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .snapshot import DIRECTORY, publish

DATASET_ID = "trade_wits_fuel_exports"
URL = ("https://wits.worldbank.org/API/V1/SDMX/V21/datasource/tradestats-trade/"
       "reporter/can/year/2023/partner/wld/product/fuels/indicator/XPRT-TRD-VL?format=JSON")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected provider redirect")


def fetch() -> bytes:
    parsed = urlsplit(URL)
    if parsed.scheme != "https" or parsed.hostname != "wits.worldbank.org":
        raise ValueError("Unexpected WITS endpoint")
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (Aplomb bounded public research ingestion)",
        "Accept": "application/json",
    })
    for attempt in range(3):
        try:
            with opener.open(request, timeout=25) as response:
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, 2_000_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError("WITS response exceeds byte cap")
                    if time.monotonic() - started > 25:
                        raise TimeoutError("WITS total read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("WITS retry exhausted")


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if body["header"]["id"] != "DF_WITS_TradeStats_Trade" or body["header"]["sender"]["id"] != "WBG_WITS":
        raise ValueError("Unexpected WITS dataset")
    structure = body["structure"]
    dimensions = structure["dimensions"]
    expected = [("FREQ", "A"), ("REPORTER", "CAN"), ("PARTNER", "WLD"),
                ("PRODUCTCODE", "Fuels"), ("INDICATOR", "XPRT-TRD-VL")]
    if dimensions["dataset"] or len(dimensions["series"]) != len(expected):
        raise ValueError("Unexpected WITS dimensions")
    for index, (dimension, (key, value)) in enumerate(zip(dimensions["series"], expected)):
        if (dimension["id"] != key or dimension["keyPosition"] != index
                or len(dimension["values"]) != 1 or dimension["values"][0]["id"] != value):
            raise ValueError("Unexpected WITS series dimension")
    times = dimensions["observation"]
    if (len(times) != 1 or times[0]["id"] != "TIME_PERIOD" or len(times[0]["values"]) != 1
            or times[0]["values"][0]["id"] != "2023"):
        raise ValueError("Unexpected WITS year")
    attributes = structure["attributes"]
    if (attributes["dataset"] or attributes["series"] or len(attributes["observation"]) != 1
            or attributes["observation"][0]["id"] != "DATASOURCE"
            or [x["id"] for x in attributes["observation"][0]["values"]] != ["WITS-CMT"]):
        raise ValueError("Unexpected WITS underlying source")
    datasets = body["dataSets"]
    if len(datasets) != 1 or datasets[0]["action"] != "Information":
        raise ValueError("Unexpected WITS data set count")
    series = datasets[0]["series"]
    if set(series) != {"0:0:0:0:0"} or set(series["0:0:0:0:0"]["observations"]) != {"0"}:
        raise ValueError("Missing or unexpected WITS observation")
    observation = series["0:0:0:0:0"]["observations"]["0"]
    value = observation[0]
    if (len(observation) != 2 or observation[1] != 0 or isinstance(value, bool)
            or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
        raise ValueError("Invalid WITS observation")
    row = {
        "id": f"{DATASET_ID}:CAN:2023:WLD:Fuels:XPRT-TRD-VL", "sourceId": DATASET_ID,
        "category": "trade", "title": "Canada fuel exports to the world, 2023",
        "sourceUrl": URL, "retrievedAt": stamp, "availableAt": stamp,
        "observedAt": None, "publishedAt": None, "latitude": None, "longitude": None,
        "countryIso3": "CAN", "properties": {
            "reporterName": "Canada", "referenceYear": 2023, "temporalPrecision": "year",
            "partnerCode": "WLD", "partnerName": "World", "productCode": "Fuels",
            "indicatorCode": "XPRT-TRD-VL", "valueUsdThousands": value,
            "underlyingSource": "WITS - UNSD Comtrade", "geographicRole": "reporting_country",
            "securityRelationship": None,
        },
    }
    return [row], {"sourceRows": 1, "rejected": 0, "coverageComplete": False,
                   "scope": "2023 Canada fuel exports to World only; no geographic point or company link."}


def collect(directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    payload = fetcher()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-113"],
        "name": "WITS Canada annual fuel exports sample", "sourceUrl": URL,
        "licence": "WITS identifies UNSD Comtrade as underlying source; UN Comtrade reuse and "
                   "redistribution rules apply. Attribute WITS and Source: UN Comtrade.",
        "licenceUrl": "https://uncomtrade.org/docs/re-dissemination-of-data/",
        "frequency": "fixed annual 2023 sample; manual capture",
        "limitations": [
            "One reporter, year, partner and product group only; no global coverage is implied.",
            "WITS value is in US dollars thousand; underlying UN Comtrade data may be revised.",
            "Source publication date is unavailable; historical availability is not inferred.",
            "Country-level record has no source coordinates and is not port or issuer exposure.",
            "UN Comtrade commercial APIs and streaming require a distribution arrangement.",
        ], **quality, "retrievedAt": stamp,
    }
    return publish(directory, rows, metadata, [(URL, payload)])


UNCTAD_ID = "trade_unctad_concentration"
UNCTAD_META = "https://unctadstat-api.unctad.org/api/reportMetadata/US.ConcentStructIndices"
UNCTAD_BULK = "https://unctadstat-api.unctad.org/bulkdownload/US.ConcentStructIndices/US_ConcentStructIndices"


def fetch_unctad(url: str) -> bytes:
    if url not in {UNCTAD_META, UNCTAD_BULK}:
        raise ValueError("Unexpected UNCTAD endpoint")
    opener = urllib.request.build_opener(_NoRedirect())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Aplomb research ingestion)"})
    with opener.open(req, timeout=25) as response:
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("UNCTAD response exceeds byte cap")
        return data


def unpack_unctad(payload: bytes) -> str:
    # Validate archive members and advertised size before extracting a single known CSV.
    with tempfile.TemporaryDirectory() as folder:
        archive = Path(folder) / "source.7z"
        archive.write_bytes(payload)
        listing = subprocess.run(["7z", "l", "-slt", str(archive)], check=True,
                                 capture_output=True, text=True, timeout=25).stdout
        member_section = listing.split("----------\n", 1)
        if len(member_section) != 2:
            raise ValueError("Unexpected UNCTAD archive listing")
        paths = re.findall(r"^Path = (.+)$", member_section[1], re.MULTILINE)
        sizes = re.findall(r"^Size = (\d+)$", member_section[1], re.MULTILINE)
        if paths != ["US_ConcentStructIndices.csv"] or len(sizes) != 1 or int(sizes[0]) > 5_000_000:
            raise ValueError("Unexpected UNCTAD archive contents")
        data = subprocess.run(["7z", "e", "-so", str(archive)], check=True,
                              capture_output=True, timeout=25).stdout
        if len(data) != int(sizes[0]):
            raise ValueError("Incomplete UNCTAD extraction")
        return data.decode("utf-8-sig")


def collect_unctad(directory: Path = DIRECTORY) -> dict:
    metadata_payload = fetch_unctad(UNCTAD_META)
    metadata = json.loads(metadata_payload)
    if (metadata["name"] != "US.ConcentStructIndices"
            or "Market concentration and structural change indices" not in metadata["title"]):
        raise ValueError("Unexpected UNCTAD dataset")
    payload = fetch_unctad(UNCTAD_BULK)
    text = unpack_unctad(payload)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    products = {"TOTAL": "TOTAL ALL PRODUCTS", "A04": "Fuels (SITC 3)"}
    rows, source_rows = [], 0
    for item in csv.DictReader(io.StringIO(text)):
        source_rows += 1
        code = item["Product"]
        if item["Year"] != "2025" or item["Flow"] != "02" or code not in products:
            continue
        if (item["Flow Label"] != "Exports" or item["Product Label"] != products[code]
                or item["Concentration Index Footnote"] or item["Concentration Index Missing value"]):
            raise ValueError("Unexpected UNCTAD record flags or dimensions")
        value = float(item["Concentration Index"])
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid UNCTAD concentration index")
        rows.append({
            "id": f"{UNCTAD_ID}:2025:02:{code}", "sourceId": UNCTAD_ID, "category": "trade",
            "title": f"Global export market concentration, {products[code]}, 2025",
            "sourceUrl": UNCTAD_BULK, "retrievedAt": stamp, "availableAt": stamp,
            "observedAt": None, "publishedAt": None, "latitude": None, "longitude": None,
            "countryIso3": None, "properties": {
                "referenceYear": 2025, "temporalPrecision": "year", "flow": "Exports",
                "productCode": code, "productLabel": products[code], "concentrationIndex": value,
                "metric": "Normalized Herfindahl-Hirschman index of exporter market concentration",
                "geographicRole": "global_aggregate", "securityRelationship": None,
            },
        })
    if len(rows) != len(products) or {row["properties"]["productCode"] for row in rows} != set(products):
        raise ValueError("Missing or duplicate UNCTAD observations")
    info = {
        "datasetId": UNCTAD_ID, "sourceIds": ["SRC-114", "SRC-208"],
        "name": "UNCTAD global export concentration sample", "sourceUrl": UNCTAD_BULK,
        "licence": "CC BY 3.0 IGO; cite United Nations Trade and Development Data Hub",
        "licenceUrl": "https://unctadstat.unctad.org/EN/About.html#TERMS_OF_USE",
        "frequency": "fixed annual 2025 sample; manual capture",
        "limitations": [
            "Two selected global product groups; not a complete trade dataset or country measure.",
            "Concentration is a normalized index, not trade value or shipping activity.",
            "Publication time is not inferred from the dataset update; availability is gated at capture.",
            "No geographic points or security links are present. Source archive may be revised.",
        ],
        "sourceRows": source_rows, "selectedRows": len(rows), "rejected": 0, "coverageComplete": False,
        "scope": "2025 global export concentration for total merchandise and fuels only.",
        "retrievedAt": stamp,
    }
    return publish(directory, rows, info, [(UNCTAD_META, metadata_payload), (UNCTAD_BULK, payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    parser.add_argument("--source", choices=("wits", "unctad", "all"), default="all")
    args = parser.parse_args()
    result = {}
    if args.source in {"wits", "all"}:
        result["wits"] = collect(args.directory)["dataVersion"]
    if args.source in {"unctad", "all"}:
        result["unctad"] = collect_unctad(args.directory)["dataVersion"]
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
