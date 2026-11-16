import pytest
from aplomb.api.errors import Conflict, NotFound, ServiceError
from aplomb.contracts import api as a
from aplomb.contracts.models import InvestorContext
from aplomb.profiles.service import ProfileServiceImpl
from pydantic import ValidationError

from tests.unit.profiles.test_profiles import CLOCK, A, B, make_repo


@pytest.fixture(scope='module')
def snapshot_fx(tmp_path_factory):
    from pathlib import Path

    from aplomb.datastore.global_fx import materialize_pinned_global_fx
    from aplomb.datastore.snapshot import LocalDataStore
    root = tmp_path_factory.mktemp('account-operations-fx')
    reference = Path(__file__).resolve().parents[4] / 'data'
    materialize_pinned_global_fx(root, reference, 'snap-20261115-globalfx')
    return LocalDataStore(root).open('snap-20261115-globalfx')


def test_refresh_preserves_receipt_and_rejects_unavailable_history(snapshot_fx):
    service = ProfileServiceImpl(make_repo(), lambda: snapshot_fx, clock=CLOCK)
    p = service.create_account(A, 'robert', a.CreateAccountRequest(name='Yen', version=1, currency='JPY', nativeValueOrigin='imported', nativeValueSource='bank statement',
        portfolio={'totalValue': 100000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}))
    account_id = p.active_account_id
    original = p.accounts[-1].native_valuation
    assert original.native_value_origin == 'imported' and original.native_value_source == 'bank statement'
    refreshed = service.refresh_account(A, 'robert', account_id, p.version)
    assert refreshed.accounts[-1].native_valuation.native_value_origin == 'imported'
    assert refreshed.accounts[-1].native_valuation.native_value_source == 'bank statement'
    assert refreshed.accounts[-1].valuation_history == [original]
    assert refreshed.accounts[-1].native_valuation.reporting_value == pytest.approx(original.reporting_value)
    with pytest.raises(Conflict):
        service.refresh_account(A, 'robert', account_id, p.version)
    with pytest.raises(ServiceError, match='No sourced'):
        service.refresh_account(A, 'robert', account_id, refreshed.version, '2020-01-01')
    assert service.get(A, 'robert') == refreshed
    with pytest.raises(NotFound):
        service.refresh_account(B, 'robert', account_id, 1)


def test_transfer_conserves_holdings_and_total_including_aggregate(snapshot_fx):
    service = ProfileServiceImpl(make_repo(), lambda: snapshot_fx, clock=CLOCK)
    p = service.create_account(A, 'robert', a.CreateAccountRequest(name='Second', version=1, currency='CAD',
        portfolio={'totalValue': 1000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}))
    source, dest = p.accounts[-1].account_id, p.accounts[0].account_id
    p = service.select_account(A, 'robert', 'aggregate', p.version)
    before_total = p.portfolio.total_value
    before = {x.ticker: x.weight_pct * before_total / 100 for x in p.portfolio.positions}
    result = service.transfer_account(A, 'robert', source, dest, 400, p.version)
    after = {x.ticker: x.weight_pct * result.portfolio.total_value / 100 for x in result.portfolio.positions}
    assert result.portfolio.total_value == pytest.approx(before_total)
    assert after == pytest.approx(before)
    assert result.accounts[-1].portfolio.total_value == pytest.approx(600)
    assert result.accounts[-1].native_valuation is None
    assert len(result.accounts[-1].valuation_history) == 1
    with pytest.raises(ServiceError):
        service.transfer_account(A, 'robert', source, dest, 600, result.version)
    assert service.get(A, 'robert') == result


def test_context_round_trip_and_reject_false_regulatory_claim():
    context = InvestorContext.model_validate({'riskCapacity': 'low', 'riskCapacityOrigin': 'imported',
        'horizons': [{'name': 'Education', 'startDate': '2027-01-01', 'endDate': '2030-01-01', 'origin': 'assumption'}],
        'requirements': [{'name': 'Rent', 'kind': 'spending', 'amount': 100, 'frequency': 'annual', 'origin': 'user'}]})
    assert InvestorContext.model_validate(context.to_wire()) == context
    with pytest.raises(ValidationError):
        InvestorContext.model_validate({'horizons': [{'name': 'Bad', 'startDate': '2030-01-01', 'endDate': '2029-01-01'}]})
    with pytest.raises(ValidationError):
        InvestorContext.model_validate({'requirements': [{'name': 'Tax', 'kind': 'liability', 'amount': 10,
                                                          'origin': 'regulatory', 'sourceUrl': 'https://example.org'}]})


