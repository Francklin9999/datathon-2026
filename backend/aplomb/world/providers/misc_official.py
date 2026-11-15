"""Anonymous bounded NY Fed SCE workbook capture, with its embedded reuse licence."""
from __future__ import annotations

import argparse
import io
import json
import math
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, validate_row

DATASET_ID = "world_nyfed_sce_inflation_2024"
DATA_URL = "https://www.newyorkfed.org/medialibrary/interactives/sce/sce/downloads/data/frbny-sce-data.xlsx"
PAGE_URL = "https://www.newyorkfed.org/microeconomics/sce"
TERMS_URL = "https://www.newyorkfed.org/privacy/termsofuse"
SHEET_TITLE = "Inflation expectations"
SERIES_TITLE = "Median one-year ahead expected inflation rate"
ATTRIBUTION = (
    "Source: Survey of Consumer Expectations, © 2013-2026 Federal Reserve Bank of New York (FRBNY). "
    "The SCE data are available without charge at http://www.newyorkfed.org/microeconomics/sce "
    "and may be used subject to license terms posted there. FRBNY disclaims any responsibility "
    "for this analysis and interpretation of Survey of Consumer Expectations data. "
    "Aplomb selected the 2024 monthly observations and normalized dates and storage format. "
    "No FRBNY endorsement is implied. Workbook dataset licence and source copyright notices "
    "are preserved in the immutable original download."
)
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected SCE redirect")


