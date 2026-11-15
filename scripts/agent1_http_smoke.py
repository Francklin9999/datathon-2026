"""Real HTTP acceptance for Agent 1. Synthetic investor inputs; no model is invoked."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx
from aplomb.contracts.registry import adapter

BASE = os.environ.get('APLOMB_QA_API', 'http://localhost:8101/v1')
OUTPUT = Path(os.environ.get('APLOMB_QA_OUTPUT', 'docs/evidence/parallel/agent-1'))


def main():
    session = 's_' + str(uuid.uuid4())
    client = httpx.Client(base_url=BASE, headers={'X-Aplomb-Session': session}, timeout=60)
    records = []

    def call(method, path, body=None, status=200, contract=None, session_id=None):
        headers = {'X-Aplomb-Session': session_id} if session_id else None
        retries = 0
        response = client.request(method, path, json=body, headers=headers)
        while response.status_code == 429 and status != 429 and retries < 2:
            # Respect the real session limiter; do not weaken production controls for QA.
            time.sleep(min(5, max(1, int(response.headers.get('Retry-After', '1')))))
            retries += 1
            response = client.request(method, path, json=body, headers=headers)
        assert response.status_code == status, f'{method} {path}: {response.status_code} != {status}: {response.text[:1000]}'
        value = response.json()
        if contract:
            adapter(contract).validate_python(value)
        records.append({'method': method, 'path': path, 'status': status, 'contract': contract, 'rateLimitRetries': retries})
        return value

    meta = call('GET', '/meta', contract='Meta')
    seed = call('GET', '/profiles/amira', contract='Profile')
    inputs = {key: seed[key] for key in ('age', 'riskLevel', 'horizonYears', 'objective', 'experience', 'preferences')}
    inputs.update(name='Synthetic EU investor', reportingCurrency='EUR',
                  portfolio={'totalValue': 100000, 'positions': [{'ticker': 'SPY', 'weightPct': 70},
                                                                   {'ticker': 'XBB.TO', 'weightPct': 30}]},
                  rules=None, fromDraftRunId=None,
                  investorContext={'country': 'FR', 'investorType': 'synthetic research foundation', 'language': 'fr',
                    'riskCapacity': 'low', 'riskCapacityOrigin': 'imported',
                    'horizons': [{'name': 'Project', 'startDate': '2027-01-01', 'endDate': '2032-01-01', 'origin': 'assumption'}],
                    'requirements': [{'name': 'Annual spending', 'kind': 'spending', 'amount': 1000,
                                      'frequency': 'annual', 'dueDate': '2027-06-01', 'origin': 'user'},
                                     {'name': 'Reserve', 'kind': 'liquidity', 'amount': 500,
                                      'frequency': 'once', 'dueDate': '2027-06-01', 'origin': 'imported'}],
                    'objectives': [{'name': 'Education', 'horizonYears': 5, 'priority': 1,
                                    'targetAmount': 30000, 'allocatedValue': 10000, 'annualContribution': 1000,
                                    'assumedReturnPct': 2, 'origin': 'assumption'}]})
    p = call('POST', '/profiles', inputs, status=201, contract='Profile')
    pid = p['profileId']
    assert p['reportingCurrency'] == 'EUR' and p['investorContext']['riskCapacityOrigin'] == 'imported'
    assert p['investorContext']['horizons'][0]['origin'] == 'assumption'
    assert call('GET', f'/profiles/{pid}', status=404, session_id='s_' + str(uuid.uuid4()), contract='ApiError')
    cp = call('POST', f'/profiles/{pid}/duplicate', {'name': 'Independent copy'}, status=201, contract='Profile')
    assert cp['investorContext'] == p['investorContext'] and cp['profileId'] != pid
    p = call('POST', f'/profiles/{pid}/custom-rules', {'version': p['version'], 'dimension': 'position',
        'key': 'SPY', 'operation': 'cap', 'threshold': 20}, contract='Profile')
    overview = call('GET', f'/profiles/{pid}/overview?window=1y', contract='OverviewResponse')
    assert any(r['ruleId'] == 'cap.position.SPY' and r['status'] == 'conflict' for r in overview['ruleChecks'])
    p = call('POST', f'/profiles/{pid}/accounts', {'name': 'Yen account', 'currency': 'JPY', 'version': p['version'],
        'portfolio': {'totalValue': 1000000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}}, status=201, contract='Profile')
    new_id = p['activeAccountId']
    receipt = p['accounts'][-1]['nativeValuation']
    assert receipt['nativeCurrency'] == 'JPY' and receipt['reportingCurrency'] == 'EUR'
    assert abs(receipt['reportingValue'] - receipt['nativeValue'] * receipt['conversionRate']) < 1e-6
    original = receipt.copy()
    stale = p['version']
    p = call('POST', f'/profiles/{pid}/accounts/{new_id}/refresh', {'version': p['version']}, contract='Profile')
    assert p['accounts'][-1]['valuationHistory'][-1] == original
    call('POST', f'/profiles/{pid}/accounts/{new_id}/refresh', {'version': stale}, status=409, contract='ApiError')
    call('POST', f'/profiles/{pid}/accounts/{new_id}/refresh', {'version': p['version'], 'asOf': '2020-01-01'}, status=422, contract='ApiError')
    assert call('GET', f'/profiles/{pid}', contract='Profile') == p
    p = call('POST', f'/profiles/{pid}/accounts/aggregate/select', {'version': p['version']}, contract='Profile')
    total = p['portfolio']['totalValue']
    destination = p['accounts'][0]['accountId']
    p = call('POST', f'/profiles/{pid}/accounts/{new_id}/transfer', {'version': p['version'],
        'destinationAccountId': destination, 'amountReporting': 100}, contract='Profile')
    assert abs(p['portfolio']['totalValue'] - total) < 1e-6
    assert p['accounts'][-1]['nativeValuation'] is None and len(p['accounts'][-1]['valuationHistory']) == 2
    call('POST', f'/profiles/{pid}/accounts/{new_id}/transfer', {'version': p['version'],
        'destinationAccountId': destination, 'amountReporting': 1e9}, status=422, contract='ApiError')
    assert call('GET', f'/profiles/{pid}', contract='Profile') == p
    summary_before = call('GET', f'/profiles/{pid}/account-valuations')
    p = call('POST', f'/profiles/{pid}/accounts/{destination}/private-assets', {'version': p['version'],
        'name': 'Synthetic art', 'assetType': 'art', 'valuationDate': '2026-11-01', 'origin': 'user',
        'sourceDescription': 'Synthetic appraisal, not a real asset', 'nativeCurrency': 'EUR', 'nativeValue': 2500,
        'liquidityNotes': 'Sale may take months'}, contract='Profile')
    summary_after = call('GET', f'/profiles/{pid}/account-valuations')
    assert abs(summary_after['combinedValue'] - summary_before['combinedValue'] - 2500) < 1e-6
    assert 'excluded' in summary_after['limitations'][0]
    scenario = call('POST', f'/profiles/{pid}/requirements-scenario', {'asOf': '2027-01-01', 'through': '2027-12-31',
        'liquidCapital': 2000, 'annualReturnPct': 0, 'cashflows': []})
    assert scenario['state'] == 'scenario_funded' and scenario['endingValue'] == 1000
    assert scenario['events'][0]['reserve'] == 500
    candidates = call('GET', f'/profiles/{pid}/strategic-candidates')
    assert len(candidates['candidates']) <= 3
    assert all(fid in candidates['facts'] for c in candidates['candidates'] for fid in c['factIds'])
    funds = call('POST', '/decision/target-funding', {'totalValue': 100, 'before': {'A': .6, 'B': .4},
        'target': {'A': .25, 'C': .75}, 'externalFlow': 20})
    assert abs(funds['purchases'] - funds['sales'] - 20) < 1e-9
    call('POST', '/decision/target-funding', {'totalValue': 100, 'before': {'A': 1},
        'target': {'A': 1}, 'externalFlow': -100}, status=422, contract='ApiError')
    shock = call('POST', '/risk/scenario', {'asOf': '2024-01-01', 'weights': {'A': .6, 'B': .4},
        'shock': {'kind': 'interest_rate', 'key': 'CAD', 'change': 100, 'assumption': 'synthetic parallel shock'},
        'sensitivities': {'A': {'value': -5, 'source': 'synthetic assumption', 'asOf': '2024-01-01'}}})
    assert shock['impactFraction'] is None and abs(shock['knownImpactFraction'] + .03) < 1e-12 and shock['missing'] == ['B']
    evidence = {'source_id': 'synthetic', 'url': 'https://example.com/synthetic', 'content_sha256': 'a' * 64,
                'available_at': '2024-01-05T00:00:00Z', 'retrieved_at': '2024-01-06T00:00:00Z', 'licence': 'synthetic'}
    look = {'asOf': '2024-01-06', 'historical': True, 'positions': {'US78462F1030': .5, 'US0378331005': .5},
        'snapshots': [{'fundIsin': 'US78462F1030', 'holdingsDate': '2024-01-04', 'evidence': evidence,
                       'constituents': [{'isin': 'US0378331005', 'weight': .4}]}]}
    lt = call('POST', '/risk/fund-look-through', look)
    assert lt['direct']['US0378331005'] == .5 and lt['indirect']['US0378331005'] == .2 and lt['unresolvedWeight'] == .3
    look['asOf'] = '2024-01-05'
    call('POST', '/risk/fund-look-through', look, status=422, contract='ApiError')
    start = date(2024, 1, 1)
    rows, factors = [], []
    for i in range(35):
        a, b = (start + timedelta(days=i)).isoformat(), (start + timedelta(days=i + 1)).isoformat()
        x = ((i % 7) - 3) / 100
        rows.append({'start': a, 'end': b, 'value': .0001 + .001 + 1.5 * x})
        factors.append({'start': a, 'end': b, 'riskFree': .0001, 'factors': {'market': x}, 'source': 'synthetic'})
    fit = call('POST', '/risk/factor-fit', {'names': ['market'], 'returns': rows, 'factors': factors})
    assert abs(fit['betas']['market'] - 1.5) < 1e-9 and fit['observations'] == 35
    sources = call('GET', '/risk/source-inputs')
    assert {'sofr', 'cftc-cot', 'treasury-par', 'treasury-debt'} <= {s['id'] for s in sources['sources']}
    providers = call('GET', '/risk/providers')
    assert {p['id'] for p in providers['providers']} == {'fama-french', 'aqr', 'cboe', 'occ', 'finra-volume'}
    assert {p['id'] for p in providers['setAside']} == {'oanda', 'cme', 'fred', 'finra-interest'}
    call('POST', '/risk/providers/cme/capture', {'asOf': meta['dataAsOf']}, status=503, contract='ApiError')
    call('POST', '/risk/providers/oanda/capture', {'asOf': meta['dataAsOf']}, status=503, contract='ApiError')
    call('POST', '/risk/providers/fred/capture', {'asOf': meta['dataAsOf']}, status=503, contract='ApiError')
    call('POST', '/risk/providers/finra-interest/capture', {'asOf': meta['dataAsOf']}, status=503, contract='ApiError')
    blocked = next((p['id'] for p in providers['providers'] if p['status'] == 'permission_required'), None)
    if blocked:
        call('POST', f'/risk/providers/{blocked}/capture', {'asOf': meta['dataAsOf']}, status=503, contract='ApiError')
    old = call('GET', '/risk/source-inputs?asOf=2020-01-01')
    assert all(s['status'] != 'available' for s in old['sources'])
    as_of = meta['dataAsOf']
    check = call('POST', '/check', {'profileId': pid, 'move': None, 'asOf': as_of}, contract='CheckResult')
    history = call('POST', '/check', {'profileId': pid, 'move': None, 'asOf': as_of, 'knowledgeMode': 'historical'}, status=422, contract='ApiError')
    assert check['asOf'] == as_of and history['error']['code'] == 'insufficient_data'
    OUTPUT.mkdir(parents=True, exist_ok=True)
    evidence_path = OUTPUT / 'http-smoke.json'
    evidence_path.write_text(json.dumps({'testData': 'synthetic investor, sensitivities, fund holdings and factor observations',
        'modelExecution': 'none', 'apiBase': BASE, 'reportingCurrency': 'EUR', 'snapshotAsOf': as_of,
        'checks': records, 'historicalCheck': {'explicitHistoricalStatus': history['error']['code'], 'historicalMessage': history['error']['message'],
        'currentLimitations': check.get('limitations')}}, indent=2) + '\n')
    print(json.dumps({'checks': len(records), 'evidence': str(evidence_path), 'reportingCurrency': 'EUR'}))


if __name__ == '__main__':
    main()
