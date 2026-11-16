"""Pure provider parsers. Geographic precision and incomplete coverage remain explicit."""
from __future__ import annotations

import json
import math
from datetime import datetime
from urllib.parse import urlencode

from .snapshot import validate_row

POLICY_URL = "https://www.federalregister.gov/api/v1/documents.json?per_page=20&order=newest"
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_POINTS = (
    ("London", 51.5074, -0.1278, "GBR"),
    ("Johannesburg", -26.2041, 28.0473, "ZAF"),
    ("Tokyo", 35.6762, 139.6503, "JPN"),
    ("Sydney", -33.8688, 151.2093, "AUS"),
    ("Dubai", 25.2048, 55.2708, "ARE"),
    ("Sao Paulo", -23.5505, -46.6333, "BRA"),
)
POWER_PERIOD = ("20261001", "20261031")
EPA_BASE = "https://data.epa.gov/dmapservice/sems.envirofacts_site/fk_ref_state_code/equals"
EPA_STATES = ("CA", "FL", "IL", "NY", "TX", "WA")


def base(source: str, key: str, category: str, title: str, url: str, stamp: str, **extra) -> dict:
    return {"id": source + ":" + key, "sourceId": source, "category": category,
            "title": title, "sourceUrl": url, "retrievedAt": stamp, "availableAt": stamp,
            "observedAt": None, "publishedAt": None, "latitude": None, "longitude": None,
            "countryIso3": None, "properties": {}, **extra}


def _accepted(candidates) -> tuple[list[dict], int]:
    rows, rejected, seen = [], 0, set()
    for candidate in candidates:
        try:
            row = candidate()
            validate_row(row)
            if row["id"] in seen:
                raise ValueError("Duplicate source record")
            seen.add(row["id"])
            rows.append(row)
        except (KeyError, ValueError, TypeError, OverflowError):
            rejected += 1
    return rows, rejected


def policy(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if not isinstance(body.get("results"), list):
        raise ValueError("Invalid Federal Register response")

    def parse(item):
        if item["publication_date"] > stamp[:10]:
            raise ValueError("Future publication")
        return base("world_federal_register", item["document_number"], "policy", item["title"],
                    item["html_url"], stamp, countryIso3="USA", publishedAt=item["publication_date"],
                    properties={"documentType": item["type"], "documentNumber": item["document_number"],
                                "agencies": [a["name"] for a in item.get("agencies", []) if a.get("name")],
                                "geographicRole": "national_jurisdiction", "legalAuthority":
                                "Metadata only; consult linked official PDF for authoritative text."})

    rows, rejected = _accepted([lambda item=item: parse(item) for item in body["results"]])
    return rows, {"sourceRows": len(body["results"]), "rejected": rejected,
                  "coverageComplete": not bool(body.get("next_page_url")),
                  "scope": "Newest bounded metadata page; no exhaustive historical policy coverage."}


def power_url(lat: float, lon: float) -> str:
    return POWER_URL + "?" + urlencode({
        "parameters": "T2M", "community": "RE", "latitude": lat, "longitude": lon,
        "start": POWER_PERIOD[0], "end": POWER_PERIOD[1], "format": "JSON",
    })


def power(captures: list[tuple[str, bytes]], stamp: str) -> tuple[list[dict], dict]:
    if len(captures) != len(POWER_POINTS):
        raise ValueError("Incomplete NASA POWER sample")
    candidates = []
    count = 0
    for (name, lat, lon, iso3), (url, payload) in zip(POWER_POINTS, captures, strict=True):
        if url != power_url(lat, lon):
            raise ValueError("Unexpected NASA POWER point URL")
        body = json.loads(payload)
        header = body["header"]
        parameter = body["properties"]["parameter"]["T2M"]
        coords = body["geometry"]["coordinates"]
        if (body["type"] != "Feature" or body["geometry"]["type"] != "Point"
                or header["time_standard"] != "LST" or header["start"] != POWER_PERIOD[0]
                or header["end"] != POWER_PERIOD[1] or body["parameters"]["T2M"]["units"] != "C"
                or len(coords) < 2 or abs(coords[0] - lon) > 0.01 or abs(coords[1] - lat) > 0.01
                or len(parameter) != 31):
            raise ValueError("NASA POWER schema, position, or period changed")
        count += len(parameter)
        for date_key, value in parameter.items():
            def parse(date_key=date_key, value=value, name=name, lat=lat, lon=lon, iso3=iso3, url=url, header=header):
                date = datetime.strptime(date_key, "%Y%m%d").date().isoformat()
                if not POWER_PERIOD[0] <= date_key <= POWER_PERIOD[1]:
                    raise ValueError("Outside NASA POWER capture period")
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("Invalid temperature")
                if value == header["fill_value"] or not -100 <= value <= 100:
                    raise ValueError("Missing or implausible temperature")
                return base("world_nasa_power", f"{iso3}:{date_key}", "environment",
                            f"{name} daily 2 m temperature: {value:.1f} °C", url, stamp,
                            latitude=lat, longitude=lon, countryIso3=iso3, observedAt=date,
                            properties={"temperatureC": value, "date": date, "sourceModel": header["sources"],
                                        "timeStandard": "local solar time", "geographicRole": "sample_grid_point",
                                        "coordinateMeaning": "Requested grid location, not a weather station",
                                        "temporalPrecision": "day; API date has no exact UTC observation time"})
            candidates.append(parse)
    rows, rejected = _accepted(candidates)
    return rows, {"sourceRows": count, "rejected": rejected, "coverageComplete": False,
                  "scope": "October 2026 daily gridded 2 m temperatures at six requested world locations; not global coverage."}


def epa_url(state: str) -> str:
    if state not in EPA_STATES:
        raise ValueError("Unapproved EPA state")
    return f"{EPA_BASE}/{state}/0:200"


def epa(captures: list[tuple[str, bytes]], stamp: str) -> tuple[list[dict], dict]:
    if len(captures) != len(EPA_STATES):
        raise ValueError("Incomplete EPA state sample")
    candidates = []
    count = 0
    for state, (url, payload) in zip(EPA_STATES, captures, strict=True):
        if url != epa_url(state):
            raise ValueError("Unexpected EPA query URL")
        body = json.loads(payload)
        if not isinstance(body, list) or len(body) > 200:
            raise ValueError("EPA site response is not a bounded list")
        count += len(body)
        for item in body:
            def parse(item=item, state=state, url=url):
                if item["fk_ref_state_code"] != state or not item["epa_id"] or not item["name"]:
                    raise ValueError("EPA site identity/state mismatch")
                lat = float(item["primary_latitude_decimal_val"])
                lon = float(item["primary_longitude_decimal_val"])
                return base("world_epa_sems_sites", item["epa_id"], "environment", item["name"],
                            url, stamp, latitude=lat, longitude=lon, countryIso3="USA",
                            properties={"epaId": item["epa_id"], "state": state,
                                        "city": item.get("city_name"),
                                        "sourceNplStatus": item.get("npl_status_name"),
                                        "sourceArchiveIndicator": item.get("archived_ind"),
                                        "geographicRole": "epa_sems_site_reference",
                                        "relationshipToIssuer": None, "emissionsMeasurement": None})
            candidates.append(parse)
    rows, rejected = _accepted(candidates)
    return rows, {"sourceRows": count, "rejected": rejected, "coverageComplete": False,
                  "scope": "First 200 SEMS site records in each of six US states; only source-geocoded records retained."}
