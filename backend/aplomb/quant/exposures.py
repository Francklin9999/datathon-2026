"""Dated exact-identifier fund look-through and explicit sensitivity scenarios.

These are numerical consumers, not data providers. A caller must supply validated,
attributed snapshots or clearly identified hypothetical assumptions. No security
matching by ticker/name and no guessed sensitivities or nested fund look-through.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal, Mapping

from aplomb.intelligence.entities import Evidence, valid_isin

_TOL = 1e-9


@dataclass(frozen=True)
class FundConstituent:
    isin: str
    weight: float  # fraction of fund value; may sum to less than one for partial disclosures

    def __post_init__(self):
        if not valid_isin(self.isin):
            raise ValueError('constituent needs a valid ISIN')
        if not math.isfinite(self.weight) or not 0 <= self.weight <= 1:
            raise ValueError('constituent weight must be a finite fraction between zero and one')


@dataclass(frozen=True)
class FundSnapshot:
    fund_isin: str
    holdings_date: date
    evidence: Evidence
    constituents: tuple[FundConstituent, ...]

    def __post_init__(self):
        if not valid_isin(self.fund_isin):
            raise ValueError('fund needs a valid ISIN')
        ids = [entry.isin for entry in self.constituents]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate constituent ISIN')
        if math.fsum(entry.weight for entry in self.constituents) > 1 + _TOL:
            raise ValueError('constituent weights exceed fund value')
        if self.holdings_date > self.evidence.available_at.date():
            raise ValueError('holdings date is later than evidence availability')


@dataclass(frozen=True)
class LookThrough:
    direct: Mapping[str, float]
    indirect: Mapping[str, float]
    unresolved_weight: float
    snapshot_dates: Mapping[str, date]
    source_ids: Mapping[str, str]


def look_through(positions: Mapping[str, float], snapshots: Mapping[str, FundSnapshot],
                 as_of: date, *, historical: bool = False) -> LookThrough:
    """One-level look-through by exact ISIN. Non-fund positions stay direct.

    All positions are long-only fractions of portfolio value and sum to one. Fund
    remainder is reported as unresolved, not silently scaled to 100%. A snapshot
    that is future-dated or not visible at the requested cutoff must not be used.
    Unknown fund membership must be indicated by passing an empty snapshot; otherwise
    a position is treated as a direct security (not presumed to be a fund).
    """
    if any(not valid_isin(k) or not math.isfinite(v) or v < 0 for k, v in positions.items()):
        raise ValueError('positions require valid ISINs and finite nonnegative weights')
    if not math.isclose(math.fsum(positions.values()), 1, abs_tol=_TOL, rel_tol=0):
        raise ValueError('portfolio weights must sum to one')
    direct, indirect, dates, sources = {}, {}, {}, {}
    unresolved = 0.0
    for isin, weight in positions.items():
        snapshot = snapshots.get(isin)
        if snapshot is None:
            direct[isin] = weight
            continue
        if snapshot.fund_isin != isin:
            raise ValueError('snapshot key does not match fund ISIN')
        if snapshot.holdings_date > as_of or not snapshot.evidence.visible(as_of, historical=historical):
            raise ValueError('fund snapshot is not visible at the requested date')
        dates[isin] = snapshot.holdings_date
        sources[isin] = snapshot.evidence.source_id
        covered = math.fsum(item.weight for item in snapshot.constituents)
        unresolved += weight * max(0.0, 1 - covered)
        for item in snapshot.constituents:
            indirect[item.isin] = indirect.get(item.isin, 0.0) + weight * item.weight
    return LookThrough(direct, indirect, unresolved, dates, sources)


def disclosed_overlap(first: FundSnapshot, second: FundSnapshot, as_of: date,
                      *, historical: bool = False) -> float:
    """Shared weight, sum(min(weight A, weight B)) on exact constituent ISINs.

    This is a lower bound on disclosed overlap when either capture is partial; it
    does not account for derivatives, nested funds, or issuer-level relationships.
    """
    for snapshot in (first, second):
        if snapshot.holdings_date > as_of or not snapshot.evidence.visible(as_of, historical=historical):
            raise ValueError('fund snapshot is not visible at the requested date')
    left = {x.isin: x.weight for x in first.constituents}
    right = {x.isin: x.weight for x in second.constituents}
    return math.fsum(min(left[k], right[k]) for k in left.keys() & right.keys())


ShockKind = Literal['currency', 'interest_rate', 'credit_spread', 'commodity', 'factor']


@dataclass(frozen=True)
class Shock:
    kind: ShockKind
    key: str
    change: float  # FX/commodity/factor: fractional return; rate/spread: basis points
    assumption: str

    def __post_init__(self):
        if self.kind not in ('currency', 'interest_rate', 'credit_spread', 'commodity', 'factor'):
            raise ValueError('unknown shock kind')
        if not self.key or not self.assumption or not math.isfinite(self.change):
            raise ValueError('shock requires a key, finite change and explicit assumption')
        if self.kind in ('currency', 'commodity') and self.change < -1:
            raise ValueError('currency and commodity price shocks cannot be below -100%')

    @property
    def decimal_change(self) -> float:
        return self.change / 10_000 if self.kind in ('interest_rate', 'credit_spread') else self.change


@dataclass(frozen=True)
class Sensitivity:
    value: float  # signed elasticity to decimal change; rate durations normally negative
    source: str  # source reference or explicit user assumption
    as_of: date

    def __post_init__(self):
        if not math.isfinite(self.value) or not self.source:
            raise ValueError('sensitivity requires a finite value and source or assumption')


@dataclass(frozen=True)
class ShockResult:
    impact_fraction: float | None
    known_impact_fraction: float
    contributions: Mapping[str, float]
    missing: tuple[str, ...]


def linear_shock(weights: Mapping[str, float], shock: Shock,
                 sensitivities: Mapping[str, Sensitivity], as_of: date) -> ShockResult:
    """First-order impact = sum(weight * signed sensitivity * decimal shock).

    A rate sensitivity of -5 is a modified duration of five: a +100 bp move
    implies approximately -5% for that position. Currency exposure requires a
    sensitivity to a rise in reporting currency per unit of foreign currency;
    quote currency alone is not sufficient. No interaction/convexity is modeled.
    Missing exposure is unknown (including for a holding whose exposure might be
    zero); the total is None until every nonzero position has an input.
    """
    if any(not k or not math.isfinite(v) or v < 0 for k, v in weights.items()):
        raise ValueError('weights must be finite and nonnegative')
    if not math.isclose(math.fsum(weights.values()), 1, abs_tol=_TOL, rel_tol=0):
        raise ValueError('weights must sum to one')
    contributions, missing = {}, []
    for key, weight in sorted(weights.items()):
        if weight == 0:
            continue
        sensitivity = sensitivities.get(key)
        if sensitivity is None or sensitivity.as_of > as_of:
            missing.append(key)
        else:
            amount = weight * sensitivity.value * shock.decimal_change
            if not math.isfinite(amount):
                raise ValueError('scenario impact overflows')
            contributions[key] = amount
    known = math.fsum(contributions.values())
    if not math.isfinite(known):
        raise ValueError('scenario impact overflows')
    return ShockResult(None if missing else known, known, contributions, tuple(missing))
