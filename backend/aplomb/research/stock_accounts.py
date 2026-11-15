"""Account-backed stock observations with bounded provider-specific requests.

A source ticker is provider-local and is never a global issuer identity. Raw
responses and normalized observations are session-owned; credentials never enter
source URLs or captures. Account use is subject to the provider's terms.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.limiter import SessionLimiter
from aplomb.api.storage import Write
from aplomb.ledger.sources import strict_json
from aplomb.research.keyed_markets import KeyedSourceError, NoRedirect, number

PROVIDERS = {
    'fmp': {'key': 'APLOMB_FMP_KEY', 'origin': 'https://financialmodelingprep.com/stable/quote',
            'docs': 'https://site.financialmodelingprep.com/developer/docs/quickstart',
            'signup': 'https://site.financialmodelingprep.com/developer/docs/dashboard', 'limit': 200,
            'operation': 'provider quote by ticker'},
    'eodhd': {'key': 'APLOMB_EODHD_KEY', 'origin': 'https://eodhd.com/api/eod/',
              'docs': 'https://eodhd.com/financial-apis/quick-start-with-our-financial-data-apis',
              'signup': 'https://eodhd.com/register', 'limit': 18,
              'operation': 'daily history by provider CODE.EXCHANGE'},
    'massive': {'key': 'APLOMB_MASSIVE_KEY', 'origin': 'https://api.massive.com/v3/reference/tickers/',
                'docs': 'https://massive.com/docs/rest/stocks/tickers/ticker-overview',
                'signup': 'https://massive.com/dashboard/signup', 'limit': 200,
                'operation': 'US listing detail by provider ticker'},
    'marketstack': {'key': 'APLOMB_MARKETSTACK_KEY', 'origin': 'https://api.marketstack.com/v2/eod',
                    'docs': 'https://marketstack.com/documentation',
                    'signup': 'https://marketstack.com/pricing', 'limit': 80,
                    'operation': 'daily bars by provider ticker'},
}
MAX_BYTES = 1_000_000


def request_spec(provider, symbol, *, today=None):
    if provider not in PROVIDERS or not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,24}', symbol):
        raise KeyedSourceError('invalid_provider_or_symbol')
    origin = PROVIDERS[provider]['origin']
    if provider == 'eodhd':
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9-]*\.[A-Z0-9]{2,10}', symbol):
            raise KeyedSourceError('provider_exchange_suffix_required')
        last = today or date.today()
        params = {'from': (last - timedelta(days=45)).isoformat(), 'to': last.isoformat(), 'fmt': 'json'}
        return origin + symbol, params
    if provider == 'massive':
        return origin + symbol, {}
    if provider == 'marketstack':
        return origin, {'symbols': symbol, 'limit': 30, 'sort': 'DESC'}
    return origin, {'symbol': symbol}


def fetch(provider, url, params, secret):
    safe_url = url + (('?' + urlencode(params)) if params else '')
    headers = {'Accept': 'application/json', 'User-Agent': 'Aplomb Research'}
    if provider == 'massive':
        headers['Authorization'] = 'Bearer ' + secret
        private_url = safe_url
    else:
        key = {'fmp': 'apikey', 'eodhd': 'api_token', 'marketstack': 'access_key'}[provider]
        private_url = url + '?' + urlencode({**params, key: secret})
    try:
        with build_opener(NoRedirect).open(Request(private_url, headers=headers), timeout=12) as response:
            if response.status != 200:
                raise KeyedSourceError('provider_unavailable')
            raw = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        code = ('credential_or_plan_rejected' if exc.code in (401, 403) else
                'rate_limited' if exc.code == 429 else
                'instrument_not_found' if exc.code == 404 else 'provider_unavailable')
        raise KeyedSourceError(code) from None
    except (URLError, TimeoutError, OSError):
        raise KeyedSourceError('provider_unavailable') from None
    if len(raw) > MAX_BYTES:
        raise KeyedSourceError('source_too_large')
    if secret.encode() in raw:
        raise KeyedSourceError('source_echoed_credential')
    return safe_url, raw


def _day(value, as_of):
    try:
        result = date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        raise KeyedSourceError('invalid_source_dates') from None
    if result > as_of:
        raise KeyedSourceError('invalid_source_dates')
    return result


def _bars(rows, *, symbol, as_of, verify_symbol):
    if not isinstance(rows, list) or not rows or len(rows) > 50:
        raise KeyedSourceError('source_result_bound_or_empty')
    output, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise KeyedSourceError('invalid_source_schema')
        if verify_symbol and row.get('symbol') != symbol:
            raise KeyedSourceError('provider_symbol_mismatch')
        day = _day(row.get('date'), as_of)
        if day in seen:
            raise KeyedSourceError('duplicate_source_date')
        seen.add(day)
        bar = {'date': day}
        for name in ('open', 'high', 'low', 'close', 'volume'):
            val = row.get(name)
            bar[name] = None if val is None else number(val)
        if bar['close'] is None:
            raise KeyedSourceError('invalid_source_number')
        if all(bar[k] is not None for k in ('open','high','low','close')):
            low, high = Decimal(bar['low']), Decimal(bar['high'])
            if low > min(Decimal(bar[k]) for k in ('open','close')) or high < max(Decimal(bar[k]) for k in ('open','close')) or low > high:
                raise KeyedSourceError('invalid_ohlc_range')
        adjusted = row.get('adjusted_close')
        bar['adj_close'] = number(adjusted) if adjusted is not None else None
        output.append(bar)
    return sorted(output, key=lambda item: item['date'])


def normalize(provider, symbol, body, as_of):
    if provider == 'fmp':
        if not isinstance(body, list) or len(body) != 1 or not isinstance(body[0], dict):
            raise KeyedSourceError('invalid_source_schema')
        row = body[0]
        if row.get('symbol') != symbol:
            raise KeyedSourceError('provider_symbol_mismatch')
        return {'provider_symbol': symbol, 'price': number(row['price']), 'price_unit': 'currency not stated',
                'currency': None, 'observed_date': None,
                'identity_basis': 'exact provider ticker; exchange and issuer not established'}
    if provider == 'massive':
        if not isinstance(body, dict) or body.get('status') != 'OK' or not isinstance(body.get('results'), dict):
            raise KeyedSourceError('invalid_source_schema')
        row = body['results']
        if row.get('ticker') != symbol:
            raise KeyedSourceError('provider_symbol_mismatch')
        fields = ('ticker','name','market','locale','currency_name','primary_exchange','type','cik','composite_figi','share_class_figi','list_date')
        company = {key:row.get(key) for key in fields}
        if any(v is not None and (not isinstance(v,str) or len(v)>500) for v in company.values()):
            raise KeyedSourceError('invalid_company_profile')
        return {'provider_symbol':symbol, 'company':company,
                'identity_basis':'provider-reported listing identifiers; not independently verified'}
    if provider == 'eodhd':
        bars = _bars(body,symbol=symbol,as_of=as_of,verify_symbol=False)
        return {'provider_symbol':symbol,'currency':None,'bars':bars,
                'identity_basis':'provider path CODE.EXCHANGE; response rows do not echo instrument identity',
                'adjustment':'provider adjusted close where present; availability before capture unknown'}
    if provider == 'marketstack':
        if not isinstance(body, dict) or not isinstance(body.get('pagination'),dict):
            raise KeyedSourceError('invalid_source_schema')
        bars = _bars(body.get('data'),symbol=symbol,as_of=as_of,verify_symbol=True)
        return {'provider_symbol':symbol,'currency':None,'bars':bars,
                'identity_basis':'exact provider ticker; exchange identity not established',
                'adjustment':'provider data; availability before capture unknown'}
    raise KeyedSourceError('invalid_provider_or_symbol')


def connection_status():
    return [{'id':provider, 'signup_url':info['signup'], 'documentation_url':info['docs'],
             'credential_variable':info['key'], 'credential_present':bool(os.getenv(info['key'])),
             'rights_confirmed':os.getenv(info['key'].removesuffix('_KEY')+'_RIGHTS_CONFIRMED')=='true',
             'supported_operation':info['operation']} for provider,info in PROVIDERS.items()]


def capture(store, sid, provider, symbol, *, get=fetch, now=None):
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise KeyedSourceError('invalid_clock')
    url,params = request_spec(provider,symbol,today=stamp.date())
    info = PROVIDERS[provider]
    secret = os.getenv(info['key'],'')
    if not secret:
        raise KeyedSourceError('signup_key_required')
    if os.getenv(info['key'].removesuffix('_KEY')+'_RIGHTS_CONFIRMED') != 'true':
        raise KeyedSourceError('account_data_rights_unconfirmed')
    SessionLimiter(store).take('stock-'+hashlib.sha256(secret.encode()).hexdigest(),provider,info['limit'],86400)
    safe_url,raw = get(provider,url,params,secret)
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES or secret.encode() in raw or secret in safe_url:
        raise KeyedSourceError('invalid_or_secret_bearing_response')
    try:
        body = strict_json(raw.decode('utf-8'))
        if secret in json.dumps(body):
            raise KeyedSourceError('source_echoed_credential')
        observation = normalize(provider,symbol,body,stamp.date().isoformat())
    except (KeyError,TypeError,UnicodeError,ValueError) as exc:
        if isinstance(exc,KeyedSourceError):
            raise
        raise KeyedSourceError('invalid_source_schema') from None
    digest=hashlib.sha256(raw).hexdigest()
    result={'status':'available','provider':provider,'observation':observation,'source_url':safe_url,
            'source_sha256':digest,'dataset_version':'stock-'+provider+'-'+digest[:16],
            'retrieved_at':stamp.isoformat(),'available_at':stamp.isoformat(),'published_at':None,
            'licence':'Account-specific terms; no public redistribution rights asserted',
            'documentation_url':info['docs'],
            'limitations':['Provider ticker is not a globally unique security identity.',
                           'Historical publication/revision availability prior to capture is unknown.',
                           'Provider plan and data entitlement limit actual availability.']}
    owner='STOCK_ACCOUNT#'+hashlib.sha256(sid.encode()).hexdigest()
    sk='CAPTURE#'+hashlib.sha256((safe_url+digest).encode()).hexdigest()
    item={'revision':1,'sessionId':sid,'raw':raw.decode('utf-8'),'result':result}
    try:
        store.transact([Write('cache',owner,sk,item,None)])
    except Conflict:
        prior=store.get('cache',owner,sk)
        if not prior or prior.get('sessionId')!=sid or prior.get('raw')!=item['raw']:
            raise KeyedSourceError('capture_integrity_failure') from None
        return prior['result']
    return result
