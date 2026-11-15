import pytest
from aplomb.api.errors import Conflict, NotFound
from aplomb.contracts import api as a

from tests.unit.profiles.test_profiles import A, B, service


def test_account_selection_and_value_weighted_aggregation_do_not_leak_sessions():
    svc = service()
    original = svc.get(A, 'robert')
    p = svc.create_account(A, 'robert', a.CreateAccountRequest(name='Growth', version=1,
        portfolio=a.InitialPortfolio(total_value=400000, positions=[{'ticker': 'SPY', 'weightPct': 100}])))
    assert p.active_account_id == p.accounts[1].account_id
    assert p.portfolio.total_value == 400000
    assert svc.get(B, 'robert').portfolio == original.portfolio
    with pytest.raises(NotFound):
        svc.select_account(B, 'robert', p.active_account_id, 1)
    aggregate = svc.select_account(A, 'robert', 'aggregate', p.version)
    assert aggregate.portfolio.total_value == 1000000
    weights = {x.ticker: x.weight_pct for x in aggregate.portfolio.positions}
    assert weights['SPY'] == pytest.approx(46)
    assert sum(weights.values()) == pytest.approx(100)
    assert aggregate.rules == p.rules
    restored = svc.select_account(A, 'robert', p.accounts[0].account_id, aggregate.version)
    assert restored.portfolio == original.portfolio
    assert len(restored.accounts) == 2


def test_stale_account_creation_and_aggregate_edits_are_rejected():
    svc = service()
    req = a.CreateAccountRequest(name='Growth', version=1,
        portfolio=a.InitialPortfolio(total_value=1000, positions=[{'ticker': 'SPY', 'weightPct': 100}]))
    p = svc.create_account(A, 'robert', req)
    with pytest.raises(Conflict):
        svc.create_account(A, 'robert', req)
    agg = svc.select_account(A, 'robert', 'aggregate', p.version)
    edit = a.UpdatePortfolioRequest(total_value=1000, positions=[{'ticker': 'SPY', 'weightPct': 100}], version=agg.version)
    with pytest.raises(Conflict):
        svc.set_portfolio(A, 'robert', edit, agg.version)


def test_account_edits_are_saved_when_switching_away_and_back():
    svc = service()
    p = svc.create_account(A, 'robert', a.CreateAccountRequest(name='Growth', version=1,
        portfolio=a.InitialPortfolio(total_value=1000, positions=[{'ticker': 'SPY', 'weightPct': 100}])))
    account_id = p.active_account_id
    edit = a.UpdatePortfolioRequest(total_value=2000, positions=[{'ticker': 'MSFT', 'weightPct': 100}], version=p.version)
    p = svc.set_portfolio(A, 'robert', edit, p.version)
    p = svc.select_account(A, 'robert', p.accounts[0].account_id, p.version)
    p = svc.select_account(A, 'robert', account_id, p.version)
    assert p.portfolio.total_value == 2000
    assert p.portfolio.positions[0].ticker == 'MSFT'
