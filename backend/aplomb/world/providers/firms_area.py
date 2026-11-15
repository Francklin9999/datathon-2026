"""Capture a bounded FIRMS area API response without recording its credential."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .hazards_remaining import NASA_TERMS, _NoRedirect, fetch, firms
from .snapshot import DIRECTORY, publish

DATASET = "world_firms_modis_australia_area"
AREA_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/"
# A bounded continental Australia window, which also includes nearby ocean and islands.
BOUNDS = (112, -44, 154, -10)


def collect(directory: Path = DIRECTORY) -> dict:
    key_file = os.environ.get("FIRMS_MAP_KEY_FILE")
    key = Path(key_file).read_text().strip() if key_file else os.environ.get("FIRMS_MAP_KEY", "")
    if not re.fullmatch(r"[A-Za-z0-9]{32}", key):
        raise ValueError("FIRMS_MAP_KEY must contain a 32-character map key")
    bounds = ",".join(map(str, BOUNDS))
    url = f"{AREA_URL}csv/{key}/MODIS_NRT/{bounds}/1"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AplombDatathon/1.0 (bounded area capture)"})
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=25) as response:
            payload = response.read(500001)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        # urllib exceptions can contain the complete URL, including the map key.
        raise RuntimeError("FIRMS area request failed; check the key and service availability") from None
    if len(payload) > 500000:
        raise ValueError("FIRMS area payload exceeds byte cap")
    if key.encode() in payload:
        raise ValueError("FIRMS response contains the credential")
    rights = fetch(NASA_TERMS)
    if b"Creative Commons Zero" not in rights:
        raise ValueError("NASA open-data licence guidance changed")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = firms(payload, stamp, DATASET)
    if any(not (BOUNDS[0] <= row["longitude"] <= BOUNDS[2] and BOUNDS[1] <= row["latitude"] <= BOUNDS[3])
           for row in rows):
        raise ValueError("FIRMS detection outside requested bounding box")
    metadata = {
        "datasetId": DATASET, "sourceIds": ["SRC-174", "MASTER-067"],
        "name": "NASA FIRMS MODIS Australia area thermal detections",
        "licence": "NASA-led Terra/Aqua mission data: CC0 under NASA Earthdata guidance unless marked restricted; no restriction in selected CSV",
        "licenceUrl": NASA_TERMS,
        "attribution": "NASA FIRMS / LANCE, MODIS Collection 6.1 Terra and Aqua near-real-time active-fire data; no NASA endorsement",
        "sourceUrl": AREA_URL,
        "requestParameters": {"source": "MODIS_NRT", "boundsWestSouthEastNorth": list(BOUNDS), "dayRange": 1},
        "frequency": "Manual bounded current capture",
        "retrievedAt": stamp,
        **quality,
        "scope": "FIRMS area API MODIS NRT detections for one day in the 112,-44,154,-10 bounding box; captured feed only.",
        "limitations": [
            "One bounded Australia-area request for the most recent one-day interval; the box includes ocean and nearby islands.",
            "Clouds, orbital revisit and sensor resolution limit detection coverage; thermal anomalies may include industrial heat or volcanoes.",
            "Coordinates are satellite pixel centers, not confirmed wildfire locations or fire boundaries.",
            "Fire radiative power is instantaneous, not damage, area burned or financial loss.",
            "Near-real-time detections can be replaced by later products; replay is gated at capture and issuer exposure is not established.",
            "The area API requires a MAP_KEY; the credential is excluded from capture metadata and raw evidence.",
        ],
    }
    return publish(directory, rows, metadata, [(AREA_URL, payload), (NASA_TERMS, rights)])


if __name__ == "__main__":
    result = collect()
    print(json.dumps({"version": result["dataVersion"], "rows": result["rowCount"]}))
