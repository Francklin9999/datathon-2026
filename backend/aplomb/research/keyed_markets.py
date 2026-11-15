"""Credential-ready provider observations, never automatic security identity joins.

Keys travel only to fixed official origins. Stored source URLs exclude credentials;
provider errors and secret-echoing responses never enter captures or agent traces.
"""

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

PROVIDERS = {
    'alpha-vantage': {'key': 'APLOMB_ALPHA_VANTAGE_KEY', 'origin': 'https://www.alphavantage.co/query',
                      'signup': 'https://www.alphavantage.co/support/#api-key',
                      'docs': 'https://www.alphavantage.co/documentation/', 'limit': 20},
    'twelve-data': {'key': 'APLOMB_TWELVEDATA_KEY', 'origin': 'https://api.twelvedata.com/time_series',
                    'signup': 'https://twelvedata.com/docs',
                    'docs': 'https://twelvedata.com/docs/market-data/time-series', 'limit': 200},
    'finnhub': {'key': 'APLOMB_FINNHUB_KEY', 'origin': 'https://finnhub.io/api/v1/stock/profile2',
                'signup': 'https://finnhub.io/register',
                'docs': 'https://finnhub.io/docs/api/company-profile2', 'limit': 200},
}
MAX_BYTES = 1_000_000


class KeyedSourceError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_spec(provider, symbol, mic=None, kind="quote"):
    if provider not in PROVIDERS or not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9.^:/_-]{0,39}', symbol):
        raise KeyedSourceError('invalid_provider_or_symbol')
    if mic is not None and not re.fullmatch(r'[A-Z0-9]{4}', mic):
        raise KeyedSourceError('invalid_mic')
    if provider == 'alpha-vantage':
        functions={'quote':'GLOBAL_QUOTE','overview':'OVERVIEW','income':'INCOME_STATEMENT','balance':'BALANCE_SHEET','cashflow':'CASH_FLOW'}
        if kind not in functions:
            raise KeyedSourceError('unsupported_source_operation')
        if mic:
            raise KeyedSourceError('provider_does_not_verify_mic')
        return {'function':functions[kind],'symbol':symbol}
    if provider != 'alpha-vantage' and kind != 'quote':
        raise KeyedSourceError('unsupported_source_operation')
    if provider == 'twelve-data':
        if not mic:
            raise KeyedSourceError('exact_mic_required')
        return {'symbol': symbol, 'mic_code': mic, 'interval': '1day', 'outputsize': 30}
    if mic:
        raise KeyedSourceError('provider_does_not_verify_mic')
    return {'symbol': symbol}


def fetch(provider, params, secret):
    safe_url = PROVIDERS[provider]['origin'] + '?' + urlencode(params)
    private = {**params, 'token' if provider == 'finnhub' else 'apikey': secret}
    url = PROVIDERS[provider]['origin'] + '?' + urlencode(private)
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Aplomb Research'})
    try:
        with build_opener(NoRedirect).open(request, timeout=12) as response:
            if response.status != 200 or response.headers.get_content_type() != 'application/json':
                raise KeyedSourceError('provider_unavailable')
            raw = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        reason = 'credential_or_plan_rejected' if exc.code in (401, 403) else 'rate_limited' if exc.code == 429 else 'instrument_not_found' if exc.code == 404 else 'provider_unavailable'
        raise KeyedSourceError(reason) from None
    except (URLError, OSError, TimeoutError):
        raise KeyedSourceError('provider_unavailable') from None
    if len(raw) > MAX_BYTES:
        raise KeyedSourceError('source_too_large')
    if secret.encode() in raw:
        raise KeyedSourceError('source_echoed_credential')
    return safe_url, raw


def number(value, nonnegative=True):
    if isinstance(value, bool) or value is None:
        raise KeyedSourceError('invalid_source_number')
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise KeyedSourceError('invalid_source_number') from None
    if not n.is_finite() or (nonnegative and n < 0):
        raise KeyedSourceError('invalid_source_number')
    return str(n)


