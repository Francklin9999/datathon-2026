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
    # The calculation is real, but its current producer does not register input
    # facts. A caller-supplied verified flag must not bypass T10's lineage check.
    assert first.facts
    assert all(fact.verification.status == "unverified" for fact in first.facts.values())
