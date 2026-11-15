import statistics
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from aplomb.api.errors import ServiceError
from aplomb.contracts.api import CreateProfileRequest
from aplomb.intelligence.entities import Evidence
from aplomb.quant import LocalLedger, QuantEngine
from aplomb.quant.covariance import sample_covariance
from aplomb.quant.expanded_api import make_router
from aplomb.quant.exposures import FundConstituent, FundSnapshot
from aplomb.quant.liquidity import SaleAssumption, sale_scenario
from aplomb.quant.nested import nested_look_through
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from tests.unit.profiles.test_profiles import A, B, create_request, service

SPY = 'US78462F1030'
IVV = 'US4642872000'
APPLE = 'US0378331005'
MSFT = 'US5949181045'


def capture():
    return Evidence(source_id='fixture', url='https://example.com/source.csv', content_sha256='a' * 64,
                    available_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
                    retrieved_at=datetime(2024, 1, 6, tzinfo=timezone.utc), licence='synthetic')


def fund(isin, rows):
    return FundSnapshot(isin, date(2024, 1, 4), capture(),
                        tuple(FundConstituent(asset, weight) for asset, weight in rows))


def test_nested_preserves_direct_indirect_unknown_and_cycles():
    snapshots = {SPY: fund(SPY, [(IVV, .6), (APPLE, .2)]),
                 IVV: fund(IVV, [(SPY, .1), (MSFT, .5)])}
    result = nested_look_through({SPY: .8, APPLE: .2}, snapshots, set(snapshots), date(2024, 1, 6), historical=True)
    assert result.direct[APPLE] == pytest.approx(.2)
    assert result.indirect[APPLE] == pytest.approx(.16)
    assert result.indirect[MSFT] == pytest.approx(.24)
    assert result.unresolved_by_reason['cycle'] == pytest.approx(.048)
    assert result.unresolved_by_reason['undisclosed_fund_weight'] == pytest.approx(.352)
    assert result.unresolved_weight == pytest.approx(.4)
    assert sum(result.direct.values()) + sum(result.indirect.values()) + result.unresolved_weight == pytest.approx(1)
    missing = nested_look_through({SPY: 1}, {}, {SPY}, date(2024, 1, 6))
    assert missing.unresolved_by_reason == {'fund_snapshot_missing': 1}
    with pytest.raises(ValueError, match='visible'):
        nested_look_through({SPY: 1}, snapshots, set(snapshots), date(2024, 1, 5), historical=True)


def test_covariance_matches_independent_statistics_reference():
    samples = [[.01, -.02, .03, .04], [-.03, .04, -.01, .02], [0, 0, 0, 0]]
    result = sample_covariance(samples)
    for i in range(3):
        for j in range(3):
            assert result[i][j] == pytest.approx(statistics.covariance(samples[i], samples[j]))
    assert sample_covariance([[1], [2]]) is None
    with pytest.raises(ValueError, match='calendar'):
        sample_covariance([[1, 2], [1]])
    with pytest.raises(ValueError):
        sample_covariance([[float('inf'), 0]])


def test_liquidity_uses_only_explicit_sale_dates_and_unknown_is_not_zero():
    days = (date(2025, 1, 2), date(2025, 1, 4))
    assumptions = {'A': SaleAssumption(days, 300, 50, 50, 'user input', date(2025, 1, 1))}
    partial = sale_scenario({'A': 500, 'B': 100}, assumptions, date(2025, 1, 1), date(2025, 1, 5), 500)
    assert partial['knownNetProceeds'] == pytest.approx(495)
    assert partial['totalNetProceeds'] is None
    assert partial['missingHoldings'] == ['B']
    assert partial['state'] == 'unknown_missing_positions'
    assert partial['cashflows'] == [{'date': '2025-01-02', 'netProceeds': 297},
                                    {'date': '2025-01-04', 'netProceeds': 198}]
    covered = sale_scenario({'A': 500, 'B': 100}, assumptions, date(2025, 1, 1), date(2025, 1, 5), 290)
    assert covered['state'] == 'covered_by_modeled_positions'
    assert covered['firstCoveredDate'] == '2025-01-02'
    with pytest.raises(ValueError, match='cost'):
        SaleAssumption(days, 100, 9000, 2000, 'user input', date(2025, 1, 1))
    with pytest.raises(ValueError, match='unique'):
        SaleAssumption((days[0], days[0]), 100, 0, 0, 'user input', date(2025, 1, 1))


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


