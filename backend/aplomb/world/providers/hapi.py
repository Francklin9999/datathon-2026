"""Bounded HAPI INFORM national risk capture using a locally supplied app identifier."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import DIRECTORY, publish, validate_row

DATASET_ID = "world_hapi_inform_risk_2025"
API_URL = "https://hapi.humdata.org/api/v2/coordination-context/national-risk"
HDX_URL = "https://data.humdata.org/api/action/package_show?id=f5ec2ee7-8a1b-49b4-864b-70bdb582a022"
GUIDE_URL = "https://hdx-hapi.readthedocs.io/en/latest/data_usage_guides/coordination_and_context/"
RESOURCE_ID = "11a789fc-e9b3-48c6-b1e6-260959799220"
HDX_DATASET_URL = "https://data.humdata.org/dataset/inform-risk-index"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _identifier() -> str:
    value = os.getenv("HAPI_APP_IDENTIFIER")
    if not value:
        path = Path.cwd() / ".env.world-data.local"
        if path.exists():
            for line in path.read_text().splitlines():
                if line.startswith("HAPI_APP_IDENTIFIER="):
                    value = line.split("=", 1)[1]
                    break
    if not value or not re.fullmatch(r"[A-Za-z0-9_.~%+=/-]{16,512}", value):
        raise ValueError("HAPI_APP_IDENTIFIER is missing or malformed")
    return value


def _fetch(url: str, *, limit: int) -> bytes:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AplombDatathon/1.0 bounded world capture"})
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=20) as response:
            payload = response.read(limit + 1)
            if response.status != 200 or len(payload) > limit:
                raise ValueError("HAPI capture response status or size is invalid")
            return payload
    except Exception:
        # urllib errors can include the query URL; the URL contains a credential.
        raise ValueError("HAPI capture request failed") from None


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    document = json.loads(payload)
    source_rows = document.get("data")
    if not isinstance(source_rows, list) or not 1 <= len(source_rows) < 250:
        raise ValueError("HAPI result is empty, malformed or may need pagination")
    result, seen = [], set()
    for item in source_rows:
        if not isinstance(item, dict) or item.get("resource_hdx_id") != RESOURCE_ID:
            raise ValueError("Unexpected HAPI source resource")
        code = item["location_code"]
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z]{3}", code) or code in seen:
            raise ValueError("Invalid or duplicate HAPI country")
        seen.add(code)
        if not (item["reference_period_start"].startswith("2025-01-01")
                and item["reference_period_end"].startswith("2025-12-31")):
            raise ValueError("Unexpected HAPI reference year")
        numbers = ("overall_risk", "hazard_exposure_risk", "vulnerability_risk",
                   "coping_capacity_risk", "meta_missing_indicators_pct",
                   "meta_avg_recentness_years")
        values = {key: float(item[key]) for key in numbers}
        if any(not math.isfinite(value) for value in values.values()):
            raise ValueError("Nonfinite HAPI risk value")
        if any(not 0 <= values[key] <= 10 for key in numbers[:4]):
            raise ValueError("HAPI risk score outside 0–10")
        if not 0 <= values["meta_missing_indicators_pct"] <= 1:
            raise ValueError("Invalid HAPI missing-indicator fraction")
        risk_class = str(item["risk_class"])
        rank = item["global_rank"]
        if risk_class not in {"1", "2", "3", "4", "5"} or not isinstance(rank, int) or rank < 1:
            raise ValueError("Invalid HAPI class or rank")
        row = base(
            DATASET_ID, code, "hazards", f"INFORM 2025 national humanitarian risk: {item['location_name']}",
            HDX_DATASET_URL, stamp, countryIso3=code, observedAt="2025-01-01",
            properties={
                "referenceYear": 2025, "referencePeriodEnd": "2025-12-31",
                "temporalPrecision": "annual; January 1 is a display anchor",
                "geographicRole": "national_composite_index_no_coordinate",
                "sourceCountryName": item["location_name"], "riskClass": risk_class,
                "globalRank": rank, "overallRisk": values["overall_risk"],
                "hazardExposureRisk": values["hazard_exposure_risk"],
                "vulnerabilityRisk": values["vulnerability_risk"],
                "copingCapacityRisk": values["coping_capacity_risk"],
                "missingIndicatorsFraction": values["meta_missing_indicators_pct"],
                "averageIndicatorRecentnessYears": values["meta_avg_recentness_years"],
                "sourceResourceId": RESOURCE_ID,
                "attribution": "Source: INFORM Risk Index, accessed through OCHA HDX HAPI; "
                               "selected and normalized by Aplomb. HDX dataset licence: CC BY.",
            },
        )
        validate_row(row)
        result.append(row)
    return result, {"sourceRows": len(source_rows), "rejected": 0, "coverageComplete": False,
                    "scope": f"All {len(source_rows)} returned country records from the 2025 INFORM Risk Index "
                             "resource; annual national composite scores, not disaster events or issuer risk."}


def collect(directory: Path = DIRECTORY) -> dict:
    identifier = _identifier()
    query = urllib.parse.urlencode({"app_identifier": identifier, "limit": 250, "offset": 0})
    payload = _fetch(f"{API_URL}?{query}", limit=1_000_000)
    rights = _fetch(HDX_URL, limit=500_000)
    guide = _fetch(GUIDE_URL, limit=500_000)
    rights_record = json.loads(rights)
    info = rights_record.get("result") or {}
    if not rights_record.get("success") or info.get("name") != "inform-risk-index" or info.get("license_id") != "cc-by":
        raise ValueError("INFORM dataset licence or identity changed")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = parse(payload, stamp)
    metadata = {
        "datasetId": DATASET_ID, "sourceIds": ["SRC-133"],
        "name": "INFORM Risk Index 2025 via OCHA HDX HAPI",
        "sourceUrl": HDX_DATASET_URL, "retrievedAt": stamp,
        "frequency": "Annual source, manual bounded capture",
        "attribution": rows[0]["properties"]["attribution"],
        "licence": info["license_title"], "licenceUrl": info["license_url"],
        "credentialMethod": "HAPI app identifier supplied locally; excluded from capture and manifest",
        "limitations": [
            "Annual national composite index, not a disaster event, forecast, issuer measure or financial risk score.",
            "Index components and ranks are source values; country records have no source point coordinates.",
            "191 source countries in this resource, not proof of complete global country coverage.",
            "Original historical availability is unproven; current capture gates replay.",
            "Linked INFORM resource update timestamps do not state a timezone and are not converted to publication instants.",
        ], **quality,
    }
    safe_url = API_URL + "?limit=250&offset=0&app_identifier=[redacted]"
    return publish(directory, rows, metadata, [(safe_url, payload), (HDX_URL, rights), (GUIDE_URL, guide)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    manifest = collect(args.directory)
    print(json.dumps({"version": manifest["dataVersion"], "rows": manifest["rowCount"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
