"""Real HTTP smoke for native-currency account receipts and complete target allocations."""
import json
import os
import uuid
from pathlib import Path

import httpx
from aplomb.contracts import CONTRACT_VERSION
from aplomb.contracts.registry import adapter


def main():
    client = httpx.Client(base_url=os.environ.get('APLOMB_QA_API', 'http://localhost:8001/v1'),
                          headers={'X-Aplomb-Session': 's_' + str(uuid.uuid4())}, timeout=30)
    records = []
    def call(method, path, contract, body=None, status=200):
        response = client.request(method, path, json=body)
        assert response.status_code == status, (path, response.text[:300])
        value = response.json()
        adapter(contract).validate_python(value)
        records.append({'method': method, 'path': path, 'status': status, 'contract': contract})
        return value
    assert call('GET', '/meta', 'Meta')['contractVersion'] == CONTRACT_VERSION
    profile = call('POST', '/profiles/amira/duplicate', 'Profile', {'name': 'FX and target checks'}, 201)
    pid = profile['profileId']
    created = call('POST', f'/profiles/{pid}/accounts', 'Profile', {'name': 'Japan account',
        'version': profile['version'], 'currency': 'JPY',
        'portfolio': {'totalValue': 100000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}}, 201)
    receipt = created['accounts'][-1]['nativeValuation']
    assert receipt['nativeCurrency'] == 'JPY' and receipt['reportingCurrency'] == 'CAD'
    assert len(receipt['verifiedChecks']) == 8 and receipt['quotes'][0]['source']['datasetId'] == 'fx_boc_global'
    assert abs(receipt['nativeValue'] * receipt['conversionRate'] - receipt['reportingValue']) < 1e-6
    combined = call('POST', f'/profiles/{pid}/accounts/aggregate/select', 'Profile', {'version': created['version']})
    assert abs(combined['portfolio']['totalValue'] - profile['portfolio']['totalValue'] - receipt['reportingValue']) < 1e-6
    result = call('POST', '/rebalance/check', 'RebalanceResponse', {'profileId': pid,
        'profileVersion': combined['version'], 'positions': [{'ticker': 'SPY', 'weightPct': 5}, {'ticker': 'XBB.TO', 'weightPct': 95}], 'window': {'code': '1y'}})
    assert result['portfolioBefore']['totalValue'] == result['portfolioAfter']['totalValue']
    assert {p['ticker']: p['weightPct'] for p in result['portfolioAfter']['positions']} == {'SPY': 5, 'XBB.TO': 95}
    assert any(p['targetPct'] == 0 for p in result['changes'])
    assert all(fid in result['facts'] for rule in result['ruleChecksAfter'] for fid in [rule['valueFactId'], rule['thresholdFactId']] if fid)
    unchanged = call('GET', f'/profiles/{pid}', 'Profile')
    assert unchanged == combined
    call('POST', '/rebalance/check', 'ApiError', {'profileId': pid, 'profileVersion': 999,
        'positions': [{'ticker': 'SPY', 'weightPct': 100}]}, 409)
    call('POST', '/rebalance/check', 'ApiError', {'profileId': pid, 'profileVersion': combined['version'],
        'positions': [{'ticker': 'SPY', 'weightPct': 10}]}, 422)
    out = Path(os.environ.get('APLOMB_QA_OUTPUT', 'docs/evidence/investigation-controls'))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'http-smoke.json').write_text(json.dumps({'contractVersion': CONTRACT_VERSION, 'checks': records,
        'accountValuation': receipt, 'rebalance': result}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'checks': len(records), 'nativeCurrency': 'JPY', 'reportingCurrency': 'CAD',
                      'verifiedFXChecks': len(receipt['verifiedChecks']), 'allocationChanges': len(result['changes'])}))


if __name__ == '__main__':
    main()
