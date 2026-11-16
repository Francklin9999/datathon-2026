import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from aplomb.intelligence.exact import exact_pair

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)
ISIN = 'US0378331005'
LEI = 'HWUPKR0MPOU8FGXBT394'


def test_exact_pair_requires_matching_row_and_handles_truncation():
    wrong = json.dumps({'data': [{'attributes': {'isin': 'US67066G1040', 'lei': LEI}}],
                        'meta': {'pagination': {'currentPage': 1, 'lastPage': 2}}}).encode()
    result, raw = exact_pair(ISIN, LEI, fetch=lambda url: wrong, max_pages=1, now=NOW)
    assert result['status'] == 'search_incomplete' and raw is None


def test_exact_pair_from_actual_captured_gleif_page():
    raw = Path('docs/evidence/parallel/agent-2/security/gleif-apple-isins-page-4.json').read_bytes()
    body = json.loads(raw)
    assert any(row['attributes'] == {'lei': LEI, 'isin': ISIN} for row in body['data'])
    # Feed the actual fourth page after three empty but correctly paginated pages.
    def fetch(url):
        from urllib.parse import parse_qs, urlsplit
        page = int(parse_qs(urlsplit(url).query)['page[number]'][0])
        return raw if page == 4 else json.dumps({'data': [], 'meta': {'pagination': {
            'currentPage': page, 'lastPage': 5}}}).encode()
    result, selected = exact_pair(ISIN, LEI, fetch=fetch, now=NOW)
    assert selected == raw and result['relationship']['object_id'] == 'lei:' + LEI
    assert result['relationship']['valid_from'] == '2026-11-15'


def test_real_indexed_partial_disclosure_is_time_gated():
    from aplomb.intelligence.disclosure_examples import aapu_partial_lookthrough
    available = aapu_partial_lookthrough(date(2026, 11, 15), historical=True)
    assert available['exposures'][0]['security_id'] == 'isin:US0378331005'
    assert available['exposures'][0]['weight_pct'] == pytest.approx(12.0058273429)
    assert available['unresolved_portfolio_weight_pct'] == pytest.approx(87.9941726571)
    earlier = aapu_partial_lookthrough(date(2026, 1, 31), historical=True)
    assert earlier['exposures'] == [] and earlier['unresolved_portfolio_weight_pct'] == 100


def test_coinmetrics_actual_capture_and_licence_gate():
    from aplomb.api.storage import MemoryStore
    from aplomb.intelligence.coinmetrics import CoinMetricsError, capture, latest
    raw = Path('docs/evidence/parallel/agent-2/security/coinmetrics-btc-2026-11-15.json').read_bytes()
    result, captured = latest('btc', get=lambda url: raw, now=datetime(2026, 11, 15, 17, tzinfo=timezone.utc))
    assert captured == raw and result['asset'] == 'btc' and result['metric'] == 'PriceUSD'
    assert result['published_at'] is None and result['available_at'].startswith('2026-11-15')
    store = MemoryStore()
    with pytest.raises(CoinMetricsError, match='licence_not_enabled'):
        capture(store, 'session', 'btc', get=lambda url: raw, permitted=False)
    first = capture(store, 'session', 'btc', get=lambda url: raw, permitted=True)
    repeat = capture(store, 'session', 'btc', get=lambda url: raw, permitted=True)
    assert first == repeat and first['source_sha256'] == hashlib.sha256(raw).hexdigest()
    capture(store, 'other-session', 'btc', get=lambda url: raw, permitted=True)
    first_pk = 'COINMETRICS#' + hashlib.sha256(b'session').hexdigest()
    second_pk = 'COINMETRICS#' + hashlib.sha256(b'other-session').hexdigest()
    assert store.query('cache', first_pk)[0]['sessionId'] == 'session'
    assert store.query('cache', second_pk)[0]['sessionId'] == 'other-session'
    with pytest.raises(CoinMetricsError):
        latest('eth', get=lambda url: raw, now=NOW)