def normalize(provider, symbol, mic, body, as_of, kind="quote"):
    if not isinstance(body, dict):
        raise KeyedSourceError('invalid_source_schema')
    if provider == 'alpha-vantage':
        if 'Information' in body or 'Note' in body:
            raise KeyedSourceError('provider_plan_or_quota_limit')
        if kind == 'overview':
            if body.get('Symbol') != symbol:
                raise KeyedSourceError('provider_symbol_mismatch')
            labels = {key:body.get(key) for key in ('Symbol','Name','AssetType','Description','Exchange','Currency','Country','Sector','Industry','CIK')}
            if any(value is not None and (not isinstance(value,str) or len(value)>15000) for value in labels.values()):
                raise KeyedSourceError('invalid_source_company')
            return {'provider_symbol':symbol,'company':labels,'classification':'provider reported; not primary SEC identity evidence'}
        if kind in ('income','balance','cashflow'):
            if body.get('symbol') != symbol:
                raise KeyedSourceError('provider_symbol_mismatch')
            columns = {'income':('totalRevenue','grossProfit','operatingIncome','netIncome','ebitda','costOfRevenue','incomeTaxExpense','interestExpense'),
                       'balance':('totalAssets','totalLiabilities','totalShareholderEquity','cashAndCashEquivalentsAtCarryingValue','longTermDebt','shortTermDebt'),
                       'cashflow':('operatingCashflow','capitalExpenditures','cashflowFromInvestment','cashflowFromFinancing','dividendPayout','changeInCashAndCashEquivalents')}[kind]
            statements=[]
            for frequency in ('annualReports','quarterlyReports'):
                reports=body.get(frequency,[])
                if not isinstance(reports,list) or len(reports)>200:
                    raise KeyedSourceError('source_result_bound')
                seen=set()
                for report in reports:
                    end=str(date.fromisoformat(report['fiscalDateEnding']))
                    currency=report.get('reportedCurrency')
                    if end>as_of or end in seen or not isinstance(currency,str) or not re.fullmatch(r'[A-Z]{3}',currency):
                        raise KeyedSourceError('invalid_financial_period_or_currency')
                    seen.add(end)
                    for column in columns:
                        value=report.get(column)
                        statements.append({'frequency':frequency,'period_end':end,'concept':column,
                                           'value':None if value in (None,'None','') else number(value,False),'unit':currency,
                                           'published_at':None,'classification':'provider-reported historical financials, not estimates'})
            return {'provider_symbol':symbol,'statements':statements,'source_statement_kind':kind,
                    'availability_basis':'current capture; fiscal period end is not publication'}
        row = body.get('Global Quote', {})
        if row.get('01. symbol') != symbol:
            raise KeyedSourceError('provider_symbol_mismatch')
        observed = str(date.fromisoformat(row['07. latest trading day']))
        if observed > as_of:
            raise KeyedSourceError('future_observation')
        return {'provider_symbol': symbol, 'identity_basis': 'exact provider symbol; exchange identity not established',
                'currency': None, 'price': number(row['05. price']), 'observed_date': observed,
                'volume': number(row['06. volume']), 'price_unit': 'not stated by quote response',
                'classification': 'provider-reported quote; latency depends on plan'}
    if provider == 'twelve-data':
        if body.get('status') == 'error':
            raise KeyedSourceError('provider_plan_or_query_rejected')
        meta, rows = body['meta'], body['values']
        if meta.get('symbol') != symbol or meta.get('mic_code') != mic or meta.get('interval') != '1day':
            raise KeyedSourceError('provider_listing_mismatch')
        currency = meta.get('currency')
        if not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency):
            raise KeyedSourceError('missing_source_currency')
        if not isinstance(rows, list) or len(rows) > 30:
            raise KeyedSourceError('source_result_bound')
        output, seen = [], set()
        for row in rows:
            day = str(date.fromisoformat(row['datetime']))
            if day > as_of or day in seen:
                raise KeyedSourceError('invalid_source_dates')
            seen.add(day)
            bar = {key: number(row[key]) for key in ('open', 'high', 'low', 'close')}
            if Decimal(bar['low']) > min(map(Decimal,bar.values())) or Decimal(bar['high']) < max(map(Decimal,bar.values())):
                raise KeyedSourceError('invalid_ohlc_range')
            output.append({'date': day, **bar, 'volume': number(row['volume']) if row.get('volume') not in ('',None) else None})
        return {'provider_symbol': symbol, 'mic': mic, 'currency': currency, 'bars': sorted(output,key=lambda r:r['date']),
                'exchange_label': meta.get('exchange'), 'timezone': meta.get('exchange_timezone'),
                'adjustment': 'provider default; no independent total-return adjustment asserted'}
    if not body or body.get('ticker') != symbol or not isinstance(body.get('name'), str):
        raise KeyedSourceError('provider_symbol_mismatch')
    profile = {key: body.get(key) for key in ('ticker','name','country','currency','exchange','finnhubIndustry','weburl','ipo')}
    if any(v is not None and (not isinstance(v,str) or len(v)>1000) for v in profile.values()):
        raise KeyedSourceError('invalid_company_profile')
    return {'company': profile, 'identity_basis': 'provider ticker and exchange labels; no ISIN/issuer inference',
            'market_cap_millions_reported': number(body['marketCapitalization']) if body.get('marketCapitalization') is not None else None}


