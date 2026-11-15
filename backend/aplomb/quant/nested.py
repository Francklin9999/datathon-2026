"""Bounded exact-ISIN nested fund decomposition with explicit unknown mass.

The caller must identify known fund ISINs and provide dated attributed captures.
No name matching, inferred security identity, rescaling or unbounded graph walk.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Mapping

from aplomb.intelligence.entities import valid_isin

from .exposures import FundSnapshot

MAX_NODES = 10_000
MAX_DEPTH = 8
MAX_PATHS = 2_000


@dataclass(frozen=True)
class NestedExposure:
    direct: dict[str, float]
    indirect: dict[str, float]
    unresolved_weight: float
    unresolved_by_reason: dict[str, float]
    source_ids: dict[str, str]
    snapshot_dates: dict[str, str]
    paths: list[dict]
    omitted_paths: int


def nested_look_through(positions: Mapping[str, float], snapshots: Mapping[str, FundSnapshot],
                        known_funds: set[str], as_of: date, *, historical: bool = False,
                        max_depth: int = MAX_DEPTH) -> NestedExposure:
    """Decompose one portfolio by exact ISIN, preserving partial/cyclic/unknown fund value.

    No-snapshot securities in ``known_funds`` are unresolved, never labeled direct.
    Unknown fund membership must be declared by caller. Cycles and depth/complexity
    limits leave unresolved weights instead of silently dropping or renormalizing.
    ``paths`` are auditable contributions; totals include any omitted path entries.
    """
    if not 1 <= max_depth <= MAX_DEPTH:
        raise ValueError('max depth must be within the bounded range')
    if not positions or any(not valid_isin(k) or not math.isfinite(v) or v < 0 for k, v in positions.items()):
        raise ValueError('positions require valid ISINs and finite nonnegative weights')
    if not math.isclose(math.fsum(positions.values()), 1, abs_tol=1e-9, rel_tol=0):
        raise ValueError('portfolio weights must sum to one')
    if any(not valid_isin(isin) for isin in known_funds):
        raise ValueError('known fund IDs must be valid ISINs')
    if any(key != value.fund_isin for key, value in snapshots.items()):
        raise ValueError('snapshot key does not match fund ISIN')
    funds = known_funds | set(snapshots)
    direct: dict[str, list[float]] = {}
    indirect: dict[str, list[float]] = {}
    missing: dict[str, list[float]] = {}
    paths, source_ids, dates = [], {}, {}
    visited = omitted = 0

    def record(destination: str, amount: float, route: tuple[str, ...], reason: str | None = None):
        nonlocal omitted
        target = missing if reason else indirect if len(route) > 1 else direct
        key = reason or destination
        target.setdefault(key, []).append(amount)
        row = {'isin': destination, 'weight': amount, 'path': list(route), 'reason': reason}
        if len(paths) < MAX_PATHS:
            paths.append(row)
        else:
            omitted += 1

    def expand(isin: str, value: float, route: tuple[str, ...]):
        nonlocal visited
        if value == 0:
            return
        visited += 1
        if visited > MAX_NODES:
            record(isin, value, route, 'expansion_limit')
            return
        if isin not in funds:
            record(isin, value, route)
            return
        if route.count(isin) > 1:
            record(isin, value, route, 'cycle')
            return
        if len(route) > max_depth:
            record(isin, value, route, 'depth_limit')
            return
        snapshot = snapshots.get(isin)
        if snapshot is None:
            record(isin, value, route, 'fund_snapshot_missing')
            return
        if snapshot.holdings_date > as_of or not snapshot.evidence.visible(as_of, historical=historical):
            raise ValueError('fund snapshot is not visible at the requested date')
        source_ids[isin] = snapshot.evidence.source_id
        dates[isin] = snapshot.holdings_date.isoformat()
        coverage = math.fsum(row.weight for row in snapshot.constituents)
        remainder = value * max(0, 1 - coverage)
        if remainder:
            record(isin, remainder, route, 'undisclosed_fund_weight')
        for row in snapshot.constituents:
            expand(row.isin, value * row.weight, (*route, row.isin))

    for isin, weight in sorted(positions.items()):
        expand(isin, weight, (isin,))
    direct_result = {key: math.fsum(values) for key, values in direct.items()}
    indirect_result = {key: math.fsum(values) for key, values in indirect.items()}
    unresolved = {key: math.fsum(values) for key, values in missing.items()}
    unknown = math.fsum(unresolved.values())
    total = math.fsum([*direct_result.values(), *indirect_result.values(), unknown])
    if not math.isfinite(total) or not math.isclose(total, 1, abs_tol=1e-8, rel_tol=0):
        raise ValueError('nested decomposition failed value conservation')
    return NestedExposure(direct_result, indirect_result, unknown, unresolved, source_ids, dates, paths, omitted)