def test_sec_rss_rejects_unsafe_links_and_malicious_xml():
    from aplomb.intelligence.sec_structured import SecFeedError, parse
    raw = b'''<rss><channel>
    <item><title>10-K</title><link>https://www.sec.gov/Archives/edgar/data/1/filing</link><pubDate>Mon, 01 Jun 2026 10:00:00 GMT</pubDate></item>
    <item><title>bad</title><link>https://evil.example/Archives/edgar/data/1</link></item>
    </channel></rss>'''
    result = parse(raw, now=NOW)
    assert len(result['items']) == 1 and result['available_at'].startswith('2026-11-15')
    with pytest.raises(SecFeedError):
        parse(b'<!DOCTYPE foo [<!ENTITY x "payload">]><rss>&x;</rss>')


def test_sec_data_library_extracts_only_sec_owned_links():
    from aplomb.intelligence.sec_structured import parse_data_library
    raw = b'''<html><a href="/data-research/sec-markets-data/form-n-port-data-sets">Form N-PORT</a>
        <a href="https://evil.example/data-research/steal">Fake</a>
        <a href="javascript:alert(1)">No</a></html>'''
    result = parse_data_library(raw, now=NOW)
    assert result['items'] == [{'title': 'Form N-PORT', 'url': 'https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets'}]
    assert result['source_sha256'] == hashlib.sha256(raw).hexdigest()


def test_instrument_master_disambiguates_listing_and_routes_by_mic():
    from aplomb.intelligence.master import captured_master, route_hint
    master = captured_master()
    with pytest.raises(ValueError):
        master.discover(as_of=date(2026, 11, 15), ticker='AAPU')
    both = master.discover(as_of=date(2026, 11, 15), isin='US25461A8743')
    assert {x.mic for x in both} == {'XNAS', 'XLIM'}
    assert len({x.listing_id for x in both}) == 2
    peru = master.discover(as_of=date(2026, 11, 15), ticker='AAPU', mic='XLIM')
    assert len(peru) == 1 and peru[0].valid_from == date(2025, 12, 10)
    assert master.discover(as_of=date(2026, 11, 12), ticker='AAPU', mic='XLIM') == []
    assert master.detail(peru[0].listing_id, as_of=date(2026, 11, 15)) == peru[0]
    assert route_hint('XLIM')['filings'] == 'bvl_captured_registration_only'
    assert route_hint('XLIM')['prices'] == 'unavailable'
    assert route_hint('XTKS')['filings'] == 'unavailable'
    assert route_hint('XYYY')['status'] == 'no_adapter'


def test_us_listings_are_not_routed_to_removed_sec_sources():
    # The 'sec' capability family is owner-removed; the crosswalk must not advertise it.
    from aplomb.intelligence.master import MIC_ROUTES, US_MICS, route_hint
    for mic in US_MICS:
        route = route_hint(mic, asset_class='stock')
        assert (route['filings'], route['financials'], route['prices']) == ('unavailable', 'unavailable', 'tiingo_on_demand')
        assert 'removed' in route['requirement']
    assert not any(str(v).startswith('sec_') for r in MIC_ROUTES.values() for v in r.values())


def test_market_identity_http_workflows_and_failure_states(monkeypatch):
    from aplomb.api.app import create_app
    from aplomb.api.settings import Settings
    from fastapi.testclient import TestClient

    monkeypatch.delenv('APLOMB_COINMETRICS_NONCOMMERCIAL', raising=False)
    monkeypatch.delenv('APLOMB_SEC_CONTACT', raising=False)
    client = TestClient(create_app(Settings()))
    headers = {'X-Aplomb-Session': 's_123e4567-e89b-42d3-a456-426614174000'}
    params = {'isin': 'US25461A8743', 'as_of': '2026-11-15'}
    response = client.get('/v1/intelligence/listings', params=params, headers=headers)
    assert response.status_code == 200 and response.json()['total'] == 2
    listing_id = response.json()['items'][0]['listing_id']
    assert client.get('/v1/intelligence/listings/' + listing_id, params={'as_of': '2026-11-15'}, headers=headers).status_code == 200
    assert client.get('/v1/intelligence/listings', params={'ticker': 'AAPU', 'as_of': '2026-11-15'}, headers=headers).status_code == 422
    assert client.get('/v1/intelligence/disclosures/aapu', params={'as_of': '2026-11-12'}, headers=headers).json()['exposures'] == []
    assert client.get('/v1/intelligence/coinmetrics/btc', headers=headers).status_code == 503
    assert client.get('/v1/intelligence/sec-structured', headers=headers).status_code == 503
    assert client.get('/v1/intelligence/sec-data-library', headers=headers).status_code == 503
