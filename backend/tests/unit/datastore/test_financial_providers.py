"""Synthetic formats only: no provider access or data-use rights are implied."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime, timezone

import pytest
from aplomb.api.errors import ServiceError
from aplomb.api.storage import MemoryStore, Write
from aplomb.datastore import financial_connectors as fc
from aplomb.datastore.financial_provider_api import make_router
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

DATE = date(2026, 11, 12)


def zipped(name, data):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(name, data)
    return buffer.getvalue()


def workbook():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('xl/workbook.xml', '''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="BAB Data" r:id="rId1" sheetId="1"/></sheets></workbook>''')
        archive.writestr('xl/_rels/workbook.xml.rels', '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>''')
        archive.writestr('xl/worksheets/sheet1.xml', '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Synthetic factor</t></is></c><c r="B1"><v>0.023</v></c></row></sheetData></worksheet>''')
    return buffer.getvalue()


SAMPLES = {
    'fama-french': zipped('F-F_Research_Data_Factors_daily.csv',
                         ',Mkt-RF,SMB,HML,RF\n20261112,1.5,-0.2,0.3,0.02\n'),
    'aqr': workbook(),
    'cboe': b'DATE,OPEN,HIGH,LOW,CLOSE\n11/12/2026,20,25,19,21\n',
    'occ': b'Product,Calls,Puts\nSynthetic options,42,30\n',
    'finra-volume': (b'Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n'
                     b'20261112|SPY|70.5|30|90|Q\n1\n'),
    'finra-interest': json.dumps([{'symbolCode': 'SPY', 'settlementDate': '2026-11-12',
        'currentShortPositionQuantity': 100, 'previousShortPositionQuantity': 90,
        'averageDailyVolumeQuantity': 25, 'daysToCoverQuantity': 4, 'marketClassCode': 'S'}]).encode(),
}


@pytest.mark.parametrize('provider', sorted(set(SAMPLES) - {'finra-interest'}))
def test_synthetic_source_parsing_and_attribution(provider, monkeypatch):
    monkeypatch.setenv(f'APLOMB_SOURCE_{fc.PROVIDERS[provider].permission_env}_RIGHTS_CONFIRMED', 'true')
    requests = []
    monkeypatch.setattr(fc, '_request', lambda url, **kwargs: (requests.append((url, kwargs)) or SAMPLES[provider]))
    day = datetime.now(timezone.utc).date() if provider == 'aqr' else DATE
    result, raw = fc.acquire(provider, day=day)
    assert result['provider'] == provider and result['source']['rawSha256']
    assert result['availableAt'] == result['source']['retrievedAt']
    assert result['records'] and raw == SAMPLES[provider]
    if provider == 'fama-french':
        assert result['records'][0]['market_excess'] == .015
    elif provider == 'cboe':
        assert result['records'][0]['close'] == 21
    elif provider == 'finra-volume':
        assert result['records'][0]['short'] == '70.5' and 'not short interest' in result['unit']
    elif provider == 'aqr':
        assert result['records'][0]['sourceCells']['B1'] == .023
        assert 'units not inferred' in result['unit']
    elif provider == 'occ':
        assert result['records'][1]['fields'] == ['Synthetic options', '42', '30']


def test_permission_gate_precedes_network_and_set_aside_sources_stay_inactive(monkeypatch):
    for name in fc.PROVIDERS:
        monkeypatch.delenv(f'APLOMB_SOURCE_{fc.PROVIDERS[name].permission_env}_RIGHTS_CONFIRMED', raising=False)
    monkeypatch.setattr(fc, '_request', lambda *args, **kwargs: pytest.fail('unpermitted network request'))
    with pytest.raises(ServiceError, match='permission_required'):
        fc.acquire('cboe', day=DATE)
    for name in ('cme', 'oanda', 'fred', 'finra-interest'):
        with pytest.raises(ServiceError, match='Unknown financial provider'):
            fc.acquire(name, day=DATE)


def make_client():
    store = MemoryStore()
    app = FastAPI()

    def session(x_aplomb_session: str = Header()):
        return x_aplomb_session

    @app.exception_handler(ServiceError)
    async def error_handler(request, error):
        return JSONResponse({'code': error.code}, status_code=error.status)

    app.include_router(make_router(store, session))
    return TestClient(app), store


def test_session_capture_cache_historical_cutoff_and_rights_revocation(monkeypatch):
    monkeypatch.setenv('APLOMB_SOURCE_CBOE_RIGHTS_CONFIRMED', 'true')
    requests = []
    monkeypatch.setattr(fc, '_request', lambda url, **kwargs: (requests.append(url) or SAMPLES['cboe']))
    client, _ = make_client()
    headers = {'X-Aplomb-Session': 'synthetic-session-a'}
    url = '/v1/risk/providers/cboe/capture'
    request = {'asOf': DATE.isoformat()}
    first = client.post(url, headers=headers, json=request)
    assert first.status_code == 200, first.text
    body = first.json()
    assert client.post(url, headers=headers, json=request).json() == body and len(requests) == 1
    capture_url = f"/v1/risk/providers/cboe/captures/{body['captureId']}"
    assert client.get(capture_url, headers=headers).json() == body
    assert client.get(capture_url, headers={'X-Aplomb-Session': 'synthetic-session-b'}).status_code == 404
    assert client.get(capture_url, headers={**headers, 'X-Aplomb-Known-Date': '2020-01-01'}).status_code == 422
    monkeypatch.delenv('APLOMB_SOURCE_CBOE_RIGHTS_CONFIRMED')
    assert client.get(capture_url, headers=headers).status_code == 503
    assert client.post(url, headers=headers, json=request).status_code == 503


@pytest.mark.parametrize('field', ['rawBase64', 'response'])
def test_capture_tampering_is_rejected_on_cached_and_direct_reads(field, monkeypatch):
    monkeypatch.setenv('APLOMB_SOURCE_CBOE_RIGHTS_CONFIRMED', 'true')
    monkeypatch.setattr(fc, '_request', lambda url, **kwargs: SAMPLES['cboe'])
    client, store = make_client()
    headers = {'X-Aplomb-Session': 'synthetic-session-a'}
    url = '/v1/risk/providers/cboe/capture'
    request = {'asOf': DATE.isoformat()}
    result = client.post(url, headers=headers, json=request).json()
    import hashlib
    owner = hashlib.sha256(headers['X-Aplomb-Session'].encode()).hexdigest()
    partition = f'FINANCIAL#{owner}#cboe'
    record = store.get('cache', partition, result['captureId'])
    if field == 'rawBase64':
        record[field] = 'dGFtcGVyZWQ='
    else:
        record[field]['records'][0]['close'] = 999
    record['revision'] += 1
    store.transact([Write('cache', partition, result['captureId'], record, 1)])
    capture_url = f"/v1/risk/providers/cboe/captures/{result['captureId']}"
    assert client.get(capture_url, headers=headers).status_code == 503
    assert client.post(url, headers=headers, json=request).status_code == 503


def test_malformed_source_is_a_graceful_provider_error(monkeypatch):
    monkeypatch.setenv('APLOMB_SOURCE_FINRA_RIGHTS_CONFIRMED', 'true')
    monkeypatch.setattr(fc, '_request', lambda url, **kwargs: b'not a FINRA file')
    client, _ = make_client()
    result = client.post('/v1/risk/providers/finra-volume/capture',
                         headers={'X-Aplomb-Session': 'synthetic'}, json={'asOf': DATE.isoformat()})
    assert result.status_code == 503


def test_invalid_and_duplicate_vix_rejected(monkeypatch):
    monkeypatch.setenv('APLOMB_SOURCE_CBOE_RIGHTS_CONFIRMED', 'true')
    header = b'DATE,OPEN,HIGH,LOW,CLOSE\n'
    for raw in (header + b'11/12/2026,25,24,19,21\n',
                header + b'11/12/2026,20,25,19,21\n11/12/2026,20,25,19,21\n'):
        monkeypatch.setattr(fc, '_request', lambda *args, **kwargs: raw)
        with pytest.raises(ValueError):
            fc.acquire('cboe', day=DATE)


def test_bad_workbook_and_date_are_rejected_without_inferring_units(monkeypatch):
    monkeypatch.setenv('APLOMB_SOURCE_AQR_RIGHTS_CONFIRMED', 'true')
    monkeypatch.setattr(fc, '_request', lambda *args, **kwargs: workbook())
    with pytest.raises(ValueError, match='current-capture only'):
        fc.acquire('aqr', day=DATE)
    with pytest.raises(ValueError, match='data sheets'):
        fc.acquire('aqr', day=datetime.now(timezone.utc).date(), sheet='missing')


def test_provider_directory_and_capture_set_aside_login_sources(monkeypatch):
    client, _ = make_client()
    listing = client.get('/v1/risk/providers', headers={'X-Aplomb-Session': 'synthetic'})
    assert listing.status_code == 200
    assert len(listing.json()['providers']) == 5
    assert {row['id'] for row in listing.json()['setAside']} == {'cme', 'oanda', 'fred', 'finra-interest'}
    for name in ('cme', 'oanda', 'fred', 'finra-interest'):
        result = client.post(f'/v1/risk/providers/{name}/capture',
            headers={'X-Aplomb-Session': 'synthetic'}, json={'asOf': DATE.isoformat()})
        assert result.status_code == 503