def test_real_http_portfolio_comparison_covariance_and_session_versions():
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
    assert result['portfolios'][0]['conversion']['direction'] == 'USD/CAD'
    assert result['portfolios'][0]['capital'] == pytest.approx(
        profile.portfolio.total_value * result['portfolios'][0]['conversion']['rate'])
    assert result['portfolios'][0]['sample'] == result['portfolios'][1]['sample']
    fact = result['portfolios'][0]['factIds']['return.period']
    assert fact in result['portfolios'][0]['facts']
    body['profiles'][0]['version'] += 1
    assert client.post('/v1/portfolios/compare', json=body, headers={'X-Aplomb-Session': A}).status_code == 409
    body['profiles'][0]['version'] -= 1
    assert client.post('/v1/portfolios/compare', json=body, headers={'X-Aplomb-Session': B}).status_code == 404
    cov = client.post('/v1/risk/covariance', json={'profileId': profile.profile_id, 'version': profile.version,
                      'window': {'code': '1y'}}, headers={'X-Aplomb-Session': A})
    assert cov.status_code == 200, cov.text
    matrix = cov.json()['dailyCovariance']
    assert len(matrix) == 2 and matrix[0][1] == pytest.approx(matrix[1][0])
    assert all(fid in cov.json()['facts'] for fid in cov.json()['sourceFactIds'])


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


def test_active_factor_portfolio_alignment_and_quantity_provenance():
    client, svc = make_client()
    p = svc.create(A, CreateProfileRequest.model_validate(create_request()))
    gate = svc.snapshot().gate(svc.snapshot().data_as_of, 'current')
    engine = QuantEngine(gate, LocalLedger(), currency='CAD', subject_id=p.profile_id, created_at='2026-11-15T00:00:00Z')
    wr = engine.window({'code': '1y'})
    weights = {row.ticker: row.weight_pct / 100 for row in p.portfolio.positions}
    from aplomb.quant.metrics import portfolio_returns
    rets = portfolio_returns(list(weights.values()), [engine.asset_returns(t, wr.i0, wr.i1) for t in weights])
    dates = engine.market.dates[wr.i0:wr.i1 + 1]
    rows = [{'start': dates[i], 'end': dates[i + 1], 'riskFree': .0001,
             'factors': {'synthetic': (rets[i] - .0001 - .001) / 1.5}} for i in range(40)]
    payload = {'version': p.version, 'window': {'code': '1y'}, 'names': ['synthetic'],
               'source': {'origin': 'user', 'description': 'synthetic assumption', 'currency': 'CAD',
                          'availableAt': svc.snapshot().data_as_of}, 'factors': rows}
    response = client.post(f'/v1/profiles/{p.profile_id}/factor-exposure', json=payload,
                           headers={'X-Aplomb-Session': A})
    assert response.status_code == 200, response.text
    assert response.json()['betas']['synthetic'] == pytest.approx(1.5)
    assert response.json()['observations'] == 40
    details = client.post(f'/v1/profiles/{p.profile_id}/position-details', json={'version': p.version,
        'quantities': [{'ticker': 'SPY', 'quantity': 2, 'asOf': '2026-11-10', 'origin': 'user',
                        'source': 'fictional account statement'}]}, headers={'X-Aplomb-Session': A})
    assert details.status_code == 200, details.text
    first = next(row for row in details.json()['positions'] if row['ticker'] == 'SPY')
    assert first['quantity']['quantity'] == 2 and first['modeledPositionValue'] == pytest.approx(600)
    assert first['valueBasis'] == 'modeled weight × reported portfolio capital'


