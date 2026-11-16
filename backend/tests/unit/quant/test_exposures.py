from datetime import date, datetime, timezone

import pytest
from aplomb.intelligence.entities import Evidence
from aplomb.quant.exposures import (
    FundConstituent,
    FundSnapshot,
    Sensitivity,
    Shock,
    disclosed_overlap,
    linear_shock,
    look_through,
)
from aplomb.quant.metrics import (
    compound,
    max_drawdown_pct,
    simple_returns,
    worst_rolling_return_pct,
)
from aplomb.quant.scenario_api import router
from fastapi import FastAPI
from fastapi.testclient import TestClient

APPLE = 'US0378331005'
MICROSOFT = 'US5949181045'
SPY = 'US78462F1030'
IVV = 'US4642872000'


def evidence():
    return Evidence(source_id='fixture', url='https://example.com/holdings.csv', content_sha256='a' * 64,
                    available_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
                    retrieved_at=datetime(2024, 1, 6, tzinfo=timezone.utc), licence='synthetic fixture')


def fund(isin, rows):
    return FundSnapshot(isin, date(2024, 1, 4), evidence(),
                        tuple(FundConstituent(key, value) for key, value in rows))


def test_fund_lookthrough_conserves_unreported_and_combines_exact_isin():
    spy = fund(SPY, [(APPLE, .4), (MICROSOFT, .2)])
    ivv = fund(IVV, [(APPLE, .3), (MICROSOFT, .1)])
    result = look_through({SPY: .5, IVV: .3, APPLE: .2}, {SPY: spy, IVV: ivv}, date(2024, 1, 6))
    assert result.direct[APPLE] == .2
    assert result.indirect[APPLE] == pytest.approx(.29)
    assert result.indirect[MICROSOFT] == pytest.approx(.13)
    assert result.unresolved_weight == pytest.approx(.38)
    assert sum(result.direct.values()) + sum(result.indirect.values()) + result.unresolved_weight == pytest.approx(1)
    assert disclosed_overlap(spy, ivv, date(2024, 1, 6)) == pytest.approx(.4)


def test_fund_temporal_visibility_and_malformed_disclosure():
    snapshot = fund(SPY, [(APPLE, .4)])
    with pytest.raises(ValueError, match='visible'):
        look_through({SPY: 1}, {SPY: snapshot}, date(2024, 1, 5), historical=True)
    assert look_through({SPY: 1}, {SPY: snapshot}, date(2024, 1, 5)).unresolved_weight == pytest.approx(.6)
    with pytest.raises(ValueError, match='duplicate'):
        fund(SPY, [(APPLE, .4), (APPLE, .2)])
    with pytest.raises(ValueError, match='exceed'):
        fund(SPY, [(APPLE, .9), (MICROSOFT, .2)])
    with pytest.raises(ValueError, match='ISIN'):
        FundConstituent('SPY', 1)


def test_first_order_shocks_and_missing_inputs():
    shock = Shock('interest_rate', 'CAD yield', 100, 'parallel increase')
    one = Sensitivity(-5, 'user-entered duration', date(2024, 1, 1))
    two = Sensitivity(-2, 'user-entered duration', date(2024, 1, 1))
    result = linear_shock({'A': .6, 'B': .4}, shock, {'A': one, 'B': two}, date(2024, 1, 1))
    assert result.impact_fraction == pytest.approx(-.038)
    assert result.contributions == pytest.approx({'A': -.03, 'B': -.008})
    partial = linear_shock({'A': .6, 'B': .4}, shock, {'A': one}, date(2024, 1, 1))
    assert partial.impact_fraction is None
    assert partial.known_impact_fraction == pytest.approx(-.03)
    assert partial.missing == ('B',)
    future = linear_shock({'A': 1}, shock, {'A': one}, date(2023, 12, 31))
    assert future.impact_fraction is None
    with pytest.raises(ValueError):
        Shock('currency', 'CAD per USD', -1.1, 'assumption')


