"""Pure provider parsers. Geographic precision and incomplete coverage remain explicit."""
from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, timezone

from .snapshot import validate_row

AVIATION_URL = "https://aviationweather.gov/api/data/metar?ids=EGLL,LFPG,RJTT,YSSY,FAOR,OMDB&format=json"
NOAA_URL = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
POLICY_URL = "https://www.federalregister.gov/api/v1/documents.json?per_page=20&order=newest"
WRI_URL = "https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv"
GDACS_URL = "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/latest?eventlist=EQ;TC;FL;VO;WF;DR&alertlevel=Green;Orange;Red&pageSize=100&pageNumber=1"
PORTS_BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/PortWatch_ports_database/FeatureServer/0/query"
STATION_COUNTRY_CODES = {"GB": "GBR", "ZA": "ZAF", "FR": "FRA", "AE": "ARE", "JP": "JPN", "AU": "AUS"}


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


def aviation(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if not isinstance(body, list):
        raise ValueError("Invalid METAR response")

    def parse(item):
        observed = datetime.fromtimestamp(item["obsTime"], timezone.utc).isoformat().replace("+00:00", "Z")
        if not item["icaoId"] or not item["rawOb"]:
            raise ValueError("Missing weather identity")
        country_code = item["name"].split(",")[-1].strip()
        return base("world_aviation_weather", item["icaoId"], "aviation", item["name"], AVIATION_URL, stamp,
                    latitude=item["lat"], longitude=item["lon"], observedAt=observed,
                    countryIso3=STATION_COUNTRY_CODES.get(country_code),
                    publishedAt=item.get("receiptTime"), properties={
                        "stationId": item["icaoId"], "metar": item["rawOb"],
                        "sourceStationName": item["name"],
                        "sourceCountryCode": country_code if country_code in STATION_COUNTRY_CODES else None,
                        "temperatureC": item.get("temp"), "windSpeedKnots": item.get("wspd"),
                        "flightCategory": item.get("fltCat"),
                        "geographicRole": "weather_station", "aircraftTracking": False})

    rows, rejected = _accepted([lambda item=item: parse(item) for item in body])
    return rows, {"sourceRows": len(body), "rejected": rejected, "coverageComplete": False,
                  "scope": "Six requested international airport weather stations; no aircraft positions."}


def noaa(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if body.get("type") != "FeatureCollection" or not isinstance(body.get("features"), list):
        raise ValueError("Invalid NOAA alert collection")

    def parse(feature):
        props, geometry = feature["properties"], feature.get("geometry")
        if not geometry or geometry["type"] != "Polygon":
            raise ValueError("Missing supported alert polygon; no invented location")
        ring = geometry["coordinates"][0]
        if len(ring) < 4 or ring[0] != ring[-1]:
            raise ValueError("Invalid alert polygon")
        for lon, lat in ring:
            if not math.isfinite(lon) or not math.isfinite(lat) or not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise ValueError("Invalid alert coordinates")
        # This is an explicit display anchor, not a source observation of a point.
        lon = sum(p[0] for p in ring[:-1]) / (len(ring) - 1)
        lat = sum(p[1] for p in ring[:-1]) / (len(ring) - 1)
        return base("world_noaa_alerts", props["id"], "hazards", props["headline"] or props["event"],
                    feature["id"], stamp, latitude=lat, longitude=lon, countryIso3="USA",
                    publishedAt=props["sent"], observedAt=props.get("onset") or props["effective"],
                    properties={"event": props["event"], "severity": props["severity"],
                                "certainty": props["certainty"], "expires": props["expires"],
                                "areaDescription": props["areaDesc"], "geometry": geometry,
                                "geographicRole": "alert_polygon_representative_anchor"})

    rows, rejected = _accepted([lambda f=f: parse(f) for f in body["features"]])
    return rows, {"sourceRows": len(body["features"]), "rejected": rejected,
                  "coverageComplete": not bool(body.get("pagination", {}).get("next")),
                  "scope": "Active US weather alerts with source polygon only; zone-only alerts excluded."}


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


def plants(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    required = {"gppd_idnr", "name", "country", "latitude", "longitude", "capacity_mw", "primary_fuel", "owner", "source", "url"}
    if not required <= set(reader.fieldnames or []):
        raise ValueError("WRI plant schema changed")
    body = list(reader)

    def parse(item):
        capacity = float(item["capacity_mw"])
        if not math.isfinite(capacity) or capacity < 0:
            raise ValueError("Invalid generation capacity")
        return base("energy_wri_plants", item["gppd_idnr"], "energy", item["name"],
                    "https://datasets.wri.org/datasets/global-power-plant-database", stamp,
                    latitude=float(item["latitude"]), longitude=float(item["longitude"]), countryIso3=item["country"],
                    properties={"plantId": item["gppd_idnr"], "capacityMw": capacity,
                                "primaryFuel": item["primary_fuel"], "reportedOwner": item["owner"] or None,
                                "providerReferenceUrl": item["url"], "providerReferenceName": item["source"],
                                "geographicRole": "power_plant", "securityRelationship": None,
                                "databaseRelease": "v1.3.0 (2021); historical static reference"})

    rows, rejected = _accepted([lambda item=item: parse(item) for item in body])
    return rows, {"sourceRows": len(body), "rejected": rejected, "coverageComplete": True,
                  "scope": "WRI v1.3.0 static plant reference; reported owners are not verified listed issuers."}


def gdacs(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    if body.get("type") != "FeatureCollection" or not isinstance(body.get("features"), list):
        raise ValueError("Invalid GDACS collection")

    def parse(feature):
        props, geometry = feature["properties"], feature["geometry"]
        if geometry.get("type") != "Point" or len(geometry.get("coordinates", [])) != 2:
            raise ValueError("GDACS record has no supported point")
        lon, lat = geometry["coordinates"]
        if props["eventtype"] not in {"EQ", "TC", "FL", "VO", "WF", "DR"}:
            raise ValueError("Unexpected GDACS event type")
        if props["alertlevel"] not in {"Green", "Orange", "Red"}:
            raise ValueError("Unexpected GDACS alert level")
        observed = props["fromdate"]
        if datetime.fromisoformat(observed.replace("Z", "+00:00")).tzinfo is None:
            observed += "Z"
        modified = props.get("datemodified")
        if modified and datetime.fromisoformat(modified.replace("Z", "+00:00")).tzinfo is None:
            modified += "Z"
        url = props["url"]["report"]
        iso3 = props.get("iso3") or None
        role = props.get("Class") or "GDACS point"
        return base("world_gdacs_alerts", f"{props['eventtype']}:{props['eventid']}:{props['episodeid']}",
                    "hazards", props["name"] or props["description"], url, stamp,
                    latitude=lat, longitude=lon, countryIso3=iso3, observedAt=observed,
                    publishedAt=modified,
                    properties={"event": props["eventtype"], "severity": props["alertlevel"],
                                "sourceAgency": props.get("source"), "sourceRecordId": props.get("sourceid"),
                                "geographicRole": role, "gdacsAlertScore": props.get("alertscore"),
                                "coordinateMeaning": "GDACS representative point; not a verified impact footprint"})

    rows, rejected = _accepted([lambda feature=feature: parse(feature) for feature in body["features"]])
    return rows, {"sourceRows": len(body["features"]), "rejected": rejected,
                  "coverageComplete": len(body["features"]) < 100,
                  "scope": "Newest GDACS disaster-alert page across six event types; at most 100 rows, not the complete archive."}


def ports(payloads: list[bytes], stamp: str) -> tuple[list[dict], dict]:
    bodies = [json.loads(p) for p in payloads]
    if not bodies or any("error" in b or not isinstance(b.get("features"), list) for b in bodies):
        raise ValueError("Invalid ArcGIS ports response")
    if bodies[-1].get("exceededTransferLimit"):
        raise ValueError("Incomplete PortWatch pagination")
    if any(b.get("spatialReference", {}).get("wkid") != 4326 for b in bodies):
        raise ValueError("PortWatch coordinates must use EPSG:4326")
    features = [f for b in bodies for f in b["features"]]

    def parse(feature):
        a, g = feature["attributes"], feature["geometry"]
        return base("trade_portwatch_ports", a["portid"], "trade", a["fullname"],
                    "https://portwatch.imf.org/", stamp, latitude=g["y"], longitude=g["x"], countryIso3=a["ISO3"],
                    properties={"portId": a["portid"], "portName": a["portname"], "geographicRole": "port",
                                "locode": a.get("LOCODE"), "securityRelationship": None})

    rows, rejected = _accepted([lambda f=f: parse(f) for f in features])
    return rows, {"sourceRows": len(features), "rejected": rejected, "coverageComplete": True,
                  "scope": "PortWatch port reference layer only; not daily activity, ownership or issuer exposure."}
