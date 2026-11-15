"""Explicit-input nominal liquid-capital scenario, with no borrowing assumption."""
from __future__ import annotations

import math
from datetime import date


def _anniversary(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:  # leap day: use February 28 in non-leap years
        return day.replace(year=year, day=28)


def requirement_scenario(requirements, *, as_of: date, through: date,
                         liquid_capital: float, annual_return_pct: float,
                         cashflows: list[tuple[date, float]]) -> dict:
    """Assess dated spending/liability and liquidity reserves in reporting currency.

    A cash flow list is explicitly supplied; an empty list assumes no other flows.
    Return is a user-supplied constant annual effective rate, compounded by actual
    days / 365. Spending and liabilities consume cash on their due date; liquidity
    requirements are a minimum available balance at that date, never a withdrawal.
    Annual requirements recur on their stated anniversary. All same-day cash flows
    and outflows settle before testing the maximum same-day liquidity reserve.
    Stop at the first shortfall; no debt or sale of illiquid assets is assumed.
    """
    if through < as_of or (through - as_of).days > 365 * 151:
        raise ValueError('through must be on or after as-of and within 150 years')
    if not math.isfinite(liquid_capital) or liquid_capital < 0:
        raise ValueError('liquid capital must be finite and nonnegative')
    if not math.isfinite(annual_return_pct) or annual_return_pct <= -100 or annual_return_pct > 100:
        raise ValueError('annual return assumption must be greater than -100% and at most 100%')
    if not requirements:
        return {'state': 'missing_inputs', 'missingInputs': ['requirement schedule'], 'endingValue': None,
                'shortfall': None, 'shortfallDate': None, 'events': []}
    missing = []
    events: dict[date, dict] = {}
    for req in requirements:
        if not req.due_date:
            missing.append(f'{req.name}: dueDate')
            continue
        due = date.fromisoformat(str(req.due_date))
        if req.frequency == 'once' and due < as_of:
            missing.append(f'{req.name}: past obligation payment status')
            continue
        for year in range(max(as_of.year, due.year), through.year + 1):
            day = due if req.frequency == 'once' else _anniversary(due, year)
            if as_of <= day <= through:
                event = events.setdefault(day, {'flow': 0.0, 'outflow': 0.0, 'reserve': 0.0, 'names': []})
                if req.kind == 'liquidity':
                    event['reserve'] = max(event['reserve'], float(req.amount))
                else:
                    event['outflow'] += float(req.amount)
                event['names'].append(req.name)
            if req.frequency == 'once':
                break
    for day, amount in cashflows:
        if not math.isfinite(amount) or not as_of <= day <= through:
            raise ValueError('cash flows must be finite and occur inside the scenario dates')
        event = events.setdefault(day, {'flow': 0.0, 'outflow': 0.0, 'reserve': 0.0, 'names': []})
        event['flow'] += amount
    if missing:
        return {'state': 'missing_inputs', 'missingInputs': missing, 'endingValue': None, 'shortfall': None,
                'shortfallDate': None, 'events': []}
    balance = liquid_capital
    previous = as_of
    details = []
    try:
        for day, event in sorted(events.items()):
            balance *= (1 + annual_return_pct / 100) ** ((day - previous).days / 365)
            balance += event['flow'] - event['outflow']
            if not math.isfinite(balance):
                raise ValueError('cash flow scenario overflows')
            gap = max(0, event['reserve'] - balance)
            details.append({'date': day.isoformat(), 'balance': balance, 'reserve': event['reserve'],
                            'shortfall': gap, 'requirements': event['names']})
            if gap > 1e-9:
                return {'state': 'scenario_shortfall', 'missingInputs': [], 'endingValue': None,
                        'shortfall': gap, 'shortfallDate': day.isoformat(), 'events': details}
            previous = day
        balance *= (1 + annual_return_pct / 100) ** ((through - previous).days / 365)
    except OverflowError as exc:
        raise ValueError('cash flow scenario overflows') from exc
    if not math.isfinite(balance):
        raise ValueError('cash flow scenario overflows')
    return {'state': 'scenario_funded', 'missingInputs': [], 'endingValue': balance,
            'shortfall': 0, 'shortfallDate': None, 'events': details}
