"""Synthetic provider boundary tests; no external evidence is asserted here."""
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from aplomb.agents.bridges import (
    CandidateFinding,
    EventRelationship,
    candidate_priorities,
    event_hypotheses,
)
from aplomb.intelligence.entities import Evidence, Relationship


def test_candidates_require_verified_run_owned_facts():
    verified = SimpleNamespace(verification=SimpleNamespace(status="verified"))
    ledger = SimpleNamespace(export=lambda: SimpleNamespace(facts={"F-002": verified}))
    assert candidate_priorities(lambda *_: [CandidateFinding("risk", 75, ("F-002",))], None, None, ledger) == {"risk": 75}
    with pytest.raises(ValueError, match="foreign"):
        candidate_priorities(lambda *_: [CandidateFinding("risk", 75, ("F-001",))], None, None, ledger)


def test_event_hypothesis_requires_exact_direct_links_source_and_cutoff():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    src = Evidence(source_id="synthetic", url="https://example.org/evidence", content_sha256="a" * 64,
                   published_at=ts, available_at=ts, retrieved_at=ts, licence="synthetic")
    event = Relationship(subject_id="evt_1", relation="EVENT_REFERENCES_ENTITY", object_id="lei_issuer",
                         evidence_class="direct", valid_from=date(2026, 1, 1), evidence=src)
    issuer = Relationship(subject_id="listing_exact", relation="SECURITY_ISSUED_BY", object_id="lei_issuer",
                          evidence_class="direct", valid_from=date(2026, 1, 1), evidence=src)
    evidence = SimpleNamespace(url=src.url, retrieved_at="2026-01-01T00:00:00Z",
                               verification=SimpleNamespace(status="verified"))
    ledger = SimpleNamespace(export=lambda: SimpleNamespace(evidence={"E-001": evidence}))
    def provider(*_):
        return [EventRelationship(event, issuer, ("E-001",))]
    got = event_hypotheses(provider, SimpleNamespace(event_id="evt_1"), None, date(2026, 1, 2), ledger)
    assert got[0]["impact"] == "not_established"
    with pytest.raises(ValueError, match="cutoff"):
        event_hypotheses(provider, SimpleNamespace(event_id="evt_1"), None, date(2025, 12, 31), ledger)
    bad = issuer.model_copy(update={"object_id": "other_issuer"})
    with pytest.raises(ValueError, match="identity"):
        event_hypotheses(lambda *_: [EventRelationship(event, bad, ("E-001",))],
                         SimpleNamespace(event_id="evt_1"), None, date(2026, 1, 2), ledger)
    with pytest.raises(ValueError, match="verified"):
        event_hypotheses(lambda *_: [EventRelationship(event, issuer, ("E-999",))],
                         SimpleNamespace(event_id="evt_1"), None, date(2026, 1, 2), ledger)
