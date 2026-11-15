"""Dated, explicit-assumption planning across goals and cash requirements.

The model uses one shared pool in the profile reporting currency. It never
infers a liability, return, asset liquidity or an income stream from a persona.
A full-funding test discounts every dated net flow and same-day liquidity floor
back to the start, so a dollar cannot fund two goals or two independent reserves.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any


class PlanInputError(ValueError):
    """An impossible or ambiguous input; no scenario is produced."""


def _finite(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise PlanInputError(f'{label} must be a finite number')
    value = float(value)
    if nonnegative and value < 0:
        raise PlanInputError(f'{label} cannot be negative')
    return value


def _day(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(str(value)) if not isinstance(value, date) else value
    except (ValueError, TypeError) as exc:
        raise PlanInputError(f'{label} must be a valid ISO date') from exc


def _anniversary(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:
        return day.replace(year=year, day=28)


def _on_date(value: Any) -> date | None:
    if value is None:
        return None
    return _day(str(value)[:10], 'valuation date')


def _horizon_date(start: date, years: float) -> date:
    """Calendar anniversaries for whole years; fractional year uses next anniversary."""
    whole = math.floor(years)
    try:
        end = _anniversary(start, start.year + whole)
        fraction = years - whole
        if fraction:
            following = _anniversary(start, start.year + whole + 1)
            end += timedelta(days=round((following - end).days * fraction))
        return end
    except (OverflowError, ValueError) as exc:
        raise PlanInputError('goal horizon exceeds supported calendar dates') from exc


def _due_for_goal(goal, as_of: date) -> tuple[date, str]:
    if goal.deadline:
        return _day(goal.deadline, 'goal deadline'), 'deadline'
    if goal.end_date:
        return _day(goal.end_date, 'goal end date'), 'endDate'
    start = _day(goal.start_date, 'goal start') if goal.start_date else as_of
    return _horizon_date(start, goal.horizon_years), 'horizonYears'


def _capital(profile, sources: list[dict], as_of: date, outside_is_additional: bool) -> tuple[float, list[dict], list[str]]:
    """Validate explicit source amounts and dated account/private valuation receipts."""
    account_list = profile.accounts or []
    accounts = {account.account_id: account for account in account_list}
    if len(accounts) != len(account_list):
        raise PlanInputError('profile contains duplicate account identifiers')
    private = {}
    for account in accounts.values():
        for asset in account.private_assets or []:
            if asset.asset_id in private:
                raise PlanInputError('profile contains duplicate private asset identifiers')
            private[asset.asset_id] = (account, asset)
    seen: set[tuple[str, str]] = set()
    known = []
    missing = []
    for index, item in enumerate(sources):
        kind, identity = item['kind'], item['id'].strip()
        if not identity:
            raise PlanInputError(f'capitalSources[{index}].id is required')
        key = (kind, identity)
        if key in seen:
            raise PlanInputError(f'capital source {kind}:{identity} is repeated')
        seen.add(key)
        amount = _finite(item['amount'], f'capitalSources[{index}].amount', nonnegative=True)
        description = (item.get('sourceDescription') or '').strip()
        detail = {'kind': kind, 'id': identity, 'amount': amount,
                  'origin': item['origin'], 'sourceDescription': description or None,
                  'recordedValue': None, 'valuationDate': None}
        if kind == 'account':
            if identity not in accounts:
                raise PlanInputError(f'unknown account {identity}')
            account = accounts[identity]
            if account.portfolio.currency != profile.reporting_currency:
                raise PlanInputError(f'account {identity} is not valued in reporting currency')
            recorded = float(account.portfolio.total_value)
            available = _on_date(account.portfolio.updated_at)
            receipt = account.native_valuation
            if receipt is not None:
                available = max(filter(None, (available, _on_date(receipt.captured_at))))
            detail.update(recordedValue=recorded, valuationDate=available.isoformat() if available else None,
                          name=account.name)
        elif kind == 'private_asset':
            if identity not in private:
                raise PlanInputError(f'unknown private asset {identity}')
            account, asset = private[identity]
            receipt = asset.valuation.conversion
            if receipt.reporting_currency != profile.reporting_currency:
                raise PlanInputError(f'private asset {identity} is not valued in reporting currency')
            recorded = float(receipt.reporting_value)
            available = max(filter(None, (_on_date(asset.valuation.valuation_date), _on_date(receipt.captured_at))))
            detail.update(recordedValue=recorded, valuationDate=asset.valuation.valuation_date,
                          availableAt=receipt.captured_at, name=asset.name, accountId=account.account_id,
                          appraisalOrigin=asset.valuation.origin,
                          appraisalSource=asset.valuation.source_description,
                          liquidityNotes=asset.liquidity_notes)
        elif kind == 'portfolio':
            if accounts or identity != 'active':
                raise PlanInputError('portfolio source is valid only for a profile without separate accounts and id active')
            if profile.portfolio.currency != profile.reporting_currency:
                raise PlanInputError('portfolio is not valued in reporting currency')
            recorded = float(profile.portfolio.total_value)
            available = _on_date(profile.portfolio.updated_at)
            detail.update(recordedValue=recorded, valuationDate=available.isoformat() if available else None)
        elif kind == 'outside':
            if not outside_is_additional:
                raise PlanInputError('outside capital requires outsideIsAdditional confirmation')
            if not description:
                raise PlanInputError('outside capital requires a sourceDescription')
            recorded, available = None, None
        else:
            raise PlanInputError(f'unknown capital source kind {kind}')
        if recorded is not None:
            if not math.isfinite(recorded) or amount > recorded:
                raise PlanInputError(f'selected liquid amount exceeds recorded value for {kind}:{identity}')
            if available and available > as_of:
                missing.append(f'capitalSources[{index}]: valuation not available by asOf')
        known.append(detail)
    try:
        total = math.fsum(source['amount'] for source in known)
    except OverflowError as exc:
        raise PlanInputError('capital sources overflow') from exc
    if not math.isfinite(total):
        raise PlanInputError('capital sources overflow')
    return total, known, missing


def _indices(values: list[int], length: int, label: str) -> list[int]:
    if any(type(i) is not int or i < 0 or i >= length for i in values):
        raise PlanInputError(f'{label} contains an invalid index')
    if len(set(values)) != len(values):
        raise PlanInputError(f'{label} cannot contain duplicates')
    return values


def joint_plan(profile, *, as_of: date, through: date, annual_return_pct: float,
               annual_inflation_pct: float, amount_basis: str, capital_sources: list[dict],
               outside_is_additional: bool, cashflows: list[dict], goal_indexes: list[int],
               requirement_indexes: list[int], liquidity_aggregation: str,
               allocation_treatment: str) -> dict:
    """Calculate a deterministic shared-capital plan, all figures in reporting currency.

    `cashflows` are the entire stated additional schedule, positive deposits or
    negative withdrawals. Each positive flow is counted once. Existing goal-specific
    contributions/allocations/returns are not added on top of these shared inputs.

    Same-day withdrawals and spending/liabilities settle before reserves and goals.
    Goals are allocated by priority then profile order. Independent reserves sum;
    explicitly overlapping reserves use the maximum. Both choices are assumptions.
    Required starting capital is the maximum discounted cumulative obligation plus
    reserve over all event dates, not a prediction or a monotonic position bound.
    """
    as_of, through = _day(as_of, 'asOf'), _day(through, 'through')
    if through < as_of or (through - as_of).days > 54_787:
        raise PlanInputError('through must be on or after asOf and within 150 years')
    rate = _finite(annual_return_pct, 'annualReturnPct')
    inflation = _finite(annual_inflation_pct, 'annualInflationPct')
    if not -100 < rate <= 100 or not -100 < inflation <= 100:
        raise PlanInputError('annual return and inflation must be greater than -100% and at most 100%')
    if amount_basis not in ('nominal', 'as_of_real'):
        raise PlanInputError('amountBasis must be nominal or as_of_real')
    if liquidity_aggregation not in ('independent', 'overlapping'):
        raise PlanInputError('liquidityAggregation must be independent or overlapping')
    if allocation_treatment != 'shared_pool':
        raise PlanInputError('allocationTreatment must explicitly be shared_pool')

    context = profile.investor_context
    goals = context.objectives if context else []
    requirements = context.requirements if context else []
    _indices(goal_indexes, len(goals), 'goalIndexes')
    _indices(requirement_indexes, len(requirements), 'requirementIndexes')
    capital, sources, missing = _capital(profile, capital_sources, as_of, outside_is_additional)
    if not goal_indexes and not requirement_indexes:
        missing.append('Select at least one explicitly entered goal or requirement')
    flows = []
    for index, item in enumerate(cashflows):
        day = _day(item['date'], f'cashflows[{index}].date')
        amount = _finite(item['amount'], f'cashflows[{index}].amount')
        if not as_of <= day <= through:
            raise PlanInputError(f'cashflows[{index}].date is outside the scenario')
        flows.append({'date': day, 'amount': amount, 'origin': item['origin'],
                      'description': (item.get('description') or '').strip() or None})

    output_goals: dict[int, dict] = {}
    output_requirements: dict[int, dict] = {}
    conflicts: list[dict] = []
    plan_events: dict[date, dict] = {}

    def event(day: date) -> dict:
        return plan_events.setdefault(day, {'cashflows': [], 'requirements': [], 'reserves': [], 'goals': []})

    def adjusted(amount: float, day: date) -> float:
        amount = _finite(amount, 'stated amount', nonnegative=True)
        try:
            result = amount if amount_basis == 'nominal' else amount * (1 + inflation / 100) ** ((day - as_of).days / 365)
        except OverflowError as exc:
            raise PlanInputError('inflation adjustment overflows') from exc
        if not math.isfinite(result):
            raise PlanInputError('inflation adjustment overflows')
        return result

    for index in goal_indexes:
        goal = goals[index]
        due, due_method = _due_for_goal(goal, as_of)
        row = {'index': index, 'name': goal.name, 'origin': goal.origin, 'sourceUrl': goal.source_url,
               'priority': goal.priority, 'dueDate': due.isoformat(), 'dueDateMethod': due_method,
               'statedTarget': goal.target_amount, 'targetAtDue': None, 'paid': None,
               'shortfall': None, 'state': 'outside_horizon' if due > through else 'pending'}
        output_goals[index] = row
        if goal.deadline and goal.end_date and goal.deadline != goal.end_date:
            conflicts.append({'code': 'deadline_and_end_date_differ', 'goalIndexes': [index],
                              'detail': f'{goal.name}: deadline {goal.deadline} takes precedence over endDate {goal.end_date}.'})
        if goal.start_date and (goal.deadline or goal.end_date):
            implied = _horizon_date(_day(goal.start_date, 'goal start'), goal.horizon_years)
            if abs((due - implied).days) > 1:
                conflicts.append({'code': 'goal_dates_and_horizon_differ', 'goalIndexes': [index],
                                  'detail': f'{goal.name}: stated horizon implies {implied.isoformat()}, while its selected due date is {due.isoformat()}.'})
        if due < as_of:
            missing.append(f'goals[{index}]: payment status for past deadline')
        elif goal.target_amount is None:
            missing.append(f'goals[{index}].targetAmount')
        elif due <= through:
            row['targetAtDue'] = adjusted(goal.target_amount, due)
            event(due)['goals'].append(row)

    for index in requirement_indexes:
        requirement = requirements[index]
        output_requirements[index] = {'index': index, 'name': requirement.name,
            'kind': requirement.kind, 'origin': requirement.origin, 'sourceUrl': requirement.source_url,
            'frequency': requirement.frequency, 'statedAmount': requirement.amount,
            'dueDate': requirement.due_date, 'occurrences': [], 'state': 'outside_horizon'}
        if not requirement.due_date:
            missing.append(f'requirements[{index}].dueDate')
            output_requirements[index]['state'] = 'missing_due_date'
            continue
        due = _day(requirement.due_date, 'requirement due date')
        if due < as_of and requirement.frequency == 'once':
            missing.append(f'requirements[{index}]: payment status for past obligation')
            output_requirements[index]['state'] = 'missing_payment_status'
            continue
        if requirement.frequency == 'annual':
            try:
                days = (_anniversary(due, year) for year in range(max(as_of.year, due.year), through.year + 1))
                days = [day for day in days if day >= due and as_of <= day <= through]
            except (OverflowError, ValueError) as exc:
                raise PlanInputError('recurring requirement exceeds supported calendar dates') from exc
        else:
            days = [due] if as_of <= due <= through else []
        if days:
            output_requirements[index]['state'] = 'included'
            output_requirements[index]['occurrences'] = [day.isoformat() for day in days]
        for day in days:
            entry = {'index': index, 'name': requirement.name, 'kind': requirement.kind,
                     'origin': requirement.origin, 'sourceUrl': requirement.source_url,
                     'statedAmount': requirement.amount, 'amountDue': adjusted(requirement.amount, day)}
            event(day)['reserves' if requirement.kind == 'liquidity' else 'requirements'].append(entry)
    for flow in flows:
        event(flow['date'])['cashflows'].append(flow)
        if flow['description'] and flow['amount'] < 0:
            duplicates = [item for item in event(flow['date'])['requirements']
                          if item['name'].casefold().strip() == flow['description'].casefold()
                          and math.isclose(item['amountDue'], -flow['amount'], abs_tol=1e-9, rel_tol=0)]
            if duplicates:
                conflicts.append({'code': 'possible_duplicate_cashflow',
                                  'requirementIndexes': [item['index'] for item in duplicates],
                                  'detail': 'A named withdrawal matches a selected requirement on the same day. Both are counted; remove one if they are the same obligation.'})
    explicit_allocations = math.fsum(goals[index].allocated_value or 0 for index in goal_indexes)
    if explicit_allocations > capital:
        conflicts.append({'code': 'goal_allocations_exceed_shared_capital', 'goalIndexes': goal_indexes,
                          'detail': 'Saved goal allocations exceed selected capital. This explicitly selected shared-pool scenario does not add those allocations a second time.'})

    assumptions = [
        'One shared pool; selected capital and external cash flows are counted once.',
        'Account liquidity is the user-stated available portion, not independently verified saleability.',
        'Private appraisal is an estimate; its user-stated liquid amount is not an executable price.',
        'Goal-specific allocated amounts, annual contributions and individual return assumptions are excluded from this shared-pool model.',
        'The explicit annual return compounds on actual days / 365; no borrowing, fees, taxes or unentered cash flows are inferred.',
        'A goal deadline takes precedence over end date; otherwise whole-year horizon dates use calendar anniversaries and fractional years the next anniversary interval.',
        ('Stated target/requirements amounts are nominal; the inflation input is disclosed but not applied.' if amount_basis == 'nominal'
         else 'Stated target/requirements amounts are as-of purchasing-power values, escalated at the explicit annual inflation assumption.'),
        ('Same-day liquidity requirements are independent and sum.' if liquidity_aggregation == 'independent'
         else 'Same-day liquidity requirements are explicitly assumed to overlap; the largest reserve is used.'),
        'Same-day external flows and spending/liabilities settle first, then reserve is protected; goals are funded by stated priority and original order.',
        'Required initial capital is the greatest discounted cumulative net obligation plus the same-day reserve; it is not a forecast.',
        'This assesses only selected entries through the stated end date. Entries after that date and unentered obligations remain unknown.',
    ]
    base = {'profileId': profile.profile_id, 'profileVersion': profile.version, 'currency': profile.reporting_currency,
            'asOf': as_of.isoformat(), 'through': through.isoformat(), 'capital': capital, 'capitalSources': sources,
            'annualReturnPct': rate, 'annualInflationPct': inflation, 'amountBasis': amount_basis,
            'liquidityAggregation': liquidity_aggregation, 'allocationTreatment': allocation_treatment,
            'selectedGoalIndexes': goal_indexes, 'selectedRequirementIndexes': requirement_indexes,
            'state': 'missing_inputs', 'missingInputs': missing, 'goals': [output_goals[i] for i in goal_indexes],
            'requirements': [output_requirements[i] for i in requirement_indexes],
            'cashflows': [{**flow, 'date': flow['date'].isoformat()} for flow in flows],
            'conflicts': conflicts, 'events': [], 'requiredInitialCapital': None, 'additionalInitialCapital': None,
            'firstShortfallDate': None, 'endingLiquidValue': None, 'assumptions': assumptions,
            'method': 'shared-pool daily compounding; discounted cumulative obligations and reserve',
            'claimIds': [], 'factIds': [], 'priorityPlan': None}
    if missing:
        return base

    balance, previous = capital, as_of
    cumulative_discounted, required_initial = 0.0, 0.0
    output_events = []
    first_shortfall = None
    try:
        for day, item in sorted(plan_events.items()):
            growth = (1 + rate / 100) ** ((day - previous).days / 365)
            before = balance * growth
            flow = math.fsum(entry['amount'] for entry in item['cashflows'])
            after_flow = before + flow
            flow_gap = max(0.0, -after_flow)
            available = max(0.0, after_flow)
            requirement_results = []
            for obligation in item['requirements']:
                paid = min(available, obligation['amountDue'])
                available -= paid
                requirement_results.append({**obligation, 'paid': paid, 'shortfall': obligation['amountDue'] - paid})
            reserve_values = [entry['amountDue'] for entry in item['reserves']]
            reserve = math.fsum(reserve_values) if liquidity_aggregation == 'independent' else max(reserve_values, default=0.0)
            reserve_gap = max(0.0, reserve - available)
            payable = max(0.0, available - reserve)
            goal_results = []
            for goal in sorted(item['goals'], key=lambda row: (row['priority'], row['index'])):
                paid = min(payable, goal['targetAtDue'])
                payable -= paid
                available -= paid
                goal.update(paid=paid, shortfall=goal['targetAtDue'] - paid,
                            state='scenario_funded' if paid >= goal['targetAtDue'] else 'scenario_shortfall')
                goal_results.append(goal.copy())
            gap = math.fsum([flow_gap, reserve_gap, *(x['shortfall'] for x in requirement_results),
                             *(x['shortfall'] for x in goal_results)])
            if gap > 1e-9 and first_shortfall is None:
                first_shortfall = day.isoformat()
            # Discount the fully funded schedule, including all actual stated goals,
            # even if this simulated balance could not pay one of them.
            g = (1 + rate / 100) ** ((day - as_of).days / 365)
            outflow = math.fsum([*(x['amountDue'] for x in item['requirements']),
                                 *(x['targetAtDue'] for x in item['goals'])])
            if g == 0 or not math.isfinite(g):
                raise PlanInputError('discount factor underflows or overflows')
            cumulative_discounted += (outflow - flow) / g
            required_initial = max(required_initial, cumulative_discounted + reserve / g)
            values = (before, flow, available, gap, cumulative_discounted, required_initial)
            if not all(math.isfinite(value) for value in values):
                raise PlanInputError('plan calculation overflows')
            output_events.append({'date': day.isoformat(), 'openingValue': before, 'externalFlow': flow,
                'cashflows': [{**x, 'date': x['date'].isoformat()} for x in item['cashflows']],
                'externalFlowShortfall': flow_gap, 'requirements': requirement_results,
                'reserveRequirements': item['reserves'], 'liquidityReserve': reserve,
                'reserveShortfall': reserve_gap, 'goals': goal_results, 'closingValue': available,
                'shortfall': gap, 'requiredInitialThroughDate': max(0.0, required_initial)})
            balance, previous = available, day
        balance *= (1 + rate / 100) ** ((through - previous).days / 365)
    except OverflowError as exc:
        raise PlanInputError('plan calculation overflows') from exc
    if not math.isfinite(balance):
        raise PlanInputError('plan calculation overflows')
    required_initial = max(0.0, required_initial)
    priority_plan = _priority_plan(capital, plan_events, rate, liquidity_aggregation, goal_indexes, output_goals, as_of)
    priority_by_index = {row['index']: row for row in priority_plan['goals']}
    for index in goal_indexes:
        chronological = output_goals[index]
        prioritized = priority_by_index.get(index)
        if prioritized and chronological['paid'] is not None and prioritized['paid'] is not None and abs(chronological['paid'] - prioritized['paid']) > 1e-7:
            conflicts.append({'code': 'goal_priority_tradeoff', 'goalIndexes': [index],
                              'detail': f"{chronological['name']}: chronological and priority-preserving allocation differ; inspect both schedules."})
    base.update(priorityPlan=priority_plan, state='scenario_shortfall' if first_shortfall else 'scenario_funded_through',
                goals=[output_goals[i] for i in goal_indexes], events=output_events,
                requiredInitialCapital=required_initial, additionalInitialCapital=max(0.0, required_initial - capital),
                firstShortfallDate=first_shortfall, endingLiquidValue=balance)
    return base


def _priority_plan(capital: float, events: dict, rate: float, liquidity_aggregation: str,
                   indexes: list[int], goals: dict[int, dict], as_of: date) -> dict:
    """Lexicographically allocate by priority subject to dated mandatory constraints.

    In present-value units a goal spending at day d reduces all checkpoint
    balances on/after d by the same amount. Its maximum safe funding is the
    minimum remaining headroom of those checkpoints. Repeating in priority
    order exactly maximizes each goal while preserving higher priorities.
    """
    checkpoints = []
    discounted_net = 0.0
    essential_capital = 0.0
    try:
        for day, event in sorted(events.items()):
            factor = (1 + rate / 100) ** ((day - as_of).days / 365)
            if not math.isfinite(factor) or factor == 0:
                raise PlanInputError('discount factor underflows or overflows')
            flows = math.fsum(row['amount'] for row in event['cashflows'])
            obligations = math.fsum(row['amountDue'] for row in event['requirements'])
            amounts = [row['amountDue'] for row in event['reserves']]
            reserve = math.fsum(amounts) if liquidity_aggregation == 'independent' else max(amounts, default=0.0)
            discounted_net += (flows - obligations) / factor
            reserve_pv = reserve / factor
            essential_capital = max(essential_capital, reserve_pv - discounted_net)
            if not all(math.isfinite(v) for v in (discounted_net, reserve_pv, essential_capital)):
                raise PlanInputError('priority plan overflows')
            checkpoints.append({'date': day, 'factor': factor, 'netPV': discounted_net, 'reservePV': reserve_pv})
        essential_capital = max(0.0, essential_capital)
        additional = max(0.0, essential_capital - capital)
        tolerance = max(1e-9, 16 * math.ulp(capital))
        output = {'essentialRequiredInitialCapital': essential_capital,
                  'additionalEssentialCapital': additional,
                  'state': 'mandatory_shortfall' if additional > tolerance else 'priority_scenario',
                  'goals': [],
                  'method': 'lexicographic goal funding by priority with all dated essential spending and reserve constraints preserved',
                  'limitation': 'Assumes the explicit fixed return and cash-flow schedule; no prediction, execution, borrowing or unselected obligation is inferred.'}
        if additional > tolerance:
            output['goals'] = [{'index': i, 'name': goals[i]['name'], 'priority': goals[i]['priority'],
                                'dueDate': goals[i]['dueDate'], 'targetAtDue': goals[i]['targetAtDue'],
                                'paid': None, 'shortfall': None,
                                'state': 'outside_horizon' if goals[i]['state'] == 'outside_horizon' else 'mandatory_shortfall'}
                               for i in indexes]
            return output
        allocated: list[tuple[date, float]] = []
        ordered = sorted((goals[i] for i in indexes if goals[i]['state'] != 'outside_horizon'),
                         key=lambda row: (row['priority'], row['index']))
        for goal in ordered:
            due = _day(goal['dueDate'], 'goal due date')
            factor = (1 + rate / 100) ** ((due - as_of).days / 365)
            later = [checkpoint for checkpoint in checkpoints if checkpoint['date'] >= due]
            if not later or factor == 0 or not math.isfinite(factor):
                raise PlanInputError('goal checkpoint unavailable or discount factor underflows')
            slack = min(capital + checkpoint['netPV'] - checkpoint['reservePV']
                        - math.fsum(amount for allocated_day, amount in allocated if allocated_day <= checkpoint['date'])
                        for checkpoint in later)
            paid = min(goal['targetAtDue'], max(0.0, slack * factor))
            if not math.isfinite(paid):
                raise PlanInputError('priority plan overflows')
            allocated.append((due, paid / factor))
            output['goals'].append({'index': goal['index'], 'name': goal['name'], 'origin': goal['origin'],
                                    'priority': goal['priority'], 'dueDate': goal['dueDate'],
                                    'targetAtDue': goal['targetAtDue'], 'paid': paid,
                                    'shortfall': max(0.0, goal['targetAtDue'] - paid),
                                    'state': 'scenario_funded' if paid >= goal['targetAtDue'] else 'scenario_shortfall'})
        output['goals'].extend({'index': goals[i]['index'], 'name': goals[i]['name'], 'origin': goals[i]['origin'],
                                'priority': goals[i]['priority'], 'dueDate': goals[i]['dueDate'],
                                'targetAtDue': None, 'paid': None, 'shortfall': None, 'state': 'outside_horizon'}
                               for i in indexes if goals[i]['state'] == 'outside_horizon')
        return output
    except OverflowError as exc:
        raise PlanInputError('priority plan overflows') from exc
