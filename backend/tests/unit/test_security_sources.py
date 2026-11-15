import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from aplomb.intelligence.entities import Evidence
from aplomb.intelligence.exact import exact_pair
from aplomb.intelligence.holdings_ingest import issuer_holdings_csv, nport_holdings_xml
from aplomb.intelligence.overlap import Holding, portfolio_lookthrough

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)
ISIN = 'US0378331005'
LEI = 'HWUPKR0MPOU8FGXBT394'


def evidence(raw):
    return Evidence(source_id='test_only', url='https://example.org/data',
                    content_sha256=hashlib.sha256(raw).hexdigest(), available_at=NOW,
                    retrieved_at=NOW, licence='test fixture')


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


def test_holdings_do_not_resolve_names_and_respect_history():
    raw = b'ISIN,Weight (%)\nUS0378331005,7.5\n,10\n'
    snapshot, missing = issuer_holdings_csv(raw, fund_isin='US4642872000',
                                            effective_date=date(2026, 11, 12), evidence=evidence(raw))
    assert missing[0]['weight_pct'] == 10
    positions = [Holding(security_id='isin:US4642872000', weight_pct=100.0)]
    current = portfolio_lookthrough(positions, [snapshot], date(2026, 11, 15), fund_ids={'isin:US4642872000'})
    assert current['exposures'][0]['weight_pct'] == 7.5
    assert current['unresolved_portfolio_weight_pct'] == 92.5
    historical = portfolio_lookthrough(positions, [snapshot], date(2026, 11, 12), fund_ids={'isin:US4642872000'}, historical=True)
    assert historical['unresolved_portfolio_weight_pct'] == 100


def test_nport_rejects_derivatives_and_never_guesses_ids():
    raw = b'''<edgarSubmission xmlns="http://www.sec.gov/edgar/nport"><repPdDate>2026-09-30</repPdDate><invstOrSecs>
    <invstOrSec><identifiers><isin value="US0378331005"/></identifiers><pctVal>4.5</pctVal><payoffProfile>Long</payoffProfile><assetCat>EC</assetCat></invstOrSec>
    <invstOrSec><identifiers><isin value="US67066G1040"/></identifiers><pctVal>2</pctVal><payoffProfile>Long</payoffProfile><assetCat>EC</assetCat><derivativeInfo/></invstOrSec>
    </invstOrSecs></edgarSubmission>'''
    snap, unresolved = nport_holdings_xml(raw, fund_isin='US4642872000', fund_mapping=evidence(b'map'), evidence=evidence(raw))
    assert [h.security_id for h in snap.holdings] == ['isin:US0378331005']
    assert unresolved[0]['weight_pct'] == 2
    later_mapping = evidence(b'map').model_copy(update={'available_at': datetime(2026, 11, 16, tzinfo=timezone.utc), 'retrieved_at': datetime(2026, 11, 16, tzinfo=timezone.utc)})
    later, _ = nport_holdings_xml(raw, fund_isin='US4642872000', fund_mapping=later_mapping, evidence=evidence(raw))
    assert later.evidence.available_at.date() == date(2026, 11, 16)
    assert not later.evidence.visible(date(2026, 11, 15), historical=True)
    with pytest.raises(ValueError):
        nport_holdings_xml(b'<!DOCTYPE x>', fund_isin='US4642872000', fund_mapping=evidence(b'map'), evidence=evidence(b'<!DOCTYPE x>'))


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
    from aplomb.intelligence.master import captured_master, source_route
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
    assert source_route('XLIM', 'filings') == 'bvl_captured_registration_only'
    assert source_route('XLIM', 'prices') == 'unavailable'
    assert source_route('XTKS', 'filings') == 'unavailable'


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