def test_custom_conditions_are_measured_and_survive_duplicate(snapshot_fx):
    service = ProfileServiceImpl(make_repo(), lambda: snapshot_fx, clock=CLOCK)
    p = service.duplicate(A, 'robert')
    p = service.add_custom_rule(A, p.profile_id, a.AddCustomRuleRequest(
        dimension='position', key='SPY', operation='cap', threshold=5, version=p.version))
    p = service.add_custom_rule(A, p.profile_id, a.AddCustomRuleRequest(
        dimension='asset_class', key='cash', operation='floor', threshold=15, version=p.version))
    checks = {item.rule_id: item for item in service.overview(A, p.profile_id, {}).rule_checks}
    assert checks['cap.position.SPY'].status == 'conflict'
    assert checks['floor.asset_class.cash'].status == 'conflict'
    duplicate = service.duplicate(A, p.profile_id)
    assert next(x for x in duplicate.rules if x.rule_id == 'cap.position.SPY').origin == 'user'
    with pytest.raises(ServiceError):
        service.add_custom_rule(A, p.profile_id, a.AddCustomRuleRequest(
            dimension='position', key='SPY;DROP', operation='cap', threshold=5, version=p.version))


def test_account_and_candidate_routes_enforce_session_and_versions(snapshot_fx):
    from aplomb.api.app import create_app
    from aplomb.api.services import Services
    from aplomb.api.settings import Settings
    from fastapi.testclient import TestClient

    svc = ProfileServiceImpl(make_repo(), lambda: snapshot_fx, clock=CLOCK)
    client = TestClient(create_app(Settings(data_version=snapshot_fx.data_version, features={'profile_creator': True}),
                                   Services(profiles=svc, capabilities={'profile_creator'})))
    headers = {'X-Aplomb-Session': A}
    url = '/v1/profiles/robert/accounts'
    body = {'name': 'US', 'currency': 'USD', 'version': 1,
            'portfolio': {'totalValue': 1000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}}
    created = client.post(url, headers=headers, json=body)
    assert created.status_code == 201, created.text
    p = created.json()
    refreshed = client.post(f"{url}/{p['activeAccountId']}/refresh", headers=headers, json={'version': p['version']})
    assert refreshed.status_code == 200, refreshed.text
    assert len(refreshed.json()['accounts'][-1]['valuationHistory']) == 1
    assert client.post(f"{url}/{p['activeAccountId']}/refresh", headers=headers, json={'version': p['version']}).status_code == 409
    assert client.post(f"{url}/{p['activeAccountId']}/refresh", headers={'X-Aplomb-Session': B}, json={'version': 1}).status_code == 404
    candidates = client.get('/v1/profiles/robert/strategic-candidates', headers=headers)
    assert candidates.status_code == 200, candidates.text
    assert len(candidates.json()['candidates']) <= 3


