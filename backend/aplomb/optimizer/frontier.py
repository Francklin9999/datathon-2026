"""Descriptive frontier (optimizer SPEC §6, api.md §3.11). Never feeds a rule, a threshold or a verdict.

``M_FRONTIER_MINVAR``: long-only minimum variance at total-equity targets 0, 10, ..., 100%
(equity = equity and crypto groups), solved on the product of two scaled simplexes.
``M_FRONTIER_HIST_MV``: long-only mean-variance points ``min w'Sw - lambda * mu'w`` on the
simplex for a log-spaced lambda grid (historical mean returns, illustration only).
Both use accelerated projected gradient (FISTA), sample covariance of aligned daily returns,
deterministic iteration limits and a fixed tolerance; no random sampling.
"""

from __future__ import annotations

import math

from aplomb.api.errors import ServiceError
from aplomb.contracts import models as m
from aplomb.datastore.constants import CASH_TICKERS
from aplomb.quant import QuantEngine, Unavailable
from aplomb.quant import metrics as mx
from aplomb.quant.facts import fact_key, make_fact

from .derive import VOL_BUDGET

GROUP_PROXIES = ("XIU.TO", "SPY", "QQQ", "XBB.TO", "AGG", "GLD")
MAX_ASSETS = 20
TOL = 1e-12
MAX_ITER = 20000
SOLVER = {"solver": "FISTA projected gradient", "tolerance": TOL, "maxIterations": MAX_ITER}
LIMITATIONS = ["LIM_PAST_NOT_FUTURE", "LIM_MV_ILLUSTRATION", "LIM_SAMPLE_WINDOW", "LIM_CONSTANT_WEIGHTS"]


def project_simplex(v: list[float], z: float) -> list[float]:
    """Euclidean projection onto {w >= 0, sum w = z} (sort-based algorithm)."""
    if z <= 0:
        return [0.0] * len(v)
    u = sorted(v, reverse=True)
    css, theta = 0.0, 0.0
    for i, ui in enumerate(u, start=1):
        css += ui
        t = (css - z) / i
        if ui - t > 0:
            theta = t
    return [max(x - theta, 0.0) for x in v]


def _matvec(S, w):
    return [math.fsum(row[j] * w[j] for j in range(len(w))) for row in S]


def _quad(S, w):
    return math.fsum(wi * si for wi, si in zip(w, _matvec(S, w)))


def solve(S, blocks: list[tuple[list[int], float]], linear: list[float] | None = None) -> list[float]:
    """Minimize w'Sw - linear'w over a product of scaled simplexes (index block, block sum)."""
    n = len(S)
    lip = 2.0 * max(math.fsum(abs(x) for x in row) for row in S) or 1.0  # Gershgorin bound on 2*lambda_max

    def project(v):
        out = [0.0] * n
        for idx, z in blocks:
            for i, x in zip(idx, project_simplex([v[i] for i in idx], z)):
                out[i] = x
        return out

    w = project([1.0 / n] * n)
    y, t = list(w), 1.0
    lin = linear or [0.0] * n
    for _ in range(MAX_ITER):
        g = [2.0 * gi - li for gi, li in zip(_matvec(S, y), lin)]
        w_next = project([yi - gi / lip for yi, gi in zip(y, g)])
        t_next = (1.0 + math.sqrt(1.0 + 4.0 * t * t)) / 2.0
        y = [a + (t - 1.0) / t_next * (a - b) for a, b in zip(w_next, w)]
        if max(abs(a - b) for a, b in zip(w_next, w)) < TOL:
            w = w_next
            break
        w, t = w_next, t_next
    return w


def _annual_return(levels: list[float]) -> float:
    return ((levels[-1] / levels[0]) ** (252.0 / (len(levels) - 1)) - 1.0) * 100.0