def connection_status():
    result = {'providers': [{'id': provider, 'signup_url': info['signup'], 'documentation_url': info['docs'],
                           'credential_variable': info['key'], 'credential_present': bool(os.getenv(info['key'])),
                           'rights_confirmed': os.getenv(info['key'].removesuffix('_KEY') + '_RIGHTS_CONFIRMED') == 'true',
                           'supported_operation': {'alpha-vantage': 'quote, company overview and financial statements',
                                                   'twelve-data': 'thirty daily bars by exact MIC',
                                                   'finnhub': 'company profile by exact provider symbol'}[provider]}
                          for provider,info in PROVIDERS.items()]}
    result['providers'].append({'id':'tiingo','signup_url':'https://www.tiingo.com/account/api/token', 'credential_variable':'APLOMB_TIINGO_TOKEN','credential_present':bool(os.getenv('APLOMB_TIINGO_TOKEN')), 'rights_confirmed':True,'supported_operation':'US non-fund equity daily history, internal account use'})
    return result


def capture(store, sid, provider, symbol, mic=None, *, kind="quote", get=fetch, now=None):
    params = request_spec(provider,symbol,mic,kind)
    info=PROVIDERS[provider]
    secret=os.getenv(info['key'],'')
    if not secret:
        raise KeyedSourceError('signup_key_required')
    if os.getenv(info['key'].removesuffix('_KEY')+'_RIGHTS_CONFIRMED') != 'true':
        raise KeyedSourceError('account_data_rights_unconfirmed')
    from aplomb.api.limiter import SessionLimiter
    limiter=SessionLimiter(store)
    limiter.take('provider-'+hashlib.sha256(secret.encode()).hexdigest(),provider,info['limit'],86400)
    url,raw=get(provider,params,secret)
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES or secret.encode() in raw:
        raise KeyedSourceError('invalid_or_secret_bearing_response')
    from aplomb.ledger.sources import strict_json
    try:
        body=strict_json(raw.decode('utf-8'))
        if secret in json.dumps(body):
            raise KeyedSourceError('source_echoed_credential')
        stamp=now or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            raise KeyedSourceError('invalid_clock')
        observation=normalize(provider,symbol,mic,body,str(stamp.date()),kind)
    except (KeyError,TypeError,UnicodeError,InvalidOperation,ValueError) as exc:
        if isinstance(exc,KeyedSourceError):
            raise
        raise KeyedSourceError('invalid_source_schema') from None
    digest=hashlib.sha256(raw).hexdigest()
    result={'status':'available','provider':provider,'observation':observation,'source_url':url,
            'source_sha256':digest,'dataset_version':'market-'+provider+'-'+digest[:16],
            'retrieved_at':stamp.isoformat(),'available_at':stamp.isoformat(),'published_at':None,
            'licence':'Configured account terms; rights confirmation required, no blanket redistribution licence',
            'documentation_url':info['docs'],
            'limitations':['Provider symbols/labels are not globally unique issuer identities.',
                           'Original publication and revision availability before capture is unknown.',
                           'Entitlement/latency depend on the actual account; no paid endpoint fallback.']}
    owner='KEYED_MARKET#'+hashlib.sha256(sid.encode()).hexdigest()
    sk='CAPTURE#'+hashlib.sha256((url+digest).encode()).hexdigest()
    record={'revision':1,'sessionId':sid,'raw':raw.decode('utf-8'),'result':result}
    try:
        store.transact([Write('cache',owner,sk,record,None)])
    except Conflict:
        prior=store.get('cache',owner,sk)
        if not prior or prior.get('sessionId')!=sid or prior.get('raw')!=record['raw']:
            raise KeyedSourceError('capture_integrity_failure') from None
        return prior['result']
    return result


