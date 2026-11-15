"""Safe bounded conditional trees over the existing financial measurements.

No user-authored code, SQL, formulas or arbitrary attribute paths are evaluated.
Unknown measurements propagate through three-valued boolean logic.
"""
from __future__ import annotations

from dataclasses import dataclass

from aplomb.contracts.models import ConditionalPolicy, ConditionGroup, ConditionPredicate
from aplomb.quant.engine import Measurement, PortfolioView

TOL = 1e-9
METRICS = {
    'position': 'weight.position', 'sector': 'weight.sector', 'asset_class': 'weight.asset_class',
    'country': 'weight.country', 'currency': 'weight.currency', 'theme': 'weight.theme',
    'volatility': 'vol.annualized', 'drawdown': 'drawdown.max',
}


@dataclass(frozen=True)
class EvaluatedPredicate:
    predicate: ConditionPredicate
    measurement: Measurement
    matched: bool | None


@dataclass(frozen=True)
class EvaluatedPolicy:
    status: str
    guard: bool | None
    required: bool | None
    predicates: tuple[EvaluatedPredicate, ...]
    requirements: tuple[EvaluatedPredicate, ...]


def _predicate(predicate: ConditionPredicate, view: PortfolioView) -> EvaluatedPredicate:
    measurement = view.measure(METRICS[predicate.dimension], predicate.key)
    value = measurement.value
    if value is None:
        return EvaluatedPredicate(predicate, measurement, None)
    threshold = predicate.threshold
    matched = {
        'lt': lambda: value < threshold - TOL,
        'lte': lambda: value <= threshold + TOL,
        'eq': lambda: abs(value - threshold) <= TOL,
        'gte': lambda: value >= threshold - TOL,
        'gt': lambda: value > threshold + TOL,
    }[predicate.operator]()
    return EvaluatedPredicate(predicate, measurement, matched)


def _tree(node: ConditionPredicate | ConditionGroup, view: PortfolioView,
          leaves: list[EvaluatedPredicate]) -> bool | None:
    if isinstance(node, ConditionPredicate):
        item = _predicate(node, view)
        leaves.append(item)
        return item.matched
    values = [_tree(child, view, leaves) for child in node.clauses]
    if node.mode == 'all':
        return False if False in values else None if None in values else True
    return True if True in values else None if None in values else False


def evaluate(policy: ConditionalPolicy, view: PortfolioView) -> EvaluatedPolicy:
    guards: list[EvaluatedPredicate] = []
    requirements: list[EvaluatedPredicate] = []
    guard = _tree(policy.when, view, guards) if policy.when else True
    required = _tree(policy.require, view, requirements)
    # False guard => inapplicable; true consequent => implication holds even
    # when the guard is unknown. Otherwise preserve an unknown if needed.
    status = ('pass' if guard is False or required is True else
              'nee' if guard is None or required is None else 'conflict')
    return EvaluatedPolicy(status, guard, required, tuple(guards), tuple(requirements))
