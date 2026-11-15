"""Provider identity, source validation and credential privacy regressions."""
import hashlib
import json
from datetime import datetime, timezone

import pytest
from aplomb.api.storage import MemoryStore
from aplomb.research.keyed_markets import KeyedSourceError
from aplomb.research.stock_accounts import capture, normalize, request_spec


def test_eodhd_requires_explicit_provider_exchange():
    with pytest.raises(KeyedSourceError, match='provider_exchange_suffix_required'):
        request_spec('eodhd', 'AAPL')
    url, _ = request_spec('eodhd', 'AAPL.US')
    assert url.endswith('/AAPL.US')


def test_ticker_mismatch_is_rejected():
    with pytest.raises(KeyedSourceError, match='provider_symbol_mismatch'):
        normalize('fmp', 'AAPL', [{'symbol': 'MSFT', 'price': 5}], '2026-11-15')
    body = {'status': 'OK', 'results': {'ticker': 'MSFT'}}
    with pytest.raises(KeyedSourceError, match='provider_symbol_mismatch'):
        normalize('massive', 'AAPL', body, '2026-11-15')
    rows = {'pagination': {}, 'data': [{'symbol':'MSFT','date':'2026-11-13','close':3}]}
    with pytest.raises(KeyedSourceError, match='provider_symbol_mismatch'):
        normalize('marketstack', 'AAPL', rows, '2026-11-15')


def test_daily_observations_reject_future_and_invalid_ohlc():
    with pytest.raises(KeyedSourceError, match='invalid_source_dates'):
        normalize('eodhd','AAPL.US',[{'date':'2026-11-16','close':1}],'2026-11-15')
    with pytest.raises(KeyedSourceError, match='invalid_ohlc_range'):
        normalize('eodhd','AAPL.US',[{'date':'2026-11-13','open':3,'high':2,'low':1,'close':3}],'2026-11-15')


def test_capture_refuses_echo_and_retains_owned_source(monkeypatch):
    monkeypatch.setenv('APLOMB_FMP_KEY', 'private-test-secret')
    monkeypatch.setenv('APLOMB_FMP_RIGHTS_CONFIRMED', 'true')
    store = MemoryStore()
    url = 'https://financialmodelingprep.com/stable/quote?symbol=AAPL'
    def echo(provider, target, params, secret):
        return url, json.dumps([{'symbol':'AAPL','price':1,'extra':secret}]).encode()
    with pytest.raises(KeyedSourceError, match='secret_bearing_response'):
        capture(store,'one','fmp','AAPL',get=echo)
    def safe(provider, target, params, secret):
        return url,b'[{"symbol":"AAPL","price":1}]'
    result = capture(store,'one','fmp','AAPL',get=safe,now=datetime(2026,11,15,tzinfo=timezone.utc))
    owner = 'STOCK_ACCOUNT#' + hashlib.sha256(b'one').hexdigest()
    row, = store.query('cache',owner)
    assert row['sessionId']=='one' and 'private-test-secret' not in json.dumps(row)
    assert result['source_sha256']==hashlib.sha256(row['raw'].encode()).hexdigest()
