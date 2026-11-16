#!/usr/bin/env python3
"""Validate the captured investor examples and prepare conditional database records.

No network or database writes. The resulting records belong only to shared,
explicitly fictional profiles/map examples and attributed public filing facts.
An operator must create them conditionally; this tool never overwrites a session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from aplomb.contracts.models import Profile
from aplomb.intelligence.investor_examples import (
    FILINGS_PARTITION,
    MAP_PARTITION,
    InvestorLocation,
    _read_capture,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/inputs/investor-examples"
# Exact, share-class-specific source ticker/CUSIP pairs. A same-name or related
# security (including a Canadian cross-listing) is not substituted.
PRICE_IDENTITIES = {
    "AAPL": "037833100", "AMZN": "023135106", "GOOGL": "02079K305",
    "MSFT": "594918104", "NVDA": "67066G104", "SPY": "78462F103",
    "JNJ": "478160104", "XOM": "30231G102", "PG": "742718109", "JPM": "46625H100",
}


def record(table: str, pk: str, sk: str, value: dict) -> dict:
    document = {"revision": 1, "value": value}
    if pk == "SHARED#PROFILES":
        document.update(profileId=value["profileId"], overlay=False)
    return {"table": table, "pk": pk, "sk": sk, "value": document}


def prepare(source: Path = SOURCE) -> list[dict]:
    records = []
    profiles = {}
    for value in json.loads((source / "profiles.json").read_text()):
        value["version"] = 1
        profile = Profile.model_validate(value)
        if not profile.is_default or not profile.portfolio.is_fictional:
            raise ValueError("shared examples must be fictional templates")
        if profile.profile_id in profiles:
            raise ValueError("duplicate profile")
        profiles[profile.profile_id] = profile
        records.append(record("profiles", "SHARED#PROFILES", f"PROFILE#{profile.profile_id}",
                              profile.to_wire()))
    if len(profiles) != 5:
        raise ValueError("exactly five fictional investor examples required")
    for value in json.loads((source / "locations.json").read_text())["investors"]:
        investor = InvestorLocation.model_validate(value)
        profile = profiles[investor.profile_id]
        if {w.account_id for w in investor.wallets} != {a.account_id for a in profile.accounts}:
            raise ValueError("wallet locations must correspond exactly to profile accounts")
        records.append(record("profiles", MAP_PARTITION, f"INVESTOR#{investor.profile_id}",
                              investor.model_dump(mode="json", by_alias=True)))
    metadata = json.loads((source / "filings/manifest.json").read_text())
    for item in metadata["records"]:
        raw = (source / "filings" / item["raw_data_file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["raw_data_sha256"]:
            raise ValueError("filing capture checksum mismatch")
        holdings = []
        for row in json.loads(raw)["data"]:
            ticker, issuer, share_class, cusip, value, weight, shares, principal, option = row
            holdings.append({
                "ticker": ticker or None, "issuer": issuer, "shareClass": share_class,
                "cusip": cusip, "valueUsd": value * 1000, "shares": shares,
                "principal": principal, "optionType": option, "sourceWeightPct": weight,
            })
        modeled = [
            h for h in holdings
            if h["ticker"] in PRICE_IDENTITIES
            and h["cusip"] == PRICE_IDENTITIES[h["ticker"]]
            and not h["optionType"] and h["valueUsd"] > 0
        ]
        filename = item["raw_data_file"].removesuffix("-data.json")
        capture = _read_capture({
            "filingId": f"{filename}-{item['report_date']}",
            "manager": item["manager"], "associatedPerson": item["associated_person_context"],
            "cik": item["cik"], "accession": item["accession"],
            "reportDate": item["report_date"], "filingDate": item["filing_date"],
            "retrievedAt": item["captured_no_later_than"].replace("+00:00", "Z"),
            "sourceUrl": item["source_page_url"], "secUrl": item["sec_index_url"],
            "sourceDataUrl": item["source_data_url"], "sourceSha256": item["raw_data_sha256"],
            "reportedValueUsd": item["manager_index_value_usd_thousands"] * 1000,
            "indexedLongValueUsd": item["non_option_sum_usd_thousands"] * 1000,
            "indexedAllValueUsd": item["all_row_sum_usd_thousands"] * 1000,
            "holdings": holdings, "modeledHoldings": modeled,
            "sourceKind": "third_party_indexed_transcription", "pointInTimeVerified": False,
            "limitations": [
                item["source_limitation"],
                "Manager association is context, not the named person's private holdings.",
                "Only exact source ticker/CUSIP pairs with available prices enter the comparison; "
                "uncovered long holdings and all options are excluded.",
                "Values are USD, converted from the index's thousands-of-dollars units. "
                "Indexed row totals and the source's aggregate may differ through rounding.",
                "The capture was retrieved after the price snapshot; comparison is retrospective "
                "and point-in-time availability is not verified.",
            ],
        })
        if len(holdings) != item["displayed_row_count"]:
            raise ValueError("filing row count mismatch")
        records.append(record("cache", FILINGS_PARTITION, f"FILING#{capture.filing_id}",
                              capture.model_dump(mode="json", by_alias=True)))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path,
                        default=ROOT / ".artifacts/investor-examples/seed-records.json")
    args = parser.parse_args()
    records = prepare(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"records": records}, ensure_ascii=False, indent=2) + "\n")
    print(f"Validated {len(records)} database records: {args.output}")


if __name__ == "__main__":
    main()