def test_factor_capture_uses_session_rights_integrity_and_historical_availability(monkeypatch):
    import base64
    import hashlib
    import io
    import zipfile
    from dataclasses import asdict

    from aplomb.api.storage import MemoryStore, Write, canonical
    from aplomb.datastore.fama_french import SOURCE, read_capture
    from aplomb.quant.metrics import portfolio_returns

    client, svc = make_client()
    p = svc.create(A, CreateProfileRequest.model_validate(create_request(reportingCurrency='USD')))
    gate = svc.snapshot().gate(svc.snapshot().data_as_of, 'current')
    eng = QuantEngine(gate, LocalLedger(), currency='USD', subject_id=p.profile_id, created_at='2026-11-15T00:00:00Z')
    wr = eng.window({'code': '1y'})
    weights = {row.ticker: row.weight_pct / 100 for row in p.portfolio.positions}
    rets = portfolio_returns(list(weights.values()), [eng.asset_returns(t, wr.i0, wr.i1) for t in weights])
    dates = eng.market.dates[wr.i0:wr.i1 + 1]
    lines = [',Mkt-RF,SMB,HML,RF', f'{dates[0].replace("-", "")},0,0,0,0.01']
    for index in range(40):
        factor = (rets[index] - .0001 - .001) / 1.5
        lines.append(f'{dates[index + 1].replace("-", "")},{factor * 100:.12f},0,0,0.01')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('F-F_Research_Data_Factors_daily.csv', '\n'.join(lines))
    raw = output.getvalue()
    metadata = {'sourceUrl': SOURCE, 'retrievedAt': '2026-11-15T00:00:00Z', 'rawSha256': hashlib.sha256(raw).hexdigest()}
    parsed = read_capture(raw, metadata)
    capture_id = 'capture_' + 'b' * 64
    response = {'provider': 'fama-french', 'captureId': capture_id, 'source': metadata,
                'availableAt': metadata['retrievedAt'], 'asOf': gate.as_of.isoformat(),
                'version': 'risk_fama-french_synthetic', 'unit': 'fractional daily factor return',
                'records': [asdict(row) for row in parsed.through(metadata['retrievedAt'], gate.as_of.isoformat())],
                'limitations': ['synthetic fixture'], 'query': {'asOf': gate.as_of.isoformat(), 'limit': 100}}
    store = MemoryStore()
    partition = 'FINANCIAL#' + hashlib.sha256(A.encode()).hexdigest() + '#fama-french'
    record = {'revision': 1, 'sessionId': A, 'response': response, 'rawBase64': base64.b64encode(raw).decode(),
              'responseSha256': hashlib.sha256(canonical(response)).hexdigest()}
    store.transact([Write('cache', partition, capture_id, record, None)])
    client.app.state.financial_capture_store = store
    monkeypatch.setattr('aplomb.datastore.financial_connectors.provider_status', lambda provider: {'status': 'configured'})
    payload = {'version': p.version, 'window': {'code': '1y'}, 'names': ['market_excess'], 'captureId': capture_id}
    result = client.post(f'/v1/profiles/{p.profile_id}/factor-exposure', json=payload, headers={'X-Aplomb-Session': A})
    assert result.status_code == 200, result.text
    assert result.json()['betas']['market_excess'] == pytest.approx(1.5)
    assert result.json()['source']['captureId'] == capture_id
    payload['knowledgeMode'] = 'historical'
    unavailable = client.post(f'/v1/profiles/{p.profile_id}/factor-exposure', json=payload,
                              headers={'X-Aplomb-Session': A})
    assert unavailable.status_code == 422
    payload.pop('knowledgeMode')
    # A forged normalized value fails even when an attacker also recomputes its response hash.
    record['revision'] = 2
    record['response']['records'][-1]['market_excess'] += .1
    record['responseSha256'] = hashlib.sha256(canonical(record['response'])).hexdigest()
    store.transact([Write('cache', partition, capture_id, record, 1)])
    corrupt = client.post(f'/v1/profiles/{p.profile_id}/factor-exposure', json=payload,
                          headers={'X-Aplomb-Session': A})
    assert corrupt.status_code == 503