def test_scenario_http_real_validation_and_no_implicit_zero_sensitivity():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    payload = {'asOf': '2024-01-01', 'weights': {'A': .6, 'B': .4},
               'shock': {'kind': 'interest_rate', 'key': 'CAD', 'change': 100, 'assumption': 'parallel rise'},
               'sensitivities': {'A': {'value': -5, 'source': 'user assumption', 'asOf': '2024-01-01'}}}
    response = client.post('/v1/risk/scenario', json=payload)
    assert response.status_code == 200
    assert response.json()['impactFraction'] is None
    assert response.json()['knownImpactFraction'] == pytest.approx(-.03)
    assert response.json()['missing'] == ['B']
    payload['weights']['B'] = .5
    assert client.post('/v1/risk/scenario', json=payload).status_code == 422


def test_bad_levels_do_not_emit_nan_or_divide_by_zero():
    assert simple_returns([100, 0]) == [-1]
    assert max_drawdown_pct([100, 0]) == 100
    assert compound([-.2, .25]) == pytest.approx([1, .8, 1])
    for levels in ([0, 1], [-1, 1], [1, float('nan')], [1e-320, 1e308]):
        with pytest.raises(ValueError):
            simple_returns(levels)
    with pytest.raises(ValueError):
        compound([1e308, 1e308])
    with pytest.raises(ValueError):
        worst_rolling_return_pct([1, 2], 0)


def test_strategic_candidates_are_ranked_and_facts_belong_to_result_ledger():
    from aplomb.contracts.api import CreateProfileRequest
    from aplomb.quant.candidates import strategic_brief

    from tests.unit.profiles.test_profiles import A, create_request, service

    svc = service()
    goals = [
        {'name': 'Near-term', 'horizonYears': 2, 'priority': 1, 'targetAmount': 2000,
         'allocatedValue': 500, 'annualContribution': 100, 'assumedReturnPct': 0},
        {'name': 'Later', 'horizonYears': 10, 'priority': 2, 'targetAmount': 2000},
    ]
    profile = svc.create(A, CreateProfileRequest.model_validate(create_request(investorContext={'objectives': goals})))
    profile = profile.model_copy(update={'rules': []})
    result = strategic_brief(profile, svc.snapshot(), '2026-11-15T00:00:00Z')
    assert len(result['candidates']) <= 3
    shortfall = next(c for c in result['candidates'] if c['candidateId'] == 'goal:0')
    missing = next(c for c in result['candidates'] if c['candidateId'] == 'goal:1')
    assert shortfall['severity'] == 'scenario_shortfall'
    assert set(missing['missingInputs']) == {'allocatedValue', 'annualContribution', 'assumedReturnPct'}
    assert not shortfall['claimIds']
    assert all(fid in result['facts'] for c in result['candidates'] for fid in c['factIds'])
    assert all(fid in result['facts'] for fact in result['facts'].values() for fid in fact['inputs'])
    # QA 4.5b: the fact-ID remapping note is for code, not a limitation shown to the user.
    assert not any('fact ID' in line or 'ledger' in line for line in result['limitations'])


def test_target_funding_http_conserves_deposits_and_withdrawals():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    body = {'totalValue': 100, 'before': {'A': .6, 'B': .4}, 'target': {'A': .25, 'C': .75}, 'externalFlow': 20}
    result = client.post('/v1/decision/target-funding', json=body)
    assert result.status_code == 200
    result = result.json()
    assert result['afterValue'] == 120
    assert result['purchases'] == 90
    assert result['sales'] == 70
    assert result['purchases'] - result['sales'] == result['externalFlow']
    body['externalFlow'] = -20
    result = client.post('/v1/decision/target-funding', json=body).json()
    assert result['afterValue'] == 80
    assert result['purchases'] - result['sales'] == result['externalFlow']
    body['externalFlow'] = -100
    assert client.post('/v1/decision/target-funding', json=body).status_code == 422
    body['externalFlow'] = 0
    body['target'] = {'A': 1.1, 'B': -.1}
    assert client.post('/v1/decision/target-funding', json=body).status_code == 422


