import math
from pathlib import Path

import pytest
from aplomb.api.errors import ServiceError
from aplomb.contracts import api as a
from aplomb.datastore.global_fx import materialize_pinned_global_fx
from aplomb.datastore.snapshot import LocalDataStore
from aplomb.profiles.service import ProfileServiceImpl

from tests.unit.profiles.test_profiles import CLOCK, A, B, create_request, make_repo


@pytest.fixture(scope='module')
def snapshot(tmp_path_factory):
    root = tmp_path_factory.mktemp('account-fx')
    reference = Path(__file__).resolve().parents[4] / 'data'
    materialize_pinned_global_fx(root, reference, 'snap-20261115-globalfx')
    return LocalDataStore(root).open('snap-20261115-globalfx')


def test_native_capital_uses_documented_direction_and_aggregate_is_base_currency(snapshot):
    svc = ProfileServiceImpl(make_repo(), lambda: snapshot, clock=CLOCK)
    p = svc.create(A, a.CreateProfileRequest.model_validate(create_request(reportingCurrency='GBP')))
    p = svc.create_account(A, p.profile_id, a.CreateAccountRequest(name='US account', version=p.version, currency='USD',
        portfolio={'totalValue': 1000, 'positions': [{'ticker': 'MSFT', 'weightPct': 100}]}))
    gate = snapshot.gate(snapshot.data_as_of)
    expected = 1000 * gate.fx(None, None).rows[-1]['usdcad'] / gate.global_fx('GBP').rows[-1]['cad_per_unit']
    account = p.accounts[-1]
    receipt = account.native_valuation
    assert account.portfolio.currency == p.reporting_currency == 'GBP'
    assert receipt.native_currency == 'USD' and receipt.native_value == 1000
    assert receipt.reporting_value == pytest.approx(expected)
    assert account.portfolio.total_value == pytest.approx(expected)
    assert {q.source.dataset_id for q in receipt.quotes} == {'fx_usdcad_daily', 'fx_boc_global'}
    assert all(q.source.data_version == snapshot.data_version for q in receipt.quotes)
    assert all(q.observed_on <= snapshot.data_as_of for q in receipt.quotes)
    aggregate = svc.select_account(A, p.profile_id, 'aggregate', p.version)
    assert aggregate.portfolio.total_value == pytest.approx(1000 + expected)
    weights = {row.ticker: row.weight_pct for row in aggregate.portfolio.positions}
    assert weights['MSFT'] == pytest.approx(expected / (1000 + expected) * 100)
    assert math.fsum(weights.values()) == pytest.approx(100)
    assert all(row.profile_id != p.profile_id for row in svc.list(B))
    restored = svc.select_account(A, p.profile_id, account.account_id, aggregate.version)
    assert restored.portfolio.total_value == pytest.approx(expected)
    assert restored.accounts[-1].native_valuation == receipt
    duplicate = svc.duplicate(A, p.profile_id)
    assert duplicate.accounts[-1].account_id != account.account_id
    assert duplicate.accounts[-1].native_valuation == receipt


def test_editing_base_capital_replaces_receipt_instead_of_silently_rewriting_native_input(snapshot):
    svc = ProfileServiceImpl(make_repo(), lambda: snapshot, clock=CLOCK)
    p = svc.create_account(A, 'robert', a.CreateAccountRequest(name='Japan', version=1, currency='JPY',
        portfolio={'totalValue': 100000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}))
    account_id = p.active_account_id
    assert p.accounts[-1].native_valuation.native_currency == 'JPY'
    p = svc.set_portfolio(A, 'robert', a.UpdatePortfolioRequest(version=p.version, totalValue=2000,
        positions=[{'ticker': 'SPY', 'weightPct': 100}]), p.version)
    assert p.accounts[-1].native_valuation is None and p.accounts[-1].portfolio.total_value == 2000
    p = svc.select_account(A, 'robert', p.accounts[0].account_id, p.version)
    p = svc.select_account(A, 'robert', account_id, p.version)
    assert p.portfolio.total_value == 2000 and p.accounts[-1].native_valuation is None


def test_unavailable_fx_rejects_entire_creation_without_changing_profile(snapshot):
    svc = ProfileServiceImpl(make_repo(), lambda: snapshot, clock=CLOCK)
    before = svc.get(A, 'robert')
    with pytest.raises(ServiceError, match='No sourced') as error:
        svc.create_account(A, 'robert', a.CreateAccountRequest(name='Unknown FX', version=before.version, currency='ZZZ',
            portfolio={'totalValue': 1000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}))
    assert error.value.code == 'insufficient_data'
    assert svc.get(A, 'robert') == before


def test_independent_receipt_checks_reject_precise_sabotage(snapshot):
    from aplomb.profiles.account_fx import convert_account_value, verify_account_valuation
    receipt = convert_account_value(snapshot, 'JPY', 100000, 'GBP', '2026-11-15T00:00:00Z')
    assert 'ACCOUNT_FX_SOURCE_ROW' in receipt.verified_checks
    with pytest.raises(ValueError, match='ACCOUNT_FX_DIRECTION'):
        verify_account_valuation(snapshot, receipt.model_copy(update={'conversion_rate': 1 / receipt.conversion_rate}))
    with pytest.raises(ValueError, match='ACCOUNT_FX_MULTIPLICATION'):
        verify_account_valuation(snapshot, receipt.model_copy(update={'reporting_value': receipt.reporting_value + 1}))
    quotes = list(receipt.quotes)
    quotes[0] = quotes[0].model_copy(update={'cad_per_unit': quotes[0].cad_per_unit * 2})
    with pytest.raises(ValueError, match='ACCOUNT_FX_SOURCE_ROW'):
        verify_account_valuation(snapshot, receipt.model_copy(update={'quotes': quotes}))


def test_aggregate_extreme_values_fail_without_corrupting_account_state(snapshot):
    svc = ProfileServiceImpl(make_repo(), lambda: snapshot, clock=CLOCK)
    p = svc.create_account(A, 'robert', a.CreateAccountRequest(name='Large 1', version=1,
        portfolio={'totalValue': 1e308, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}))
    p = svc.create_account(A, 'robert', a.CreateAccountRequest(name='Large 2', version=p.version,
        portfolio={'totalValue': 1e308, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}))
    with pytest.raises(ServiceError, match='finite range'):
        svc.select_account(A, 'robert', 'aggregate', p.version)
    assert svc.get(A, 'robert') == p


def test_receipt_source_metadata_cannot_substitute_an_unrelated_source(snapshot):
    from aplomb.profiles.account_fx import convert_account_value, verify_account_valuation
    receipt = convert_account_value(snapshot, 'JPY', 1000, 'CAD', '2026-11-15T00:00:00Z')
    bad_source = receipt.quotes[0].source.model_copy(update={'source_url': 'https://example.org/unrelated'})
    bad_quote = receipt.quotes[0].model_copy(update={'source': bad_source})
    with pytest.raises(ValueError, match='ACCOUNT_FX_SOURCE_METADATA'):
        verify_account_valuation(snapshot, receipt.model_copy(update={'quotes': [bad_quote]}))
    identity = convert_account_value(snapshot, 'CAD', 1000, 'CAD', '2026-11-15T00:00:00Z')
    assert 'ACCOUNT_FX_SOURCE_ROW' not in identity.verified_checks
    assert identity.reporting_value == 1000 and not identity.quotes