def test_account_valuations_route_adds_private_appraisals_per_account(snapshot_fx):
    """api.md A1.1 over HTTP: traded plus separately appraised private values, per account and combined."""
    from aplomb.api.app import create_app
    from aplomb.api.services import Services
    from aplomb.api.settings import Settings
    from fastapi.testclient import TestClient

    svc = ProfileServiceImpl(make_repo(), lambda: snapshot_fx, clock=CLOCK)
    client = TestClient(create_app(Settings(data_version=snapshot_fx.data_version, features={'profile_creator': True}),
                                   Services(profiles=svc, capabilities={'profile_creator'})))
    headers = {'X-Aplomb-Session': A}
    url = '/v1/profiles/robert/account-valuations'
    before = client.get(url, headers=headers)
    assert before.status_code == 200, before.text
    seed_value = svc.get(A, 'robert').portfolio.total_value
    assert before.json()['accounts'] == [{'accountId': None, 'name': 'Primary', 'modeledTradedValue': seed_value,
                                          'privateValue': 0.0, 'combinedValue': seed_value}]
    created = client.post('/v1/profiles/robert/accounts', headers=headers, json={
        'name': 'Holding', 'currency': 'CAD', 'version': 1,
        'portfolio': {'totalValue': 1000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}})
    assert created.status_code == 201, created.text
    p = created.json()
    valued = client.post(f"/v1/profiles/robert/accounts/{p['activeAccountId']}/private-assets", headers=headers, json={
        'version': p['version'], 'name': 'Private land', 'assetType': 'land', 'liquidityNotes': 'Illiquid',
        'valuationDate': '2026-01-01', 'origin': 'imported', 'sourceDescription': 'Owner appraisal',
        'nativeCurrency': 'CAD', 'nativeValue': 5000})
    assert valued.status_code == 200, valued.text
    summary = client.get(url, headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body['currency'] == 'CAD' and body['profileId'] == 'robert'
    row = body['accounts'][-1]
    assert (row['accountId'], row['modeledTradedValue'], row['privateValue'], row['combinedValue']) == (
        p['activeAccountId'], 1000, 5000, 6000)
    assert body['combinedValue'] == sum(r['combinedValue'] for r in body['accounts'])
    assert 'excluded' in body['limitations'][0]
    assert client.get(url, headers={'X-Aplomb-Session': B}).json()['accounts'][0]['privateValue'] == 0.0
    assert client.get('/v1/profiles/p_0000000000/account-valuations', headers=headers).status_code == 404


def test_private_valuations_are_additional_preserved_and_excluded_from_traded_risk(snapshot_fx):
    service = ProfileServiceImpl(make_repo(), lambda: snapshot_fx, clock=CLOCK)
    p = service.create_account(A, 'robert', a.CreateAccountRequest(name='Holding', version=1, currency='CAD',
        portfolio={'totalValue': 1000, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}))
    account_id = p.active_account_id
    body = {'version': p.version, 'name': 'Private land', 'assetType': 'land', 'liquidityNotes': 'Illiquid',
            'valuationDate': '2026-01-01', 'origin': 'imported', 'sourceDescription': 'Owner appraisal',
            'nativeCurrency': 'CAD', 'nativeValue': 5000}
    p = service.value_private_asset(A, 'robert', account_id, a.PrivateAssetRequest.model_validate(body))
    asset = p.accounts[-1].private_assets[0]
    assert asset.valuation.conversion.native_value_origin == 'imported'
    assert asset.valuation.conversion.native_value_source == 'Owner appraisal'
    assert p.portfolio.total_value == 1000
    summary = service.account_valuation_summary(A, 'robert')
    assert summary['combinedValue'] == 606000
    assert summary['accounts'][-1]['privateValue'] == 5000
    assert 'excluded' in summary['limitations'][0]
    updated = service.value_private_asset(A, 'robert', account_id, a.PrivateAssetRequest.model_validate(
        {**body, 'version': p.version, 'assetId': asset.asset_id, 'nativeValue': 6000}))
    assert updated.accounts[-1].private_assets[0].valuation_history[0] == asset.valuation
    assert service.account_valuation_summary(A, 'robert')['combinedValue'] == 607000
    with pytest.raises(Conflict):
        service.value_private_asset(A, 'robert', account_id, a.PrivateAssetRequest.model_validate(body))
    with pytest.raises(ServiceError, match='No sourced'):
        service.value_private_asset(A, 'robert', account_id, a.PrivateAssetRequest.model_validate(
            {**body, 'version': updated.version, 'assetId': asset.asset_id, 'nativeCurrency': 'ZZZ'}))
    assert service.get(A, 'robert') == updated


def test_target_drift_and_legacy_edits_preserve_explicit_origin(snapshot_fx):
    from tests.unit.profiles.test_profiles import create_request

    service = ProfileServiceImpl(make_repo(), lambda: snapshot_fx, clock=CLOCK)
    context = {'inputOrigins': {'reportingCurrency': 'imported'},
        'targetAllocations': [{'dimension': 'position', 'key': 'SPY', 'targetPct': 50, 'origin': 'imported'},
                              {'dimension': 'theme', 'key': 'unsupported_custom_tag', 'targetPct': 10, 'origin': 'user'}],
        'rebalancing': {'frequency': 'quarterly', 'driftThresholdPct': 5, 'origin': 'user'}}
    body = create_request(investorContext=context)
    profile = service.create(A, a.CreateProfileRequest.model_validate(body))
    comparison = service.allocation_targets(A, profile.profile_id)
    measured, missing = comparison['targets']
    assert measured['actualPct'] == pytest.approx(60)
    assert measured['driftPct'] == pytest.approx(10)
    assert measured['state'] == 'outside_drift_threshold'
    assert measured['factId'] in comparison['facts']
    assert missing['state'] == 'unavailable' and missing['unavailableReason'] == 'unsupported_key'
    legacy_update = create_request(name='Renamed')
    profile = service.replace(A, profile.profile_id, a.UpdateProfileRequest.model_validate(
        {**legacy_update, 'version': profile.version}), profile.version)
    assert profile.investor_context.input_origins['reportingCurrency'] == 'imported'
    clone = service.duplicate(A, profile.profile_id)
    assert clone.investor_context == profile.investor_context


def test_explicit_historical_knowledge_excludes_later_fx_at_snapshot_cutoff(snapshot_fx):
    """An observation day equal to the latest price day is still a historical cutoff."""
    from aplomb.api.app import create_app
    from aplomb.api.runtime import gate_factory
    from aplomb.api.services import Services
    from aplomb.api.settings import Settings
    from aplomb.optimizer.check import CheckServiceImpl
    from aplomb.timemachine import validate_asof
    from fastapi.testclient import TestClient

    from tests.unit.profiles.test_profiles import create_request

    profiles = ProfileServiceImpl(make_repo(), lambda: snapshot_fx, clock=CLOCK)
    body = create_request(reportingCurrency='EUR', rules=[])
    profile = profiles.create(A, a.CreateProfileRequest.model_validate(body))
    checks = CheckServiceImpl(profiles, lambda: snapshot_fx, clock=CLOCK)
    app = create_app(Settings(data_version=snapshot_fx.data_version), Services(profiles=profiles, checks=checks))
    client = TestClient(app)
    request = {'profileId': profile.profile_id, 'move': None, 'asOf': snapshot_fx.data_as_of}
    current = client.post('/v1/check', headers={'X-Aplomb-Session': A}, json=request)
    historical = client.post('/v1/check', headers={'X-Aplomb-Session': A},
                             json={**request, 'knowledgeMode': 'historical'})
    assert current.status_code == historical.status_code == 200
    assert current.json()['portfolioAfter']['metrics']['volatilityPct'] is not None
    assert historical.json()['portfolioAfter']['metrics']['volatilityPct'] is None
    assert any(s['datasetId'] == 'fx_boc_global' for f in current.json()['facts'].values() for s in f['sources'])
    assert not any(s['datasetId'] == 'fx_boc_global' for f in historical.json()['facts'].values() for s in f['sources'])
    # Replay requires future observations for reveal, so the latest date is not eligible.
    with pytest.raises(ServiceError, match='asOf must be between'):
        validate_asof(snapshot_fx.data_as_of, profile, snapshot_fx)
    replay_gate = gate_factory(lambda: snapshot_fx)({'dataVersion': snapshot_fx.data_version,
        'asOf': snapshot_fx.data_as_of, 'mode': 'historical', 'profile': profile.to_wire()})
    assert replay_gate.mode == 'historical'
    assert replay_gate.global_fx('EUR').rows == ()


def test_refresh_keeps_legacy_native_value_provenance_unknown(snapshot_fx):
    from aplomb.contracts.models import Profile
    service = ProfileServiceImpl(make_repo(), lambda: snapshot_fx, clock=CLOCK)
    profile = service.create_account(A, 'robert', a.CreateAccountRequest(name='Old', version=1,
        portfolio={'totalValue': 100, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}))
    assert profile.accounts[-1].native_valuation.native_value_origin == 'user'
    wire = profile.to_wire()
    receipt = wire['accounts'][-1]['nativeValuation']
    receipt.pop('nativeValueOrigin')
    receipt.pop('nativeValueSource')
    _, stored = service._load(A, 'robert')
    profile = service._save(A, Profile.model_validate(wire), stored)
    refreshed = service.refresh_account(A, 'robert', profile.active_account_id, profile.version)
    assert refreshed.accounts[-1].native_valuation.native_value_origin is None
    assert refreshed.accounts[-1].native_valuation.native_value_source is None