def test_fund_lookthrough_http_accepts_only_visible_exact_disclosures():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    body = {'asOf': '2024-01-06', 'historical': True, 'positions': {SPY: .5, APPLE: .5},
            'snapshots': [{'fundIsin': SPY, 'holdingsDate': '2024-01-04',
                           'evidence': evidence().model_dump(mode='json'),
                           'constituents': [{'isin': APPLE, 'weight': .4}]}]}
    response = client.post('/v1/risk/fund-look-through', json=body)
    assert response.status_code == 200
    assert response.json()['direct'][APPLE] == .5
    assert response.json()['indirect'][APPLE] == .2
    assert response.json()['unresolvedWeight'] == .3
    body['asOf'] = '2024-01-05'
    assert client.post('/v1/risk/fund-look-through', json=body).status_code == 422


def test_explicit_cashflow_scenario_reserves_and_unfunded_dates():
    from aplomb.contracts.models import InvestorRequirement
    from aplomb.quant.cashflows import requirement_scenario

    requirements = [InvestorRequirement.model_validate({'name': 'Spending', 'kind': 'spending', 'amount': 40,
        'frequency': 'annual', 'dueDate': '2024-06-01'}),
        InvestorRequirement.model_validate({'name': 'Reserve', 'kind': 'liquidity', 'amount': 50,
        'dueDate': '2025-06-01'})]
    result = requirement_scenario(requirements, as_of=date(2024, 1, 1), through=date(2025, 12, 31),
                                  liquid_capital=100, annual_return_pct=0, cashflows=[])
    assert result['state'] == 'scenario_shortfall'
    assert result['shortfallDate'] == '2025-06-01'
    assert result['shortfall'] == 30
    result = requirement_scenario(requirements, as_of=date(2024, 1, 1), through=date(2025, 12, 31),
                                  liquid_capital=100, annual_return_pct=0, cashflows=[(date(2025, 6, 1), 30)])
    assert result['state'] == 'scenario_funded'
    assert result['endingValue'] == 50
    missing = InvestorRequirement.model_validate({'name': 'Debt', 'kind': 'liability', 'amount': 10})
    result = requirement_scenario([missing], as_of=date(2024, 1, 1), through=date(2025, 1, 1),
                                  liquid_capital=100, annual_return_pct=0, cashflows=[])
    assert result['state'] == 'missing_inputs' and result['missingInputs'] == ['Debt: dueDate']


def test_missing_listing_country_does_not_create_false_zero_exposure():
    from aplomb.quant import LocalLedger, QuantEngine

    from tests.unit.datastore._support import starter_snapshot

    snapshot = starter_snapshot()
    engine = QuantEngine(snapshot.gate(snapshot.data_as_of, 'current'), LocalLedger(),
                         currency='CAD', subject_id='test', created_at='2026-11-15T00:00:00Z')
    measurement = engine.view({'CASH.CAD': 1}, 'cash', 100).measure('weight.country', 'CAN')
    assert measurement.value is None
    assert measurement.nee_reason == 'no_evidence_loaded'


def test_requirements_http_uses_session_profile_and_echoes_inputs():
    from types import SimpleNamespace

    from aplomb.contracts.models import InvestorRequirement

    requirement = InvestorRequirement.model_validate({'name': 'Rent', 'kind': 'spending', 'amount': 10,
                                                      'dueDate': '2024-06-01'})
    profile = SimpleNamespace(profile_id='p_test', version=2, reporting_currency='EUR',
                              investor_context=SimpleNamespace(requirements=[requirement]))

    class Profiles:
        def get(self, session, profile_id):
            assert session == 's_test' and profile_id == 'p_test'
            return profile

    app = FastAPI()
    app.state.services = SimpleNamespace(profiles=Profiles())
    app.include_router(router)
    client = TestClient(app)
    body = {'asOf': '2024-01-01', 'through': '2024-12-31', 'liquidCapital': 100,
            'annualReturnPct': 0, 'cashflows': []}
    response = client.post('/v1/profiles/p_test/requirements-scenario', json=body,
                           headers={'X-Aplomb-Session': 's_test'})
    assert response.status_code == 200
    assert response.json()['endingValue'] == 90
    assert response.json()['currency'] == 'EUR'
    assert response.json()['inputs'] == body


