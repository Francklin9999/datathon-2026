"""Bounded anonymous CC BY energy/climate captures, gated at retrieval."""
from __future__ import annotations

import argparse
import hashlib
import html
import http.cookiejar
import io
import json
import math
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .snapshot import DIRECTORY, publish

ENERGY_ID = "world_energy_charts_de_power"
ENERGY_URL = "https://api.energy-charts.info/v2/public_power?country=de&start=2026-11-14&end=2026-11-14"
ENERGY_DOC = "https://api.energy-charts.info/openapi.json"
GCB_ID = "world_global_carbon_budget_2026"
GCB_URL = "https://data.icos-cp.eu/objects/tGBR0_JV6zn3TGDzwaIEUNNn"
GCB_META = "https://meta.icos-cp.eu/objects/tGBR0_JV6zn3TGDzwaIEUNNn"
GCB_RIGHTS = "https://www.icos-cp.eu/data-services/data-portal/data-licence"
GCB_ACCEPT = "https://data.icos-cp.eu/licence_accept?ids=%5B%22tGBR0_JV6zn3TGDzwaIEUNNn%22%5D"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected source redirect")


def fetch(url: str) -> bytes:
    if url not in {ENERGY_URL, ENERGY_DOC, GCB_URL, GCB_META, GCB_RIGHTS}:
        raise ValueError("Unexpected source URL")
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "Aplomb bounded public research ingestion"})
    with opener.open(request, timeout=25) as response:
        chunks, size, started = [], 0, time.monotonic()
        while True:
            chunk = response.read(min(65536, 2_000_001 - size))
            if not chunk:
                return b"".join(chunks)
            size += len(chunk)
            if size > 2_000_000 or time.monotonic() - started > 25:
                raise ValueError("Provider capture exceeded byte or time bound")
            chunks.append(chunk)


