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
    # Real calculations now carry gated-series receipts and allocation assumptions.
    # Ledger verification follows those dependencies; no producer flag bypasses it.
    assert first.facts
    assert all(fact.verification.status == "verified" for fact in first.facts.values())
    vol = first.facts[metrics.fact_ids["vol.annualized"]]
    assert len(vol.inputs) == 2
    receipt = first.facts[vol.inputs[0]]
    assert receipt.sources and len(receipt.method.params["inputSha256"]) == 64
    assert receipt.n_obs > 1000
    assert first.facts[vol.inputs[1]].kind == "assumption"


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
    # Without input facts, a computed figure is verified only by dated sources of its own.
    for strip in ({"inputs": [], "sources": []}, {"inputs": [], "availableAt": None}):
        orphan = {**template, **strip, "subject": {**template["subject"], "variant": "orphan:" + "-".join(strip)},
                  "verification": {"status": "verified", "checks": []}}
        orphan.pop("id"), orphan.pop("key")
        assert ledger.get_fact(ledger.add_fact(orphan)).verification.status == "unverified"
