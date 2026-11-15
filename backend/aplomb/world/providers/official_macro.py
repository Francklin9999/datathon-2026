"""Three bounded anonymous official macro captures, consumed by World Explorer.

Run: python -m aplomb.world.providers.official_macro --source ecb --source bis --source fed
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, validate_row

SOURCES = {
    "ecb": {
        "datasetId": "world_ecb_eurosystem_assets_2024", "sourceIds": ["SRC-093", "MASTER-035"],
        "name": "ECB 2024 Eurosystem total assets/liabilities",
        "sourceUrl": "https://data-api.ecb.europa.eu/service/data/ILM/W.U2.C.T000000.Z5.Z01?startPeriod=2024-01-01&endPeriod=2024-12-31&format=csvdata",
        "licence": "ECB statistics reuse with accurate source credit, modification disclosure and free-source notice",
        "licenceUrl": "https://www.ecb.europa.eu/services/disclaimer/html/index.en.html",
        "attribution": "Source: European Central Bank, ILM.W.U2.C.T000000.Z5.Z01. Adapted to selected normalized records by Aplomb; numerical values unchanged. This information is available free of charge from the ECB website.",
    },
    "bis": {
        "datasetId": "world_bis_us_debt_service_2024", "sourceIds": ["SRC-094", "MASTER-036"],
        "name": "BIS 2024 United States private nonfinancial debt-service ratio",
        "sourceUrl": "https://stats.bis.org/api/v1/data/WS_DSR/Q.US.P?startPeriod=2024-Q1&endPeriod=2024-Q4",
        "licence": "BIS statistics terms: credit BIS, no misleading endorsement, no additional charge for data inclusion",
        "licenceUrl": "https://data.bis.org/help/legal",
        "attribution": "Source: Bank for International Settlements (BIS), WS_DSR Q.US.P. Selected normalized records by Aplomb. No BIS endorsement. Any translation is not an official BIS translation.",
    },
    "fed": {
        "datasetId": "world_fed_chargeoffs_2024", "sourceIds": ["SRC-103"],
        "name": "Federal Reserve 2024 all-bank total loan and lease charge-off rate",
        "sourceUrl": "https://www.federalreserve.gov/releases/chargeoff/chgallsa.htm",
        "licence": "Federal Reserve Board information public domain unless otherwise indicated; Board source credit",
        "licenceUrl": "https://www.federalreserve.gov/disclaimer.htm",
        "attribution": "Source: Board of Governors of the Federal Reserve System, charge-off rates, all banks, seasonally adjusted. Selected normalized records by Aplomb; no government endorsement.",
    },
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected official macro redirect")


def fetch(url: str) -> bytes:
    if url not in {source["sourceUrl"] for source in SOURCES.values()}:
        raise ValueError("Unexpected macro endpoint")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AplombDatathon/1.0 (bounded anonymous statistics capture)",
                                                          "Accept": "text/csv,application/xml,text/html"})
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=20) as response:
                chunks, size, started = [], 0, time.monotonic()
                while True:
                    chunk = response.read(min(65536, 500_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > 500_000 or time.monotonic() - started > 20:
                        raise ValueError("Macro payload exceeds byte or read-time cap")
                    chunks.append(chunk)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Macro retries exhausted")


def _number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("Invalid macro value")
    return number


def _quarter(period: str) -> str:
    if not re.fullmatch(r"2024-Q[1-4]", period):
        raise ValueError("Unexpected quarter")
    return f"2024-{(int(period[-1]) - 1) * 3 + 1:02d}-01"


class _ChargeoffTable(HTMLParser):
    """Select source-defined TOTAL cells, rather than relying on column positions."""
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.active = False
        self.cell = None
        self.text = []
        self.period = None
        self.points = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            if self.active:
                self.depth += 1
            elif attrs.get("class") == "statistics":
                self.active, self.depth = True, 1
        if self.active and tag == "tr":
            self.period = None
        if self.active and tag in {"th", "td"}:
            headers = attrs.get("headers", "").split()
            self.cell = "period" if tag == "th" and attrs.get("id", "").startswith("date") else (
                "value" if "TOTAL" in headers else None)
            self.text = []

    def handle_data(self, data):
        if self.cell:
            self.text.append(data)

    def handle_endtag(self, tag):
        if self.active and tag in {"th", "td"} and self.cell:
            text = "".join(self.text).strip()
            if self.cell == "period":
                self.period = text
            elif self.period and self.period.startswith("2024:"):
                self.points.append((self.period.replace(":", "-Q"), _number(text)))
            self.cell = None
        if self.active and tag == "table":
            self.depth -= 1
            if self.depth == 0:
                self.active = False


def parse(name: str, payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    source = SOURCES[name]
    points = []
    if name == "ecb":
        records = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
        if not 1 <= len(records) <= 53:
            raise ValueError("ECB weekly scope mismatch")
        for record in records:
            expected = {"KEY": "ILM.W.U2.C.T000000.Z5.Z01", "FREQ": "W", "REF_AREA": "U2",
                        "BS_REP_SECTOR": "C", "BS_ITEM": "T000000", "COUNT_AREA": "Z5",
                        "CURRENCY_TRANS": "Z01", "UNIT": "EUR", "UNIT_MULT": "6", "OBS_STATUS": "A"}
            if any(record.get(key) != value for key, value in expected.items()):
                raise ValueError("ECB series dimensions or unit mismatch")
            period = record["TIME_PERIOD"]
            if not re.fullmatch(r"2024-W\d{2}", period):
                raise ValueError("ECB reference week mismatch")
            reference = date.fromisocalendar(2024, int(period[-2:]), 1).isoformat()
            points.append((period, reference, _number(record["OBS_VALUE"]), "million EUR"))
    elif name == "bis":
        if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
            raise ValueError("Unsafe XML declaration")
        root = ET.fromstring(payload)
        datasets = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "DataSet"]
        if len(datasets) != 1 or datasets[0].get("UNIT_MEASURE") != "367" or datasets[0].get("UNIT_MULT") != "0":
            raise ValueError("BIS dataset unit mismatch")
        series = list(datasets[0])
        if len(series) != 1 or any(series[0].get(key) != value for key, value in {
            "FREQ": "Q", "BORROWERS_CTY": "US", "DSR_BORROWERS": "P",
            "TITLE_TS": "United States - Private non-financial sector",
        }.items()):
            raise ValueError("BIS series dimensions mismatch")
        for point in series[0]:
            if point.tag.rsplit("}", 1)[-1] != "Obs" or point.get("OBS_STATUS") != "A":
                raise ValueError("BIS observation schema mismatch")
            period = point.attrib["TIME_PERIOD"]
            value = _number(point.attrib["OBS_VALUE"])
            if value > 100:
                raise ValueError("BIS percentage out of range")
            points.append((period, _quarter(period), value, "percent of income"))
    elif name == "fed":
        text = payload.decode("utf-8-sig")
        for label in ("Charge-Off Rates", "All Banks, SA", 'id="TOTAL"'):
            if label not in text:
                raise ValueError("Federal Reserve table identity mismatch")
        parser = _ChargeoffTable()
        parser.feed(text)
        points = [(period, _quarter(period), value, "percent, annualized") for period, value in parser.points]
    else:
        raise ValueError("Unknown macro source")
    if name != "ecb" and {point[0] for point in points} != {f"2024-Q{i}" for i in range(1, 5)}:
        raise ValueError("Expected four 2024 quarters")
    if not points or len({point[0] for point in points}) != len(points):
        raise ValueError("Empty or duplicate macro periods")
    rows = []
    for period, reference, value, unit in points:
        row = base(source["datasetId"], period, "macro", f"{source['name']}, {period}: {value:g} {unit}",
                   source["sourceUrl"], stamp, observedAt=reference,
                   **({"countryIso3": "USA"} if name != "ecb" else {}),
                   properties={"referencePeriod": period, "value": value, "unit": unit,
                               "temporalPrecision": "reference period; first day is only a display anchor",
                               "geographicRole": "supranational_statistical_area" if name == "ecb" else "national_statistical_area",
                               "seasonalAdjustment": "seasonally adjusted" if name == "fed" else "not specified",
                               "attribution": source["attribution"]})
        validate_row(row)
        rows.append(row)
    return rows, {"sourceRows": len(points), "rejected": 0, "coverageComplete": False,
                  "scope": "One selected 2024 official macro series; incomplete provider and history coverage."}


def collect(name: str, directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    source = SOURCES[name]
    payload = fetcher(source["sourceUrl"])
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(name, payload, stamp)
    limitations = [
        "One 2024 series only. National or supranational aggregate; no point coordinates, issuer links or financial impact.",
        "Period start is a display anchor; source publication time and historical vintage are unproven.",
        "Latest captured values may be revised; excluded before retrieval, unavailable for original historical replay.",
    ]
    if name == "ecb":
        limitations.append("ECB information is available free of charge from the original linked ECB source; normalized selection by Aplomb.")
    elif name == "bis":
        limitations.append("BIS statistics inclusion must cause no additional charge to users. Any translation is not an official BIS translation. No BIS endorsement.")
    else:
        limitations.append("Charge-offs are net of recoveries as a percentage of average loans, annualized and seasonally adjusted; insured U.S.-chartered commercial banks. Official release table is used, not the interactive Data Download Program.")
    return publish(directory, rows, {**source, **quality, "retrievedAt": stamp,
                                    "frequency": "Weekly" if name == "ecb" else "Quarterly",
                                    "limitations": limitations}, [(source["sourceUrl"], payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", choices=sorted(SOURCES), action="append", required=True)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    results, failed = [], False
    for name in dict.fromkeys(args.source):
        try:
            manifest = collect(name, args.directory)
            results.append({"source": name, "version": manifest["dataVersion"], "rows": manifest["rowCount"]})
        except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as exc:
            failed = True
            results.append({"source": name, "status": "failed", "error": str(exc)})
    print(json.dumps(results, indent=2))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
