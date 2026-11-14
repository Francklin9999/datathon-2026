"""Field parsing and data-quality helpers shared by ingestion and the gate.

Rejections raise via the caller's problem list; flags are retained rows that deserve attention.
Nothing here deletes or interpolates a value (data SPEC "Data quality").
"""

from __future__ import annotations

import math
from fractions import Fraction

# Organizer thresholds (Datathon2026/alphaforge_starter/build_dataset.py, function `check`):
SUSPICIOUS_ONE_DAY_MOVE = 0.40      # |adjusted one-day return| above this is flagged
MAX_GAP_DAYS_EXCHANGE = 5           # calendar days between observations, equities/ETFs
MAX_GAP_DAYS_CRYPTO = 1             # calendar days between observations, crypto
# FX: organizer computes cadusd = round(1 / usdcad, 6).
FX_INVERSE_TOLERANCE = 1.5e-6
# Split ratios whose numerator and denominator (new:old) fit in this bound are "ordinary".
SPLIT_MAX_DENOMINATOR = 10


def parse_finite(text: str, field: str) -> float:
    if text is None or text.strip() == "":
        raise ValueError(f"{field}: empty")
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"{field}: not a number {text!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{field}: not finite {text!r}")
    return value


def fmt_number(value: float) -> str:
    """Deterministic, lossless text form of a parsed double."""
    if value == 0:
        return "0.0"
    return repr(float(value))


def fmt_volume(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return repr(value)


def parse_bool(text: str, field: str) -> bool:
    lowered = (text or "").strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"{field}: expected true or false, got {text!r}")


def fmt_bool(value: bool) -> str:
    return "true" if value else "false"


def is_split_anomaly(ratio: float) -> bool:
    """True when a split ratio is not a small rational such as 2, 3/2, 10 or 1/20.

    CNQ.TO's 1.021 "split" on 2022-08-22 is the motivating case (LIM_CNQ_FACTOR).
    """
    if ratio <= 0 or not math.isfinite(ratio):
        return True
    approx = Fraction(ratio).limit_denominator(SPLIT_MAX_DENOMINATOR)
    if abs(float(approx) - ratio) > 1e-9 * max(1.0, ratio):
        return True
    return approx.numerator > 1000  # absurd ratios are anomalies too


def ohlc_consistent(open_: float, high: float, low: float, close: float) -> bool:
    eps = 1e-9
    if low > high * (1 + eps):
        return False
    for v in (open_, close):
        if v < low * (1 - eps) or v > high * (1 + eps):
            return False
    return True