def energy(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if (body.get("schema_version") != "2.0" or body.get("endpoint") != "public_power"
            or body.get("country") != "de" or body.get("unit") != "MW"
            or body.get("resolution") != "PT15M" or body.get("interval_minutes") != 15
            or not (body.get("license") or "").startswith("CC BY 4.0")):
        raise ValueError("Unexpected Energy-Charts schema, country, unit or rights")
    descriptors = {s["id"]: s for s in body["series"]}
    if len(descriptors) != len(body["series"]):
        raise ValueError("Duplicate Energy-Charts series")
    wanted = {"solar", "wind_onshore", "wind_offshore", "fossil_gas"}
    if not wanted.issubset(descriptors) or not 1 <= len(body["data"]) <= 100:
        raise ValueError("Missing generation series or unbounded daily response")
    rows, rejected = [], 0
    for record in body["data"]:
        observed = datetime.fromisoformat(record["timestamp"])
        if observed.tzinfo is None or observed.date().isoformat() != "2026-11-14":
            raise ValueError("Unexpected generation interval")
        observed_utc = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        for key in sorted(wanted):
            value = record["values"].get(key)
            if value is None:
                rejected += 1
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("Invalid selected generation value")
            if descriptors[key].get("unit", "MW") != "MW":
                raise ValueError("Generation unit changed")
            rows.append({
                "id": f"{ENERGY_ID}:{observed_utc}:{key}", "sourceId": ENERGY_ID,
                "category": "energy", "title": f"Germany {descriptors[key]['name']}: {value:g} MW",
                "sourceUrl": ENERGY_URL, "retrievedAt": stamp, "availableAt": stamp,
                "observedAt": observed_utc, "publishedAt": None, "countryIso3": "DEU",
                "latitude": None, "longitude": None,
                "properties": {"value": value, "unit": "MW", "productionType": key,
                    "intervalMinutes": 15, "geographicRole": "reporting_country",
                    "sourceGeneratedAt": body["generated_at"], "sourceTimezone": body["timezone"],
                    "attribution": "Energy-Charts.info / Fraunhofer ISE, CC BY 4.0; selected and normalized by Aplomb.",
                    "securityRelationship": None},
            })
    return rows, {"sourceIntervals": len(body["data"]), "selectedSeries": sorted(wanted),
                  "sourceSeries": len(descriptors), "rejected": rejected, "coverageComplete": False}


def workbook_rows(payload: bytes, sheet: str) -> list[dict[str, str]]:
    """Read source cell text without evaluating formulas or running workbook code."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 30_000_000:
            raise ValueError("Workbook expansion exceeds limit")
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(x.itertext()) for x in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        result = []
        root = ET.fromstring(archive.read(sheet))
        for record in root.find("s:sheetData", NS):
            values = {}
            for cell in record:
                value = cell.find("s:v", NS)
                text = value.text if value is not None else ""
                if cell.attrib.get("t") == "s":
                    text = shared[int(text)]
                elif cell.attrib.get("t") == "inlineStr":
                    text = "".join(cell.find("s:is", NS).itertext())
                column = "".join(c for c in cell.attrib["r"] if c.isalpha())
                values[column] = text
            result.append(values)
        return result


def collect_energy(directory: Path = DIRECTORY, fetcher=fetch) -> dict:
    payload, documentation = fetcher(ENERGY_URL), fetcher(ENERGY_DOC)
    doc = json.loads(documentation)
    rights_text = re.sub("<[^>]+>", "", doc["info"]["description"])
    if "data provided by the Energy-Charts API is licensed under the CC BY 4.0" not in rights_text:
        raise ValueError("Publisher rights documentation changed")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = energy(payload, stamp)
    return publish(directory, rows, {
        "datasetId": ENERGY_ID, "sourceIds": ["SRC-195"],
        "name": "Fraunhofer Energy-Charts Germany selected public net generation",
        "sourceUrl": ENERGY_URL, "licence": "CC BY 4.0; attribution Energy-Charts.info; Aplomb selects and normalizes four series.",
        "licenceUrl": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Energy-Charts.info / Fraunhofer ISE; CC BY 4.0. Selected and normalized by Aplomb.",
        "frequency": "Fixed 2026-11-14 day; manual bounded capture",
        "retrievedAt": stamp, **quality,
        "limitations": ["Germany only, four production types and one day; no complete electricity mix.",
            "Power in MW at fifteen-minute source intervals is not energy in MWh.",
            "National series has no source point; no plant, operator, issuer or financial exposure is inferred.",
            "Capture gates historical replay; source generation time does not prove original interval publication time."],
    }, [(ENERGY_URL, payload), (ENERGY_DOC, documentation)])


def carbon_budget(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    source = workbook_rows(payload, "xl/worksheets/sheet2.xml")
    headers = next((r for r in source if r.get("A") == "Year"), None)
    expected = {"B": "fossil emissions excluding carbonation", "C": "land-use change emissions",
                "D": "atmospheric growth", "E": "ocean sink", "F": "land sink",
                "G": "cement carbonation sink", "H": "budget imbalance"}
    if headers is None or any(headers.get(k) != v for k, v in expected.items()):
        raise ValueError("Global carbon budget columns changed")
    if not any(r.get("A") == "GtC/yr" for r in source):
        raise ValueError("Global carbon budget units changed")
    rows, years = [], set()
    for record in source:
        year = record.get("A", "")
        if not year.isdigit() or not 1959 <= int(year) <= 2025:
            continue
        if year in years:
            raise ValueError("Duplicate global carbon budget year")
        years.add(year)
        for column, name in expected.items():
            value = float(record[column])
            if not math.isfinite(value) or abs(value) > 100:
                raise ValueError("Invalid carbon budget value")
            rows.append({
                "id": f"{GCB_ID}:{year}:{column}", "sourceId": GCB_ID, "category": "environment",
                "title": f"Global {name}, {year}: {value:.4f} GtC/yr",
                "sourceUrl": GCB_META, "retrievedAt": stamp, "availableAt": stamp,
                "observedAt": None, "publishedAt": None, "countryIso3": None,
                "latitude": None, "longitude": None,
                "properties": {"value": value, "unit": "GtC/yr", "referenceYear": int(year),
                    "component": name, "sourceVersion": "2026 v0.1", "sourcePublicationDate": "2026-11-10",
                    "temporalPrecision": "year", "geographicRole": "global_aggregate",
                    "attribution": "Global Carbon Project, Friedlingstein et al. (2026), DOI 10.18160/GCP-2026; CC BY 4.0 via ICOS RI. Selected and normalized by Aplomb.",
                    "securityRelationship": None},
            })
    if years != {str(y) for y in range(1959, 2026)}:
        raise ValueError("Incomplete selected global carbon budget years")
    return rows, {"selectedYears": [1959, 2025], "selectedComponents": list(expected.values()),
                  "rejected": 0, "coverageComplete": False}


def fetch_gcb_workbook() -> bytes:
    # Anonymous licence acceptance is implemented with an ephemeral cookie jar.
    # The publisher redirects from acceptance to this exact dataset download.
    class _GcbRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if newurl not in {GCB_URL, "https://data.icos-cp.eu/licence?ids=%5B%22tGBR0_JV6zn3TGDzwaIEUNNn%22%5D"}:
                raise ValueError("Unexpected ICOS download redirect")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    opener = urllib.request.build_opener(_GcbRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(GCB_ACCEPT, timeout=25) as response:
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000 or not payload.startswith(b"PK"):
        raise ValueError("ICOS did not return the bounded workbook")
    return payload


def collect_gcb(directory: Path = DIRECTORY, fetcher=fetch, workbook_fetcher=fetch_gcb_workbook) -> dict:
    metadata, rights = fetcher(GCB_META), fetcher(GCB_RIGHTS)
    metadata_text = metadata.decode()
    rights_text = html.unescape(re.sub("<[^>]+>", "", rights.decode()))
    if "Creative Commons Attribution 4.0 International" not in rights_text or "icosLicence" not in metadata_text:
        raise ValueError("ICOS dataset rights changed")
    payload = workbook_fetcher()
    # The authoritative landing page carries the original workbook digest.
    if hashlib.sha256(payload).hexdigest() not in metadata_text:
        raise ValueError("GCB workbook differs from publisher metadata")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = carbon_budget(payload, stamp)
    return publish(directory, rows, {
        "datasetId": GCB_ID, "sourceIds": ["SRC-224"], "name": "Global Carbon Budget 2026 v0.1 selected annual global components",
        "sourceUrl": GCB_META, "licence": "CC BY 4.0 via ICOS RI; cite Global Carbon Project, Friedlingstein et al. (2026), DOI 10.18160/GCP-2026; selected and normalized by Aplomb.",
        "licenceUrl": GCB_RIGHTS, "frequency": "Annual revised scientific budget; manual capture",
        "attribution": "Global Carbon Project / ICOS RI; Friedlingstein et al. (2026), DOI 10.18160/GCP-2026; CC BY 4.0; selected and normalized by Aplomb.",
        "retrievedAt": stamp, **quality,
        "limitations": ["Seven global annual components, 1959–2025; no country, facility or source point.",
            "Values are gigatonnes of carbon per year, not gigatonnes of CO2; source model estimates and uncertainty apply.",
            "2026 release version 0.1 may be revised; selected annual estimates are not real-time emissions.",
            "Latest released estimates are gated at capture; original annual vintages are unavailable.",
            "No issuer relationship, comprehensive ESG score or financial effect is inferred."],
    }, [(GCB_URL, payload), (GCB_META, metadata), (GCB_RIGHTS, rights)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    parser.add_argument("--source", choices=["energy", "gcb"], default="energy")
    args = parser.parse_args()
    print(json.dumps((collect_energy if args.source == "energy" else collect_gcb)(args.directory), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
