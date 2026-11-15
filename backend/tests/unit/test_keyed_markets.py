"""Credential safety, exact listings, financial availability and session isolation."""
import json
from datetime import datetime, timezone

import pytest
from aplomb.api.storage import MemoryStore
from aplomb.research.keyed_markets import KeyedSourceError, capture, normalize, request_spec


def test_exact_listing_and_operation_required():
    with pytest.raises(KeyedSourceError, match='exact_mic_required'):
        request_spec('twelve-data', 'AAPL')
    with pytest.raises(KeyedSourceError, match='unsupported_source_operation'):
        request_spec('finnhub', 'AAPL', kind='income')
    body = {'meta': {'symbol': 'AAPL', 'mic_code': 'XNAS', 'interval': '1day'}, 'values': []}
    with pytest.raises(KeyedSourceError, match='provider_listing_mismatch'):
        normalize('twelve-data', 'AAPL', 'XNGS', body, '2026-11-15')


def test_financial_period_is_not_publication():
    result = normalize('alpha-vantage', 'IBM', None, {'symbol': 'IBM', 'annualReports': [
        {'fiscalDateEnding': '2025-12-31', 'reportedCurrency': 'USD', 'netIncome': '-12.50'}
    ]}, '2026-11-15', 'income')
    loss = next(row for row in result['statements'] if row['concept'] == 'netIncome')
    assert loss['value'] == '-12.50'
    assert loss['published_at'] is None
    assert result['availability_basis'] == 'current capture; fiscal period end is not publication'


def test_secret_echo_never_reaches_store(monkeypatch):
    monkeypatch.setenv('APLOMB_FINNHUB_KEY', 'private-test-secret')
    monkeypatch.setenv('APLOMB_FINNHUB_RIGHTS_CONFIRMED', 'true')
    store = MemoryStore()
    def get(provider, params, secret):
        return 'https://finnhub.io/api/v1/stock/profile2?symbol=AAPL', json.dumps({'ticker': 'AAPL', 'name': secret}).encode()
    with pytest.raises(KeyedSourceError, match='secret_bearing_response'):
        capture(store, 'session-one', 'finnhub', 'AAPL', get=get)
    assert not store.query('cache', 'KEYED_MARKET#')


def test_capture_owner_and_original_are_retained(monkeypatch):
    monkeypatch.setenv('APLOMB_FINNHUB_KEY', 'private-test-secret')
    monkeypatch.setenv('APLOMB_FINNHUB_RIGHTS_CONFIRMED', 'true')
    store = MemoryStore()
    def get(provider, params, secret):
        return 'https://finnhub.io/api/v1/stock/profile2?symbol=AAPL', b'{"ticker":"AAPL","name":"Apple","currency":"USD"}'
    a = capture(store, 'session-one', 'finnhub', 'AAPL', get=get, now=datetime(2026,11,15,tzinfo=timezone.utc))
    b = capture(store, 'session-two', 'finnhub', 'AAPL', get=get, now=datetime(2026,11,16,tzinfo=timezone.utc))
    assert a['source_sha256'] == b['source_sha256']
    assert a['available_at'] != b['available_at']
    assert 'private-test-secret' not in json.dumps(a)
