"""Pure strategy simulation (strategies SPEC §2) on synthetic prices: exact, deterministic behaviour."""

from __future__ import annotations

import math

import pytest
from aplomb.strategies.simulate import book_metrics, simulate

TARGET = {"EQ": 0.6, "BD": 0.4}
GROUPS = {"EQ": "equity", "BD": "fixed_income", "CASH.CAD": "cash"}


def days(n: int, start_month: int = 1) -> list[str]:
    """``n`` business-like days spread over months: 21 per month."""
    out = []
    for k in range(n):
        month = start_month + k // 21
        out.append(f"{2022 + (month - 1) // 12}-{(month - 1) % 12 + 1:02d}-{k % 21 + 1:02d}")
    return out


def run(config, returns, n, safe=None):
    return simulate(dates=days(n), returns=returns, target=TARGET, start_value=1000.0, config=config,
                    groups=GROUPS, safe_ticker=safe, currency="CAD")


def test_baseline_drifts_and_monthly_rebalance_restores_target():
    n = 63  # three months
    returns = {"EQ": [0.01] * (n - 1), "BD": [0.0] * (n - 1)}
    sim = run({"kind": "rebalance", "trigger": "calendar", "frequency": "monthly", "costBps": 0}, returns, n)
    # Two month ends inside the window (the last day never acts).
    assert [a.kind for a in sim.actions] == ["rebalance", "rebalance"]
    for action in sim.actions:
        assert math.isclose(sum(t.amount for t in action.trades), 0.0, abs_tol=1e-9)   # money moves, none is created
    # Right after a rebalance the weights are the target again.
    assert all(abs(t.weight_after_pct - TARGET[t.ticker] * 100) < 1e-9 for t in sim.actions[0].trades)
    # The untouched baseline drifts towards equity; the strategy stays closer to target.
    _, _, base_w = sim.month_ends[-1]
    _, strat_w, _ = sim.month_ends[-1]
    assert base_w["EQ"] > strat_w["EQ"] > TARGET["EQ"]
    assert book_metrics(sim.baseline)["actions"] == 0


def test_costs_are_taken_from_the_portfolio():
    n = 63
    returns = {"EQ": [0.01] * (n - 1), "BD": [0.0] * (n - 1)}
    free = run({"kind": "rebalance", "trigger": "calendar", "frequency": "monthly", "costBps": 0}, returns, n)
    paid = run({"kind": "rebalance", "trigger": "calendar", "frequency": "monthly", "costBps": 50}, returns, n)
    assert paid.strategy.costs > 0
    assert paid.strategy.value < free.strategy.value


def test_band_acts_only_past_the_band():
    n = 42
    calm = {"EQ": [0.001] * (n - 1), "BD": [0.0] * (n - 1)}
    assert run({"kind": "rebalance", "trigger": "band", "bandPts": 5, "costBps": 0}, calm, n).actions == []
    jump = {"EQ": [0.0] * 10 + [0.5] + [0.0] * (n - 12), "BD": [0.0] * (n - 1)}
    sim = run({"kind": "rebalance", "trigger": "band", "bandPts": 5, "costBps": 0}, jump, n)
    assert len(sim.actions) == 1 and sim.actions[0].date == days(n)[11]
    assert "drifted" in sim.actions[0].reason["en"] and "écarté" in sim.actions[0].reason["fr"]


def test_contributions_to_the_underweight_never_sell_and_are_not_returns():
    n = 63
    returns = {"EQ": [0.01] * (n - 1), "BD": [0.0] * (n - 1)}
    sim = run({"kind": "contribute", "amount": 100, "frequency": "monthly", "allocation": "underweight", "costBps": 0}, returns, n)
    assert [a.kind for a in sim.actions] == ["contribute", "contribute"]           # first day of months 2 and 3
    assert all(t.amount >= 0 for a in sim.actions for t in a.trades)              # never sells
    assert sim.actions[0].trades[0].ticker == "BD"                                 # the underweight bond is bought
    assert math.isclose(sim.strategy.invested, 1200.0)
    assert sim.invested_series[-1] == pytest.approx(1200.0)
    metrics = book_metrics(sim.strategy)
    assert metrics["gain"] == pytest.approx(metrics["endValue"] - 1200.0)
    # Deposits are flows: with zero returns the time-weighted return stays at zero.
    flat = run({"kind": "contribute", "amount": 100, "frequency": "monthly", "allocation": "target", "costBps": 0},
               {"EQ": [0.0] * (n - 1), "BD": [0.0] * (n - 1)}, n)
    assert book_metrics(flat.strategy)["twrPct"] == pytest.approx(0.0, abs=1e-9)


def test_risk_guard_de_risks_after_the_fall_and_returns_after_recovery():
    n = 63
    crash = [0.0] * 5 + [-0.05] * 4 + [0.0] * 10 + [0.06] * 5 + [0.0] * (n - 1 - 24)
    returns = {"EQ": crash, "BD": [0.0] * (n - 1), "CASH.CAD": [0.0] * (n - 1)}
    config = {"kind": "risk_guard", "triggerDrawdownPct": 8, "shiftPct": 50, "reentryDrawdownPct": 2, "costBps": 0}
    sim = run(config, returns, n, safe="BD")
    assert [a.kind for a in sim.actions] == ["de_risk", "re_risk"]
    de_risk = sim.actions[0]
    sold = sum(-t.amount for t in de_risk.trades if t.amount < 0)
    bought = sum(t.amount for t in de_risk.trades if t.amount > 0)
    assert sold == pytest.approx(bought)                                           # equity moved to the bond, nothing lost
    assert {t.ticker for t in de_risk.trades} == {"EQ", "BD"}
    # Protection lowers the deepest fall compared with doing nothing.
    assert book_metrics(sim.strategy)["maxDrawdownPct"] < book_metrics(sim.baseline)["maxDrawdownPct"]


def test_next_action_reports_without_acting():
    n = 42
    jump = {"EQ": [0.0] * (n - 2) + [0.5], "BD": [0.0] * (n - 1)}
    sim = run({"kind": "rebalance", "trigger": "band", "bandPts": 5, "costBps": 0}, jump, n)
    assert sim.actions == []                                   # the last day is today: nothing applied
    assert sim.next_action["due"] is True and sim.next_action["trades"]
    assert "Rebalance now" in sim.next_action["summary"]["en"]


def test_same_inputs_same_result():
    n = 63
    returns = {"EQ": [0.01, -0.02, 0.015] * 20 + [0.0, 0.0], "BD": [0.0] * (n - 1)}
    config = {"kind": "rebalance", "trigger": "band", "bandPts": 2, "costBps": 10}
    a, b = run(config, returns, n), run(config, returns, n)
    assert a.strategy.values == b.strategy.values and [x.date for x in a.actions] == [x.date for x in b.actions]
