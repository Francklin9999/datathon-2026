"""Exercise paired local contracts over HTTP; no LLM, AWS writes, or fixture responses."""
import json
import os
import uuid
from pathlib import Path

import httpx
from aplomb.contracts import CONTRACT_VERSION
from aplomb.contracts.registry import adapter

BASE = os.environ.get('APLOMB_QA_API', 'http://localhost:8001/v1')
OUT = Path(os.environ.get('APLOMB_QA_OUTPUT', 'docs/evidence/global-continuation'))


def main():
    results = []
    sid = 's_' + str(uuid.uuid4())
    client = httpx.Client(base_url=BASE, headers={'X-Aplomb-Session': sid}, timeout=40)

    def call(method, path, contract, body=None, expected=200):
        response = client.request(method, path, json=body)
        assert response.status_code == expected, (method, path, response.status_code, response.text[:300])
        data = response.json()
        adapter(contract).validate_python(data)
        results.append({'method': method, 'path': path, 'status': response.status_code, 'contract': contract})
        return data

    meta = call('GET', '/meta', 'Meta')
    assert meta['contractVersion'] == CONTRACT_VERSION
    assert set(meta['reportingCurrencies']) == {'CAD', 'USD', 'EUR', 'GBP', 'CHF', 'JPY', 'HKD', 'SGD', 'AUD'}
    seed = call('GET', '/profiles/amira', 'Profile')
    payload = {key: seed[key] for key in ('age', 'riskLevel', 'horizonYears', 'objective', 'experience', 'preferences')}
    payload.update(name='UK multi-goal research', reportingCurrency='GBP', rules=None, fromDraftRunId=None,
                   portfolio={'totalValue': 10000, 'positions': [{'ticker': 'SPY', 'weightPct': 60}, {'ticker': 'XBB.TO', 'weightPct': 40}]},
                   investorContext={'country': 'GB', 'investorType': 'individual', 'objectives': [
                       {'name': 'Home', 'horizonYears': 2, 'priority': 1, 'targetAmount': 6000,
                        'allocatedValue': 4000, 'annualContribution': 500, 'assumedReturnPct': 0},
                       {'name': 'Retirement', 'horizonYears': 20, 'priority': 2, 'targetAmount': 50000,
                        'allocatedValue': 6000, 'annualContribution': 1000, 'assumedReturnPct': 3} ]})
    profile = call('POST', '/profiles', 'Profile', payload, 201)
    pid = profile['profileId']
    overview = call('GET', f'/profiles/{pid}/overview', 'OverviewResponse')
    assert overview['facts'] and all(f.get('currency') in (None, 'GBP') for f in overview['facts'].values())
    goals = call('GET', f'/profiles/{pid}/goals', 'GoalFundingResponse')
    assert goals['currency'] == 'GBP' and goals['goals'][0]['projectedValue'] == 5000 and goals['goals'][0]['fundingGap'] == 1000
    profile = call('POST', f'/profiles/{pid}/exposure-limits', 'Profile',
                   {'dimension': 'currency', 'key': 'USD', 'threshold': 30, 'version': profile['version']})
    assert next(r for r in profile['rules'] if r['ruleId'] == 'cap.currency.USD')['origin'] == 'user'
    clone = call('POST', f'/profiles/{pid}/duplicate', 'Profile', {'name': 'Independent duplicate'}, 201)
    assert clone['profileId'] != pid
    assert next(r for r in clone['rules'] if r['ruleId'] == 'cap.currency.USD')['origin'] == 'user'  # duplicate() keeps origins
    archived = call('PATCH', f'/profiles/{pid}/archive', 'Profile', {'archived': True, 'version': profile['version']})
    assert pid not in {p['profileId'] for p in call('GET', '/profiles', 'ProfilesResponse')['items']}
    assert pid in {p['profileId'] for p in call('GET', '/profiles/archived', 'ProfilesResponse')['items']}
    call('PATCH', f'/profiles/{pid}/archive', 'Profile', {'archived': False, 'version': archived['version']})
    airport = call('GET', '/world/airports?country=JPN&limit=2', 'AirportsResponse')
    assert airport['total'] > 2 and all(r['countryIso3'] == 'JPN' for r in airport['items'])
    call('GET', '/world/airports?asOf=2020-01-01', 'ApiError', expected=422)
    passport = call('GET', '/datasets/world_airports', 'DatasetPassport')
    assert passport['rowCount'] == 1154 and passport['status'] == 'in_use' and passport['dataVersion'] == airport['dataVersion']
    country = call('GET', f'/world/countries/GBR?profileId={pid}', 'WorldCountryResponse')
    assert len([f for f in country['macro'] if any(s['datasetId'] == 'world_bank_indicators' for s in f['sources'])]) == 4
    facilities = call('GET', '/world/facilities?limit=3', 'FacilitiesResponse')
    assert facilities['total'] == 1863 and facilities['reportingYear'] == 2024
    assert all(row['ticker'] is None and row['matchConfidence'] == 'none' for row in facilities['items'])
    facility_passport = call('GET', '/datasets/emissions_facilities', 'DatasetPassport')
    assert facility_passport['status'] == 'in_use' and facility_passport['dataVersion'] == facilities['dataVersion']
    call('GET', '/world/facilities?asOf=2020-01-01', 'ApiError', expected=422)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'http-smoke.json').write_text(json.dumps({'meta': meta, 'checks': results, 'profileCurrency': 'GBP',
        'goals': goals, 'airportPassport': passport, 'facilityPassport': facility_passport}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'checks': len(results), 'currency': 'GBP', 'goals': len(goals['goals']),
                      'airports': passport['rowCount']}))


if __name__ == '__main__':
    main()
