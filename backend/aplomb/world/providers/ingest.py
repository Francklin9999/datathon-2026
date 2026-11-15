"""Bounded manual provider refresh, preserving prior content addressed captures.

Run: python -m aplomb.world.providers.ingest --source aviation --source noaa
Runtime APIs consume only saved snapshots. Each optional source failure is isolated.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from . import public
from .snapshot import DIRECTORY, publish
from .transport import Transport

SOURCES = {
    "aviation": {
        "datasetId": "world_aviation_weather", "sourceIds": ["SRC-216", "MASTER-070", "MASTER-099"],
        "name": "NOAA AviationWeather international METAR stations", "sourceUrl": public.AVIATION_URL,
        "licence": "NOAA/NWS public domain; attribution, no endorsement, modified data labeled",
        "licenceUrl": "https://www.weather.gov/disclaimer", "frequency": "current captured station observations",
        "limitations": ["Six selected stations; not global weather coverage or aircraft tracking.", "No historical vintages."],
        "parser": public.aviation,
    },
    "noaa": {
        "datasetId": "world_noaa_alerts", "sourceIds": ["SRC-176"],
        "name": "NOAA National Weather Service active alerts", "sourceUrl": public.NOAA_URL,
        "licence": "NOAA/NWS public domain; attribution, no endorsement, modified data labeled",
        "licenceUrl": "https://www.weather.gov/disclaimer", "frequency": "active alerts captured batch",
        "limitations": ["US only. Zone-only alerts without source polygons rejected.",
                        "Polygon display anchor is not an observed disaster epicenter.", "No historical vintages."],
        "parser": public.noaa,
    },
    "plants": {
        "datasetId": "energy_wri_plants", "sourceIds": ["SRC-196", "MASTER-083"],
        "name": "WRI Global Power Plant Database repository snapshot", "sourceUrl": public.WRI_URL,
        "licence": "CC BY 4.0; attribution World Resources Institute Global Power Plant Database, adapted by Aplomb",
        "licenceUrl": "https://creativecommons.org/licenses/by/4.0/", "frequency": "static; WRI maintenance ended 2022",
        "limitations": ["Repository CSV captured by hash; last named release v1.3.0, repository may differ.",
                        "Coordinates and reported owners can contain source matching errors.",
                        "Reported owner names do not establish security relationships.", "No historical vintages."],
        "parser": public.plants,
    },
    "policy": {
        "datasetId": "world_federal_register", "sourceIds": ["SRC-141"],
        "name": "US Federal Register document metadata", "sourceUrl": public.POLICY_URL,
        "licence": "US federal government metadata; public domain",
        "licenceUrl": "https://www.federalregister.gov/reader-aids/government-policy-and-ofr-procedures",
        "frequency": "newest twenty-document page captured batch",
        "limitations": ["Bounded recent page, incomplete history. Future-dated entries rejected.",
                        "National jurisdiction only; metadata has no source point.",
                        "Linked official PDF governs legal authority. No full text redistributed."],
        "parser": public.policy,
    },
    "gdacs": {
        "datasetId": "world_gdacs_alerts", "sourceIds": ["SRC-134", "SRC-175", "MASTER-068"],
        "name": "GDACS global disaster alerts", "sourceUrl": public.GDACS_URL,
        "licence": "European Commission/JRC owned metadata CC BY 4.0 with attribution and changes indicated; linked third-party material excluded",
        "licenceUrl": "https://commission.europa.eu/legal-notice_en#copyright-notice",
        "frequency": "newest 100 alert records per manual batch",
        "limitations": ["Bounded newest page; incomplete archive when 100 rows are returned.",
                        "Representative source coordinates are not disaster footprints or verified effects.",
                        "GDACS aggregates inputs from named agencies; linked third-party material is not copied.",
                        "No historical vintages; capture time is first proven availability."],
        "parser": public.gdacs,
    },
}


def collect(name: str, fetch, stamp: str | None = None, directory: Path = DIRECTORY) -> dict:
    source = SOURCES[name]
    url = source["sourceUrl"]
    if name == "policy":
        day = stamp[:10] if stamp else datetime.now(timezone.utc).date().isoformat()
        url += "&" + urlencode({"conditions[publication_date][lte]": day})
    payload = fetch(url)
    if stamp is None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = source["parser"](payload, stamp)
    metadata = {key: value for key, value in source.items() if key != "parser"}
    return publish(directory, rows, {**metadata, **quality, "sourceUrl": url, "retrievedAt": stamp}, [(url, payload)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", choices=sorted(SOURCES), action="append", required=True)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    transport, results, failures = Transport(), [], False
    for name in dict.fromkeys(args.source):
        try:
            manifest = collect(name, transport, directory=args.directory)
            results.append({"source": name, "status": "captured", "version": manifest["dataVersion"], "rows": manifest["rowCount"]})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            failures = True
            results.append({"source": name, "status": "failed", "error": str(exc)})
    print(json.dumps(results, indent=2))
    return int(failures)


if __name__ == "__main__":
    raise SystemExit(main())
