"""Explicit sale-date capacity, spread and impact scenarios for modeled positions.

Not an order, executable quote or prediction. The caller supplies every schedule,
capacity and cost assumption; a missing position is unknown, never zero exposure.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Mapping


@dataclass(frozen=True)
class SaleAssumption:
    dates: tuple[date, ...]
    daily_capacity: float  # gross value in reporting currency per listed date
    half_spread_bps: float
    impact_bps: float
    source: str
    as_of: date

    def __post_init__(self):
        if (not self.source.strip() or not math.isfinite(self.daily_capacity) or self.daily_capacity < 0
                or not math.isfinite(self.half_spread_bps) or not math.isfinite(self.impact_bps)
                or self.half_spread_bps < 0 or self.impact_bps < 0
                or self.half_spread_bps + self.impact_bps > 10_000):
            raise ValueError('capacity and costs must be finite, nonnegative and total cost at most 100%')
        if len(self.dates) > 3660 or len(set(self.dates)) != len(self.dates):
            raise ValueError('sale dates must be unique and bounded')


def sale_scenario(position_values: Mapping[str, float], assumptions: Mapping[str, SaleAssumption],
                  as_of: date, through: date, target: float | None = None) -> dict:
    """Schedule independent gross sales against explicit dates and per-date capacities.

    ``net = gross * (1 - (halfSpreadBps + impactBps)/10000)``. Capacity and
    costs are fixed user/source assumptions, no interaction or price movement.
    Every input value is in a single reporting currency. A position with no input,
    or a later input date, is unresolved. A known subset can cover a target; a
    deficit with unresolved positions has unknown portfolio-wide feasibility.
    """
    if through < as_of or (through - as_of).days > 3660:
        raise ValueError('through must be on or after as-of within ten years')
    if target is not None and (not math.isfinite(target) or target < 0):
        raise ValueError('withdrawal target must be finite and nonnegative')
    if (not position_values or any(not k or not math.isfinite(v) or v < 0
                                   for k, v in position_values.items())):
        raise ValueError('position values must be finite nonnegative amounts')
    if set(assumptions) - set(position_values):
        raise ValueError('liquidity assumptions must reference owned positions')
    rows, unknown, timeline = [], [], {}
    for ticker, initial in sorted(position_values.items()):
        if initial == 0:
            continue
        model = assumptions.get(ticker)
        if model is None or model.as_of > as_of:
            unknown.append(ticker)
            rows.append({'ticker': ticker, 'modeledValue': initial, 'status': 'missing_input',
                         'grossSale': None, 'netSale': None, 'remainingValue': None})
            continue
        dates = sorted(day for day in model.dates if as_of <= day <= through)
        remaining, gross, net = initial, 0.0, 0.0
        ratio = 1 - (model.half_spread_bps + model.impact_bps) / 10_000
        for day in dates:
            sold = min(remaining, model.daily_capacity)
            received = sold * ratio
            if not all(math.isfinite(v) for v in (sold, received)):
                raise ValueError('liquidity scenario overflows')
            timeline.setdefault(day.isoformat(), []).append(received)
            gross += sold
            net += received
            remaining -= sold
            if remaining == 0:
                break
        rows.append({'ticker': ticker, 'modeledValue': initial, 'status': 'modeled',
                     'grossSale': gross, 'netSale': net, 'remainingValue': remaining,
                     'source': model.source, 'assumptionAsOf': model.as_of.isoformat(),
                     'scheduledDates': [day.isoformat() for day in dates],
                     'dailyCapacity': model.daily_capacity,
                     'halfSpreadBps': model.half_spread_bps, 'impactBps': model.impact_bps})
    try:
        cashflows = [{'date': day, 'netProceeds': math.fsum(values)} for day, values in sorted(timeline.items())]
        known = math.fsum(event['netProceeds'] for event in cashflows)
    except OverflowError as exc:
        raise ValueError('liquidity proceeds overflow') from exc
    if not math.isfinite(known):
        raise ValueError('liquidity proceeds overflow')
    needed_by = None
    if target == 0:
        needed_by = as_of.isoformat()
    elif target is not None:
        running = 0.0
        for event in cashflows:
            running += event['netProceeds']
            if running >= target:
                needed_by = event['date']
                break
    state = ('no_target' if target is None else 'covered_by_modeled_positions' if needed_by else
             'unknown_missing_positions' if unknown else 'modeled_shortfall')
    return {'asOf': as_of.isoformat(), 'through': through.isoformat(), 'targetWithdrawal': target,
            'state': state, 'firstCoveredDate': needed_by, 'knownNetProceeds': known,
            'totalNetProceeds': None if unknown else known, 'missingHoldings': unknown,
            'holdings': rows, 'cashflows': cashflows,
            'limitations': ['Only caller-specified sale dates and capacity are used; omitted holdings are unknown.',
                            'Half-spread and fixed impact are assumptions per gross sale, not measured market impact.',
                            'No taxes, settlements, fees, correlated selling, market movement or execution are modeled.']}
