"""Largest size before the first conflict and funding comparison (optimizer SPEC §4, A-18).

The size scan is a contiguous prefix on a 0.5-point grid starting at zero: it stops at the first
conflicting size and never jumps over one (no binary search). Grid points are evaluated without
facts; only retained results become facts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from aplomb.contracts.models import PolicyRule
from aplomb.quant import FundingError, QuantEngine, apply_move
from aplomb.rules.engine import RuleInputs, quick_statuses, verdict_of_statuses

STEP = 0.5
MODES = ("pro_rata", "from_cash", "from_holdings", "new_money")


@dataclass
class SizeSearch:
    max_size_pct: float                 # last grid size before the first conflict (0 when none)
    baseline_conflict: bool
    first_conflict_pct: float | None    # None when the whole capacity was scanned without conflict
    capacity_pct: float
    stopped_by: str                     # "conflict" | "capacity" | "funding"
    grid: list[tuple[float, str]] = field(default_factory=list)   # (size, verdict) tested
    remaining_at_max: list[str] = field(default_factory=list)      # statuses other than pass/info at the boundary


def evaluate(engine: QuantEngine, rules: list[PolicyRule], weights: dict[str, float], moved: tuple[str, ...], evidence=(),
             profile_id: str = "", variant: str = "scan") -> dict[str, str]:
    view = engine.view(weights, variant, 1.0, record=False)
    return quick_statuses(rules, RuleInputs(view, profile_id, moved, tuple(evidence)))


def capacity(weights: dict[str, float], ticker: str, mode: str) -> float:
    return 100.0 if mode == "new_money" else 100.0 * (1.0 - weights.get(ticker, 0.0))


def max_compatible_size(engine: QuantEngine, rules: list[PolicyRule], weights: dict[str, float], ticker: str, mode: str,
                        from_tickers: list[str] | None = None, evidence=(), profile_id: str = "",
                        extra_conflict: Callable[[dict[str, float]], bool] | None = None,
                        max_size: float | None = None) -> SizeSearch:
    """``extra_conflict`` adds request-specific constraints (a goal's own loss/volatility limits);
    it can only add conflicts, never loosen a profile rule. ``max_size`` bounds the scan."""
    base = evaluate(engine, rules, weights, (), evidence, profile_id)
    if verdict_of_statuses(base.values()) == "conflict":
        return SizeSearch(0.0, True, 0.0, capacity(weights, ticker, mode), "conflict", [(0.0, "conflict")])
    cap = capacity(weights, ticker, mode)
    if max_size is not None:
        cap = min(cap, max_size)
    best, statuses_at_best = 0.0, base
    grid: list[tuple[float, str]] = [(0.0, verdict_of_statuses(base.values()))]
    k = 1
    while k * STEP <= cap + 1e-9:
        size = k * STEP
        try:
            w = apply_move(weights, ticker, size, mode, from_tickers).weights
        except FundingError:
            return SizeSearch(best, False, None, cap, "funding", grid, _remaining(statuses_at_best))
        st = evaluate(engine, rules, w, (ticker,), evidence, profile_id)
        verdict = verdict_of_statuses(st.values())
        if verdict != "conflict" and extra_conflict is not None and extra_conflict(w):
            verdict = "conflict"
        grid.append((size, verdict))
        if verdict == "conflict":
            return SizeSearch(best, False, size, cap, "conflict", grid, _remaining(statuses_at_best))
        best, statuses_at_best = size, st
        k += 1
    return SizeSearch(best, False, None, cap, "capacity", grid, _remaining(statuses_at_best))


def _remaining(statuses: dict[str, str]) -> list[str]:
    return sorted(f"{rid}:{s}" for rid, s in statuses.items() if s in ("tension", "nee"))


def auto_donors(engine: QuantEngine, rules: list[PolicyRule], weights: dict[str, float], ticker: str,
                size_pct: float) -> tuple[list[str], bool]:
    """Named-donor default: growth assets sharing the target's themes first, then other growth
    assets; descending weight then ticker; never the target, unowned or excluded names."""
    universe = engine.universe
    target_themes = set(universe.get(ticker).themes) if ticker in universe else set()
    excluded = _excluded(rules, engine, weights)
    pool = []
    for t, w in weights.items():
        if t == ticker or w <= 0 or t in excluded:
            continue
        a = universe.get(t)
        if a.asset_group not in ("equity", "crypto"):
            continue
        shares = bool(target_themes & set(a.themes))
        pool.append((0 if shares else 1, -w, t))
    pool.sort()
    donors, total = [], 0.0
    for _, neg_w, t in pool:
        donors.append(t)
        total += -neg_w
        if total * 100 >= size_pct - 1e-9:
            return donors, True
    return donors, False  # every eligible donor, still not enough


def _excluded(rules: list[PolicyRule], engine: QuantEngine, weights: dict[str, float]) -> set[str]:
    out = set()
    for r in rules:
        if not r.enabled or r.type != "exclude":
            continue
        for t in weights:
            a = engine.universe.get(t)
            if r.rule_id.startswith("exclude.ticker.") and t == r.rule_id[len("exclude.ticker."):]:
                out.add(t)
            if r.rule_id.startswith("exclude.asset_class.") and a.asset_class == r.rule_id[len("exclude.asset_class."):]:
                out.add(t)
            if r.rule_id.startswith("exclude.sector.") and a.asset_class == "equity":
                from aplomb.quant.engine import slug

                if slug(a.sector) == r.rule_id[len("exclude.sector."):]:
                    out.add(t)
    return out


@dataclass
class FundingEval:
    mode: str
    funding: dict                       # resolved Funding wire (never "auto")
    feasible: bool
    reason: dict | None
    statuses: dict[str, str] | None
    verdict: str | None
    max_size: SizeSearch | None
    turnover_pct: float | None
    external_pct: float
    result_weights: dict[str, float] | None
    value_factor: float = 1.0
    rank: int | None = None


def counts(statuses: dict[str, str]) -> dict[str, int]:
    out = {"pass": 0, "tension": 0, "conflict": 0, "nee": 0, "info": 0}
    for s in statuses.values():
        out[s] += 1
    return out


def compare_funding(engine: QuantEngine, rules: list[PolicyRule], weights: dict[str, float], ticker: str, size_pct: float,
                    evidence=(), profile_id: str = "", named_donors: list[str] | None = None) -> list[FundingEval]:
    """Evaluate every funding mode at the requested size and rank the feasible ones
    lexicographically: conflicts, tensions, nee, external money, turnover, mode name."""
    evals: list[FundingEval] = []
    for mode in MODES:
        donors = None
        funding = {"mode": mode}
        if mode == "from_holdings":
            if named_donors:
                donors, enough = list(named_donors), True
            else:
                donors, enough = auto_donors(engine, rules, weights, ticker, size_pct)
            if not donors:
                continue  # no eligible holding at all: the mode cannot even be described
            funding["fromTickers"] = donors
            if not enough:
                evals.append(FundingEval(mode, funding, False,
                                         {"en": "Eligible growth holdings are not large enough to fund the move.",
                                          "fr": "Les positions de croissance admissibles ne suffisent pas à financer le mouvement."},
                                         None, None, None, None, 0.0, None))
                continue
        try:
            res = apply_move(weights, ticker, size_pct, mode, donors)
        except FundingError as exc:
            evals.append(FundingEval(mode, funding, False, exc.reason, None, None, None, None, 0.0, None))
            continue
        st = evaluate(engine, rules, res.weights, (ticker,), evidence, profile_id)
        search = max_compatible_size(engine, rules, weights, ticker, mode, donors, evidence, profile_id)
        before = {k: v * (1.0 / res.value_factor) for k, v in weights.items()} if mode == "new_money" else weights
        turnover = 50.0 * math.fsum(abs(res.weights.get(t, 0.0) - before.get(t, 0.0)) for t in set(res.weights) | set(before))
        evals.append(FundingEval(mode, funding, True, None, st, verdict_of_statuses(st.values()), search, turnover,
                                 size_pct if mode == "new_money" else 0.0, res.weights, res.value_factor))
    feasible = sorted((e for e in evals if e.feasible),
                      key=lambda e: (counts(e.statuses)["conflict"], counts(e.statuses)["tension"], counts(e.statuses)["nee"],
                                     e.external_pct, round(e.turnover_pct, 9), e.mode))
    for i, e in enumerate(feasible):
        e.rank = i + 1
    return evals


def funding_option_wire(e: FundingEval) -> dict:
    rank = e.rank
    if not e.feasible:
        note = {"en": "Not feasible for this size.", "fr": "Impossible pour cette taille."}
    elif rank == 1:
        note = {"en": "Keeps the plan most intact among the feasible hypothetical funding modes (fewest conflicts, then tensions).",
                "fr": "Préserve le mieux le plan parmi les modes de financement hypothétiques possibles (le moins de conflits, puis de tensions)."}
    else:
        note = {"en": f"Ranked {rank} of the feasible funding modes.", "fr": f"Rang {rank} parmi les modes de financement possibles."}
    if e.mode == "from_holdings" and e.feasible:
        note = {"en": note["en"] + f" Donors, in order: {', '.join(e.funding['fromTickers'])}.",
                "fr": note["fr"] + f" Positions vendues, dans l'ordre : {', '.join(e.funding['fromTickers'])}."}
    return {
        "funding": e.funding, "feasible": e.feasible, "infeasibleReason": e.reason,
        "verdict": e.verdict, "counts": counts(e.statuses) if e.statuses else None,
        "maxCompatibleSizePct": e.max_size.max_size_pct if e.max_size else None,
        "recommended": rank == 1, "rank": rank, "note": note,
    }
