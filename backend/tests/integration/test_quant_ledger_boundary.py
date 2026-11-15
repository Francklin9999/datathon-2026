"""A real T05 calculation uses the T10 sink without bypassing provenance checks."""

from aplomb.ledger import Ledger
from aplomb.quant import QuantEngine
from tests.unit.datastore._support import starter_snapshot


def test_repeated_actual_quant_facts_keep_identity_and_honest_verification():
    ledger = Ledger("quant-integration", "2026-11-12", clock=lambda: "2026-11-14T23:00:00Z")
    engine = QuantEngine(
        starter_snapshot().gate("2026-11-12"),
        ledger,
        currency="CAD",
        subject_id="integration",
        created_at="2026-11-14T23:00:00Z",
    )
    metrics = engine.view({"SPY": 0.5, "XBB.TO": 0.5}, "before", 1000).metrics()
    first = ledger.export()
    again = engine.view({"SPY": 0.5, "XBB.TO": 0.5}, "before", 1000).metrics()
    assert metrics.fact_ids == again.fact_ids
    assert ledger.export().digest() == first.digest()
    assert abs(metrics.volatility_pct - 9.52506016903674) < 1e-9
    # Lineage, not a producer's declaration, verifies a fact: series figures cite dated dataset
    # rows; weight and concentration figures cite the stipulated portfolio composition.
    assert first.facts
    assert all(fact.verification.status == "verified" for fact in first.facts.values())
    by_metric = {fact.metric: fact for fact in first.facts.values()}
    assert by_metric["vol.annualized"].sources and by_metric["vol.annualized"].available_at
    composition = by_metric["value.portfolio"]
    assert composition.kind == "assumption" and by_metric["concentration.hhi"].inputs == [composition.id]


def test_a_declared_verified_flag_without_lineage_is_still_unverified():
    ledger = Ledger("quant-integration", "2026-11-12", clock=lambda: "2026-11-14T23:00:00Z")
    engine = QuantEngine(
        starter_snapshot().gate("2026-11-12"),
        ledger,
        currency="CAD",
        subject_id="integration",
        created_at="2026-11-14T23:00:00Z",
    )
    engine.view({"SPY": 0.5, "XBB.TO": 0.5}, "before", 1000).metrics()
    template = next(f for f in ledger.export().facts.values() if f.metric == "vol.annualized").to_wire()
    for strip in ({"sources": []}, {"availableAt": None}):
        orphan = {**template, **strip, "subject": {**template["subject"], "variant": "orphan:" + next(iter(strip))},
                  "verification": {"status": "verified", "checks": []}}
        orphan.pop("id"), orphan.pop("key")
        assert ledger.get_fact(ledger.add_fact(orphan)).verification.status == "unverified"
