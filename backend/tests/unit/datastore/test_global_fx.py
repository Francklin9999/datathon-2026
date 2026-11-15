from pathlib import Path

import pytest
from aplomb.datastore.snapshot import LocalDataStore
from aplomb.quant import LocalLedger, MarketData, QuantEngine


def test_global_fx_cross_direction_and_temporal_availability(tmp_path):
    from aplomb.datastore.global_fx import materialize_pinned_global_fx
    reference = Path(__file__).resolve().parents[4] / 'data'
    materialize_pinned_global_fx(tmp_path, reference, 'snap-20261115-globalfx')
    snap = LocalDataStore(tmp_path).open('snap-20261115-globalfx')
    current = snap.gate(snap.data_as_of, 'current')
    market = MarketData(current, 'EUR')
    day = market.dates[-1]
    eur = current.global_fx('EUR').rows[-1]['cad_per_unit']
    gbp = current.global_fx('GBP').rows[-1]['cad_per_unit']
    assert market.conversion_at('GBP', 'EUR', day)[0] == pytest.approx(gbp / eur)
    assert market.conversion_at('EUR', 'GBP', day)[0] == pytest.approx(eur / gbp)
    assert snap.gate('2025-01-01', 'historical').global_fx('EUR').rows == ()
    # The snapshot observation date predates this capture. An explicit historical
    # cutoff equal to the snapshot end must not inherit current-mode availability.
    same_day = snap.gate(snap.data_as_of, 'historical').global_fx('EUR')
    assert same_day.rows == () and same_day.rows_withheld > 0
    assert market.conversion_at('ZZZ', 'EUR', day) is None
    ledger = LocalLedger()
    engine = QuantEngine(current, ledger, currency='EUR', subject_id='europe', created_at='2026-11-15T08:00:00Z')
    metric = engine.asset_metrics('SPY', {'code': '1y'})['return.period']
    assert metric.value is not None
    fact = ledger.get_fact(metric.fact_id)
    assert {s.dataset_id for s in fact.sources} >= {'fx_boc_global', 'fx_usdcad_daily'}
