"""Capture three published ClinicalTrials.gov studies with Canadian study locations.

Run: python -m aplomb.world.providers.trials_extra --directory PATH
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from .public import base
from .snapshot import publish, validate_row

DATASET_ID = "world_clinicaltrials_canada_study_locations"
DEFAULT_DIRECTORY = Path(__file__).resolve().parents[4] / "docs/evidence/parallel/agent-3/trials-extra/providers"
VERSION_URL = "https://clinicaltrials.gov/api/v2/version"
TERMS_URL = "https://clinicaltrials.gov/about-site/terms-conditions"
FIELDS = (
    "NCTId,BriefTitle,OverallStatus,StudyFirstPostDate,StudyFirstPostDateType,"
    "LastUpdatePostDate,LastUpdatePostDateType,StartDate,StartDateType,"
    "PrimaryCompletionDate,PrimaryCompletionDateType,CompletionDate,CompletionDateType,"
    "LocationFacility,LocationCity,LocationState,LocationCountry,LocationGeoPoint,LocationStatus"
)
DATA_URL = "https://clinicaltrials.gov/api/v2/studies?" + urlencode({
    "format": "json", "pageSize": 3, "query.locn": "Canada",
    "sort": "LastUpdatePostDate:desc", "fields": FIELDS,
})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected ClinicalTrials.gov redirect")


def fetch(url: str) -> bytes:
    if url not in {DATA_URL, VERSION_URL}:
        raise ValueError("Unexpected ClinicalTrials.gov request")
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "AplombDatathon/1.0 (bounded public research capture)",
    })
    for attempt in range(3):
        try:
            with opener.open(request, timeout=25) as response:
                size, chunks, started = 0, [], time.monotonic()
                while True:
                    chunk = response.read(min(65536, 500_001 - size))
                    if not chunk:
                        return b"".join(chunks)
                    size += len(chunk)
                    if size > 500_000:
                        raise ValueError("ClinicalTrials.gov payload exceeds byte cap")
                    chunks.append(chunk)
                    if time.monotonic() - started > 25:
                        raise TimeoutError("ClinicalTrials.gov read deadline exceeded")
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("ClinicalTrials.gov retries exhausted")


def _posted_date(value: dict) -> str:
    if not isinstance(value, dict) or value.get("type") != "ACTUAL":
        raise ValueError("Expected actual registry posting date")
    text = value.get("date")
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError("Expected day resolution registry posting date")
    date.fromisoformat(text)
    return text


def parse(payload: bytes, release: dict, stamp: str) -> tuple[list[dict], dict]:
    body = json.loads(payload)
    studies = body.get("studies")
    if not isinstance(studies, list) or not 1 <= len(studies) <= 3:
        raise ValueError("Unexpected ClinicalTrials.gov study count")
    rows, seen, locations_seen, excluded = [], set(), 0, 0
    for study in studies:
        protocol = study["protocolSection"]
        identity, status = protocol["identificationModule"], protocol["statusModule"]
        nct, title = identity["nctId"], identity["briefTitle"]
        if (not isinstance(nct, str) or not re.fullmatch(r"NCT\d{8}", nct)
                or nct in seen or not isinstance(title, str) or not title.strip()
                or not isinstance(status.get("overallStatus"), str)):
            raise ValueError("Invalid study identity or status")
        seen.add(nct)
        first = _posted_date(status["studyFirstPostDateStruct"])
        updated = _posted_date(status["lastUpdatePostDateStruct"])
        if first > updated or updated > stamp[:10]:
            raise ValueError("Invalid registry posting chronology")
        locations = protocol.get("contactsLocationsModule", {}).get("locations", [])
        if not isinstance(locations, list):
            raise ValueError("Invalid study location list")
        study_rows = 0
        for location in locations:
            locations_seen += 1
            if location.get("country") != "Canada":
                excluded += 1
                continue
            facility, city = location.get("facility"), location.get("city")
            if any(not isinstance(v, str) or not v.strip() for v in (facility, city)):
                raise ValueError("Canadian study location lacks facility or city")
            location_identity = {key: location.get(key) for key in ("facility", "city", "state", "country")}
            key = hashlib.sha256(json.dumps(location_identity, sort_keys=True).encode()).hexdigest()[:16]
            row = base(
                DATASET_ID, nct + ":" + key, "health", title,
                "https://clinicaltrials.gov/study/" + nct, stamp,
                countryIso3="CAN", properties={
                    "nctId": nct, "overallStatus": status["overallStatus"],
                    "studyFirstPostDate": first, "lastUpdatePostDate": updated,
                    "registryDateResolution": "day",
                    "startDate": status.get("startDateStruct"),
                    "primaryCompletionDate": status.get("primaryCompletionDateStruct"),
                    "completionDate": status.get("completionDateStruct"),
                    "facilityName": facility, "city": city, "state": location.get("state"),
                    "countryName": "Canada", "locationStatus": location.get("status"),
                    "geographicRole": "reported_study_location",
                    "sourceGeoPoint": location.get("geoPoint"),
                    "coordinateRole": "upstream location geocoding; facility precision unproven",
                    "dataProcessedAt": release["dataTimestamp"],
                    "attribution": "ClinicalTrials.gov, U.S. National Library of Medicine",
                },
            )
            # Registry geoPoints can be shared by distinct facilities in one city.
            # Keep them as source metadata instead of asserting facility coordinates.
            validate_row(row)
            rows.append(row)
            study_rows += 1
        if not study_rows:
            raise ValueError("Selected study has no explicit Canadian study location")
    return rows, {
        "sourceRows": len(studies), "sourceLocationRows": locations_seen,
        "excludedNonCanadianLocations": excluded, "rejected": 0,
        "coverageComplete": False,
        "scope": "One first page of at most three studies matching Canada, ordered by last registry update; Canadian locations only.",
    }


def collect(directory: Path = DEFAULT_DIRECTORY, fetcher=fetch) -> dict:
    before, payload, after = fetcher(VERSION_URL), fetcher(DATA_URL), fetcher(VERSION_URL)
    release = json.loads(before)
    if release != json.loads(after):
        raise ValueError("ClinicalTrials.gov release changed during capture")
    if (not isinstance(release.get("apiVersion"), str)
            or not isinstance(release.get("dataTimestamp"), str)):
        raise ValueError("Missing ClinicalTrials.gov processing timestamp")
    # Upstream timestamp has no timezone; retain verbatim without inventing one.
    datetime.fromisoformat(release["dataTimestamp"])
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, release, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-238"],
        "name": "ClinicalTrials.gov Canadian study locations, bounded registry sample",
        "sourceUrl": DATA_URL, "licenceUrl": TERMS_URL,
        "licence": "ClinicalTrials.gov Terms and Conditions; no-charge access and distribution subject to attribution and stated conditions; international and third-party copyright caveats",
        "attribution": "ClinicalTrials.gov, U.S. National Library of Medicine",
        "frequency": "Registry updated daily; this is a manually captured snapshot",
        "sourceRelease": release, "retrievedAt": stamp, **quality,
        "modifications": [
            "API projection retains only identifiers, brief titles, study status, study dates and location fields.",
            "Normalized rows expand studies into explicit Canadian locations, excluding other countries.",
            "Upstream geoPoints are retained as metadata; display coordinates are unset because facility precision is unproven.",
            "Registry posting dates retain day resolution; study date structures retain ACTUAL or ESTIMATED type.",
            "No contacts, emails, eligibility, interventions, outcomes, narratives, sponsors or company associations are selected.",
        ],
        "limitations": [
            "This frozen sample is not a complete or continuously current registry; consult linked live records for updates.",
            "Data processed date is the upstream version dataTimestamp, retained verbatim with unspecified timezone.",
            "Registry presence and reported status do not establish safety, efficacy, approval, ongoing operations or recruitment availability.",
            "Study titles and locations are submitter-reported registry metadata; no company or security inference is made.",
            "All selected studies may share an update date; upstream ordering within ties is not guaranteed.",
            "Original historical availability is unproven; availability is gated at capture, not registry posting or estimated study dates.",
            "ClinicalTrials.gov terms acknowledge international and third-party copyright; this capture is not labelled public domain or Creative Commons.",
        ],
    }
    return publish(directory, rows, metadata, [
        (VERSION_URL, before), (DATA_URL, payload), (VERSION_URL, after),
    ])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