def keyed_market_router(store,session_dependency):
    from fastapi import APIRouter, Depends, Query

    from aplomb.api.errors import ServiceError
    from aplomb.api.limiter import SessionLimiter
    router=APIRouter()
    limiter=SessionLimiter(store)

    @router.get('/v1/research/market-connections')
    def connections(_sid:str=Depends(session_dependency)):
        return connection_status()

    @router.get('/v1/research/market-provider/{provider}')
    def observation(provider:str,symbol:str=Query(min_length=1,max_length=40),
                    mic:str|None=Query(default=None,min_length=4,max_length=4),kind:str=Query(default='quote',pattern=r'^(quote|overview|income|balance|cashflow)$'),sid:str=Depends(session_dependency)):
        limiter.take(sid,'keyed-market',4,60)
        try:
            return capture(store,sid,provider,symbol,mic,kind=kind)
        except KeyedSourceError as exc:
            code=str(exc)
            validation=code in {'invalid_provider_or_symbol','invalid_mic','exact_mic_required','provider_does_not_verify_mic','unsupported_source_operation'}
            raise ServiceError('validation_error' if validation else 'upstream_unavailable',
                               'Market source request rejected' if validation else 'Market source unavailable',
                               {'reason':code}) from None
    @router.get('/v1/research/tiingo/{symbol}')
    def tiingo(symbol:str,start:str=Query(pattern=r'^\d{4}-\d{2}-\d{2}$'),
               end:str=Query(pattern=r'^\d{4}-\d{2}-\d{2}$'),sid:str=Depends(session_dependency)):
        limiter.take(sid,'tiingo-research',4,60)
        try:
            return tiingo_capture(store,sid,os.getenv('APLOMB_TIINGO_TOKEN',''),symbol,start,end)
        except (KeyedSourceError,ValueError) as exc:
            reason=str(exc) if isinstance(exc,KeyedSourceError) else 'invalid_dates'
            raise ServiceError('upstream_unavailable','Tiingo source unavailable',{'reason':reason}) from None
    return router


def tiingo_capture(store,sid,token,symbol,start,end):
    from aplomb.datastore.providers import ProviderError, TiingoProvider, urllib_get
    if not token:
        raise KeyedSourceError('signup_key_required')
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9.-]{0,39}',symbol or ''):
        raise KeyedSourceError('invalid_provider_or_symbol')
    first,last=date.fromisoformat(start),date.fromisoformat(end)
    if first>last or (last-first).days>366 or last>datetime.now(timezone.utc).date():
        raise KeyedSourceError('invalid_source_dates')
    from aplomb.api.limiter import SessionLimiter
    SessionLimiter(store).take('provider-'+hashlib.sha256(token.encode()).hexdigest(),'tiingo-research',200,86400)
    originals=[]
    def bounded_get(url,headers):
        status,raw=urllib_get(url,headers)
        if token.encode() in raw:
            raise KeyedSourceError('source_echoed_credential')
        originals.append((url,status,raw))
        return status,raw
    try:
        asset=TiingoProvider(token,http_get=bounded_get).fetch(symbol,start,end)
    except ProviderError as exc:
        raise KeyedSourceError('provider_'+exc.code) from None
    seen=set()
    for row in asset.rows:
        observed=date.fromisoformat(row['date'])
        if not first<=observed<=last or observed in seen:
            raise KeyedSourceError('invalid_source_dates')
        seen.add(observed)
        for name in ('open','high','low','close','adj_close','volume'):
            number(row[name])
    sources=[]
    owner='TIINGO_RESEARCH#'+hashlib.sha256(sid.encode()).hexdigest()
    for url,status,raw in originals:
        if status!=200:
            raise KeyedSourceError('provider_unavailable')
        digest=hashlib.sha256(raw).hexdigest()
        source={'url':url,'sha256':digest,'retrieved_at':asset.retrieved_at,'available_at':asset.retrieved_at,
                'published_at':None,'licence':asset.terms}
        item={'revision':1,'sessionId':sid,'raw':raw.decode('utf-8'),'source':source}
        sk='CAPTURE#'+hashlib.sha256((url+digest).encode()).hexdigest()
        try:
            store.transact([Write('cache',owner,sk,item,None)])
        except Conflict:
            old=store.get('cache',owner,sk)
            if not old or old.get('sessionId')!=sid or old.get('raw')!=item['raw']:
                raise KeyedSourceError('capture_integrity_failure') from None
            source=old['source']
        sources.append(source)
    return {'status':'available','provider':'tiingo','observation':{'provider_symbol':asset.ticker,
             'name':asset.name,'exchange_label':asset.market,'currency':asset.currency,
             'bars':list(asset.rows),'adjustment':'Tiingo adjusted close includes provider split/dividend adjustments'},
            'sources':sources,'limitations':['Internal account use; public redistribution rights are not asserted.',
             'US non-fund equity coverage only, not every globally matching symbol.','Availability before capture is unknown.']}
