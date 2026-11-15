import pytest
from aplomb.api.errors import NotFound
from aplomb.datastore.service import DatastoreService
from aplomb.quant import LocalLedger, QuantEngine
from tests.unit.datastore._support import starter_snapshot


def test_security_analytics_reproduce_quant_engine_and_resolve_every_metric_claim():
    service = DatastoreService(starter_snapshot)
    result = service.analytics('unused', 'SPY', {'currency': 'USD', 'window': '1y'})
    snap = starter_snapshot()
    engine = QuantEngine(snap.gate(snap.data_as_of, 'current'), LocalLedger(), currency='USD', subject_id='SPY', created_at='2026-11-15T00:00:00Z')
    expected = engine.asset_metrics('SPY', {'code': '1y'})
    for key, measurement in result.metrics.items():
        assert measurement.value == expected[key].value
        if measurement.value is not None:
            fact = result.facts[measurement.fact_id]
            assert fact.value == measurement.value
            assert 'currency:USD' in fact.key
            assert fact.sources


def test_unknown_instrument_is_not_mapped_to_another_market():
    with pytest.raises(NotFound):
        DatastoreService(starter_snapshot).analytics('unused', 'NOTREAL', {'currency': 'CAD'})


def test_custom_window_is_preserved():
    result = DatastoreService(starter_snapshot).analytics('unused', 'SPY', {'window': 'custom', 'start': '2024-01-01', 'end': '2025-01-01'})
    assert result.window.start == '2024-01-01'
    assert all(result.facts[m.fact_id].period.end <= '2025-01-01' for m in result.metrics.values() if m.fact_id)
