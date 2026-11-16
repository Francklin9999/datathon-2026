from types import SimpleNamespace

import pytest
from aplomb.api.errors import ServiceError
from aplomb.contracts.api import CreateProfileRequest
from aplomb.quant.expanded_api import make_router
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from tests.unit.profiles.test_profiles import A, B, create_request, service


def make_client():
    svc = service()
    app = FastAPI()
    app.state.services = SimpleNamespace(profiles=svc)

    @app.exception_handler(ServiceError)
    def map_error(request, exc):
        return JSONResponse({'code': str(exc.code), 'message': exc.message}, status_code=exc.status)

    def session(x_aplomb_session: str = Header(...)):
        return x_aplomb_session

    app.include_router(make_router(session))
    return TestClient(app), svc


def test_real_http_portfolio_comparison_and_session_versions():
    client, svc = make_client()
    profile = svc.create(A, CreateProfileRequest.model_validate(create_request()))
    second = svc.duplicate(A, profile.profile_id)
    body = {'profiles': [{'profileId': profile.profile_id, 'version': profile.version},
                         {'profileId': second.profile_id, 'version': second.version}],
            'currency': 'USD', 'window': {'code': '1y'}}
    response = client.post('/v1/portfolios/compare', json=body, headers={'X-Aplomb-Session': A})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['sameSample'] and len(result['portfolios']) == 2
    # QA 4.5b: no developer note about fact-ID remapping among the limitations shown on the page.
    assert not any('fact ID' in line or 'ledger' in line for line in result['limitations'])
    assert result['portfolios'][0]['conversion']['direction'] == 'USD/CAD'
    assert result['portfolios'][0]['capital'] == pytest.approx(
        profile.portfolio.total_value * result['portfolios'][0]['conversion']['rate'])
    assert result['portfolios'][0]['sample'] == result['portfolios'][1]['sample']
    fact = result['portfolios'][0]['factIds']['return.period']
    assert fact in result['portfolios'][0]['facts']
    # FinancialComparison.tsx looks each metric row's fact up by these fact metric ids.
    for portfolio in result['portfolios']:
        assert set(portfolio['metrics']) == {'returnPct', 'volatilityPct', 'maxDrawdownPct', 'stress2022Pct',
                                             'hhi', 'effectiveN'}
        assert set(portfolio['factIds']) == {'return.period', 'vol.annualized', 'drawdown.max', 'stress.replay_2022',
                                             'concentration.hhi', 'concentration.effective_n'}
        assert all(fid in portfolio['facts'] for fid in portfolio['factIds'].values())
    body['profiles'][0]['version'] += 1
    assert client.post('/v1/portfolios/compare', json=body, headers={'X-Aplomb-Session': A}).status_code == 409
    body['profiles'][0]['version'] -= 1
    assert client.post('/v1/portfolios/compare', json=body, headers={'X-Aplomb-Session': B}).status_code == 404


def test_unavailable_target_fx_is_not_relabelled_or_invented():
    client, svc = make_client()
    p = svc.create(A, CreateProfileRequest.model_validate(create_request()))
    q = svc.duplicate(A, p.profile_id)
    body = {'profiles': [{'profileId': p.profile_id, 'version': p.version}, {'profileId': q.profile_id, 'version': q.version}],
            'currency': 'JPY', 'window': {'code': '1y'}}
    response = client.post('/v1/portfolios/compare', json=body, headers={'X-Aplomb-Session': A})
    assert response.status_code == 200, response.text
    result = response.json()
    assert not result['sameSample']
    assert all(row['capital'] is None and not row['positions'] for row in result['portfolios'])
    assert all(row['metrics'].get('returnPct') is None for row in result['portfolios'])


def test_position_details_quantity_provenance():
    client, svc = make_client()
    p = svc.create(A, CreateProfileRequest.model_validate(create_request()))
    details = client.post(f'/v1/profiles/{p.profile_id}/position-details', json={'version': p.version,
        'quantities': [{'ticker': 'SPY', 'quantity': 2, 'asOf': '2026-11-10', 'origin': 'user',
                        'source': 'fictional account statement'}]}, headers={'X-Aplomb-Session': A})
    assert details.status_code == 200, details.text
    first = next(row for row in details.json()['positions'] if row['ticker'] == 'SPY')
    assert first['quantity']['quantity'] == 2 and first['modeledPositionValue'] == pytest.approx(600)
    assert first['valueBasis'] == 'modeled weight × reported portfolio capital'
