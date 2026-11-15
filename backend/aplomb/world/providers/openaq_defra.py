"""Bounded OpenAQ capture of one DEFRA station's historical hourly concentrations."""
from __future__ import annotations

import argparse
import json
import math
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, timestamp, validate_row

DATASET_ID = "world_openaq_defra_york_20260328"
STATION_URL = "https://api.openaq.org/v3/locations/742"
HOURS_BASE = "https://api.openaq.org/v3/sensors/{}/hours?datetime_from=2026-03-28T00%3A00%3A00Z&datetime_to=2026-03-29T00%3A00%3A00Z&limit=1000"
TERMS_URL = "https://uk-air.defra.gov.uk/data/"
LICENCE_URL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
OPENAQ_TERMS = "https://docs.openaq.org/about/terms"
SENSORS = {1279: "pm25", 5083: "pm10", 7823: "no2", 5968020: "o3"}
ATTRIBUTION = ("© Crown 2026 copyright Defra via uk-air.defra.gov.uk, licenced under the "
               "Open Government Licence (OGL). Data accessed via OpenAQ; adapted by Aplomb.")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect refused during capture")


def fetch(url: str, key: str | None = None) -> bytes:
    headers = {"User-Agent": "AplombDatathon/1.0", "Accept": "application/json,text/html"}
    if key:
        if not url.startswith("https://api.openaq.org/v3/"):
            raise ValueError("API key restricted to OpenAQ")
        headers["X-API-Key"] = key
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(urllib.request.Request(url, headers=headers), timeout=25) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("Capture exceeds byte limit")
    return body


def parse(station: bytes, hourly: dict[int, bytes], rights: bytes, stamp: str) -> tuple[list[dict], dict]:
    if b"Open Government Licence" not in rights or b"acknowledge Defra" not in rights:
        raise ValueError("DEFRA reuse terms could not be verified")
    result = json.loads(station)["results"]
    if len(result) != 1:
        raise ValueError("Unexpected station response")
    loc = result[0]
    if (loc["id"] != 742 or loc["provider"]["id"] != 169 or loc["country"]["code"] != "GB"
            or loc["isMobile"] or not loc["isMonitor"]):
        raise ValueError("Station identity or provider changed")
    licence = [x for x in loc.get("licenses") or [] if x["id"] == 34
               and x["name"] == 'UK OGL "Open Government License"'
               and x["dateFrom"] <= "2026-03-28" and (x["dateTo"] is None or x["dateTo"] >= "2026-03-29")]
    if not licence:
        raise ValueError("No applicable UK OGL for observation period")
    sensor_metadata = {x["id"]: x["parameter"] for x in loc["sensors"]}
    rows, seen = [], set()
    for sensor, name in SENSORS.items():
        p = sensor_metadata[sensor]
        if p["name"] != name or p["units"] != "µg/m³":
            raise ValueError("Sensor parameter or units changed")
        body = json.loads(hourly[sensor])
        if body["meta"]["found"] != 24 or len(body["results"]) != 24:
            raise ValueError("Incomplete hourly result")
        for item in body["results"]:
            period = item["period"]
            start, end = period["datetimeFrom"]["utc"], period["datetimeTo"]["utc"]
            val = item["value"]
            if (item["parameter"]["name"] != name or item["parameter"]["units"] != "µg/m³"
                    or period["label"] != "1hour" or timestamp(end) - timestamp(start) != timedelta(hours=1)
                    or not "2026-03-28T00:00:00Z" <= start < "2026-03-29T00:00:00Z"
                    or isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val)):
                raise ValueError("Unexpected hourly observation")
            key = f"{sensor}-{start}"
            if key in seen:
                raise ValueError("Duplicate observation")
            seen.add(key)
            row = base(DATASET_ID, key, "environment", f"York Bootham {name.upper()} {val:g} µg/m³ · {start}",
                       STATION_URL, stamp, latitude=loc["coordinates"]["latitude"],
                       longitude=loc["coordinates"]["longitude"], countryIso3="GBR", observedAt=end,
                       properties={"stationId": 742, "stationName": loc["name"], "sensorId": sensor,
                                   "parameter": name, "value": val, "unit": "µg/m³", "periodStart": start,
                                   "periodEnd": end, "hasFlags": item.get("flagInfo", {}).get("hasFlags"),
                                   "geographicRole": "air_quality_monitor", "attribution": ATTRIBUTION})
            validate_row(row)
            rows.append(row)
    return rows, {"sourceRows": len(rows), "rejected": 0, "coverageComplete": True,
                  "scope": "One DEFRA station in York; four pollutants, hourly intervals starting 28 March 2026 UTC. Not current or representative of UK air quality."}


def collect(directory: Path = DIRECTORY) -> dict:
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        raise ValueError("OPENAQ_API_KEY is required")
    urls = [STATION_URL] + [HOURS_BASE.format(s) for s in SENSORS]
    captures = [(url, fetch(url, key)) for url in urls]
    rights = fetch(TERMS_URL)
    captures.append((TERMS_URL, rights))
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(captures[0][1], dict(zip(SENSORS, (c[1] for c in captures[1:5]))), rights, stamp)
    return publish(directory, rows, {"datasetId": DATASET_ID, "sourceIds": ["SRC-189", "SRC-222"],
        "name": "OpenAQ / DEFRA York Bootham hourly air quality, 28 March 2026",
        "sourceUrl": STATION_URL, "licence": "UK Open Government Licence v3.0", "licenceUrl": LICENCE_URL,
        "accessMethod": "Authenticated OpenAQ HTTPS batch capture; no runtime source request",
        "attribution": ATTRIBUTION, "frequency": "Hourly; fixed historical batch", "retrievedAt": stamp,
        "limitations": ["One station and one historical UTC day; not current or nationally representative.",
                        "Hourly concentrations are not air-quality index values or health assessments; source values may be revised.",
                        "No claim about portfolio exposure or financial impact.", ATTRIBUTION], **quality}, captures)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    manifest = collect(parser.parse_args().directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))


if __name__ == "__main__":
    main()
