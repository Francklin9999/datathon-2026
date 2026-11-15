"""Explicit-input nominal goal scenarios. No inferred return, income, liability or feasibility."""
import math

from aplomb.contracts.api import GoalFundingResponse
from aplomb.quant.facts import FactContext, LocalLedger, fact_key, make_fact


def project_balance(capital: float, annual_contribution: float, return_pct: float, years: float) -> float:
    """Contribute at each whole-year end, then compound the remaining fractional year.

    Annual contribution excludes a contribution for an unfinished year. Real purchasing power,
    taxes, fees and withdrawals are not inferred. A user return is an assumption, never a forecast.
    """
    whole = math.floor(years)
    factor = 1 + return_pct / 100
    balance = capital
    try:
        for _ in range(whole):
            balance = balance * factor + annual_contribution
        result = balance * factor ** (years - whole)
    except OverflowError:
        raise ValueError('Scenario overflows; reduce the horizon or return assumption') from None
    if not math.isfinite(result):
        raise ValueError('Scenario overflows; reduce the horizon or return assumption')
    return result


def assess_goals(profile, data_version: str, now: str, as_of: str | None = None) -> GoalFundingResponse:
    goals = profile.investor_context.objectives if profile.investor_context else []
    allocated = math.fsum(g.allocated_value or 0 for g in goals)
    ledger = LocalLedger()
    ctx = FactContext(as_of or now[:10], now, data_version)
    results = []
    for i, goal in enumerate(goals):
        missing = [name for name, value in [('targetAmount', goal.target_amount),
            ('allocatedValue', goal.allocated_value), ('annualContribution', goal.annual_contribution),
            ('assumedReturnPct', goal.assumed_return_pct)] if value is None]
        if allocated > profile.portfolio.total_value:
            missing.append('nonOverlappingGoalAllocations')
        row = {'name': goal.name, 'state': 'missing_assumptions', 'projectedValue': None,
               'fundingGap': None, 'factIds': {}, 'missingInputs': missing}
        values = (goal.target_amount, goal.allocated_value, goal.annual_contribution, goal.assumed_return_pct)
        if allocated > profile.portfolio.total_value or any(v is None for v in values):
            results.append(row)
            continue
        try:
            projected = project_balance(goal.allocated_value, goal.annual_contribution,
                                        goal.assumed_return_pct, goal.horizon_years)
        except ValueError:
            row['missingInputs'].append('validFiniteScenario')
            results.append(row)
            continue
        gap = max(0, goal.target_amount - projected)
        inputs = []
        subject = {'type': 'request', 'id': f'{profile.profile_id}-goal-{i}', 'variant': 'assumption'}
        for name, value in {'capital': goal.allocated_value, 'annualContribution': goal.annual_contribution,
                            'returnPct': goal.assumed_return_pct, 'years': goal.horizon_years,
                            'target': goal.target_amount}.items():
            inputs.append(ledger.add_fact(make_fact(ctx,
                key=fact_key('input.goal_assumption', 'request', subject['id'], name, 'na'), kind='assumption',
                metric='input.goal_assumption', label={'en': f'User assumption: {name}', 'fr': f'Hypothèse utilisateur : {name}'},
                value=value, unit='pct' if name == 'returnPct' else ('ratio' if name == 'years' else 'currency'),
                currency=profile.reporting_currency if name not in ('returnPct', 'years') else None,
                subject={**subject, 'variant': name}, method_id='M_USER_INPUT', created_by='profile', available_at=None,
                params={'profileVersion': profile.version, 'origin': goal.origin})))
        for metric, value in [('goal.projected_value', projected), ('goal.funding_gap', gap)]:
            fid = ledger.add_fact(make_fact(ctx,
                key=fact_key(metric, 'request', subject['id'], 'scenario', 'na'), kind='scenario',
                metric=metric, label={'en': goal.name, 'fr': goal.name}, value=value, unit='currency',
                currency=profile.reporting_currency, subject=subject,
                method_id='M_GOAL_FUNDING_SCENARIO', created_by='profile', inputs=inputs, available_at=None,
                params={'capital': goal.allocated_value, 'annualContribution': goal.annual_contribution,
                        'returnPct': goal.assumed_return_pct, 'years': goal.horizon_years,
                        'target': goal.target_amount, 'contributionTiming': 'whole-year-end',
                        'scope': 'nominal user-assumption scenario, not forecast; excludes taxes/fees/withdrawals'}))
            row['factIds'][metric] = fid
        row.update(state='scenario_funded' if gap == 0 else 'scenario_shortfall', projectedValue=projected, fundingGap=gap)
        results.append(row)
    return GoalFundingResponse.model_validate({'profileId': profile.profile_id, 'currency': profile.reporting_currency,
        'overallocated': allocated > profile.portfolio.total_value,
        'unallocatedValue': max(0, profile.portfolio.total_value - allocated), 'goals': results, 'facts': ledger.wire()})


def register_goal_funding(ctx, now: str) -> dict:
    """Register calculated goal facts in the actual run ledger, remapping local references."""
    report = assess_goals(ctx.profile, ctx.gate.data_version, now, str(ctx.as_of))
    ids = {}
    for original, fact in report.facts.items():
        body = fact.to_wire()
        body.pop('id', None)
        body['inputs'] = [ids[key] for key in fact.inputs]
        ids[original] = ctx.ledger.add_fact(body)
    body = report.to_wire()
    body.pop('facts', None)
    for goal in body['goals']:
        goal['factIds'] = {key: ids[value] for key, value in goal['factIds'].items()}
    return body
