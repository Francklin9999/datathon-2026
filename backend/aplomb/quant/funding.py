"""Post-move weights (``M_WEIGHTS_AFTER_MOVE``, quant SPEC §8). Exact equations, fractions only.

``auto`` is resolved by the optimizer; quant never guesses a funding mode.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from aplomb.datastore.constants import CASH_TICKERS

EPS = 1e-12


def _fr(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


class FundingError(ValueError):
    """Infeasible or invalid move. ``code`` is stable, ``reason`` is bilingual text."""

    def __init__(self, code: str, en: str, fr: str) -> None:
        super().__init__(en)
        self.code = code
        self.reason = {"en": en, "fr": fr}


@dataclass(frozen=True)
class MoveResult:
    weights: dict[str, float]       # fractions summing to 1, zero weights dropped
    value_factor: float             # V'/V (1 + s for new money, else 1)
    donors: tuple[str, ...]         # positions reduced by the move, in order
    mode: str


def _check_weights(weights: dict[str, float]) -> None:
    total = math.fsum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise FundingError("weights_sum", f"Portfolio weights sum to {total * 100:.4f}%, not 100%.",
                           f"Les pondérations totalisent {_fr(total * 100, 4)} %, pas 100 %.")
    if any(w < -EPS or not math.isfinite(w) for w in weights.values()):
        raise FundingError("weights_invalid", "Portfolio weights must be finite and non-negative.",
                           "Les pondérations doivent être finies et non négatives.")


def apply_move(weights: dict[str, float], ticker: str, size_pct: float, mode: str,
               from_tickers: list[str] | None = None) -> MoveResult:
    """Return post-move fractional weights. ``size_pct`` is points of current value (A-17)."""
    _check_weights(weights)
    if not isinstance(size_pct, (int, float)) or not math.isfinite(size_pct) or size_pct <= 0:
        raise FundingError("size_invalid", "Move size must be a positive finite number of points.",
                           "La taille du mouvement doit être un nombre positif fini de points.")
    s = size_pct / 100.0
    w_t = weights.get(ticker, 0.0)
    out: dict[str, float]
    donors: tuple[str, ...] = ()
    if mode == "new_money":
        if size_pct > 100.0 + EPS:
            raise FundingError("size_too_large", "New money is limited to 100 points in v1.",
                               "L'argent neuf est limité à 100 points en v1.")
        out = {k: v / (1.0 + s) for k, v in weights.items()}
        out[ticker] = (w_t + s) / (1.0 + s)
        factor = 1.0 + s
    else:
        factor = 1.0
        if s > 1.0 - w_t + EPS:
            raise FundingError("size_too_large",
                               f"The move exceeds the {100 * (1 - w_t):.2f} points not already in {ticker}.",
                               f"Le mouvement dépasse les {_fr(100 * (1 - w_t), 2)} points qui ne sont pas déjà dans {ticker}.")
        if mode == "pro_rata":
            denom = 1.0 - w_t
            if denom <= EPS:
                raise FundingError("no_donors", "No other holding can fund the move.",
                                   "Aucune autre position ne peut financer le mouvement.")
            scale = (1.0 - w_t - s) / denom
            out = {k: (v * scale if k != ticker else v) for k, v in weights.items()}
            out[ticker] = w_t + s
            donors = tuple(sorted(k for k, v in weights.items() if k != ticker and v > 0))
        elif mode == "from_cash":
            cash = [k for k in weights if k in CASH_TICKERS and k != ticker and weights[k] > 0]
            d = math.fsum(weights[k] for k in cash)
            if d + EPS < s:
                raise FundingError("insufficient_cash",
                                   f"Cash positions total {d * 100:.2f} points, less than the {size_pct:g} points needed.",
                                   f"L'encaisse totalise {_fr(d * 100, 2)} points, moins que les {_fr(size_pct, 1)} points requis.")
            out = dict(weights)
            for k in cash:
                out[k] = weights[k] * (d - s) / d
            out[ticker] = w_t + s
            donors = tuple(cash)
        elif mode == "from_holdings":
            donors_in = list(from_tickers or [])
            if not donors_in:
                raise FundingError("donors_missing", "Named-holding funding needs at least one donor.",
                                   "Le financement par positions nommées exige au moins une position.")
            if len(set(donors_in)) != len(donors_in):
                raise FundingError("donors_duplicate", "Donor list contains duplicates.",
                                   "La liste des positions vendues contient des doublons.")
            if ticker in donors_in:
                raise FundingError("donor_is_target", "The target cannot also fund the move.",
                                   "L'actif visé ne peut pas financer le mouvement.")
            unowned = [k for k in donors_in if weights.get(k, 0.0) <= 0]
            if unowned:
                raise FundingError("donor_not_owned", f"Not held: {', '.join(unowned)}.",
                                   f"Positions non détenues : {', '.join(unowned)}.")
            available = math.fsum(weights[k] for k in donors_in)
            if available + EPS < s:
                raise FundingError("insufficient_donors",
                                   f"Named holdings total {available * 100:.2f} points, less than the {size_pct:g} points needed.",
                                   f"Les positions nommées totalisent {_fr(available * 100, 2)} points, moins que les {_fr(size_pct, 1)} points requis.")
            out = dict(weights)
            remaining = s
            used = []
            for k in donors_in:  # ordered depletion, never spills to unlisted holdings
                if remaining <= EPS:
                    break
                take = min(out[k], remaining)
                out[k] -= take
                remaining -= take
                used.append(k)
            out[ticker] = w_t + s
            donors = tuple(used)
        else:
            raise FundingError("mode_invalid", f"Unknown or unresolved funding mode {mode!r}.",
                               f"Mode de financement inconnu ou non résolu {mode!r}.")
    cleaned = {k: v for k, v in out.items() if v > EPS}
    if any(v < -EPS for v in out.values()):
        raise FundingError("negative_weight", "A donor would become negative.", "Une position deviendrait négative.")
    return MoveResult(cleaned, factor, donors, mode)
