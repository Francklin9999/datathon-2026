"""Synthetic provider responses; no production source or licensed capture is asserted."""
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from aplomb.research.regional import RegionalError, RegionalResearch


def NOW():
    return datetime(2026, 11, 15, tzinfo=timezone.utc)


def encode(value):
    return json.dumps(value).encode()


def test_region_never_falls_back_and_rights_are_required():
    def no_call(*args):
        raise AssertionError('source must not be called')
    provider = RegionalResearch(fetch=no_call, env={'APLOMB_JQUANTS_KEY': 'secret'}, clock=NOW)
    assert provider.query('JP', '86970', '2026-10-01', '2026-11-01')['status'] == 'unavailable'
    with pytest.raises(RegionalError, match='unsupported_region'):
        provider.query('US', 'AAPL', '2026-10-01', '2026-11-01')
    with pytest.raises(RegionalError, match='five_character'):
        provider.query('JP', 'AAPL', '2026-10-01', '2026-11-01')
    with pytest.raises(RegionalError, match='eight_digit'):
        provider.query('KR', '005930', '2026-10-01', '2026-11-01')


def test_japan_exact_issue_and_complete_pagination():
    calls = []
    def fetch(url, headers):
        calls.append((url, headers))
        page = parse_qs(urlparse(url).query).get('pagination_key')
        if not page:
            return encode({'data': [{'Date': '2026-10-02', 'Code': '86970', 'C': 102, 'AdjC': 100}], 'pagination_key': 'next'})
        return encode({'data': [{'Date': '2026-10-05', 'Code': '86970', 'C': 103, 'AdjC': 101}]})
    service = RegionalResearch(fetch=fetch, env={'APLOMB_JQUANTS_KEY': 'secret',
        'APLOMB_JQUANTS_RIGHTS_CONFIRMED': 'true'}, clock=NOW)
    result = service.query('JP', '86970', '2026-10-01', '2026-11-01')
    assert result['prices'][0]['close'] == 102 and not result['partial']
    assert len(result['prices']) == result['pagesInspected'] == 2
    assert parse_qs(urlparse(calls[1][0]).query)['pagination_key'] == ['next']
    assert result['availableAt'] == result['retrievedAt'] and result['publicationAt'] is None
    assert calls[0][1]['x-api-key'] == 'secret' and 'secret' not in json.dumps(result)
    assert result['sourceUrl'].startswith('https://api.jquants.com/')
    looping = RegionalResearch(fetch=lambda *_: encode({'data': [], 'pagination_key': 'next'}), env=service.env, clock=NOW)
    with pytest.raises(RegionalError, match='invalid_pagination'):
        looping.query('JP', '86970', '2026-10-01', '2026-11-01')
    mismatch = RegionalResearch(fetch=lambda *_: encode({'data': [{'Code': '12340'}]}), env=service.env, clock=NOW)
    with pytest.raises(RegionalError, match='identifier_mismatch'):
        mismatch.query('JP', '86970', '2026-10-01', '2026-11-01')


def test_korean_corporate_code_queries_filings_and_secrets_stay_private():
    def fetch(url, headers):
        q = parse_qs(urlparse(url).query)
        assert q['crtfc_key'] == ['private'] and q['corp_code'] == ['00126380']
        if urlparse(url).path.endswith('company.json'):
            # Official company endpoint need not echo corp_code.
            return encode({'status': '000', 'corp_name': 'Example', 'corp_name_eng': 'Example Ltd', 'stock_code': '000001'})
        page = int(q['page_no'][0])
        receipt = '2026100300000' + str(page)
        return encode({'status': '000', 'total_page': 2, 'total_count': 2, 'list': [{'corp_code': '00126380', 'rcept_no': receipt,
            'rcept_dt': '20261003', 'report_nm': 'Annual report'}]})
    service = RegionalResearch(fetch=fetch, env={'APLOMB_OPENDART_KEY': 'private',
        'APLOMB_OPENDART_RIGHTS_CONFIRMED': 'true'}, clock=NOW)
    result = service.query('KR', '00126380', '2026-10-01', '2026-11-01')
    assert result['company']['stockCode'] == '000001' and not result['partial']
    assert result['pagesInspected'] == 2 and len(result['filings']) == 2
    assert result['filings'][0]['date'] == '2026-10-03'
    assert {row['receiptNumber'] for row in result['filings']} == {'20261003000001', '20261003000002'}
    assert 'private' not in json.dumps(result) and 'crtfc_key' not in json.dumps(result)


