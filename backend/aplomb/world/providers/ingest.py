"""Bounded manual provider refresh, preserving prior content addressed captures.

Run: python -m aplomb.world.providers.ingest --source policy --source power
Runtime APIs consume only saved snapshots. Each optional source failure is isolated.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from . import (
    audit_extra,
    climate_trace_extra,
    crossref_extra,
    earthdata_extra,
    fda_extra,
    feeds_extra,
    ilo_extra,
    official_macro,
    public,
    recent_changes_extra,
    wgi_extra,
)
from .snapshot import DIRECTORY, publish
from .transport import Transport

SOURCES = {
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
    "power": {
        "datasetId": "world_nasa_power", "sourceIds": ["SRC-185", "MASTER-073"],
        "name": "NASA POWER daily gridded temperature sample", "sourceUrl": public.POWER_URL,
        "licence": "NASA United States Government data; source attribution NASA POWER",
        "licenceUrl": "https://power.larc.nasa.gov/docs/services/api/",
        "frequency": "fixed October 2026 daily period; manually captured",
        "limitations": ["Six requested grid points only; not worldwide spatial coverage or station measurements.",
                        "Daily API dates use local solar time; rendered midnight UTC is a date anchor, not an exact measurement time.",
                        "Temperature comes from the source model; no historical publication vintage is known."],
        "parser": public.power,
    },
    "epa": {
        "datasetId": "world_epa_sems_sites", "sourceIds": ["SRC-219", "MASTER-092"],
        "name": "EPA Envirofacts SEMS site reference sample", "sourceUrl": public.EPA_BASE,
        "licence": "EPA-produced geospatial data generally public domain unless otherwise specified; EPA attribution",
        "licenceUrl": "https://www.epa.gov/web-policies-and-procedures/epa-disclaimers",
        "frequency": "first 200 site records per selected state; manual capture",
        "limitations": ["Only six US states and the first 200 source rows in each; not full registry coverage.",
                        "Records without source coordinates are excluded. Site status is retained as source text.",
                        "A SEMS listing is not an emissions measurement, current contamination finding, or issuer relationship.",
                        "No source observation timestamp or historical vintage; capture time is first proven availability."],
        "parser": public.epa,
    },
}


def collect(name: str, fetch, stamp: str | None = None, directory: Path = DIRECTORY) -> dict:
    source = SOURCES[name]
    url = source["sourceUrl"]
    if name == "policy":
        day = stamp[:10] if stamp else datetime.now(timezone.utc).date().isoformat()
        url += "&" + urlencode({"conditions[publication_date][lte]": day})
    if name == "power":
        captures = [(public.power_url(lat, lon), fetch(public.power_url(lat, lon)))
                    for _, lat, lon, _ in public.POWER_POINTS]
    elif name == "epa":
        captures = [(public.epa_url(state), fetch(public.epa_url(state))) for state in public.EPA_STATES]
    else:
        payload = fetch(url)
        captures = [(url, payload)]
    if stamp is None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows, quality = source["parser"](captures if name in {"power", "epa"} else payload, stamp)
    metadata = {key: value for key, value in source.items() if key != "parser"}
    return publish(directory, rows, {**metadata, **quality, "sourceUrl": url, "retrievedAt": stamp}, captures)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", choices=sorted(SOURCES) + ["ecb", "statcan_cpi", "climate_trace", "fda", "crossref", "wgi",
                                                               "earthdata", "ecb_sdmx", "bis_sdmx", "fed_chargeoffs",
                                                               "wikipedia_recent_changes", "ilo"],
                        action="append", required=True)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    transport, results, failures = Transport(), [], False
    for name in dict.fromkeys(args.source):
        try:
            if name == "ecb":
                manifest = feeds_extra.collect(name, directory=args.directory)
            elif name == "ilo":
                manifest = ilo_extra.collect(directory=args.directory)
            elif name == "statcan_cpi":
                manifest = audit_extra.collect(args.directory)
            elif name == "climate_trace":
                manifest = climate_trace_extra.collect(directory=args.directory)
            elif name == "fda":
                manifest = fda_extra.collect(directory=args.directory)
            elif name == "crossref":
                manifest = crossref_extra.collect(directory=args.directory)
            elif name == "wgi":
                manifest = wgi_extra.collect(directory=args.directory)
            elif name in {"ecb_sdmx", "bis_sdmx", "fed_chargeoffs"}:
                manifest = official_macro.collect(
                    {"ecb_sdmx": "ecb", "bis_sdmx": "bis", "fed_chargeoffs": "fed"}[name],
                    directory=args.directory,
                )
            elif name == "earthdata":
                manifest = earthdata_extra.collect(directory=args.directory)
            elif name == "wikipedia_recent_changes":
                manifest = recent_changes_extra.collect(directory=args.directory)
            else:
                manifest = collect(name, transport, directory=args.directory)
            results.append({"source": name, "status": "captured", "version": manifest["dataVersion"], "rows": manifest["rowCount"]})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            failures = True
            results.append({"source": name, "status": "failed", "error": str(exc)})
    print(json.dumps(results, indent=2))
    return int(failures)


if __name__ == "__main__":
    raise SystemExit(main())