def test_no_requirement_schedule_never_claims_funded():
    from aplomb.quant.cashflows import requirement_scenario

    result = requirement_scenario([], as_of=date(2024, 1, 1), through=date(2025, 1, 1),
                                  liquid_capital=100, annual_return_pct=0, cashflows=[])
    assert result['state'] == 'missing_inputs'
    assert result['missingInputs'] == ['requirement schedule']


def test_factor_regression_exact_period_alignment_and_collinearity():
    from datetime import timedelta

    from aplomb.quant.factors import FactorPeriod, ReturnPeriod, fit_factor_exposures

    start = date(2024, 1, 1)
    returns, factor_rows = [], []
    for i in range(40):
        a, b = start + timedelta(days=i), start + timedelta(days=i + 1)
        market = ((i % 7) - 3) / 100
        value = ((i * i % 11) - 5) / 100
        rf = .0001
        returns.append(ReturnPeriod(a, b, rf + .001 + 1.5 * market - .5 * value))
        factor_rows.append(FactorPeriod(a, b, rf, {'market': market, 'value': value}, 'synthetic test'))
    fit = fit_factor_exposures(returns, factor_rows, ['market', 'value'])
    assert fit.alpha_per_period == pytest.approx(.001, abs=1e-12)
    assert fit.betas == pytest.approx({'market': 1.5, 'value': -.5}, abs=1e-12)
    assert fit.r_squared == pytest.approx(1)
    assert fit.residual_stdev == pytest.approx(0, abs=1e-12)
    assert fit.observations == 40 and fit.source_ids == ('synthetic test',)
    bad = [FactorPeriod(r.start, r.end, r.risk_free,
                        {'market': r.factors['market'], 'value': 2 * r.factors['market']}, r.source)
           for r in factor_rows]
    with pytest.raises(ValueError, match='singular'):
        fit_factor_exposures(returns, bad, ['market', 'value'])
    with pytest.raises(ValueError, match='insufficient'):
        fit_factor_exposures(returns[:10], factor_rows, ['market', 'value'])


def test_factor_fit_http_uses_exact_sample_not_ticker_or_implicit_data():
    from datetime import timedelta

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    start = date(2024, 1, 1)
    rows, factors = [], []
    for i in range(35):
        a = (start + timedelta(days=i)).isoformat()
        b = (start + timedelta(days=i + 1)).isoformat()
        x = ((i % 7) - 3) / 100
        rows.append({'start': a, 'end': b, 'value': .0001 + .001 + 1.5 * x})
        factors.append({'start': a, 'end': b, 'riskFree': .0001,
                        'factors': {'market': x}, 'source': 'synthetic'})
    body = {'names': ['market'], 'returns': rows, 'factors': factors}
    response = client.post('/v1/risk/factor-fit', json=body)
    assert response.status_code == 200
    assert response.json()['betas']['market'] == pytest.approx(1.5)
    assert response.json()['observations'] == 35
    body['returns'] = rows[:3]
    assert client.post('/v1/risk/factor-fit', json=body).status_code == 422


def test_extreme_tail_and_variance_inputs_fail_cleanly_without_infinities():
    from aplomb.quant.metrics import historical_tail_pct, variance_shares_pct

    with pytest.raises(ValueError, match='overflow'):
        historical_tail_pct([-1e308] * 100)
    with pytest.raises(ValueError, match='overflow'):
        variance_shares_pct([1.0], [[1e308, -1e308]])
    # Negative weights are meaningful to the pure variance decomposition.
    shares = variance_shares_pct([1.2, -0.2], [[0.01, -0.01, 0.02], [0.02, -0.02, 0.04]])
    assert shares is not None and sum(shares) == pytest.approx(100.0)
    assert shares[1] < 0
