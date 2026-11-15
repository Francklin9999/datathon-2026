"""Strategy simulation for a profile (api.md §3.13, strategies SPEC §3).

Builds the inputs of the pure simulation from the profile and the gated market data, checks the
profile's allocation rules at every month end, and returns a ``StrategySimulation`` wire dict.
"""

from __future__ import annotations

import math

from aplomb.api.errors import ServiceError
from aplomb.contracts import models as m
from aplomb.datastore.constants import CASH_TICKERS
from aplomb.quant import QuantEngine, Unavailable
from aplomb.rules.definitions import rule_def
from aplomb.rules.engine import RuleInputs, quick_statuses

from .simulate import book_metrics, simulate


def validation(message: str, details: dict | None = None) -> ServiceError:
    return ServiceError("validation_error", message, details)


LIMITATIONS = ["LIM_STRATEGY_COSTS", "LIM_STRATEGY_EXECUTION", "LIM_PAST_NOT_FUTURE", "LIM_SAMPLE_WINDOW",
               "LIM_CALENDAR_INTERSECTION", "LIM_YAHOO_NOT_CERTIFIED", "LIM_SIMULATION_ONLY"]


def with_defaults(config: dict, profile: m.Profile, target: dict[str, float], engine: QuantEngine) -> dict:
    """The strategy as simulated: every optional field filled in (echoed in the response)."""
    out = dict(config)
    out["costBps"] = float(out.get("costBps") or 0.0)
    if out["kind"] == "rebalance":
        if out["trigger"] == "calendar":
            out["frequency"] = out.get("frequency") or "quarterly"
            out.pop("bandPts", None)
        else:
            out["bandPts"] = float(out.get("bandPts") or 5.0)
            out.pop("frequency", None)
    elif out["kind"] == "risk_guard":
        out["safeTicker"] = safe_ticker(out.get("safeTicker"), profile, target, engine)
    return out


def safe_ticker(requested: str | None, profile: m.Profile, target: dict[str, float], engine: QuantEngine) -> str:
    """The asset a risk guard moves to: as requested, else the largest bond fund held, else cash."""
    if requested:
        try:
            record = engine.universe.get(requested)
        except Exception as exc:  # UnknownTicker
            raise validation(f"Unknown safe asset {requested}", {"fields": ["strategy.safeTicker"]}) from exc
        if record.asset_group in ("equity", "crypto"):
            raise validation("The safe asset must be a bond fund, a commodity fund or cash", {"fields": ["strategy.safeTicker"]})
        return requested
    bonds = [t for t in target if engine.universe.get(t).asset_class == "etf_bond"]
    if bonds:
        return max(bonds, key=lambda t: (target[t], t))
    return f"CASH.{profile.reporting_currency}"


def _allocation_rules(profile: m.Profile) -> list[m.PolicyRule]:
    """Enabled rules measured on weights alone (caps and floors); risk rules need a whole window."""
    out = []
    for rule in profile.rules:
        if not rule.enabled:
            continue
        try:
            metric = rule_def(rule.rule_id).metric
        except KeyError:
            continue
        if metric and metric.startswith("weight."):
            out.append(rule)
    return out


def _plan_check(engine: QuantEngine, profile: m.Profile, month_ends) -> dict:
    rules = _allocation_rules(profile)
    by_rule = {r.rule_id: {"ruleId": r.rule_id, "code": r.code, "strategyMonths": 0, "baselineMonths": 0} for r in rules}
    strategy_months = baseline_months = 0
    for _day, strategy_w, baseline_w in month_ends:
        for weights, field, counter in ((strategy_w, "strategyMonths", "s"), (baseline_w, "baselineMonths", "b")):
            clean = {t: w for t, w in weights.items() if w > 1e-12}
            total = math.fsum(clean.values())
            view = engine.view({t: w / total for t, w in clean.items()}, "after", 1.0, record=False)
            statuses = quick_statuses(rules, RuleInputs(view=view, profile_id=profile.profile_id))
            conflicts = [rid for rid, st in statuses.items() if st == "conflict"]
            for rid in conflicts:
                by_rule[rid][field] += 1
            if conflicts:
                if counter == "s":
                    strategy_months += 1
                else:
                    baseline_months += 1
    return {"monthsChecked": len(month_ends), "strategyMonthsInConflict": strategy_months,
            "baselineMonthsInConflict": baseline_months,
            "byRule": [row for row in by_rule.values() if row["strategyMonths"] or row["baselineMonths"]]}


def _trade(t) -> dict:
    return {"ticker": t.ticker, "amount": t.amount, "weightBeforePct": t.weight_before_pct, "weightAfterPct": t.weight_after_pct}


def run(engine: QuantEngine, profile: m.Profile, target: dict[str, float], strategy: dict, window: dict) -> dict:
    try:
        wr = engine.window(window)
    except Unavailable as exc:
        raise ServiceError("insufficient_data", exc.detail) from exc
    config = with_defaults(strategy, profile, target, engine)
    tickers = sorted(set(target) | ({config["safeTicker"]} if config["kind"] == "risk_guard" else set()))
    try:
        returns = {t: engine.asset_returns(t, wr.i0, wr.i1) for t in tickers}
        groups = {t: engine.universe.get(t).asset_group for t in tickers}
    except Unavailable as exc:
        raise ServiceError("insufficient_data", exc.detail) from exc
    dates = engine.market.dates[wr.i0:wr.i1 + 1]
    if len(dates) < 2:
        raise ServiceError("insufficient_data", "The window holds fewer than two market days")
    sim = simulate(dates=dates, returns=returns, target=target, start_value=profile.portfolio.total_value, config=config,
                   groups=groups, safe_ticker=config.get("safeTicker"), currency=profile.reporting_currency)

    limitations = list(LIMITATIONS)
    if engine.market.fx_rows_used(tickers, wr.i0, wr.i1):
        limitations.append("LIM_FX_FFILL")
    if any(t in CASH_TICKERS for t in tickers):
        limitations.append("LIM_CASH_NO_INTEREST")
    series = lambda values: [{"date": d, "value": v} for d, v in zip(dates, values)]  # noqa: E731
    return {
        "window": window, "currency": profile.reporting_currency, "strategy": config,
        "series": series(sim.strategy.values), "baseline": series(sim.baseline.values),
        "invested": series(sim.invested_series) if sim.invested_series is not None else None,
        "metrics": book_metrics(sim.strategy), "baselineMetrics": book_metrics(sim.baseline),
        "actions": [{"date": a.date, "kind": a.kind, "reason": a.reason, "valueBefore": a.value_before,
                     "trades": [_trade(t) for t in a.trades], "cost": a.cost} for a in sim.actions],
        "actionsTruncated": sim.actions_truncated,
        "plan": _plan_check(engine, profile, sim.month_ends),
        "nextAction": {"due": sim.next_action["due"], "summary": sim.next_action["summary"],
                       "trades": [_trade(t) for t in sim.next_action["trades"]]},
        "method": "M_STRATEGY_SIM", "limitations": limitations,
    }
