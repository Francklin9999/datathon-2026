import pytest
from aplomb.contracts.api import CreateProfileRequest
from aplomb.profiles.goals import project_balance

from tests.unit.profiles.test_profiles import A, create_request, service


def test_goal_projection_is_explicit_annual_cashflow_scenario():
    assert project_balance(100, 10, 10, 2) == pytest.approx(142)
    assert project_balance(100, 10, 0, 2.5) == pytest.approx(120)
    assert project_balance(100, 10, 10, .5) == pytest.approx(100 * 1.1 ** .5)


def test_goal_funding_has_inputs_and_blocks_double_counted_capital():
    svc = service()
    goal = {'name': 'Home', 'horizonYears': 2, 'priority': 1, 'targetAmount': 2000,
            'allocatedValue': 500, 'annualContribution': 100, 'assumedReturnPct': 0}
    p = svc.create(A, CreateProfileRequest.model_validate(create_request(investorContext={'objectives': [goal]})))
    result = svc.goal_funding(A, p.profile_id)
    assert result.goals[0].projected_value == 700
    assert result.goals[0].funding_gap == 1300
    assert result.facts[result.goals[0].fact_ids['goal.projected_value']].inputs
    p = svc.create(A, CreateProfileRequest.model_validate(create_request(investorContext={'objectives': [goal, goal, goal]})))
    result = svc.goal_funding(A, p.profile_id)
    assert result.overallocated
    assert all(g.projected_value is None for g in result.goals)


def test_no_return_assumption_is_inferred_from_history():
    svc = service()
    p = svc.create(A, CreateProfileRequest.model_validate(create_request(investorContext={'objectives': [
        {'name': 'Goal', 'horizonYears': 20, 'priority': 1, 'targetAmount': 100000}]})))
    result = svc.goal_funding(A, p.profile_id)
    assert result.goals[0].state == 'missing_assumptions'
    assert result.goals[0].projected_value is None and not result.facts


def test_goal_funding_registers_actual_run_facts_without_cross_ledger_references():
    from types import SimpleNamespace

    from aplomb.ledger import Ledger
    from aplomb.ledger.core import is_timeless
    from aplomb.profiles.goals import register_goal_funding

    from tests.unit.datastore._support import starter_snapshot
    svc = service()
    p = svc.create(A, CreateProfileRequest.model_validate(create_request(investorContext={'objectives': [
        {'name': 'Goal', 'horizonYears': 2, 'priority': 1, 'targetAmount': 1000,
         'allocatedValue': 500, 'annualContribution': 100, 'assumedReturnPct': 0}]})))
    ledger = Ledger('goal-run', '2025-01-01')
    ctx = SimpleNamespace(profile=p, gate=starter_snapshot().gate('2025-01-01'), as_of='2025-01-01', ledger=ledger)
    result = register_goal_funding(ctx, '2026-11-15T00:00:00Z')
    facts = ledger.export().facts
    projected = facts[result['goals'][0]['factIds']['goal.projected_value']]
    assert projected.value == 700
    assert projected.as_of == '2025-01-01'
    assert all(key in facts for key in projected.inputs)
    assert projected.verification.status == 'verified'
    assert is_timeless(projected, facts)
