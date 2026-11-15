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


def test_expanded_25_currency_snapshot_is_reproducible_and_preserves_parent(tmp_path):
    import gzip
    import json
    from decimal import Decimal

    from aplomb.datastore.global_fx import materialize_pinned_global_fx
    from aplomb.datastore.service import DatastoreService
    from aplomb.profiles.account_fx import convert_account_value, verify_account_valuation

    reference = Path(__file__).resolve().parents[4] / 'data'
    original_active = (reference / 'manifests' / 'active.json').read_bytes()
    version = 'snap-20261115-a1-fx-expanded'
    manifest = materialize_pinned_global_fx(tmp_path, reference, version)
    snapshot = LocalDataStore(tmp_path).open(version)
    currencies = DatastoreService(lambda: snapshot).reporting_currencies()
    assert len(currencies) == 25
    assert {'CAD', 'USD', 'CNY', 'INR', 'BRL', 'MXN', 'PLN', 'ZAR'} <= set(currencies)
    assert manifest['parentVersion'] == 'snap-20261114-sourced'
    source = json.loads(gzip.decompress((reference / 'inputs/global-fx-a1/boc-expanded-20261115.json.gz').read_bytes()))
    latest = next(row for row in reversed(source['observations']) if row['d'] == snapshot.data_as_of)
    # Independent decimal reference: reporting CNY per INR is CAD/INR divided by CAD/CNY.
    expected = Decimal(latest['FXINRCAD']['v']) / Decimal(latest['FXCNYCAD']['v'])
    receipt = convert_account_value(snapshot, 'INR', 100000, 'CNY', manifest['createdAt'])
    assert receipt.conversion_rate == pytest.approx(float(expected), rel=1e-12)
    assert receipt.reporting_value == pytest.approx(float(expected * 100000), rel=1e-12)
    assert verify_account_valuation(snapshot, receipt)
    assert snapshot.gate(snapshot.data_as_of, 'historical').global_fx('CNY').rows == ()
    assert (reference / 'manifests' / 'active.json').read_bytes() == original_active
    # Discontinued provider series are not advertised as current reporting coverage.
    assert not {'RUB', 'SAR', 'VND'} & set(currencies)
