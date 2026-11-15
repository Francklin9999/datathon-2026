from aplomb.datastore.financial_inputs_api import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_source_inputs_historical_day_does_not_see_later_capture():
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get('/v1/risk/source-inputs?asOf=2026-11-12')
    assert response.status_code == 200
    sources = {item['id']: item for item in response.json()['sources']}
    assert sources['sofr']['status'] == 'not_available_as_of'
    assert sources['cftc-cot']['status'] == 'not_available_as_of'
    assert sources['fama-french']['status'] == 'capture_unavailable'


def test_source_inputs_missing_capture_is_explicit(monkeypatch, tmp_path):
    from aplomb.datastore import financial_inputs_api

    monkeypatch.setattr(financial_inputs_api, 'INPUTS', tmp_path)
    app = FastAPI()
    app.include_router(router)
    result = TestClient(app).get('/v1/risk/source-inputs').json()
    assert all(item['status'] == 'capture_unavailable' for item in result['sources'])
