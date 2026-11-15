"""Pure numeric functions (quant SPEC §5–§7). Inputs are fractions/levels; no I/O, no rounding.

Conventions: simple returns, sample standard deviation (ddof=1) x sqrt(252), drawdown as a
positive magnitude including the initial level, constant-weight portfolio compounding.
"""

from __future__ import annotations

import math
from typing import Sequence

PERIODS_PER_YEAR = 252  # A-16
ROLLING_WINDOW = 252    # M_WORST_ROLLING_252


def simple_returns(levels: Sequence[float]) -> list[float]:
    return [levels[i] / levels[i - 1] - 1.0 for i in range(1, len(levels))]


def sample_stdev(values: Sequence[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    mean = math.fsum(values) / n
    return math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (n - 1))


def annualized_vol_pct(returns: Sequence[float]) -> float | None:
    """``M_VOL_STDEV_252`` in percent; None with fewer than two returns."""
    sd = sample_stdev(returns)
    return None if sd is None else sd * math.sqrt(PERIODS_PER_YEAR) * 100.0


def max_drawdown_pct(levels: Sequence[float]) -> float | None:
    """``M_MDD_PEAK_TROUGH`` as a positive magnitude in percent (0 when never below a peak)."""
    if not levels:
        return None
    peak = levels[0]
    worst = 0.0
    for v in levels:
        if v > peak:
            peak = v
        dd = v / peak - 1.0
        if dd < worst:
            worst = dd
    return -worst * 100.0


def period_return_pct(levels: Sequence[float]) -> float | None:
    if len(levels) < 2:
        return None
    return (levels[-1] / levels[0] - 1.0) * 100.0


def worst_rolling_return_pct(levels: Sequence[float], window: int = ROLLING_WINDOW) -> float | None:
    """``M_WORST_ROLLING_252``: needs window + 1 levels."""
    if len(levels) < window + 1:
        return None
    return min(levels[i + window] / levels[i] - 1.0 for i in range(len(levels) - window)) * 100.0


def portfolio_returns(weights: Sequence[float], asset_returns: Sequence[Sequence[float]]) -> list[float]:
    """``M_PORT_CONST_WEIGHTS``: r_p[t] = sum_i w_i r_i[t] (weights constant, daily rebalanced)."""
    if len(weights) != len(asset_returns):
        raise ValueError("Each weight must have exactly one return series")
    n = len(asset_returns[0]) if asset_returns else 0
    if any(len(series) != n for series in asset_returns):
        raise ValueError("Return series must share the same observation calendar")
    if any(not math.isfinite(w) for w in weights) or any(
        not math.isfinite(value) for series in asset_returns for value in series
    ):
        raise ValueError("Weights and returns must be finite")
    out = [0.0] * n
    for w, rets in zip(weights, asset_returns):
        if w == 0.0:
            continue
        for t in range(n):
            out[t] += w * rets[t]
    return out


def compound(returns: Sequence[float], start: float = 1.0) -> list[float]:
    levels = [start]
    v = start
    for r in returns:
        v *= 1.0 + r
        levels.append(v)
    return levels


def pearson(a: Sequence[float], b: Sequence[float]) -> float | None:
    """``M_CORR_PEARSON``; None for fewer than two pairs or zero variance (never NaN)."""
    n = len(a)
    if n != len(b) or n < 2:
        return None
    ma, mb = math.fsum(a) / n, math.fsum(b) / n
    sab = math.fsum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = math.fsum((x - ma) ** 2 for x in a)
    sbb = math.fsum((y - mb) ** 2 for y in b)
    if saa <= 0.0 or sbb <= 0.0:
        return None
    return sab / math.sqrt(saa * sbb)


def hhi(weights: Sequence[float]) -> float:
    """Sum of squared fractional weights."""
    return math.fsum(w * w for w in weights)
