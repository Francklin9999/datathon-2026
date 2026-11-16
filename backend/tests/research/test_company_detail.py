"""Synthetic official-schema inputs; no live SEC integration asserted by these tests."""

import hashlib
import json
from datetime import datetime, timezone

import pytest
from aplomb.api.storage import MemoryStore
from aplomb.research.company_detail import CompanyResearch, statements, submissions
from aplomb.research.core import FetchedDocument, ResearchError

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)
CIK = "0000320193"


def company():
    return {"cik": "320193", "name": "Synthetic issuer", "sicDescription": "Synthetic industry",
            "filings": {"recent": {"form": ["10-K", "4"], "accessionNumber": ["0000320193-26-000001", "0000320193-26-000002"],
            "filingDate": ["2026-11-01", "2026-11-16"], "reportDate": ["2026-09-30", "2026-11-13"],
            "primaryDocument": ["report.htm", "insider.xml"]}}}


def facts():
    return {"cik": 320193, "facts": {"us-gaap": {"Assets": {"units": {"USD": [
        {"val": 42, "end": "2026-09-30", "filed": "2026-11-01", "accn": "0000320193-26-000001", "form": "10-K"},
        {"val": 43, "end": "2026-09-30", "filed": "2026-11-16", "accn": "0000320193-26-000002", "form": "10-K/A"}]}}}}}


def test_reporting_period_does_not_admit_future_publication_or_revision():
    result = submissions(company(), CIK, "2026-11-15")
    assert len(result["filings"]) == 1
    assert result["filings"][0]["available_at"] == "2026-11-01T23:59:59Z"
    assert len(statements(facts(), CIK, "2026-11-15")) == 1
    assert statements(facts(), CIK, "2026-11-15")[0]["value"] == 42
    assert len(statements(facts(), CIK, "2026-11-16")) == 2


@pytest.mark.parametrize("mutation", ["cik", "future_period", "nan", "bool", "unsafe_accession"])
def test_invalid_structured_source_fails_closed(mutation):
    source = facts()
    row = source["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]
    if mutation == "cik":
        source["cik"] = 1
    elif mutation == "future_period":
        row["end"] = "2027-01-01"
    elif mutation == "nan":
        row["val"] = float("nan")
    elif mutation == "bool":
        row["val"] = True
    else:
        row["accn"] = "../../etc"
    with pytest.raises(ResearchError):
        statements(source, CIK, "2026-11-15")


class Captured:
    def __init__(self, failed=None):
        self.failed = failed

    def fetch(self, url, context):
        if self.failed and self.failed in url:
            raise ResearchError("Do not expose secret=synthetic-test-secret")
        text = json.dumps(company() if "submissions" in url else facts())
        digest = hashlib.sha256(text.encode()).hexdigest()
        return FetchedDocument(document_id="DOC-" + digest, run_id=context.run_id, canonical_url=url, redirects=(),
                               status=200, content_type="application/json", content_hash=digest, text=text,
                               retrieved_at=NOW)


def test_session_owned_idempotent_capture_and_graceful_partial_failure():
    store = MemoryStore()
    provider = CompanyResearch(Captured(), store, clock=lambda: NOW)
    first = provider.detail("session-a", CIK)
    assert provider.detail("session-a", CIK) == first
    provider.detail("session-b", CIK)
    assert first["status"] == "available" and len(first["sources"]) == 2
    texts = {json.dumps(company()), json.dumps(facts())}
    assert {source["captured_text_sha256"] for source in first["sources"]} == {
        hashlib.sha256(text.encode()).hexdigest() for text in texts}
    assert first["facts"][first["statements"][0]["fact_id"]]["verification"]["status"] == "verified"
    owner_a = "COMPANY#" + hashlib.sha256(b"session-a").hexdigest()
    owner_b = "COMPANY#" + hashlib.sha256(b"session-b").hexdigest()
    assert len(store.query("cache", owner_a)) == len(store.query("cache", owner_b)) == 2
    partial = CompanyResearch(Captured("companyfacts"), store, clock=lambda: NOW).detail("session-a", CIK)
    assert partial["status"] == "partial" and partial["company"]["filings"]
    assert "synthetic-test-secret" not in json.dumps(partial)
