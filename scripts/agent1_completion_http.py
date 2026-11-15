"""Real HTTP acceptance for Agent 1 models. All investors and extra source rows are synthetic."""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = os.getenv('APLOMB_QA_API', 'http://127.0.0.1:8101/v1')
OUT = Path('docs/evidence/parallel/agent-1/completion-http.json')
SID = 's_' + str(uuid.uuid4())
OTHER = 's_' + str(uuid.uuid4())
client = httpx.Client(base_url=BASE, timeout=45, headers={'X-Aplomb-Session': SID})
records = []


def call(name, method, path, body=None, status=200, session=SID):
    for _ in range(5):
        response = client.request(method, path, json=body, headers={'X-Aplomb-Session': session})
        if response.status_code != 429 or status == 429:
            break
        time.sleep(min(5, int(response.headers.get('Retry-After', '1'))))
    assert response.status_code == status, f'{name}: expected {status}, got {response.status_code}: {response.text[:800]}'
    records.append({'name': name, 'method': method, 'path': path, 'status': status})
    return response.json() if response.content else None


def main():
    meta = call('expanded FX metadata', 'GET', '/meta')
    assert {'CNY', 'INR'} <= set(meta['reportingCurrencies'])
    seed = call('ordinary seed profile', 'GET', '/profiles/robert')
    profile_body = {k: seed[k] for k in ('age', 'riskLevel', 'horizonYears', 'objective', 'experience', 'preferences')}
    profile_body.update(name='Synthetic CNY investor', reportingCurrency='CNY', rules=seed['rules'], fromDraftRunId=None,
        portfolio={'totalValue': 100000, 'positions': [{'ticker': 'SPY', 'weightPct': 60}, {'ticker': 'XBB.TO', 'weightPct': 40}]},
        investorContext={'country': 'IN', 'investorType': 'custom researcher', 'riskCapacity': 'low',
            'inputOrigins': {'reportingCurrency': 'imported'},
            'objectives': [{'name': 'Home', 'horizonYears': 1, 'priority': 1, 'targetAmount': 30000, 'deadline': '2027-06-01', 'origin': 'user'},
                           {'name': 'Education', 'horizonYears': 1, 'priority': 2, 'targetAmount': 90000, 'deadline': '2027-11-01', 'origin': 'imported'}],
            'requirements': [{'name': 'Rent', 'kind': 'spending', 'amount': 2000, 'dueDate': '2027-03-01', 'origin': 'user'}]})
    profile = call('create arbitrary CNY profile', 'POST', '/profiles', profile_body, 201)
    pid, version = profile['profileId'], profile['version']
    assert profile['reportingCurrency'] == 'CNY' and profile['investorContext']['inputOrigins']['reportingCurrency'] == 'imported'
    call('cross-session profile isolation', 'GET', f'/profiles/{pid}', status=404, session=OTHER)
    before_accounts = profile.get('accounts', [])
    profile = call('create INR account with imported origin', 'POST', f'/profiles/{pid}/accounts',
        {'name': 'INR synthetic', 'version': version, 'currency': 'INR', 'nativeValueOrigin': 'imported',
         'nativeValueSource': 'Synthetic external account statement',
         'portfolio': {'totalValue': 100000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}}, 201)
    version = profile['version']
    account = profile['accounts'][-1]
    account_id = account['accountId']
    receipt = account['nativeValuation']
    assert len(profile['accounts']) >= len(before_accounts) + 1
    assert receipt['nativeCurrency'] == 'INR' and receipt['reportingCurrency'] == 'CNY'
    assert math.isclose(receipt['nativeValue'] * receipt['conversionRate'], receipt['reportingValue'], rel_tol=1e-12)
    assert receipt.get('nativeValueOrigin') == 'imported' and receipt.get('nativeValueSource') == 'Synthetic external account statement'
    call('reject stale account edit', 'PUT', f'/profiles/{pid}/accounts/{account_id}', {'version': version - 1, 'name': 'Stale'}, 409)
    profile = call('edit account name and holdings', 'PUT', f'/profiles/{pid}/accounts/{account_id}',
        {'version': version, 'name': 'Renamed INR account', 'portfolio': {'totalValue': receipt['reportingValue'],
          'positions': [{'ticker': 'SPY', 'weightPct': 60}, {'ticker': 'XBB.TO', 'weightPct': 40}]} })
    version = profile['version']
    edited = next(a for a in profile['accounts'] if a['accountId'] == account_id)
    assert edited['name'] == 'Renamed INR account' and len(edited['portfolio']['positions']) == 2
    condition = {'when': {'mode': 'all', 'clauses': [{'dimension': 'position', 'key': 'SPY', 'operator': 'gt', 'threshold': 50}]},
                 'require': {'dimension': 'position', 'key': 'SPY', 'operator': 'lte', 'threshold': 40}}
    profile = call('save typed conditional policy', 'POST', f'/profiles/{pid}/condition-rules',
        {'version': version, 'name': 'Synthetic concentration condition', 'conditional': condition, 'origin': 'imported'})
    version = profile['version']
    custom = next(r for r in profile['rules'] if r.get('conditional'))
    assert custom['origin'] == 'imported'
    overview = call('evaluate conditional policy', 'GET', f'/profiles/{pid}/overview?window=1y')
    check = next(r for r in overview['ruleChecks'] if r['ruleId'] == custom['ruleId'])
    assert check['status'] == 'conflict' and check['valueFactId'] in overview['facts']
    malformed = {'version': version, 'name': 'Unsafe', 'conditional': {'require': {'dimension': 'position', 'key': 'SPY',
        'operator': 'lte', 'threshold': 40, 'sql': 'DROP TABLE users'}}}
    call('reject arbitrary code', 'POST', f'/profiles/{pid}/condition-rules', malformed, 422)
    clone = call('duplicate with origin', 'POST', f'/profiles/{pid}/duplicate', {'name': 'Comparison clone'}, 201)
    assert clone['investorContext']['inputOrigins']['reportingCurrency'] == 'imported'
    comp_body = {'profiles': [{'profileId': pid, 'version': version}, {'profileId': clone['profileId'], 'version': clone['version']}],
                 'currency': 'CNY', 'window': {'code': '1y'}}
    comparison = call('compare aligned portfolios', 'POST', '/portfolios/compare', comp_body)
    assert comparison['currency'] == 'CNY' and comparison['sameSample'] and len(comparison['portfolios']) == 2
    stale = {**comp_body, 'profiles': [{**comp_body['profiles'][0], 'version': version + 1}, comp_body['profiles'][1]]}
    call('reject stale comparison', 'POST', '/portfolios/compare', stale, 409)
    call('reject cross-session comparison', 'POST', '/portfolios/compare', comp_body, 404, OTHER)
    covariance = call('portfolio covariance', 'POST', '/risk/covariance',
        {'profileId': pid, 'version': version, 'window': {'code': '1y'}})
    matrix = covariance['dailyCovariance']
    assert len(matrix) == 2 and math.isclose(matrix[0][1], matrix[1][0], rel_tol=1e-12, abs_tol=1e-15)
    assert all(fid in covariance['facts'] for fid in covariance['sourceFactIds'])
    liquidity = call('partial liquidity preserves unknown positions', 'POST', f'/profiles/{pid}/liquidity-analysis',
        {'version': version, 'asOf': '2026-11-15', 'through': '2026-11-20', 'targetWithdrawal': 1000000,
         'assumptions': [{'ticker': 'SPY', 'saleDates': ['2026-11-16', '2026-11-17'], 'dailyCapacity': 1000,
            'halfSpreadBps': 50, 'impactBps': 50, 'source': 'synthetic assumption', 'asOf': '2026-11-15'}]})
    assert liquidity['state'] == 'unknown_missing_positions' and liquidity['missingHoldings'] == ['XBB.TO']
    assert math.isclose(liquidity['knownNetProceeds'], 1980)
    details = call('explicit quantity provenance', 'POST', f'/profiles/{pid}/position-details',
        {'version': version, 'quantities': [{'ticker': 'SPY', 'quantity': 2, 'asOf': '2026-11-10',
         'origin': 'imported', 'source': 'Synthetic account statement'}]})
    spy = next(row for row in details['positions'] if row['ticker'] == 'SPY')
    assert spy['quantity']['quantity'] == 2 and spy['quantity']['origin'] == 'imported' and 'modeled' in spy['valueBasis']
    call('reject unowned quantity', 'POST', f'/profiles/{pid}/position-details',
        {'version': version, 'quantities': [{'ticker': 'NOTOWNED', 'quantity': 2, 'asOf': '2026-11-10',
          'origin': 'user', 'source': 'synthetic'}]}, 422)
    plan_body = {'profileVersion': version, 'asOf': '2027-01-01', 'through': '2027-12-31',
        'annualReturnPct': 0, 'annualInflationPct': 0, 'amountBasis': 'nominal',
        'capitalSources': [{'kind': 'account', 'id': account_id, 'amount': 1000, 'origin': 'user'}],
        'outsideIsAdditional': False, 'cashflows': [], 'goalIndexes': [0, 1], 'requirementIndexes': [0],
        'liquidityAggregation': 'independent', 'allocationTreatment': 'shared_pool'}
    plan = call('joint simultaneous goals and spending', 'POST', f'/profiles/{pid}/joint-plan', plan_body)
    assert plan['state'] == 'scenario_shortfall' and plan['requiredInitialCapital'] == 122000
    assert len(plan['goals']) == 2 and plan['additionalInitialCapital'] == 121000
    call('reject stale joint plan', 'POST', f'/profiles/{pid}/joint-plan', {**plan_body, 'profileVersion': version + 1}, 409)
    call('reject cross-session joint plan', 'POST', f'/profiles/{pid}/joint-plan', plan_body, 404, OTHER)
    ev = {'source_id': 'synthetic', 'url': 'https://example.org/fixture', 'content_sha256': 'a' * 64,
          'available_at': '2024-01-05T00:00:00Z', 'retrieved_at': '2024-01-06T00:00:00Z', 'licence': 'synthetic fixture'}
    spy_isin, ivv, apple = 'US78462F1030', 'US4642872000', 'US0378331005'
    nested_body = {'asOf': '2024-01-06', 'historical': True, 'positions': {spy_isin: .8, apple: .2},
        'knownFunds': [spy_isin, ivv], 'snapshots': [
         {'fundIsin': spy_isin, 'holdingsDate': '2024-01-04', 'evidence': ev,
          'constituents': [{'isin': ivv, 'weight': .5}, {'isin': apple, 'weight': .25}]},
         {'fundIsin': ivv, 'holdingsDate': '2024-01-04', 'evidence': ev,
          'constituents': [{'isin': apple, 'weight': .5}]}]}
    nested = call('nested exact identifier exposure', 'POST', '/risk/nested-fund-look-through', nested_body)
    assert math.isclose(nested['direct'][apple], .2) and math.isclose(nested['indirect'][apple], .4)
    assert math.isclose(nested['unresolvedWeight'], .4)
    call('reject future capture on historical cutoff', 'POST', '/risk/nested-fund-look-through', {**nested_body, 'asOf': '2024-01-05'}, 422)
    performance = call('portfolio return sample', 'GET', f'/profiles/{pid}/performance?window=1y')
    series = performance['series']
    assert len(series) >= 41
    factor_rows = []
    for i in range(40):
        actual_return = series[i + 1]['value'] / series[i]['value'] - 1
        factor_rows.append({'start': series[i]['date'], 'end': series[i + 1]['date'], 'riskFree': .0001,
                            'factors': {'synthetic': (actual_return - .0001 - .001) / 1.5}})
    factor_result = call('factor exposure against exact matching synthetic periods', 'POST', f'/profiles/{pid}/factor-exposure',
        {'version': version, 'window': {'code': '1y'}, 'names': ['synthetic'],
         'source': {'origin': 'user', 'description': 'synthetic fixture constructed from portfolio return sample',
                    'currency': 'CNY', 'availableAt': '2026-11-12'}, 'factors': factor_rows})
    assert factor_result['state'] == 'calculated' and factor_result['observations'] == 40
    assert math.isclose(factor_result['betas']['synthetic'], 1.5, abs_tol=1e-9)
    assert all(fid in factor_result['facts'] for fid in factor_result['sourceFactIds'])
    factor_bad = {'version': version, 'window': {'code': '1y'}, 'names': ['x'], 'source': {'origin': 'user',
        'description': 'synthetic fixture', 'currency': 'USD', 'availableAt': '2026-11-12'}, 'factors': []}
    call('reject currency mismatch for factor exposure', 'POST', f'/profiles/{pid}/factor-exposure', factor_bad, 422)
    factor_bad['source']['currency'] = 'CNY'
    call('reject insufficient factor sample', 'POST', f'/profiles/{pid}/factor-exposure', factor_bad, 422)
    call('reject cross-session factor exposure', 'POST', f'/profiles/{pid}/factor-exposure', factor_bad, 404, OTHER)
    same_day_check = {'profileId': pid, 'move': None, 'asOf': '2026-11-12', 'knowledgeMode': 'current'}
    current_check = call('current snapshot check at observation cutoff', 'POST', '/check', same_day_check)
    assert current_check['asOf'] == '2026-11-12'
    historical_check = call('point-in-time check at same observation cutoff', 'POST', '/check',
        {**same_day_check, 'knowledgeMode': 'historical'}, 422)
    assert historical_check['error']['code'] == 'insufficient_data'
    call('reject current mode at earlier cutoff', 'POST', '/check',
        {**same_day_check, 'asOf': '2025-01-01'}, 422)
    source_input = call('sourced risk context', 'GET', '/risk/source-inputs')
    assert len(source_input['sources']) >= 5 and source_input['knownAt']
    historical_sources = call('withhold unavailable historical source captures', 'GET', '/risk/source-inputs?asOf=2020-01-01')
    assert all(s['status'] != 'available' for s in historical_sources['sources'])
    shock = call('first-order sensitivity with unknown holding', 'POST', '/risk/scenario',
        {'asOf': '2026-11-12', 'weights': {'SPY': .6, 'XBB.TO': .4},
         'shock': {'kind': 'interest_rate', 'key': 'synthetic curve', 'change': 100, 'assumption': 'parallel increase'},
         'sensitivities': {'SPY': {'value': -5, 'source': 'synthetic assumption', 'asOf': '2026-11-12'}}})
    assert shock['impactFraction'] is None and shock['missing'] == ['XBB.TO'] and math.isclose(shock['knownImpactFraction'], -.03)
    funding = call('deposit funds final allocation', 'POST', '/decision/target-funding',
        {'totalValue': 100, 'before': {'SPY': .6, 'XBB.TO': .4}, 'target': {'SPY': .25, 'QQQ': .75}, 'externalFlow': 20})
    assert funding['purchases'] == 90 and funding['sales'] == 70 and funding['afterValue'] == 120
    call('reject withdrawal exhausting capital', 'POST', '/decision/target-funding',
        {'totalValue': 100, 'before': {'SPY': 1}, 'target': {'SPY': 1}, 'externalFlow': -100}, 422)
    requirements = call('explicit liability and spending model', 'POST', f'/profiles/{pid}/requirements-scenario',
        {'asOf': '2027-01-01', 'through': '2027-12-31', 'liquidCapital': 3000, 'annualReturnPct': 0, 'cashflows': []})
    assert requirements['state'] == 'scenario_funded' and requirements['endingValue'] == 1000
    targets = call('stored target availability', 'GET', f'/profiles/{pid}/allocation-targets')
    assert targets['profileVersion'] == version and isinstance(targets['targets'], list)
    candidates = call('deterministic strategic candidates', 'GET', f'/profiles/{pid}/strategic-candidates')
    assert len(candidates['candidates']) <= 3 and all(fid in candidates['facts'] for candidate in candidates['candidates'] for fid in candidate['factIds'])
    profile = call('record private appraisal', 'POST', f'/profiles/{pid}/accounts/{account_id}/private-assets',
        {'version': version, 'name': 'Synthetic private equity', 'assetType': 'private equity', 'liquidityNotes': 'not immediately liquid',
         'valuationDate': '2026-11-10', 'origin': 'imported', 'sourceDescription': 'Synthetic statement',
         'nativeCurrency': 'CNY', 'nativeValue': 5000})
    version = profile['version']
    summary_value = call('private and traded valuation summary', 'GET', f'/profiles/{pid}/account-valuations')
    assert any(a['privateValue'] == 5000 for a in summary_value['accounts'])
    account = next(a for a in profile['accounts'] if a['accountId'] == account_id)
    if account.get('nativeValuation'):
        profile = call('refresh native receipt with history', 'POST', f'/profiles/{pid}/accounts/{account_id}/refresh', {'version': version})
        version = profile['version']
        account = next(a for a in profile['accounts'] if a['accountId'] == account_id)
        assert len(account['valuationHistory']) >= 1
        call('reject unavailable historical FX without changing state', 'POST', f'/profiles/{pid}/accounts/{account_id}/refresh',
             {'version': version, 'asOf': '2020-01-01'}, 422)
        assert call('failed refresh retains account', 'GET', f'/profiles/{pid}') == profile
    destination = next(a for a in profile['accounts'] if a['accountId'] != account_id)
    capital_before = sum(a['portfolio']['totalValue'] for a in profile['accounts'])
    profile = call('transfer conserves traded capital', 'POST', f'/profiles/{pid}/accounts/{account_id}/transfer',
        {'version': version, 'destinationAccountId': destination['accountId'], 'amountReporting': 100})
    assert math.isclose(sum(a['portfolio']['totalValue'] for a in profile['accounts']), capital_before, rel_tol=1e-12)
    summary = {'createdAt': datetime.now(timezone.utc).isoformat(), 'api': BASE, 'snapshot': 'snap-20261115-a1-fx-expanded',
               'syntheticInputs': True, 'checks': records, 'fxReceipt': receipt,
               'jointPlan': {'state': plan['state'], 'requiredInitialCapital': plan['requiredInitialCapital']},
               'limitations': ['No model or AWS execution; synthetic user inputs.', 'The synthetic factor is constructed from actual portfolio sample returns to verify exact alignment and coefficient arithmetic; it is not independent factor evidence.']}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'checks': len(records), 'evidence': str(OUT), 'snapshot': summary['snapshot']}))


if __name__ == '__main__':
    main()
