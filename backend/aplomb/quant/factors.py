"""Ordinary least squares for explicitly aligned factor return periods.

This is descriptive sample exposure, not causal attribution or a return forecast.
Each factor and portfolio observation has both start and end dates; alignment on
end date alone could incorrectly treat a multi-day return as one trading day.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ReturnPeriod:
    start: date
    end: date
    value: float  # simple total return, fraction


@dataclass(frozen=True)
class FactorPeriod:
    start: date
    end: date
    risk_free: float  # fraction for the same period
    factors: Mapping[str, float]  # fractional factor returns for the same period
    source: str


@dataclass(frozen=True)
class FactorFit:
    alpha_per_period: float
    betas: Mapping[str, float]
    residual_stdev: float | None
    r_squared: float | None
    observations: int
    first_start: date
    last_end: date
    source_ids: tuple[str, ...]
    excluded_returns: int
    excluded_factors: int


def fit_factor_exposures(returns: Sequence[ReturnPeriod], factors: Sequence[FactorPeriod],
                         names: Sequence[str], *, min_observations: int = 30) -> FactorFit:
    """Regress excess portfolio returns on a caller-selected factor set.

    Exact period intersection only, never filling or extrapolating missing returns.
    Factor returns and risk-free must use the portfolio reporting currency and the
    same price/corporate-action conventions; the caller must establish this. Fits
    include a daily/period intercept; coefficients use modified Gram-Schmidt QR.
    Singular or insufficient histories raise ValueError rather than invent betas.
    """
    names = tuple(names)
    if not names or len(names) > 8 or len(set(names)) != len(names) or any(not name for name in names):
        raise ValueError('one to eight unique factor names required')
    if min_observations < len(names) + 2:
        raise ValueError('minimum observations must exceed the number of coefficients')
    asset = {}
    for row in returns:
        key = (row.start, row.end)
        if row.end <= row.start or not math.isfinite(row.value) or row.value < -1 or key in asset:
            raise ValueError('portfolio periods must be unique, increasing and at least -100%')
        asset[key] = row
    observations = {}
    for row in factors:
        key = (row.start, row.end)
        if (row.end <= row.start or not row.source or not math.isfinite(row.risk_free) or row.risk_free < -1 or
                any(name not in row.factors or not math.isfinite(row.factors[name]) for name in names) or
                key in observations):
            raise ValueError('factor periods require unique dates, finite inputs and a source')
        observations[key] = row
    keys = sorted(asset.keys() & observations.keys())
    if len(keys) < min_observations:
        raise ValueError('insufficient aligned observations')
    if any(keys[i][0] < keys[i - 1][1] for i in range(1, len(keys))):
        raise ValueError('overlapping periods are not supported')
    y = [asset[k].value - observations[k].risk_free for k in keys]
    columns = [[1.0] * len(keys)] + [[observations[k].factors[name] for k in keys] for name in names]
    # Modified Gram-Schmidt avoids explicitly inverting X'X, and detects collinearity.
    q: list[list[float]] = []
    r = [[0.0] * len(columns) for _ in columns]
    try:
        for j, original in enumerate(columns):
            vector = list(original)
            for i in range(j):
                r[i][j] = math.fsum(a * b for a, b in zip(q[i], vector, strict=True))
                vector = [a - r[i][j] * b for a, b in zip(vector, q[i], strict=True)]
            norm = math.sqrt(math.fsum(v * v for v in vector))
            original_norm = math.sqrt(math.fsum(v * v for v in original))
            if not math.isfinite(norm) or norm <= max(1e-15, original_norm * 1e-10):
                raise ValueError('factor matrix is singular or numerically unstable')
            r[j][j] = norm
            q.append([v / norm for v in vector])
        qty = [math.fsum(a * b for a, b in zip(col, y, strict=True)) for col in q]
        coefficients = [0.0] * len(columns)
        for i in range(len(columns) - 1, -1, -1):
            coefficients[i] = (qty[i] - math.fsum(r[i][j] * coefficients[j]
                                                  for j in range(i + 1, len(columns)))) / r[i][i]
        residuals = [value - math.fsum(coefficients[j] * columns[j][i] for j in range(len(columns)))
                     for i, value in enumerate(y)]
        sse = math.fsum(v * v for v in residuals)
        mean = math.fsum(y) / len(y)
        sst = math.fsum((v - mean) ** 2 for v in y)
        residual_sd = math.sqrt(sse / (len(y) - len(columns)))
        r_squared = 1 - sse / sst if sst > 1e-30 else None
    except OverflowError as exc:
        raise ValueError('factor calculation overflows') from exc
    if any(not math.isfinite(v) for v in [*coefficients, residual_sd]) or (
        r_squared is not None and not math.isfinite(r_squared)
    ):
        raise ValueError('factor calculation overflows')
    return FactorFit(coefficients[0], dict(zip(names, coefficients[1:], strict=True)), residual_sd,
                     r_squared, len(keys), keys[0][0], keys[-1][1],
                     tuple(sorted({observations[k].source for k in keys})),
                     len(asset) - len(keys), len(observations) - len(keys))