def test_periods_and_provider_responses_are_bounded():
    service = RegionalResearch(env={}, clock=NOW)
    with pytest.raises(RegionalError, match='invalid_date_range'):
        service.query('JP', '86970', '2020-01-01', '2026-01-01')
    with pytest.raises(RegionalError, match='future_date'):
        service.query('JP', '86970', '2026-10-01', '2026-12-01')
    env = {'APLOMB_JQUANTS_KEY': 'secret', 'APLOMB_JQUANTS_RIGHTS_CONFIRMED': 'true'}
    dup = RegionalResearch(fetch=lambda *_: b'{"data": [], "data": []}', env=env, clock=NOW)
    with pytest.raises(RegionalError):
        dup.query('JP', '86970', '2026-10-01', '2026-11-01')


def test_http_route_reports_unavailable_and_rejects_bad_identifiers(monkeypatch):
    from aplomb.api.app import create_app
    from aplomb.api.settings import Settings
    from fastapi.testclient import TestClient

    monkeypatch.delenv('APLOMB_JQUANTS_KEY', raising=False)
    monkeypatch.delenv('APLOMB_JQUANTS_RIGHTS_CONFIRMED', raising=False)
    client = TestClient(create_app(Settings(local_state_file='/tmp/aplomb-regional-test-state.json')))
    headers = {'X-Aplomb-Session': 's_6f1c2d3e-4a5b-4c6d-8e7f-0123456789ab'}
    params = {'region': 'JP', 'identifier': '86970', 'start': '2024-01-01', 'end': '2024-01-30'}
    response = client.get('/v1/intelligence/regional', params=params, headers=headers)
    assert response.status_code == 200 and response.json()['status'] == 'unavailable'
    params['identifier'] = 'AAPL'
    assert client.get('/v1/intelligence/regional', params=params, headers=headers).status_code == 422


def test_captures_are_immutable_session_owned_and_exclude_credentials():
    from aplomb.api.storage import MemoryStore
    store = MemoryStore()
    env = {'APLOMB_JQUANTS_KEY': 'private-key-value', 'APLOMB_JQUANTS_RIGHTS_CONFIRMED': 'true'}
    raw = encode({'data': [{'Date': '2026-10-02', 'Code': '86970', 'C': 102, 'AdjC': 100}]})
    def client(session):
        return RegionalResearch(fetch=lambda *_: raw, env=env, clock=NOW, store=store, session_id=session)
    result = client('owner-a').query('JP', '86970', '2026-10-01', '2026-11-01')
    assert result == client('owner-a').query('JP', '86970', '2026-10-01', '2026-11-01')
    assert result['datasetVersion'].startswith('regional-')
    client('owner-b').query('JP', '86970', '2026-10-01', '2026-11-01')
    import hashlib
    def partition(owner):
        return 'REGIONAL#' + hashlib.sha256(owner.encode()).hexdigest()
    a, b = store.query('cache', partition('owner-a')), store.query('cache', partition('owner-b'))
    assert len(a) == len(b) == 1 and a[0]['sessionId'] != b[0]['sessionId']
    assert a[0]['raw']['prices'] == raw.decode() and 'private-key-value' not in json.dumps(a)
    leaked = RegionalResearch(fetch=lambda *_: b'{"data":[],"token":"private-key-value"}',
                              env=env, clock=NOW, store=store, session_id='owner-a')
    with pytest.raises(RegionalError, match='contains_credential'):
        leaked.query('JP', '86970', '2026-10-01', '2026-11-01')
    assert len(store.query('cache', partition('owner-a'))) == 1


def test_http_authorized_fixture_uses_session_store_and_never_returns_key(monkeypatch, tmp_path):
    import aplomb.research.regional as regional
    from aplomb.api.app import create_app
    from aplomb.api.settings import Settings
    from fastapi.testclient import TestClient
    real = regional.RegionalResearch
    env = {'APLOMB_JQUANTS_KEY': 'credential-should-not-appear', 'APLOMB_JQUANTS_RIGHTS_CONFIRMED': 'true'}
    raw = encode({'data': [{'Date': '2024-01-02', 'Code': '86970', 'C': 102, 'AdjC': 100}]})
    monkeypatch.setattr(regional, 'RegionalResearch',
                        lambda **kw: real(fetch=lambda *_: raw, env=env, clock=NOW, **kw))
    client = TestClient(create_app(Settings(local_state_file=str(tmp_path / 'state.json'))))
    headers = {'X-Aplomb-Session': 's_6f1c2d3e-4a5b-4c6d-8e7f-0123456789ab'}
    params = {'region': 'JP', 'identifier': '86970', 'start': '2024-01-01', 'end': '2024-01-30'}
    response = client.get('/v1/intelligence/regional', params=params, headers=headers)
    assert response.status_code == 200 and response.json()['prices'][0]['close'] == 102
    assert response.json()['datasetVersion'].startswith('regional-')
    assert 'credential-should-not-appear' not in response.text
    assert 'credential-should-not-appear' not in (tmp_path / 'state.json').read_text()
