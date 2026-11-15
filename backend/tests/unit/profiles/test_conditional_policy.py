"""Policy and account evidence survive normal profile operations."""
import pytest
from aplomb.api.errors import Conflict, NotFound
from aplomb.contracts import api as a
from aplomb.contracts.models import ConditionGroup
from pydantic import ValidationError

from tests.unit.profiles.test_profiles import A, B, create_request, service


def test_conditional_policy_is_persisted_and_evaluated():
    svc = service()
    profile = svc.create(A, a.CreateProfileRequest.model_validate(create_request()))
    condition = {'when': {'mode': 'all', 'clauses': [{'dimension': 'position', 'key': 'SPY', 'operator': 'gt', 'threshold': 50}]},
                 'require': {'dimension': 'position', 'key': 'SPY', 'operator': 'lte', 'threshold': 40}}
    profile = svc.add_conditional_rule(A, profile.profile_id, a.AddConditionalRuleRequest.model_validate(
        {'version': profile.version, 'name': 'Concentration', 'conditional': condition}))
    rule = next(rule for rule in profile.rules if rule.conditional)
    overview = svc.overview(A, profile.profile_id, {})
    check = next(check for check in overview.rule_checks if check.rule_id == rule.rule_id)
    assert check.status == 'conflict'
    assert check.value_fact_id in overview.facts
    assert check.threshold_fact_id in overview.facts
    copy = svc.duplicate(A, profile.profile_id)
    assert next(r for r in copy.rules if r.conditional).conditional == rule.conditional
    with pytest.raises(NotFound):
        svc.remove_conditional_rule(B, profile.profile_id, rule.rule_id, profile.version)
    assert not any(r.conditional for r in svc.remove_conditional_rule(A, profile.profile_id, rule.rule_id, profile.version).rules)


def test_condition_depth_and_injection_are_rejected():
    leaf = {'dimension': 'position', 'key': 'SPY', 'operator': 'gt', 'threshold': 1}
    with pytest.raises(ValidationError):
        ConditionGroup.model_validate({'clauses': [{**leaf, 'sql': 'DROP TABLE x'}]})
    node = leaf
    for _ in range(5):
        node = {'mode': 'all', 'clauses': [node]}
    with pytest.raises(ValidationError):
        ConditionGroup.model_validate(node)


def test_account_transfer_retires_quantity_and_preserves_value():
    svc = service()
    positions = [{'ticker': 'SPY', 'weightPct': 60, 'quantity': 10, 'quantityAsOf': '2026-11-10',
                  'quantityOrigin': 'imported', 'quantitySource': 'statement'}, {'ticker': 'XBB.TO', 'weightPct': 40}]
    profile = svc.create(A, a.CreateProfileRequest.model_validate(create_request(portfolio={'totalValue': 1000, 'positions': positions})))
    profile = svc.create_account(A, profile.profile_id, a.CreateAccountRequest.model_validate(
        {'name': 'Second', 'version': profile.version, 'portfolio': {'totalValue': 500, 'positions': [{'ticker': 'SPY', 'weightPct': 100}]}}))
    source, destination = profile.accounts
    profile = svc.transfer_account(A, profile.profile_id, source.account_id, destination.account_id, 200, profile.version)
    source, destination = profile.accounts
    assert source.portfolio.total_value == 800 and destination.portfolio.total_value == 700
    assert source.portfolio.positions[0].quantity is None
    assert source.quantity_history[0].quantity == 10
    with pytest.raises(Conflict):
        svc.edit_account(A, profile.profile_id, source.account_id, a.EditAccountRequest.model_validate({'version': 1, 'name': 'Stale'}))
    profile = svc.edit_account(A, profile.profile_id, source.account_id, a.EditAccountRequest.model_validate({'version': profile.version, 'name': 'Renamed'}))
    assert profile.accounts[0].name == 'Renamed'


def test_permitted_classes_enforced_and_recomputed_on_edit():
    svc = service()
    body = create_request(investorContext={'permittedAssetClasses': ['cash']})
    profile = svc.create(A, a.CreateProfileRequest.model_validate(body))
    restriction = next(rule for rule in profile.rules if rule.rule_id == 'exclude.asset_class.etf_equity')
    assert restriction.managed_by == 'permitted_asset_classes'
    check = next(check for check in svc.overview(A, profile.profile_id, {}).rule_checks if check.rule_id == restriction.rule_id)
    assert check.status == 'conflict'
    with pytest.raises(Conflict):
        svc.patch_rule(A, profile.profile_id, restriction.rule_id, None, False)
    body['investorContext']['permittedAssetClasses'].append('etf_equity')
    update = a.UpdateProfileRequest.model_validate({**body, 'version': profile.version})
    updated = svc.replace(A, profile.profile_id, update, profile.version)
    assert not any(rule.rule_id == restriction.rule_id and rule.managed_by for rule in updated.rules)


def test_custom_theme_is_explicit_complete_dated_and_auditable():
    svc = service()
    definition = {'key': 'resilience', 'asOf': '2025-01-01', 'availableAt': '2025-01-02',
                  'origin': 'imported', 'sourceReference': 'analyst classifications',
                  'classifications': [{'ticker': 'SPY', 'matches': True}, {'ticker': 'XBB.TO', 'matches': False}]}
    body = create_request(investorContext={'customThemeDefinitions': [definition]})
    profile = svc.create(A, a.CreateProfileRequest.model_validate(body))
    policy = {'require': {'dimension': 'theme', 'key': 'resilience', 'operator': 'lte', 'threshold': 50}}
    profile = svc.add_conditional_rule(A, profile.profile_id, a.AddConditionalRuleRequest.model_validate(
        {'version': profile.version, 'name': 'Theme limit', 'conditional': policy}))
    overview = svc.overview(A, profile.profile_id, {})
    check = next(check for check in overview.rule_checks if check.rule_id.startswith('custom.condition.'))
    assert check.status == 'conflict' and check.value == pytest.approx(60)
    assert check.value_fact_id in overview.facts
    assert any(f.method.params.get('sourceReference') == 'analyst classifications' for f in overview.facts.values())
    definition['classifications'].pop()
    body['investorContext']['customThemeDefinitions'] = [definition]
    updated = svc.replace(A, profile.profile_id, a.UpdateProfileRequest.model_validate({**body, 'rules': [r.to_wire() for r in profile.rules], 'version': profile.version}), profile.version)
    check = next(check for check in svc.overview(A, updated.profile_id, {}).rule_checks if check.rule_id.startswith('custom.condition.'))
    assert check.status == 'nee'
