"""Synthetic official-schema inputs; no live SEC integration asserted by these tests."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from aplomb.api.app import create_app
from aplomb.api.settings import Settings
from aplomb.api.storage import MemoryStore
from aplomb.research.company_detail import CompanyResearch, statements, submissions
from aplomb.research.core import ResearchError
from fastapi.testclient import TestClient

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
        return SimpleNamespace(canonical_url=url, text=text, content_hash=hashlib.sha256(text.encode()).hexdigest(),
                               retrieved_at=NOW, document_id="DOC-" + hashlib.sha256(text.encode()).hexdigest(),
                               run_id=context.run_id)


def test_session_owned_idempotent_capture_and_graceful_partial_failure():
    store = MemoryStore()
    provider = CompanyResearch(Captured(), store, clock=lambda: NOW)
    first = provider.detail("session-a", CIK)
    assert provider.detail("session-a", CIK) == first
    provider.detail("session-b", CIK)
    assert first["status"] == "available" and len(first["sources"]) == 2
    assert first["facts"][first["statements"][0]["fact_id"]]["verification"]["status"] == "verified"
    owner_a = "COMPANY#" + hashlib.sha256(b"session-a").hexdigest()
    owner_b = "COMPANY#" + hashlib.sha256(b"session-b").hexdigest()
    assert len(store.query("cache", owner_a)) == len(store.query("cache", owner_b)) == 2
    partial = CompanyResearch(Captured("companyfacts"), store, clock=lambda: NOW).detail("session-a", CIK)
    assert partial["status"] == "partial" and partial["company"]["filings"]
    assert "synthetic-test-secret" not in json.dumps(partial)


def test_http_exact_cik_and_region_boundaries_without_source_contact():
    with TestClient(create_app(Settings())) as client:
        headers = {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}
        response = client.get("/v1/research/company/320193", headers=headers)
        assert response.status_code == 503
        assert "contact" in response.text
        regional = client.get("/v1/research/company/320193?country=JPN", headers=headers)
        assert regional.status_code == 503 and "Regional" in regional.text
        assert client.get("/v1/research/company/320193").status_code == 422
