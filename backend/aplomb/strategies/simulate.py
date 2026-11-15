"""Pure day-by-day simulation of a standing strategy (``M_STRATEGY_SIM``, strategies SPEC §2).

Holdings start at today's target weights and drift with each asset's daily return on the master
calendar. At the close of each day before the last the strategy may act (rebalance, contribute,
de-risk, re-risk); the last day is "today": what the strategy would do then is the next action, not
part of the history. The baseline holds the same positions and never acts. No I/O, no model, no randomness: the same
inputs always give the same result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from aplomb.quant import metrics as mx

GROWTH_GROUPS = ("equity", "crypto")
MAX_ACTIONS = 200
#: Drift below this many points is not worth a recorded trade.
_MIN_DRIFT_PTS = 0.01


@dataclass
class Trade:
    ticker: str
    amount: float
    weight_before_pct: float
    weight_after_pct: float


@dataclass
class Action:
    date: str
    kind: str
    reason: dict
    value_before: float
    trades: list[Trade]
    cost: float


@dataclass
class Book:
    """Money held per ticker, plus the bookkeeping the metrics need."""
    holdings: dict[str, float]
    index: list[float] = field(default_factory=lambda: [1.0])   # time-weighted index
    values: list[float] = field(default_factory=list)
    invested: float = 0.0
    traded: float = 0.0
    costs: float = 0.0
    actions: int = 0

    @property
    def value(self) -> float:
        return math.fsum(self.holdings.values())

    def weights(self) -> dict[str, float]:
        v = self.value
        return {t: (h / v if v > 0 else 0.0) for t, h in self.holdings.items()}


@dataclass
class Simulation:
    dates: list[str]
    strategy: Book
    baseline: Book
    invested_series: list[float] | None
    actions: list[Action]
    actions_truncated: bool
    month_ends: list[tuple[str, dict[str, float], dict[str, float]]]   # date, strategy weights, baseline weights
    next_action: dict


def _period(day: str, frequency: str) -> str:
    year, month = day[:4], int(day[5:7])
    if frequency == "monthly":
        return f"{year}-{month:02d}"
    if frequency == "quarterly":
        return f"{year}-Q{(month - 1) // 3 + 1}"
    return year


def _pct(x: float) -> str:
    return f"{x:.1f}"


def _money(x: float, currency: str) -> str:
    return f"{x:,.0f} {currency}"


def _drift(book: Book, target: dict[str, float]) -> tuple[str | None, float]:
    """Ticker furthest from its target and the gap in points."""
    weights = book.weights()
    worst, gap = None, 0.0
    for t in sorted(set(target) | set(weights)):
        d = abs(weights.get(t, 0.0) - target.get(t, 0.0)) * 100.0
        if d > gap:
            worst, gap = t, d
    return worst, gap


def _set_holdings(book: Book, new: dict[str, float], cost_bps: float) -> tuple[list[Trade], float]:
    """Trade to ``new`` amounts; costs are taken pro rata from the result. Returns trades and cost."""
    before_value = book.value
    before = book.weights()
    tickers = sorted(set(book.holdings) | set(new))
    deltas = {t: new.get(t, 0.0) - book.holdings.get(t, 0.0) for t in tickers}
    traded = math.fsum(abs(d) for d in deltas.values())
    cost = traded * cost_bps / 10_000.0
    total = math.fsum(new.values())
    scale = (total - cost) / total if total > 0 else 1.0
    book.holdings = {t: new.get(t, 0.0) * scale for t in tickers if new.get(t, 0.0) > 0}
    book.traded += traded
    book.costs += cost
    after = book.weights()
    trades = [Trade(t, deltas[t], before.get(t, 0.0) * 100.0, after.get(t, 0.0) * 100.0)
              for t in tickers if abs(deltas[t]) > before_value * 1e-6]
    return trades, cost


def _rebalance_amounts(value: float, target: dict[str, float]) -> dict[str, float]:
    return {t: value * w for t, w in target.items()}


def _contribution_split(book: Book, amount: float, target: dict[str, float], allocation: str) -> dict[str, float]:
    """Money added per ticker. ``underweight`` fills the gaps to target first, never sells."""
    if allocation == "target":
        return {t: amount * w for t, w in target.items()}
    after = book.value + amount
    gaps = {t: max(0.0, after * w - book.holdings.get(t, 0.0)) for t, w in target.items()}
    total_gap = math.fsum(gaps.values())
    if total_gap <= 0:
        return {t: amount * w for t, w in target.items()}
    if total_gap >= amount:
        return {t: amount * g / total_gap for t, g in gaps.items() if g > 0}
    rest = amount - total_gap
    return {t: gaps[t] + rest * w for t, w in target.items()}


def simulate(*, dates: list[str], returns: dict[str, list[float]], target: dict[str, float], start_value: float,
             config: dict, groups: dict[str, str], safe_ticker: str | None, currency: str) -> Simulation:
    """Run ``config`` (a StrategyConfig wire dict with defaults filled in) over ``dates``.

    ``returns[t][k]`` is the simple return of ticker ``t`` from ``dates[k]`` to ``dates[k + 1]``;
    every ticker of ``target`` (and the safe asset of a risk guard) must be present.
    """
    if len(dates) < 2:
        raise ValueError("a simulation needs at least two days")
    kind = config["kind"]
    cost_bps = float(config.get("costBps") or 0.0)
    strategy = Book(holdings=_rebalance_amounts(start_value, target), invested=start_value)
    baseline = Book(holdings=_rebalance_amounts(start_value, target), invested=start_value)
    strategy.values.append(start_value)
    baseline.values.append(start_value)
    invested_series = [start_value] if kind == "contribute" else None
    actions: list[Action] = []
    month_ends: list[tuple[str, dict[str, float], dict[str, float]]] = []
    peak = start_value
    defensive_since: str | None = None
    growth = [t for t in sorted(target) if groups.get(t) in GROWTH_GROUPS]

    def record(day: str, action_kind: str, reason: dict, value_before: float, trades: list[Trade], cost: float) -> None:
        strategy.actions += 1
        actions.append(Action(day, action_kind, reason, value_before, trades, cost))

    last = len(dates) - 1
    for k in range(1, len(dates)):
        day = dates[k]
        for book in (strategy, baseline):
            before = book.value
            book.holdings = {t: h * (1.0 + returns[t][k - 1]) for t, h in book.holdings.items()}
            book.index.append(book.index[-1] * (book.value / before if before > 0 else 1.0))

        if k == last:
            pass  # today: reported as the next action, never applied
        elif kind == "rebalance":
            worst, gap = _drift(strategy, target)
            if config["trigger"] == "calendar":
                due = _period(dates[k + 1], config["frequency"]) != _period(day, config["frequency"])
                label = {"monthly": ("Month end", "Fin de mois"), "quarterly": ("Quarter end", "Fin de trimestre"),
                         "yearly": ("Year end", "Fin d’année")}[config["frequency"]]
                reason = {"en": f"{label[0]}: weights brought back to target (largest drift {_pct(gap)} pts, {worst})",
                          "fr": f"{label[1]} : pondérations ramenées à la cible (plus grand écart {_pct(gap)} pts, {worst})"}
            else:
                due = gap > config["bandPts"]
                reason = {"en": f"{worst} drifted {_pct(gap)} pts from its {_pct(target.get(worst or '', 0.0) * 100)}% target "
                                f"(band {_pct(config['bandPts'])} pts): weights brought back to target",
                          "fr": f"{worst} s’est écarté de {_pct(gap)} pts de sa cible de {_pct(target.get(worst or '', 0.0) * 100)} % "
                                f"(bande {_pct(config['bandPts'])} pts) : pondérations ramenées à la cible"}
            if due and gap > _MIN_DRIFT_PTS:
                value = strategy.value
                trades, cost = _set_holdings(strategy, _rebalance_amounts(value, target), cost_bps)
                record(day, "rebalance", reason, value, trades, cost)

        elif kind == "contribute":
            if _period(day, config["frequency"]) != _period(dates[k - 1], config["frequency"]):
                amount = float(config["amount"])
                value = strategy.value
                split = _contribution_split(strategy, amount, target, config["allocation"])
                new = dict(strategy.holdings)
                for t, a in split.items():
                    new[t] = new.get(t, 0.0) + a
                trades, cost = _set_holdings(strategy, new, cost_bps)
                strategy.invested += amount
                # A deposit is a flow, not a return: the time-weighted index ignores it.
                where = ({"en": "split by target weights", "fr": "réparti selon les pondérations cibles"} if config["allocation"] == "target"
                         else {"en": "sent to the positions furthest below their target", "fr": "envoyé aux positions les plus sous leur cible"})
                period = {"monthly": ("Monthly", "mensuel"), "quarterly": ("Quarterly", "trimestriel")}[config["frequency"]]
                record(day, "contribute", {"en": f"{period[0]} contribution of {_money(amount, currency)}, {where['en']}",
                                           "fr": f"Versement {period[1]} de {_money(amount, currency)}, {where['fr']}"}, value, trades, cost)

        elif kind == "risk_guard":
            value = strategy.value
            peak = max(peak, value)
            fall = (1.0 - value / peak) * 100.0 if peak > 0 else 0.0
            if defensive_since is None and fall >= config["triggerDrawdownPct"] and growth:
                share = config["shiftPct"] / 100.0
                new = dict(strategy.holdings)
                moved = 0.0
                for t in growth:
                    m = new.get(t, 0.0) * share
                    new[t] = new.get(t, 0.0) - m
                    moved += m
                new[safe_ticker] = new.get(safe_ticker, 0.0) + moved
                trades, cost = _set_holdings(strategy, new, cost_bps)
                defensive_since = day
                record(day, "de_risk", {
                    "en": f"Fall of {_pct(fall)}% from the peak (trigger {_pct(config['triggerDrawdownPct'])}%): "
                          f"{_pct(config['shiftPct'])}% of equity and crypto moved to {safe_ticker}",
                    "fr": f"Baisse de {_pct(fall)} % depuis le sommet (seuil {_pct(config['triggerDrawdownPct'])} %) : "
                          f"{_pct(config['shiftPct'])} % des actions et de la crypto déplacés vers {safe_ticker}"}, value, trades, cost)
            elif defensive_since is not None and fall <= config["reentryDrawdownPct"]:
                trades, cost = _set_holdings(strategy, _rebalance_amounts(value, target), cost_bps)
                record(day, "re_risk", {
                    "en": f"Fall back to {_pct(fall)}% from the peak (re-entry under {_pct(config['reentryDrawdownPct'])}%): target weights restored",
                    "fr": f"Baisse revenue à {_pct(fall)} % du sommet (retour sous {_pct(config['reentryDrawdownPct'])} %) : pondérations cibles rétablies"},
                    value, trades, cost)
                defensive_since = None

        strategy.values.append(strategy.value)
        baseline.values.append(baseline.value)
        if invested_series is not None:
            invested_series.append(strategy.invested)
        if k == last or dates[k + 1][:7] != day[:7]:
            month_ends.append((day, strategy.weights(), baseline.weights()))

    truncated = len(actions) > MAX_ACTIONS
    kept = actions[-MAX_ACTIONS:]
    return Simulation(dates, strategy, baseline, invested_series, kept, truncated, month_ends,
                      _next_action(config, strategy, target, peak, defensive_since, dates[-1], currency, safe_ticker, growth))


def _next_action(config: dict, book: Book, target: dict[str, float], peak: float, defensive_since: str | None,
                 last_day: str, currency: str, safe_ticker: str | None, growth: list[str]) -> dict:
    """What the strategy would do next from the last simulated day (nothing is executed)."""
    kind = config["kind"]
    value = book.value
    weights = book.weights()

    def preview(new: dict[str, float]) -> list[Trade]:
        total = math.fsum(new.values())
        return [Trade(t, new.get(t, 0.0) - book.holdings.get(t, 0.0), weights.get(t, 0.0) * 100.0,
                      (new.get(t, 0.0) / total * 100.0) if total > 0 else 0.0)
                for t in sorted(set(new) | set(book.holdings)) if abs(new.get(t, 0.0) - book.holdings.get(t, 0.0)) > value * 1e-6]

    if kind == "rebalance":
        worst, gap = _drift(book, target)
        trades = preview(_rebalance_amounts(value, target))
        if config["trigger"] == "band":
            due = gap > config["bandPts"]
            return {"due": due, "trades": trades if due else [], "summary": (
                {"en": f"Rebalance now: {worst} is {_pct(gap)} pts from target, past the {_pct(config['bandPts'])}-pt band",
                 "fr": f"Rééquilibrer maintenant : {worst} est à {_pct(gap)} pts de sa cible, au-delà de la bande de {_pct(config['bandPts'])} pts"} if due else
                {"en": f"No action: largest drift {_pct(gap)} pts ({worst}), band {_pct(config['bandPts'])} pts",
                 "fr": f"Aucune action : plus grand écart {_pct(gap)} pts ({worst}), bande {_pct(config['bandPts'])} pts"})}
        period = {"monthly": ("month", "du mois"), "quarterly": ("quarter", "du trimestre"), "yearly": ("year", "de l’année")}[config["frequency"]]
        return {"due": False, "trades": trades, "summary": {
            "en": f"Next rebalance at the end of the {period[0]} after {last_day}. Largest drift now {_pct(gap)} pts ({worst})",
            "fr": f"Prochain rééquilibrage à la fin {period[1]} suivant le {last_day}. Plus grand écart actuel {_pct(gap)} pts ({worst})"}}

    if kind == "contribute":
        amount = float(config["amount"])
        split = _contribution_split(book, amount, target, config["allocation"])
        new = dict(book.holdings)
        for t, a in split.items():
            new[t] = new.get(t, 0.0) + a
        first = max(split, key=lambda t: split[t]) if split else None
        return {"due": False, "trades": preview(new), "summary": {
            "en": f"Next contribution of {_money(amount, currency)} at the start of the next period; largest share to {first}",
            "fr": f"Prochain versement de {_money(amount, currency)} au début de la prochaine période ; la plus grande part à {first}"}}

    peak = max(peak, value)
    fall = (1.0 - value / peak) * 100.0 if peak > 0 else 0.0
    if defensive_since is not None and fall <= config["reentryDrawdownPct"]:
        return {"due": True, "trades": preview(_rebalance_amounts(value, target)), "summary": {
            "en": f"Return to target now: the fall is back to {_pct(fall)}% (re-entry under {_pct(config['reentryDrawdownPct'])}%)",
            "fr": f"Revenir aux cibles maintenant : la baisse est revenue à {_pct(fall)} % (retour sous {_pct(config['reentryDrawdownPct'])} %)"}}
    if defensive_since is None and fall >= config["triggerDrawdownPct"] and growth:
        share = config["shiftPct"] / 100.0
        new = dict(book.holdings)
        moved = 0.0
        for t in growth:
            m = new.get(t, 0.0) * share
            new[t] = new.get(t, 0.0) - m
            moved += m
        new[safe_ticker] = new.get(safe_ticker, 0.0) + moved
        return {"due": True, "trades": preview(new), "summary": {
            "en": f"De-risk now: the fall from the peak is {_pct(fall)}% (trigger {_pct(config['triggerDrawdownPct'])}%)",
            "fr": f"Réduire le risque maintenant : la baisse depuis le sommet est de {_pct(fall)} % (seuil {_pct(config['triggerDrawdownPct'])} %)"}}
    if defensive_since is not None:
        return {"due": False, "trades": [], "summary": {
            "en": f"Defensive since {defensive_since}: target weights return when the fall is under {_pct(config['reentryDrawdownPct'])}% (now {_pct(fall)}%)",
            "fr": f"En mode défensif depuis le {defensive_since} : retour aux cibles quand la baisse passe sous {_pct(config['reentryDrawdownPct'])} % (actuellement {_pct(fall)} %)"}}
    return {"due": False, "trades": [], "summary": {
        "en": f"Watching: fall from the peak {_pct(fall)}%; at {_pct(config['triggerDrawdownPct'])}%, {_pct(config['shiftPct'])}% of equity and crypto would move to {safe_ticker}",
        "fr": f"En veille : baisse depuis le sommet {_pct(fall)} % ; à {_pct(config['triggerDrawdownPct'])} %, {_pct(config['shiftPct'])} % des actions et de la crypto iraient vers {safe_ticker}"}}


def book_metrics(book: Book) -> dict:
    """StrategyMetrics wire dict for one book."""
    index_returns = mx.simple_returns(book.index)
    mean_value = math.fsum(book.values) / len(book.values) if book.values else 0.0
    end = book.values[-1] if book.values else 0.0
    return {
        "endValue": end,
        "invested": book.invested,
        "gain": end - book.invested,
        "twrPct": (book.index[-1] - 1.0) * 100.0,
        "volPct": mx.annualized_vol_pct(index_returns),
        "maxDrawdownPct": mx.max_drawdown_pct(book.index),
        "turnoverPct": (book.traded / mean_value * 100.0) if mean_value > 0 else 0.0,
        "costs": book.costs,
        "actions": book.actions,
    }
