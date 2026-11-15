"""Test identifier matching and credential/capture safety for connected sources."""
import json
from datetime import datetime, timezone

import pytest
from aplomb.api.storage import MemoryStore
from aplomb.research.chain_accounts import ChainSourceError, capture, normalize, request_spec


def test_cmc_uses_numeric_id_and_rejects_other_asset():
    with pytest.raises(ChainSourceError, match='numeric_asset_id_required'):
        request_spec('coinmarketcap', 'BTC')
    body = {'status': {'error_code': '0'}, 'data': [{'id': 2, 'quote': [{'symbol': 'USD', 'price': 10}]}]}
    with pytest.raises(ChainSourceError, match='identifier_mismatch'):
        normalize('coinmarketcap', '1', body)
    body['data'][0]['id'] = 1
    assert normalize('coinmarketcap', '1', body)['price'] == '10'


def test_exact_ethereum_identity_and_alchemy_rpc_shape():
    with pytest.raises(ChainSourceError, match='exact_ethereum_address_required'):
        request_spec('goldrush', 'eth-mainnet')
    with pytest.raises(ChainSourceError, match='identifier_mismatch'):
        normalize('blockscout', '0x' + '0'*40, {'hash': '0x' + '1'*40})
    with pytest.raises(ChainSourceError, match='invalid_rpc_response'):
        normalize('alchemy', 'ethereum', {'jsonrpc': '2.0', 'id': 1, 'result': 'nan'})


def test_credentials_never_in_result_or_capture(monkeypatch):
    monkeypatch.setenv('APLOMB_ALCHEMY_KEY', 'sensitive-demo-key')
    monkeypatch.setenv('APLOMB_ALCHEMY_RIGHTS_CONFIRMED', 'true')
    store = MemoryStore()
    def good(provider, url, method, body, secret):
        assert secret not in url and method == 'POST'
        return b'{"jsonrpc":"2.0","id":1,"result":"0x20"}'
    result = capture(store, 'one', 'alchemy', 'ethereum', get=good, now=datetime(2026,11,15,tzinfo=timezone.utc))
    assert result['observation']['block_number'] == '32'
    assert 'sensitive-demo-key' not in json.dumps(result)
    def echo(provider, url, method, body, secret):
        return json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': secret}).encode()
    with pytest.raises(ChainSourceError, match='secret_bearing_response'):
        capture(store, 'another', 'alchemy', 'ethereum', get=echo)


def test_goldrush_rejects_incomplete_page_and_foreign_account():
    identifier = '0x' + '0'*40
    base = {'error': False, 'data': {'address': identifier, 'chain_id': 1, 'items': [], 'pagination': {'has_more': True}}}
    with pytest.raises(ChainSourceError, match='result_limit'):
        normalize('goldrush', identifier, base)
    base['data']['pagination'] = None
    base['data']['chain_id'] = 137
    with pytest.raises(ChainSourceError, match='identifier_mismatch'):
        normalize('goldrush', identifier, base)


def test_malformed_envelopes_fail_as_provider_errors():
    for document in ({'status': []}, {'status': {'error_code': 0}, 'data': [None]}):
        with pytest.raises(ChainSourceError):
            normalize('coinmarketcap', '1', document)
    address='0x'+'1'*40
    with pytest.raises(ChainSourceError):
        normalize('goldrush',address,{'error':False,'data':{'items':[],'address':address,'chain_id':1,'pagination':'unexpected'}})