def frontier(engine: QuantEngine, profile: m.Profile, query: dict) -> dict:
    """FrontierResponse wire dict for ``universe`` = holdings | asset_groups | holdings_plus:<ticker>."""
    window = dict(engine.window_spec)  # the request window the caller built the engine with (custom keeps start/end)
    spec = (query or {}).get("universe") or "holdings"
    holdings = [p.ticker for p in profile.portfolio.positions if p.weight_pct > 0]
    extra = None
    if spec == "holdings":
        tickers = holdings
    elif spec == "asset_groups":
        tickers = [t for t in GROUP_PROXIES if t in engine.universe]
    elif spec.startswith("holdings_plus:"):
        extra = spec.split(":", 1)[1]
        if extra not in engine.universe:
            raise ServiceError("not_found", f"Unknown ticker {extra}")
        tickers = holdings + ([extra] if extra not in holdings else [])
    else:
        raise ServiceError("validation_error", "universe must be holdings, asset_groups or holdings_plus:<ticker>", {"fields": ["universe"]})
    try:
        wr = engine.window(window)
    except Unavailable as exc:
        raise ServiceError("insufficient_data", exc.detail) from exc
    usable, rets, skipped = [], [], []
    for t in dict.fromkeys(tickers):
        if t in CASH_TICKERS:
            skipped.append(t)
            continue
        try:
            r = engine.asset_returns(t, wr.i0, wr.i1)
        except Unavailable:
            skipped.append(t)
            continue
        usable.append(t)
        rets.append(r)
    usable, rets = usable[:MAX_ASSETS], rets[:MAX_ASSETS]
    if len(usable) < 2:
        raise ServiceError("insufficient_data", "At least two assets with complete history are needed for a frontier")
    n_ret = len(rets[0])
    means = [math.fsum(r) / n_ret for r in rets]
    S = [[math.fsum((a - mi) * (b - mj) for a, b in zip(ri, rj)) / (n_ret - 1) * 252.0
          for rj, mj in zip(rets, means)] for ri, mi in zip(rets, means)]
    ann_mu = [mu * 252.0 for mu in means]

    def point(w: list[float]) -> dict:
        weights = {t: x for t, x in zip(usable, w) if x > 1e-9}
        total = math.fsum(weights.values())
        weights = {t: x / total for t, x in weights.items()}
        levels = engine.portfolio_levels(weights, wr.i0, wr.i1)
        return {"volPct": mx.annualized_vol_pct(mx.simple_returns(levels)), "histReturnPct": _annual_return(levels),
                "weights": [{"ticker": t, "weightPct": min(x * 100.0, 100.0)} for t, x in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))]}

    growth = [i for i, t in enumerate(usable) if engine.universe.get(t).asset_group in ("equity", "crypto")]
    other = [i for i in range(len(usable)) if i not in growth]
    if not growth:
        targets = [0]
    elif not other:
        targets = [100]
    else:
        targets = list(range(0, 101, 10))
    min_var = []
    for e in targets:
        blocks = [(growth, e / 100.0), (other, 1.0 - e / 100.0)]
        min_var.append({**point(solve(S, [b for b in blocks if b[0]])), "equityPct": float(e)})
    hist_mv, seen = [], set()
    for k in range(12):
        lam = 10 ** (-3 + k * 0.5)
        p = point(solve(S, [(list(range(len(usable))), 1.0)], [lam * x for x in ann_mu]))
        key = tuple(round(x["weightPct"], 4) for x in p["weights"]) + tuple(x["ticker"] for x in p["weights"])
        if key not in seen:
            seen.add(key)
            hist_mv.append(p)
    hist_mv.sort(key=lambda p: p["volPct"])

    current = {t: x for t, x in ((p.ticker, p.weight_pct / 100.0) for p in profile.portfolio.positions) if x > 0}
    portfolio = None
    try:
        levels = engine.portfolio_levels(current, wr.i0, wr.i1)
        portfolio = {"volPct": mx.annualized_vol_pct(mx.simple_returns(levels)), "histReturnPct": _annual_return(levels)}
    except Unavailable as exc:
        raise ServiceError("insufficient_data", exc.detail) from exc

    ctx = engine.ctx
    for kind, pts, method, lims in (("minvar", min_var, "M_FRONTIER_MINVAR", LIMITATIONS[:1] + LIMITATIONS[2:]),
                                    ("histmv", hist_mv, "M_FRONTIER_HIST_MV", LIMITATIONS)):
        for i, p in enumerate(pts):
            engine.ledger.add_fact(make_fact(
                ctx, key=fact_key("frontier.point", "portfolio", profile.profile_id, f"{kind}:{spec}:{i}", wr.code), kind="computed",
                metric="frontier.point", label={"en": f"Frontier point {i + 1} ({kind}), volatility", "fr": f"Point {i + 1} de la frontière ({kind}), volatilité"},
                value=p["volPct"], unit="pct", currency=None, subject={"type": "portfolio", "id": profile.profile_id, "variant": f"{kind}:{i}"},
                method_id=method, created_by="optimizer", period=wr.period, window=window,
                params={"histReturnPct": p["histReturnPct"], "assets": len(usable), **SOLVER}, limitations=lims,
                checks=[{"code": "long_only_sum_one", "ok": abs(math.fsum(x["weightPct"] for x in p["weights"]) - 100.0) < 1e-6,
                         "detail": "Weights are non-negative and sum to 100%."}]))
    facts = engine.ledger.wire() if hasattr(engine.ledger, "wire") else {k: v.to_wire() for k, v in engine.ledger.export().facts.items()}
    assets = []
    for t, r in zip(usable, rets):
        lv = mx.compound(r)
        assets.append({"ticker": t, "volPct": mx.annualized_vol_pct(r), "histReturnPct": _annual_return(lv)})
    return {
        "window": window, "currency": profile.reporting_currency, "assets": assets,
        "minVarFrontier": [{k: v for k, v in p.items() if k != "equityPct"} for p in min_var], "histMvFrontier": hist_mv,
        "portfolio": portfolio, "portfolioAfter": None, "volBudgetPct": VOL_BUDGET[profile.risk_level],
        "limitations": LIMITATIONS, "facts": facts,
    }
