import math

import pytest
from aplomb.quant.metrics import historical_tail_pct, variance_shares_pct
from tests.unit.profiles.test_profiles import A, service


def test_discrete_loss_tail_has_known_boundary_and_mean():
    returns = [-i / 1000 for i in range(100)]
    var, es = historical_tail_pct(returns)
    assert var == pytest.approx(9.5)
    assert es == pytest.approx(9.7)
    assert historical_tail_pct([.01] * 100) == (0, 0)
    assert historical_tail_pct(returns[:99]) is None
    with pytest.raises(ValueError):
        historical_tail_pct([math.nan] * 100)


def test_perfectly_correlated_assets_have_weight_proportional_shares():
    assert variance_shares_pct([.25, .75], [[.01, -.02, .03], [.01, -.02, .03]]) == pytest.approx([25, 75])
    assert variance_shares_pct([1], [[0, 0, 0]]) is None
    with pytest.raises(ValueError):
        variance_shares_pct([.5, .5], [[.01], [.01, .02]])


def test_risk_service_returns_reproducible_claims_and_signed_shares():
    result = service().risk_diagnostics(A, 'robert', {'window': '1y'})
    assert result.metrics['risk.es95'].value >= result.metrics['risk.var95'].value >= 0
    assert sum(m.value for m in result.contributions.values()) == pytest.approx(100)
    for measurement in [*result.metrics.values(), *result.contributions.values()]:
        fact = result.facts[measurement.fact_id]
        assert fact.value == measurement.value
        assert fact.inputs and fact.sources
        assert fact.method.params['reportingCurrency'] == 'CAD'