def fetch(url: str) -> bytes:
    if url not in {DATA_URL, PAGE_URL, TERMS_URL}:
        raise ValueError("Unexpected SCE URL")
    opener = urllib.request.build_opener(_NoRedirect())
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AplombDatathon/1.0"})
            with opener.open(request, timeout=20) as response:
                started, size, chunks = time.monotonic(), 0, []
                while True:
                    chunk = response.read(min(65536, 2000001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > 2000000:
                        raise ValueError("SCE download exceeds 2 MB cap")
                    if time.monotonic() - started > 20:
                        raise TimeoutError("SCE read deadline exceeded")
                    chunks.append(chunk)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 1:
                raise
        time.sleep(1)
    raise RuntimeError("SCE retries exhausted")


def workbook_sheets(payload: bytes) -> dict[str, list[dict[str, str]]]:
    """Read only licence/disclaimer and selected statistical sheet, with ZIP bounds."""
    if len(payload) > 2000000:
        raise ValueError("Oversized SCE workbook")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if len(archive.infolist()) > 200:
            raise ValueError("Excessive SCE workbook entries")
        def xml(name):
            info = archive.getinfo(name)
            if info.file_size > 12000000:
                raise ValueError("SCE XML expansion exceeds cap")
            content = archive.read(name)
            if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
                raise ValueError("SCE XML entities prohibited")
            return ET.fromstring(content)
        strings = ["".join(e.itertext()) for e in xml("xl/sharedStrings.xml").findall("s:si", NS)]
        relationships = {e.attrib["Id"]: e.attrib["Target"]
                         for e in xml("xl/_rels/workbook.xml.rels")}
        result = {}
        for sheet in xml("xl/workbook.xml").findall("s:sheets/s:sheet", NS):
            name = sheet.attrib["name"]
            if name not in {"License", "Disclaimer", SHEET_TITLE}:
                continue
            rel = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = relationships[rel]
            target = target.lstrip("/") if target.startswith("/xl/") else "xl/" + target
            if ".." in target.split("/") or not target.startswith("xl/worksheets/"):
                raise ValueError("Unexpected SCE worksheet path")
            rows = []
            for row in xml(target).findall("s:sheetData/s:row", NS):
                cells = {}
                for cell in row.findall("s:c", NS):
                    value = cell.find("s:v", NS)
                    if value is None:
                        continue
                    text = value.text or ""
                    if cell.attrib.get("t") == "s":
                        text = strings[int(text)]
                    cells[cell.attrib["r"].rstrip("0123456789")] = text
                rows.append(cells)
            result[name] = rows
        if set(result) != {"License", "Disclaimer", SHEET_TITLE}:
            raise ValueError("Missing SCE licence or statistical sheet")
        return result


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    sheets = workbook_sheets(payload)
    legal = "\n".join(row.get("A", "") for row in sheets["License"])
    for required in ("worldwide, royalty-free, nonexclusive", "right to reproduce, use, and distribute",
                     "Data Attribution", "2013-2026 Federal Reserve Bank of New York"):
        if required not in legal:
            raise ValueError("SCE dataset-specific licence changed; review required")
    points = sheets[SHEET_TITLE]
    headers = [r for r in points if r.get("B") == SERIES_TITLE]
    if len(headers) != 1:
        raise ValueError("Unexpected SCE series header")
    rows = []
    for point in points:
        period = point.get("A", "")
        if not period.isdigit() or not 202401 <= int(period) <= 202412:
            continue
        year, month = int(period[:4]), int(period[4:])
        observed = datetime(year, month, 1).date().isoformat()
        value = float(point["B"])
        if not math.isfinite(value):
            raise ValueError("Nonfinite SCE expectation")
        row = base(DATASET_ID, period, "macro", SHEET_TITLE, DATA_URL, stamp,
                   countryIso3="USA", observedAt=observed, properties={
                       "sourceTitle": SHEET_TITLE, "seriesTitle": SERIES_TITLE,
                       "referenceMonth": observed[:7], "value": value, "unit": "percent",
                       "expectationHorizon": "one year ahead", "statistic": "median",
                       "geographicRole": "national_household_survey_aggregate",
                       "temporalPrecision": "monthly; first day is a display anchor",
                       "attribution": ATTRIBUTION, "normalization": "2024 row selection; unchanged source title",
                   })
        validate_row(row)
        rows.append(row)
    if len(rows) != 12 or len({r["id"] for r in rows}) != 12:
        raise ValueError("Expected exactly twelve distinct 2024 SCE monthly observations")
    return rows, {"licenseText": legal, "disclaimerText": "\n".join(
        row.get("A", "") for row in sheets["Disclaimer"])}


def collect(*, directory: Path = DIRECTORY, fetcher=fetch, stamp: str | None = None) -> dict:
    captures = [(DATA_URL, fetcher(DATA_URL)), (TERMS_URL, fetcher(TERMS_URL)),
                (PAGE_URL, fetcher(PAGE_URL))]
    stamp = stamp or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, rights = parse(captures[0][1], stamp)
    return publish(directory, rows, {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-102"], "name": "Survey of Consumer Expectations",
        "sourceUrl": PAGE_URL, "licence": "FRBNY SCE dataset-specific royalty-free reuse and derivative licence",
        "licenceUrl": DATA_URL, "attribution": ATTRIBUTION, "retrievedAt": stamp,
        "frequency": "Monthly observations; manual bounded completed-year capture",
        "sourceRows": len(rows), "rejected": 0, "coverageComplete": False,
        "scope": "United States, 2024 monthly median one-year-ahead expected inflation rate",
        "rightsEvidence": rights,
        "limitations": [
            "Twelve selected monthly national household survey expectations; not measured CPI inflation.",
            "Percent is the expected inflation rate; it is not a probability or an index.",
            "Original workbook series and sheet titles are retained unchanged.",
            "Attribution, free source URL, copyright notice and SCE licence accompany every observation.",
            "Normalized storage and row selection are Aplomb modifications; no FRBNY endorsement.",
            "Distributed source content remains subject to its original licence and cannot be given more restrictive terms.",
            "Monthly first-day display anchors are not exact observation or publication dates.",
            "Current workbook revision captured at retrieval; original vintage availability is unproven.",
            "No point coordinates, issuer relationships or modeled financial effects.",
        ],
    }, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    manifest = collect(directory=args.directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
