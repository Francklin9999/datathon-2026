"""Conservative source-backed geographic relationships for world observations.

These edges describe only the documented geographic role. They do not imply
facility ownership, securities identity, revenue geography or a price effect.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone

from aplomb.intelligence.entities import Evidence, Relationship


def _stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Source timestamp must have timezone")
    return parsed.astimezone(timezone.utc)


def _evidence(source_id: str, url: str, row: dict, retrieved_at: str, licence: str,
              observed_at: str | None = None, published_at: str | None = None) -> Evidence:
    retrieved = _stamp(retrieved_at)
    published = _stamp(published_at) if published_at else None
    return Evidence(
        source_id=source_id,
        url=url,
        # This is the exact normalized record hash. It is not claimed to be the
        # original remote document hash.
        content_sha256=hashlib.sha256(json.dumps(
            row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        observed_at=_stamp(observed_at) if observed_at else None,
        published_at=published,
        available_at=retrieved,
        retrieved_at=retrieved,
        licence=licence,
        limitations=("Hash identifies the normalized capture row, not the remote document.",
                     "Geographic relationship alone establishes no issuer or financial exposure."),
    )


def event_geography(event: dict, provenance: dict) -> Relationship | None:
    """EVENT_OCCURRED_AT to a source-supported country or point, if one exists."""
    location = event["location"]
    lat, lon = location.get("lat"), location.get("lon")
    country = location.get("countryIso3")
    if location["precision"] == "point" and lat is not None and lon is not None:
        # Coordinates are source observations; fixed decimals here are a stable
        # identifier, while the event row retains the original coordinate values.
        target = f"point:{lat:.6f},{lon:.6f}"
    elif country:
        target = f"country:{country}"
    else:
        return None
    primary = event["sources"][0]
    evidence = _evidence(
        event["datasetId"], primary["url"], event, provenance["retrievedAt"],
        provenance["licence"], event["occurredAt"] + "T00:00:00Z", primary.get("publishedAt"),
    )
    return Relationship(
        subject_id=event["eventId"], relation="EVENT_OCCURRED_AT", object_id=target,
        evidence_class="direct", valid_from=date.fromisoformat(event["occurredAt"]),
        evidence=evidence,
    )


def facility_geography(facility: dict, manifest: dict) -> Relationship:
    """FACILITY_LOCATED_IN country from a checksum-verified registry row."""
    evidence = _evidence(
        manifest["datasetId"], facility["sourceUrl"], facility, manifest["capturedAt"],
        manifest["licence"], f"{facility['reportingYear']}-12-31T00:00:00Z",
    )
    return Relationship(
        subject_id=facility["facilityId"], relation="FACILITY_LOCATED_IN",
        object_id=f"country:{facility['countryIso3']}", evidence_class="direct",
        valid_from=date(facility["reportingYear"], 1, 1), evidence=evidence,
    )
