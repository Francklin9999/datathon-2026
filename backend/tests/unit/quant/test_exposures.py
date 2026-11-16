from datetime import date

import pytest
from aplomb.quant.metrics import (
    compound,
    max_drawdown_pct,
    simple_returns,
    worst_rolling_return_pct,
)
from aplomb.quant.scenario_api import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


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
