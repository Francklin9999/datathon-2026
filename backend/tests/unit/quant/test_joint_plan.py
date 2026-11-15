"""Independent reference cases for joint goals, spending and liquidity."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from aplomb.api.app import create_app
from aplomb.api.errors import NotFound
from aplomb.api.services import Services
from aplomb.api.settings import Settings
from aplomb.contracts import models as m
from aplomb.quant.joint_plan import PlanInputError, joint_plan
from aplomb.quant.joint_plan_api import router
from fastapi.testclient import TestClient

from tests.unit.rules._support import PROFILES

A = 's_11111111-1111-4111-8111-111111111111'
B = 's_22222222-2222-4222-8222-222222222222'


def profile(goals=(), requirements=()):
    seed = PROFILES['amira'].model_copy(deep=True)
    context = m.InvestorContext.model_validate({'objectives': list(goals), 'requirements': list(requirements)})
    return seed.model_copy(update={'investor_context': context})


def scenario(p, **changes):
    args = {'as_of': date(2027, 1, 1), 'through': date(2027, 12, 31),
            'annual_return_pct': 0, 'annual_inflation_pct': 0, 'amount_basis': 'nominal',
            'capital_sources': [{'kind': 'portfolio', 'id': 'active', 'amount': 100, 'origin': 'user'}],
            'outside_is_additional': False, 'cashflows': [],
            'goal_indexes': list(range(len(p.investor_context.objectives))),
            'requirement_indexes': list(range(len(p.investor_context.requirements))),
            'liquidity_aggregation': 'independent', 'allocation_treatment': 'shared_pool'}
    args.update(changes)
    return joint_plan(p, **args)


def goal(name, target, priority, deadline=None, **kw):
    return {'name': name, 'targetAmount': target, 'priority': priority, 'horizonYears': 1,
            **({'deadline': deadline} if deadline else {}), **kw}


def requirement(name, kind, amount, day, **kw):
    return {'name': name, 'kind': kind, 'amount': amount, 'frequency': 'once',
            'dueDate': day, **kw}


def test_joint_shared_cash_prioritizes_later_goal_and_does_not_double_count():
    p = profile([goal('Early lower priority', 80, 5, '2027-03-01', allocatedValue=100, annualContribution=999),
                 goal('Later higher priority', 80, 1, '2027-11-01', allocatedValue=100)],
                [requirement('Rent', 'spending', 20, '2027-08-01')])
    result = scenario(p)
    assert result['state'] == 'scenario_shortfall'
    assert result['requiredInitialCapital'] == pytest.approx(180)
    assert result['additionalInitialCapital'] == pytest.approx(80)
    assert result['goals'][0]['paid'] == 80 and result['goals'][1]['paid'] == 0
    priority = {row['index']: row for row in result['priorityPlan']['goals']}
    assert priority[1]['paid'] == 80 and priority[0]['paid'] == 0
    assert {item['code'] for item in result['conflicts']} >= {
        'goal_allocations_exceed_shared_capital', 'goal_priority_tradeoff'}
    assert result['priorityPlan']['essentialRequiredInitialCapital'] == 20
    assert '999' not in str(result['events'])


def test_inflation_return_and_required_capital_against_hand_calculation():
    p = profile([goal('One-year', 100, 1, '2028-01-01')])
    result = scenario(p, through=date(2028, 1, 1), annual_return_pct=10,
                      annual_inflation_pct=10, amount_basis='as_of_real',
                      capital_sources=[{'kind': 'portfolio', 'id': 'active', 'amount': 50, 'origin': 'imported'}])
    assert result['goals'][0]['targetAtDue'] == pytest.approx(110)
    assert result['goals'][0]['paid'] == pytest.approx(55)
    assert result['requiredInitialCapital'] == pytest.approx(100)
    assert result['additionalInitialCapital'] == pytest.approx(50)
    assert result['events'][0]['closingValue'] == pytest.approx(0)
    assert result['capitalSources'][0]['origin'] == 'imported'


def test_same_day_reserves_are_summed_or_overlap_only_by_explicit_choice():
    p = profile([goal('Goal', 100, 1, '2027-06-01')],
                [requirement('Reserve A', 'liquidity', 10, '2027-06-01'),
                 requirement('Reserve B', 'liquidity', 20, '2027-06-01')])
    independent = scenario(p)
    overlapping = scenario(p, liquidity_aggregation='overlapping')
    assert independent['events'][0]['liquidityReserve'] == 30
    assert independent['goals'][0]['paid'] == 70
    assert independent['requiredInitialCapital'] == pytest.approx(130)
    assert overlapping['events'][0]['liquidityReserve'] == 20
    assert overlapping['goals'][0]['paid'] == 80
    assert overlapping['requiredInitialCapital'] == pytest.approx(120)


def test_mandatory_shortfall_does_not_fabricate_priority_allocations():
    p = profile([goal('Goal', 20, 1, '2027-11-01')],
                [requirement('Rent', 'liability', 120, '2027-06-01')])
    result = scenario(p)
    assert result['priorityPlan']['state'] == 'mandatory_shortfall'
    assert result['priorityPlan']['additionalEssentialCapital'] == pytest.approx(20)
    assert result['priorityPlan']['goals'][0]['paid'] is None
    assert result['firstShortfallDate'] == '2027-06-01'


def test_missing_dates_past_obligations_and_same_named_withdrawal_are_explicit():
    p = profile([goal('Past', 10, 1, '2026-12-01')],
                [{'name': 'Unscheduled rent', 'kind': 'spending', 'amount': 10}])
    result = scenario(p)
    assert result['state'] == 'missing_inputs'
    assert 'goals[0]: payment status for past deadline' in result['missingInputs']
    assert 'requirements[0].dueDate' in result['missingInputs']
    assert result['requiredInitialCapital'] is None and result['priorityPlan'] is None
    p = profile([], [requirement('Rent', 'spending', 20, '2027-06-01')])
    result = scenario(p, cashflows=[{'date': '2027-06-01', 'amount': -20,
                                     'origin': 'user', 'description': 'Rent'}])
    assert result['requiredInitialCapital'] == 40
    assert any(c['code'] == 'possible_duplicate_cashflow' for c in result['conflicts'])


def test_calendar_anniversary_and_explicit_date_conflicts():
    p = profile([goal('Leap', 100, 1, startDate='2028-01-01')])
    result = scenario(p, through=date(2029, 1, 1))
    assert result['goals'][0]['dueDate'] == '2029-01-01'
    p = profile([goal('Conflicting', 10, 1, '2027-06-01', startDate='2027-01-01', endDate='2027-09-01')])
    result = scenario(p)
    assert result['goals'][0]['dueDate'] == '2027-06-01'
    assert {c['code'] for c in result['conflicts']} >= {'deadline_and_end_date_differ', 'goal_dates_and_horizon_differ'}


def test_capital_identity_and_conservation_checks():
    p = profile([goal('Goal', 5, 1, '2027-02-01')])
    src = {'kind': 'portfolio', 'id': 'active', 'amount': 100, 'origin': 'user'}
    with pytest.raises(PlanInputError, match='repeated'):
        scenario(p, capital_sources=[src, src])
    with pytest.raises(PlanInputError, match='exceeds recorded'):
        scenario(p, capital_sources=[{**src, 'amount': p.portfolio.total_value + 1}])
    outside = {'kind': 'outside', 'id': 'reserve', 'amount': 10, 'origin': 'user', 'sourceDescription': 'Separate cash'}
    with pytest.raises(PlanInputError, match='outsideIsAdditional'):
        scenario(p, capital_sources=[src, outside])
    assert scenario(p, capital_sources=[src, outside], outside_is_additional=True)['capital'] == 110
    with pytest.raises(PlanInputError, match='sourceDescription'):
        scenario(p, capital_sources=[{**outside, 'sourceDescription': ''}], outside_is_additional=True)


def test_future_appraisal_is_not_used_for_prior_as_of():
    p = profile([goal('Goal', 5, 1, '2027-02-01')])
    valuation = {'valuationDate': '2027-01-02', 'origin': 'imported', 'sourceDescription': 'Explicit appraisal',
                 'conversion': {'nativeCurrency': 'CAD', 'nativeValue': 30, 'reportingCurrency': 'CAD',
                                'reportingValue': 30, 'conversionRate': 1, 'valuationDate': '2027-01-02',
                                'capturedAt': '2027-01-02T12:00:00Z', 'dataVersion': 'snap-20261115-globalfx', 'quotes': []}}
    account = m.PortfolioAccount.model_validate({'accountId': 'acct_0123456789ab', 'name': 'Private',
        'portfolio': p.portfolio.to_wire(), 'privateAssets': [{'assetId': 'priv_0123456789ab', 'name': 'Art',
        'assetType': 'art', 'liquidityNotes': 'Illiquid; user assumption', 'valuation': valuation}]})
    p = p.model_copy(update={'accounts': [account], 'active_account_id': account.account_id})
    source = {'kind': 'private_asset', 'id': 'priv_0123456789ab', 'amount': 30, 'origin': 'assumption'}
    prior = scenario(p, capital_sources=[source])
    assert prior['state'] == 'missing_inputs'
    assert 'valuation not available by asOf' in prior['missingInputs'][0]
    current = scenario(p, as_of=date(2027, 1, 2), capital_sources=[source])
    assert current['capital'] == 30 and current['state'] == 'scenario_funded_through'
    assert current['capitalSources'][0]['appraisalOrigin'] == 'imported'
    with pytest.raises(PlanInputError, match='exceeds recorded'):
        scenario(p, as_of=date(2027, 1, 2), capital_sources=[{**source, 'amount': 31}])


def test_zero_cash_and_discount_underflow_are_handled_without_nonfinite_results():
    p = profile([goal('Goal', 10, 1, '2027-02-01')])
    zero = scenario(p, capital_sources=[])
    assert zero['capital'] == 0 and zero['additionalInitialCapital'] == 10
    assert zero['goals'][0]['shortfall'] == 10
    far = profile([goal('Far', 10, 1, '2150-01-01')])
    with pytest.raises(PlanInputError, match='discount factor underflows'):
        scenario(far, through=date(2150, 1, 1), annual_return_pct=-99.9999)


def test_http_profile_version_and_session_ownership():
    p = profile([goal('Goal', 10, 1, '2027-02-01')])

    class Provider:
        def get(self, sid, profile_id):
            if sid != A or profile_id != p.profile_id:
                raise NotFound('Profile is not owned by this session')
            return p

    app = create_app(Settings(data_version='snap-20261115-globalfx'), Services(profiles=Provider()))
    app.state.services = SimpleNamespace(profiles=Provider())
    app.include_router(router)
    client = TestClient(app)
    payload = {'profileVersion': p.version, 'asOf': '2027-01-01', 'through': '2027-12-31',
               'annualReturnPct': 0, 'annualInflationPct': 0, 'amountBasis': 'nominal',
               'capitalSources': [{'kind': 'portfolio', 'id': 'active', 'amount': 100, 'origin': 'user'}],
               'outsideIsAdditional': False, 'cashflows': [], 'goalIndexes': [0], 'requirementIndexes': [],
               'liquidityAggregation': 'independent', 'allocationTreatment': 'shared_pool'}
    url = f'/v1/profiles/{p.profile_id}/joint-plan'
    good = client.post(url, headers={'X-Aplomb-Session': A}, json=payload)
    assert good.status_code == 200, good.text
    assert good.json()['state'] == 'scenario_funded_through'
    assert good.json()['goals'][0]['paid'] == 10
    assert client.post(url, headers={'X-Aplomb-Session': B}, json=payload).status_code == 404
    payload['profileVersion'] += 1
    assert client.post(url, headers={'X-Aplomb-Session': A}, json=payload).status_code == 409
