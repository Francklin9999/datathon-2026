"""Pure provider parsers. Geographic precision and incomplete coverage remain explicit."""
from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, timezone
from urllib.parse import urlencode

from .snapshot import validate_row

AVIATION_URL = "https://aviationweather.gov/api/data/metar?ids=EGLL,LFPG,RJTT,YSSY,FAOR,OMDB&format=json"
NOAA_URL = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
POLICY_URL = "https://www.federalregister.gov/api/v1/documents.json?per_page=20&order=newest"
WRI_URL = "https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv"
GDACS_URL = "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/latest?eventlist=EQ;TC;FL;VO;WF;DR&alertlevel=Green;Orange;Red&pageSize=100&pageNumber=1"
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
