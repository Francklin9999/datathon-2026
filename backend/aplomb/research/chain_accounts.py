"""Read-only connected crypto observations with session-owned immutable captures.

All provider requests are fixed to official HTTPS hosts; credentials only travel in
headers and are excluded from URLs, returned observations, source captures and errors.
CoinMarketCap uses stable numeric asset IDs, while chain balances require addresses.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write
from aplomb.ledger.sources import strict_json

PROVIDERS = {
    'coinmarketcap': {'key': 'APLOMB_COINMARKETCAP_KEY', 'limit': 100,
                      'docs': 'https://coinmarketcap.com/api/documentation/pro-api-reference/cryptocurrency',
                      'operation': 'Latest USD quote by numeric CoinMarketCap asset ID'},
    'blockscout': {'key': 'APLOMB_BLOCKSCOUT_KEY', 'limit': 100,
                   'docs': 'https://docs.blockscout.com/devs/apis',
                   'operation': 'Native balance for exact Ethereum address'},
    'alchemy': {'key': 'APLOMB_ALCHEMY_KEY', 'limit': 100,
                'docs': 'https://www.alchemy.com/docs/how-to-use-api-keys-in-http-headers',
                'operation': 'Ethereum mainnet head block number'},
    'goldrush': {'key': 'APLOMB_GOLDRUSH_KEY', 'limit': 100,
                 'docs': 'https://goldrush.dev/chains/',
                 'operation': 'Ethereum mainnet balances for an exact address or supported chains'},
}
MAX_BYTES = 2_000_000
ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}')


class ChainSourceError(ValueError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_spec(provider, identifier):
    """Return sanitized URL, verb and request bytes, rejecting arbitrary origins/methods."""
    if provider == 'coinmarketcap':
        if not re.fullmatch(r'[1-9][0-9]{0,8}', identifier or ''):
            raise ChainSourceError('numeric_asset_id_required')
        url = 'https://pro-api.coinmarketcap.com/v3/cryptocurrency/quotes/latest?' + urlencode({'id': identifier, 'convert': 'USD'})
        return url, 'GET', None
    if provider == 'alchemy':
        if identifier not in ('', 'ethereum'):
            raise ChainSourceError('ethereum_head_only')
        return 'https://eth-mainnet.g.alchemy.com/v2', 'POST', b'{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}'
    if provider == 'goldrush' and identifier == 'chains':
        return 'https://api.covalenthq.com/v1/chains/', 'GET', None
    if provider in ('blockscout', 'goldrush'):
        if not ADDRESS.fullmatch(identifier or ''):
            raise ChainSourceError('exact_ethereum_address_required')
        if provider == 'blockscout':
            return f'https://api.blockscout.com/1/api/v2/addresses/{identifier}', 'GET', None
        return f'https://api.covalenthq.com/v1/eth-mainnet/address/{identifier}/balances_v2/', 'GET', None
    raise ChainSourceError('unsupported_provider')


def fetch(provider, url, method, body, secret):
    headers = {'Accept': 'application/json', 'User-Agent': 'AplombResearch/1.0'}
    if provider == 'coinmarketcap':
        headers['X-CMC_PRO_API_KEY'] = secret
    else:
        headers['Authorization'] = 'Bearer ' + secret
    if body is not None:
        headers['Content-Type'] = 'application/json'
    request = Request(url, data=body, method=method, headers=headers)
    try:
        with build_opener(_NoRedirect).open(request, timeout=20) as response:
            if response.status != 200:
                raise ChainSourceError('provider_unavailable')
            raw = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        reason = ('credential_or_plan_rejected' if exc.code in (401, 403) else
                  'rate_limited' if exc.code == 429 else
                  'identifier_not_found' if exc.code == 404 else 'provider_unavailable')
        raise ChainSourceError(reason) from None
    except (URLError, OSError, TimeoutError):
        raise ChainSourceError('provider_unavailable') from None
    if len(raw) > MAX_BYTES:
        raise ChainSourceError('source_too_large')
    if secret.encode() in raw:
        raise ChainSourceError('source_echoed_credential')
    return raw


def _number(value, *, nonnegative=True):
    if isinstance(value, bool) or value is None:
        raise ChainSourceError('invalid_source_number')
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ChainSourceError('invalid_source_number') from None
    if not n.is_finite() or (nonnegative and n < 0):
        raise ChainSourceError('invalid_source_number')
    return str(n)


def _bounded_text(value, limit=300):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise ChainSourceError('invalid_source_text')
    return value


def normalize(provider, identifier, body):
    if not isinstance(body, dict):
        raise ChainSourceError('invalid_source_schema')
    if provider == 'coinmarketcap':
        status = body.get('status')
        if not isinstance(status, dict) or status.get('error_code') not in (0, '0'):
            raise ChainSourceError('provider_plan_or_query_rejected')
        rows = body.get('data')
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get('id') != int(identifier):
            raise ChainSourceError('provider_identifier_mismatch')
        row = rows[0]
        quotes = row.get('quote')
        if not isinstance(quotes, list):
            raise ChainSourceError('invalid_source_schema')
        usd = [q for q in quotes if isinstance(q, dict) and q.get('symbol') == 'USD']
        if len(usd) != 1:
            raise ChainSourceError('provider_currency_mismatch')
        return {'asset_id': identifier, 'asset_name': _bounded_text(row.get('name')),
                'asset_symbol': _bounded_text(row.get('symbol'), 50), 'price': _number(usd[0]['price']),
                'price_unit': 'USD', 'market_cap': _number(usd[0]['market_cap']) if usd[0].get('market_cap') is not None else None,
                'last_updated': _bounded_text(usd[0].get('last_updated'), 100),
                'classification': 'Provider quote; numeric asset ID is not an exchange listing identity.'}
    if provider == 'alchemy':
        val = body.get('result')
        if body.get('jsonrpc') != '2.0' or body.get('id') != 1 or not isinstance(val, str) or not re.fullmatch(r'0x[0-9a-fA-F]{1,16}', val):
            raise ChainSourceError('invalid_rpc_response')
        return {'chain': 'ethereum-mainnet', 'chain_id': 1, 'block_number': str(int(val, 16)),
                'method': 'eth_blockNumber', 'classification': 'Provider-reported latest chain head; subject to reorganization.'}
    if provider == 'blockscout':
        if str(body.get('hash', '')).lower() != identifier.lower():
            raise ChainSourceError('provider_identifier_mismatch')
        return {'chain': 'ethereum-mainnet', 'chain_id': 1, 'address': identifier,
                'native_balance_wei': _number(body['coin_balance']) if body.get('coin_balance') is not None else None,
                'is_contract': body.get('is_contract') if isinstance(body.get('is_contract'), bool) else None,
                'classification': 'Provider-indexed native balance; not an ownership attribution.'}
    if provider == 'goldrush':
        if body.get('error') is not False or not isinstance(body.get('data'), dict):
            raise ChainSourceError('provider_plan_or_query_rejected')
        data = body['data']
        rows = data.get('items')
        if not isinstance(rows, list) or len(rows) > 2000:
            raise ChainSourceError('source_result_limit')
        if identifier == 'chains':
            chains = []
            for row in rows:
                if not isinstance(row, dict):
                    raise ChainSourceError('invalid_source_schema')
                chains.append({'chain_id': str(row.get('chain_id', '')), 'name': _bounded_text(row.get('name')),
                               'label': _bounded_text(row.get('label'))})
            return {'chains': chains, 'classification': 'Provider chain coverage; endpoint entitlement varies by plan.'}
        address = data.get('address')
        if not isinstance(address, str) or address.lower() != identifier.lower() or data.get('chain_id') != 1:
            raise ChainSourceError('provider_identifier_mismatch')
        pagination = data.get('pagination')
        if pagination is not None and not isinstance(pagination, dict):
            raise ChainSourceError('invalid_source_schema')
        if pagination and pagination.get('has_more'):
            raise ChainSourceError('source_result_limit')
        items = []
        for row in rows:
            if not isinstance(row, dict):
                raise ChainSourceError('invalid_source_schema')
            contract = row.get('contract_address')
            if contract is not None and (not isinstance(contract, str) or not ADDRESS.fullmatch(contract)):
                raise ChainSourceError('invalid_contract_address')
            decimals = row.get('contract_decimals')
            if decimals is not None and (type(decimals) is not int or not 0 <= decimals <= 255):
                raise ChainSourceError('invalid_contract_decimals')
            items.append({'contract_address': contract, 'symbol': _bounded_text(row.get('contract_ticker_symbol'), 50),
                          'name': _bounded_text(row.get('contract_name')), 'decimals': decimals,
                          'balance_raw': _number(row['balance']) if row.get('balance') is not None else None,
                          'quote_usd': _number(row['quote'], nonnegative=False) if row.get('quote') is not None else None})
        return {'chain': 'ethereum-mainnet', 'chain_id': 1, 'address': identifier, 'balances': items,
                'updated_at': _bounded_text(data.get('updated_at'), 100),
                'classification': 'Provider-indexed balances at capture; address does not identify its beneficial owner.'}
    raise ChainSourceError('unsupported_provider')


def connection_status():
    return [{'id': name, 'credential_present': bool(os.getenv(info['key'])),
             'rights_confirmed': os.getenv(info['key'].removesuffix('_KEY') + '_RIGHTS_CONFIRMED') == 'true',
             'supported_operation': info['operation'], 'documentation_url': info['docs']}
            for name, info in PROVIDERS.items()]


def capture(store, sid, provider, identifier='', *, get=fetch, now=None):
    url, method, body = request_spec(provider, identifier)
    info = PROVIDERS[provider]
    secret = os.getenv(info['key'], '')
    if not secret:
        raise ChainSourceError('signup_key_required')
    if os.getenv(info['key'].removesuffix('_KEY') + '_RIGHTS_CONFIRMED') != 'true':
        raise ChainSourceError('account_data_rights_unconfirmed')
    from aplomb.api.limiter import SessionLimiter
    SessionLimiter(store).take('provider-' + hashlib.sha256(secret.encode()).hexdigest(), provider, info['limit'], 86400)
    raw = get(provider, url, method, body, secret)
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES or secret.encode() in raw:
        raise ChainSourceError('invalid_or_secret_bearing_response')
    try:
        document = strict_json(raw.decode('utf-8'))
        if secret in json.dumps(document):
            raise ChainSourceError('source_echoed_credential')
        stamp = now or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            raise ChainSourceError('invalid_clock')
        observation = normalize(provider, identifier, document)
    except (KeyError, TypeError, UnicodeError, InvalidOperation, ValueError) as exc:
        if isinstance(exc, ChainSourceError):
            raise
        raise ChainSourceError('invalid_source_schema') from None
    digest = hashlib.sha256(raw).hexdigest()
    result = {'status': 'available', 'provider': provider, 'observation': observation,
              'source_url': url, 'source_sha256': digest,
              'source_request': {'method': method, 'url': url, 'body': body.decode('utf-8') if body is not None else None}, 'dataset_version': 'chain-' + provider + '-' + digest[:16],
              'retrieved_at': stamp.isoformat(), 'available_at': stamp.isoformat(), 'published_at': None,
              'documentation_url': info['docs'],
              'licence': 'Configured account terms; no blanket redistribution licence asserted',
              'limitations': ['Source data is provider-reported and current as captured.',
                              'Original publication and revision availability before capture are unknown.',
                              'Account entitlements and allowed reuse must be respected.']}
    owner = 'CHAIN_ACCOUNT#' + hashlib.sha256(sid.encode()).hexdigest()
    sk = 'CAPTURE#' + hashlib.sha256((url + digest).encode()).hexdigest()
    record = {'revision': 1, 'sessionId': sid, 'raw': raw.decode('utf-8'), 'result': result}
    try:
        store.transact([Write('cache', owner, sk, record, None)])
    except Conflict:
        prior = store.get('cache', owner, sk)
        if not prior or prior.get('sessionId') != sid or prior.get('raw') != record['raw']:
            raise ChainSourceError('capture_integrity_failure') from None
        return prior['result']
    return result


def chain_accounts_router(store, session_dependency):
    from fastapi import APIRouter, Depends, Query

    from aplomb.api.errors import ServiceError
    from aplomb.api.limiter import SessionLimiter
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/research/chain-connections')
    def connections(_sid: str = Depends(session_dependency)):
        return {'providers': connection_status()}

    @router.get('/v1/research/chain-provider/{provider}')
    def observation(provider: str, identifier: str = Query(default='', max_length=100), sid: str = Depends(session_dependency)):
        limiter.take(sid, 'chain-account', 4, 60)
        try:
            return capture(store, sid, provider, identifier)
        except ChainSourceError as exc:
            reason = str(exc)
            validation = reason in {'unsupported_provider', 'numeric_asset_id_required', 'ethereum_head_only', 'exact_ethereum_address_required'}
            raise ServiceError('validation_error' if validation else 'upstream_unavailable',
                               'Chain source request rejected' if validation else 'Chain source unavailable',
                               {'reason': reason}) from None
    return router
