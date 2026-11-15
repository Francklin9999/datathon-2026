import pytest
from aplomb.api.errors import Conflict, NotFound, ServiceError
from aplomb.contracts.api import RebalanceRequest
from aplomb.optimizer.check import CheckServiceImpl

from tests.unit.profiles.test_profiles import CLOCK, A, B, service


def checks():
    profiles = service()
    return profiles, CheckServiceImpl(profiles, profiles.snapshot, clock=CLOCK)


def request(positions, **fields):
    return RebalanceRequest(profileId='robert', profileVersion=1,
        positions=[{'ticker': t, 'weightPct': w} for t, w in positions], **fields)


def test_complete_targets_support_reductions_removals_and_conserve_capital():
    profiles, engine = checks()
    before = profiles.get(A, 'robert')
    result = engine.rebalance(A, request([('SPY', 5), ('XBB.TO', 95)]))
    assert result.total_value == before.portfolio.total_value
    assert result.portfolio_before.total_value == result.portfolio_after.total_value
    assert {p.ticker: p.weight_pct for p in result.portfolio_after.positions} == {'SPY': 5, 'XBB.TO': 95}
    changes = {p.ticker: p for p in result.changes}
    old_spy = next(p.weight_pct for p in before.portfolio.positions if p.ticker == 'SPY')
    assert changes['SPY'].change_pct == pytest.approx(5 - old_spy)
    assert any(row.target_pct == 0 and row.change_pct < 0 for row in result.changes)
    assert sum(row.change_pct for row in result.changes) == pytest.approx(0, abs=1e-12)
    for check in result.rule_checks_after:
        assert all(fid in result.facts for fid in [check.value_fact_id, check.threshold_fact_id] if fid)
    assert profiles.get(A, 'robert') == before and profiles.get(B, 'robert') == before
    assert result.portfolio_before.variant == 'before' and result.portfolio_after.variant == 'target'


@pytest.mark.parametrize('positions', [[('SPY', 50)], [('SPY', 50), ('SPY', 50)]])
def test_incomplete_or_duplicate_targets_are_rejected(positions):
    _, engine = checks()
    with pytest.raises(ServiceError):
        engine.rebalance(A, request(positions))


def test_unknown_securities_and_stale_profile_versions_are_rejected():
    _, engine = checks()
    with pytest.raises(NotFound):
        engine.rebalance(A, request([('NOT-A-SECURITY', 100)]))
    body = request([('SPY', 100)]).model_copy(update={'profile_version': 999})
    with pytest.raises(Conflict):
        engine.rebalance(A, body)


def test_target_rebalance_does_not_claim_missing_esg_evidence_is_verified():
    profiles, engine = checks()
    profile = profiles.get(A, 'mateo')
    result = engine.rebalance(A, RebalanceRequest(profileId='mateo', profileVersion=1,
        positions=profile.portfolio.positions))
    evidence = next(row for row in result.rule_checks_after if row.rule_id == 'evidence.controversy')
    assert evidence.status == 'nee' and result.verdict_after == 'insufficient'
