"""Numerically checked sample covariance on identical return calendars."""
from __future__ import annotations

import math
from typing import Sequence


def sample_covariance(series: Sequence[Sequence[float]]) -> list[list[float]] | None:
    """Fractional-return covariance, ddof=1; inputs must already share one calendar.

    Returns None for fewer than two aligned observations. A zero variance is a
    valid covariance of zero; unlike correlation it needs no division by sigma.
    """
    if not series:
        raise ValueError('at least one return series is required')
    n = len(series[0])
    if any(len(row) != n for row in series):
        raise ValueError('return series must share the same observation calendar')
    if any(not math.isfinite(value) for row in series for value in row):
        raise ValueError('returns must be finite')
    if n < 2:
        return None
    try:
        means = [math.fsum(row) / n for row in series]
        matrix = [[0.0] * len(series) for _ in series]
        for i, left in enumerate(series):
            for j in range(i, len(series)):
                value = math.fsum((a - means[i]) * (b - means[j])
                                  for a, b in zip(left, series[j], strict=True)) / (n - 1)
                if not math.isfinite(value):
                    raise ValueError('sample covariance overflows')
                matrix[i][j] = matrix[j][i] = value
    except OverflowError as exc:
        raise ValueError('sample covariance overflows') from exc
    return matrix
