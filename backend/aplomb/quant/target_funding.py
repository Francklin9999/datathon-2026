"""Read-only final-target arithmetic with explicit external capital changes."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class TargetChange:
    before_value: float
    after_value: float
    external_flow: float
    purchases: float
    sales: float
    changes: tuple[dict, ...]


def compare_target_funding(total: float, before: Mapping[str, float], target: Mapping[str, float],
                           external_flow: float) -> TargetChange:
    """Weights are fractions; positive flow deposits, negative flow withdraws.

    An abstract frictionless simultaneous rebalance is assumed. Each signed dollar
    change is final_value * target_weight - initial_value * initial_weight. Thus
    purchases minus sales equals the external flow. No execution is implied.
    """
    if not math.isfinite(total) or total <= 0 or not math.isfinite(external_flow):
        raise ValueError('capital must be positive and capital/flow finite')
    final = total + external_flow
    if not math.isfinite(final) or final <= 0:
        raise ValueError('withdrawal must leave positive finite capital')
    for weights in (before, target):
        if not weights or any(not k or not math.isfinite(v) or v < 0 for k, v in weights.items()):
            raise ValueError('weights require nonempty IDs and finite nonnegative fractions')
        if not math.isclose(math.fsum(weights.values()), 1, abs_tol=1e-9, rel_tol=0):
            raise ValueError('weights must sum to one')
    changes = []
    for ticker in sorted(before.keys() | target.keys()):
        initial = total * before.get(ticker, 0)
        ending = final * target.get(ticker, 0)
        delta = ending - initial
        if not all(math.isfinite(v) for v in (initial, ending, delta)):
            raise ValueError('target calculation overflows')
        changes.append({'ticker': ticker, 'beforeValue': initial, 'targetValue': ending,
                        'changeValue': delta, 'beforeWeight': before.get(ticker, 0),
                        'targetWeight': target.get(ticker, 0)})
    purchases = math.fsum(max(0, item['changeValue']) for item in changes)
    sales = math.fsum(max(0, -item['changeValue']) for item in changes)
    if not all(math.isfinite(v) for v in (purchases, sales)):
        raise ValueError('target calculation overflows')
    return TargetChange(total, final, external_flow, purchases, sales, tuple(changes))
