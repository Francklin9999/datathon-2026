"""One bounded GDELT 2.0 Event/GKG update, consumed by saved world observations.

Run: python -m aplomb.world.providers.gdelt_extra
This captures machine-coded metadata only; publisher articles are not fetched.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .public import base
from .snapshot import DIRECTORY, canonical, publish, timestamp, validate_row

INDEX_URL = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
TERMS_URL = "https://www.gdeltproject.org/about.html"
GGG_INDEX_URL = "https://data.gdeltproject.org/gdeltv3/ggg/MASTERFILELIST.TXT"
ROW_CAP = 250
ARCHIVE_CAP = 5_000_000
EXPANDED_CAP = 15_000_000
KINDS = {
    "events": ("world_gdelt_event_metadata", ".export.CSV.zip", 61, ["SRC-116", "MASTER-043"]),
    "gkg": ("world_gdelt_gkg_locations", ".gkg.csv.zip", 27, ["SRC-117", "MASTER-043"]),
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("GDELT redirects are not permitted")


def fetch(url: str) -> bytes:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "data.gdeltproject.org"
            or parsed.username or parsed.port or parsed.query
            or not (parsed.path in {"/gdeltv2/lastupdate.txt", "/gdeltv3/ggg/MASTERFILELIST.TXT"}
                    or re.fullmatch(r"/gdeltv2/\d{14}\.(export\.CSV|gkg\.csv)\.zip", parsed.path)
                    or re.fullmatch(r"/gdeltv3/ggg/\d{8}\.ggg\.v1\.english\.json\.gz", parsed.path))):
        raise ValueError("Unexpected GDELT endpoint")
    request = urllib.request.Request(url, headers={
        "User-Agent": "AplombDatathon/1.0 (bounded GDELT metadata capture)",
        "Accept": "text/plain,application/zip",
    })
    started = time.monotonic()
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=20) as response:
        chunks, size = [], 0
        while True:
            chunk = response.read(min(65536, ARCHIVE_CAP + 1 - size))
            if not chunk:
                return b"".join(chunks)
            size += len(chunk)
            if size > ARCHIVE_CAP:
                raise ValueError("GDELT compressed payload exceeds cap")
            chunks.append(chunk)
            if time.monotonic() - started > 20:
                raise TimeoutError("GDELT read deadline exceeded")


def _stamp(value: str) -> str:
    return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid GDELT publisher URL")
    # This recorded publisher reference is never fetched or asserted verified.
    return value


def parse(kind: str, payload: bytes, stamp: str, batch: str, source_url: str) -> tuple[list[dict], dict]:
    dataset_id, _, width, _ = KINDS[kind]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        expected = batch + (".export.CSV" if kind == "events" else ".gkg.csv")
        if len(members) != 1 or members[0].filename != expected or members[0].file_size > EXPANDED_CAP:
            raise ValueError("Unexpected GDELT ZIP member or expanded size")
        content = archive.read(members[0])
    csv.field_size_limit(EXPANDED_CAP)
    records = list(csv.reader(io.StringIO(content.decode("utf-8")), delimiter="\t"))
    rows, seen, rejected, skipped, truncated = [], set(), 0, 0, 0
    for record in records:
        try:
            if len(record) != width:
                raise ValueError("GDELT column count mismatch")
            if kind == "events":
                if record[51] not in {"3", "4"}:
                    skipped += 1
                    continue
                key, location_name, country = record[0], record[52], record[53]
                if not key.isdigit() or not re.fullmatch(r"\d{2,4}", record[26]):
                    raise ValueError("Invalid event ID or CAMEO code")
                lat, lon = float(record[56]), float(record[57])
                added = _stamp(record[59])
                if record[59] != batch:
                    raise ValueError("Event indexing batch mismatch")
                observed = datetime.strptime(record[1], "%Y%m%d").date().isoformat()
                publisher = record[60]
                props = {
                    "globalEventId": key, "cameoEventCode": record[26],
                    "eventRootCode": record[28], "actionGeoType": int(record[51]),
                    "sourceLocationName": location_name, "sourceCountryFips": country,
                    "dateAdded": added, "sourcePublisherUrl": publisher,
                    "geographicRole": "machine_extracted_reported_action_location",
                    "temporalPrecision": "day; calendar date only",
                    "notVerifiedEvent": True,
                }
                title = f"GDELT machine-coded event {key}, CAMEO {record[26]}: {location_name}"
            else:
                if not record[0].startswith(batch + "-") or record[1] != batch or record[2] != "1":
                    raise ValueError("Unexpected GKG record identity or source collection")
                added, observed, publisher = _stamp(record[1]), None, record[4]
                locations = [location.split("#") for location in record[9].split(";") if location]
                locations = [location for location in locations if len(location) == 7 and location[0] in {"3", "4"}]
                if not locations:
                    skipped += 1
                    continue
                # One source-listed city/landmark per article is a deliberate
                # bounded sample; it is not the article's primary event location.
                location = locations[0]
                _, location_name, country, _, latitude, longitude, feature_id = location
                lat, lon = float(latitude), float(longitude)
                key = record[0] + ":" + feature_id
                props = {
                    "gkgRecordId": record[0], "sourceCollection": 1,
                    "sourceDomain": record[3], "sourcePublisherUrl": publisher,
                    "sourceLocationName": location_name, "sourceCountryFips": country,
                    "locationFeatureId": feature_id, "locationType": int(location[0]),
                    "themes": [theme for theme in record[7].split(";") if theme][:40],
                    "dateAdded": added, "geographicRole": "machine_extracted_article_location_mention",
                    "notVerifiedEvent": True,
                }
                title = f"GDELT news location mention: {location_name}"
            if timestamp(added) > timestamp(stamp) or (observed and observed > stamp[:10]):
                raise ValueError("Future GDELT date")
            _url(publisher)
            if key in seen:
                skipped += 1
                continue
            row = base(dataset_id, key, "news", title, source_url, stamp,
                       latitude=lat, longitude=lon, observedAt=observed, properties=props)
            validate_row(row)
            seen.add(key)
            if len(rows) < ROW_CAP:
                rows.append(row)
            else:
                truncated += 1
        except (ValueError, KeyError, TypeError, OverflowError):
            rejected += 1
    return rows, {"sourceRows": len(records), "rejected": rejected, "skipped": skipped,
        "truncated": truncated, "coverageComplete": False,
        "scope": f"One 15-minute {batch} GDELT update; first {ROW_CAP} valid city/landmark records. "
                 + ("One source-listed location per GKG article." if kind == "gkg" else "Action locations only.")}


def collect(directory: Path = DIRECTORY, fetcher=fetch, *, stamp: str | None = None) -> list[dict]:
    index = fetcher(INDEX_URL)
    entries = {}
    for line in index.decode("ascii").splitlines():
        size, md5, url = line.split()
        for kind, (_, suffix, _, _) in KINDS.items():
            if url.endswith(suffix):
                https_url = url.replace("http://", "https://", 1)
                match = re.fullmatch(r"https://data\.gdeltproject\.org/gdeltv2/(\d{14})" + re.escape(suffix), https_url)
                if not match or not re.fullmatch(r"[a-f0-9]{32}", md5) or not 0 < int(size) <= ARCHIVE_CAP:
                    raise ValueError("Invalid GDELT update index")
                entries[kind] = (int(size), md5, https_url, match[1])
    if set(entries) != set(KINDS) or len({entry[3] for entry in entries.values()}) != 1:
        raise ValueError("GDELT Event/GKG batch mismatch")
    captures = {}
    for kind, (size, md5, url, _) in entries.items():
        body = fetcher(url)
        if len(body) != size or hashlib.md5(body, usedforsecurity=False).hexdigest() != md5:
            raise ValueError("GDELT published archive size/checksum mismatch")
        captures[kind] = body
    stamp = stamp or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifests = []
    for kind, (dataset_id, _, _, source_ids) in KINDS.items():
        _, _, url, batch = entries[kind]
        rows, quality = parse(kind, captures[kind], stamp, batch, url)
        metadata = {
            "datasetId": dataset_id, "sourceIds": source_ids,
            "name": "GDELT 2.0 " + ("machine-coded Event metadata" if kind == "events" else "GKG news location mentions"),
            "sourceUrl": url, "retrievedAt": stamp,
            "licence": "GDELT released datasets: unlimited unrestricted academic, commercial and governmental use without fee; publisher content separate",
            "licenceUrl": TERMS_URL, "frequency": "One manually captured 15-minute update",
            "attribution": "Source: The GDELT Project; filtered metadata adapted by Aplomb.",
            "limitations": [
                "Bounded single-update sample; no continuous monitoring, complete world coverage or historical replay.",
                "Machine extraction can be wrong; these are reported event codes or article location mentions, not independently verified events.",
                "Only source city/landmark coordinates are mapped; no country/state centroid is treated as an event point.",
                "GDELT country codes are FIPS10-4, not ISO; no unverified country or issuer crosswalk is inferred.",
                "No publisher text, images, contextual snippets, personal-name matching or financial impact is presented.",
                "The source DATEADDED is indexing time, not article publication time; first proven application availability is retrieval.",
            ], **quality,
        }
        manifests.append(publish(directory, rows, metadata, [(INDEX_URL, index), (url, captures[kind])]))
    return manifests


def collect_geographic(directory: Path = DIRECTORY, fetcher=fetch, *, stamp: str | None = None) -> dict:
    """Retain a required-field projection; publisher snippets/images are omitted."""
    index = fetcher(GGG_INDEX_URL)
    day = (stamp or datetime.now(timezone.utc).isoformat())[:10].replace("-", "")
    candidates = []
    for line in index.decode("ascii").splitlines():
        match = re.fullmatch(r"https?://data\.gdeltproject\.org/gdeltv3/ggg/(\d{8})\.ggg\.v1\.english\.json\.gz", line)
        if match and match[1] < day:
            candidates.append((match[1], line.replace("http://", "https://", 1)))
    if not candidates:
        raise ValueError("No completed daily GDELT Geographic Graph file")
    source_day, url = max(candidates)
    original = fetcher(url)
    with gzip.GzipFile(fileobj=io.BytesIO(original)) as archive:
        expanded = archive.read(EXPANDED_CAP + 1)
    if len(expanded) > EXPANDED_CAP:
        raise ValueError("GDELT Geographic Graph expanded payload exceeds cap")
    stamp = stamp or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, projection, seen, rejected, skipped, truncated = [], [], set(), 0, 0, 0
    lines = expanded.decode("utf-8").splitlines()
    dataset_id = "world_gdelt_geographic_mentions"
    for line in lines:
        try:
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("Invalid Geographic Graph record")
            if item.get("GeoType") not in {"3", "4"}:
                skipped += 1
                continue
            source_time = item["DateTime"]
            if timestamp(source_time) > timestamp(stamp):
                raise ValueError("Future Geographic Graph date")
            _url(item["URL"])
            retained = {field: item.get(field) for field in
                        ("DateTime", "URL", "LangCode", "Location", "Lat", "Lon",
                         "CountryCode", "Adm1Code", "Adm2Code", "GeoType")}
            key = hashlib.sha256(canonical(retained)).hexdigest()[:24]
            if key in seen:
                skipped += 1
                continue
            props = {
                "sourcePublisherUrl": item["URL"], "sourceDateTime": source_time,
                "sourceLocationName": item["Location"], "sourceCountryFips": item["CountryCode"],
                "locationType": int(item["GeoType"]), "language": item.get("LangCode"),
                "geographicRole": "machine_extracted_article_location_mention",
                "notVerifiedEvent": True,
            }
            row = base(dataset_id, key, "news", f"GDELT Geographic Graph location mention: {item['Location']}",
                       url, stamp, latitude=item["Lat"], longitude=item["Lon"], properties=props)
            validate_row(row)
            seen.add(key)
            if len(rows) < ROW_CAP:
                rows.append(row)
                projection.append(retained)
            else:
                truncated += 1
        except (ValueError, KeyError, TypeError, OverflowError):
            rejected += 1
    metadata = {
        "datasetId": dataset_id, "sourceIds": ["MASTER-044"],
        "name": "GDELT Geographic Graph English news location mentions",
        "sourceUrl": url, "retrievedAt": stamp,
        "licence": "GDELT released datasets: unlimited unrestricted use without fee; retained metadata projection excludes publisher contextual snippets and images",
        "licenceUrl": TERMS_URL, "frequency": "One completed daily archive; bounded manual capture",
        "attribution": "Source: The GDELT Project, Global Geographic Graph; selected metadata adapted by Aplomb.",
        "originalSha256": hashlib.sha256(original).hexdigest(),
        "originalBytes": len(original), "retainedProjection": True,
        "sourceRows": len(lines), "rejected": rejected, "skipped": skipped, "truncated": truncated,
        "coverageComplete": False,
        "scope": f"First {ROW_CAP} valid unique city/landmark mentions in the {source_day} English daily archive.",
        "limitations": [
            "Daily English-language source sample; no complete global coverage or continuous monitoring.",
            "Machine-geocoded article mentions are not independently verified event locations or publisher locations.",
            "GDELT FIPS10-4 country codes are retained without an unverified ISO or issuer crosswalk.",
            "Publisher titles, snippets, images and full text are omitted from the retained capture and runtime.",
            "DateTime is retained as source metadata; no article publication timestamp is asserted.",
            "Current capture only; first proven application availability is retrieval, not historical replay.",
            "No company linkage, documented exposure or modeled financial impact.",
        ],
    }
    return publish(directory, rows, metadata, [(GGG_INDEX_URL, index), (url, canonical(projection))])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    parser.add_argument("--geographic", action="store_true", help="Capture daily Geographic Graph metadata instead")
    args = parser.parse_args()
    manifests = [collect_geographic(args.directory)] if args.geographic else collect(args.directory)
    print(json.dumps([{"version": m["dataVersion"], "rows": m["rowCount"]} for m in manifests], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
