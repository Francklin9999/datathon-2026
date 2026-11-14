"""Goal candidates, alternatives, rebalance (OPT-06/07), frontier (OPT-08), agent tools and
goal/alternative/rebalance scenarios in the T08 controls provider."""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from aplomb.agents.registry import LOOKUP, QUANT, RISK, ToolContext, ToolRegistry
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.optimizer.frontier import frontier, project_simplex, solve
from aplomb.optimizer.scenarios import alternatives, goal_candidates, rebalance
from aplomb.optimizer.services import DecisionControls
from aplomb.optimizer.tools import HANDLERS, register_domain_tools
from aplomb.quant import LocalLedger, QuantEngine, apply_move

from tests.unit.datastore._support import starter_snapshot
from tests.unit.rules._support import PROFILES, weights_of

NOW = "2026-11-14T23:55:00Z"


def engine(pid="t"):
    return QuantEngine(starter_snapshot().gate("2026-11-12"), LocalLedger(), currency="CAD", subject_id=pid, created_at=NOW)


def goal(**kw) -> m.ExposureGoal:
    body = {"themes": [], "assetClasses": [], "tickers": [], "targetExposurePct": None, "maxLossPct": None, "maxVolPct": None, "notes": ""}
    body.update(kw)
    return m.ExposureGoal.model_validate(body)


def with_portfolio(pid: str, weights: dict[str, float]) -> m.Profile:
    data = PROFILES[pid].to_wire()
    data["portfolio"]["positions"] = [{"ticker": t, "weightPct": w * 100} for t, w in weights.items()]
    return m.Profile.model_validate(data)


class Goals(unittest.TestCase):

    def test_robert_ai_goal(self):
        r = goal_candidates(engine("robert"), PROFILES["robert"], goal(themes=["ai"], maxLossPct=15))
        self.assertEqual(r.screened, ["MSFT", "NVDA", "GOOGL"])
        self.assertEqual([s["moves"][0]["ticker"] for s in r.scenarios], ["GOOGL", "MSFT", "NVDA"])  # ties: ticker order
        self.assertEqual([s["moves"][0]["sizePct"] for s in r.scenarios], [10.0, 10.0, 10.0])  # the 10% position cap binds
        self.assertEqual([s["isBestFit"] for s in r.scenarios], [True, False, False])
        self.assertEqual([s["rank"] for s in r.scenarios], [1, 2, 3])
        for s in r.scenarios:
            self.assertEqual(s["kind"], "goal_candidate")
            self.assertNotEqual(s["verdict"], "conflict")
            self.assertAlmostEqual(s["exposure"][0]["afterPct"], 10.0)
            self.assertIn("never by past returns", s["rationale"]["en"])

    def test_target_exposure_is_reached_and_union_counted(self):  # OPT-07
        r = goal_candidates(engine("amira"), PROFILES["amira"], goal(themes=["ai", "semiconductors"], tickers=["NVDA"], targetExposurePct=30))
        self.assertTrue(r.scenarios)
        self.assertLessEqual(len(r.scenarios), 3)
        self.assertEqual(len({s["moves"][0]["ticker"] for s in r.scenarios}), len(r.scenarios))
        self.assertEqual(sum(s["isBestFit"] for s in r.scenarios), 1)
        for s in r.scenarios:
            after = {e["theme"]: e["afterPct"] for e in s["exposure"]}
            self.assertGreaterEqual(after["ai"], 30 - 1e-9)  # ai covers every matched holding here
        before = {e["theme"]: e["beforePct"] for e in r.scenarios[0]["exposure"]}
        self.assertAlmostEqual(before["ai"], 22.0)  # NVDA + MSFT + GOOGL counted once each

    def test_goal_limits_only_tighten(self):
        tight = goal_candidates(engine("robert"), PROFILES["robert"], goal(themes=["ai"], maxVolPct=5.0))  # baseline is 6.09%
        self.assertEqual(tight.scenarios, [])
        self.assertTrue(tight.notes)
        excluded = goal_candidates(engine("robert"), PROFILES["robert"], goal(assetClasses=["crypto"]))
        self.assertEqual((excluded.screened, excluded.scenarios), ([], []))  # Robert excludes crypto
        met = goal_candidates(engine("amira"), PROFILES["amira"], goal(themes=["ai"], targetExposurePct=10))
        self.assertEqual(met.scenarios, [])
        self.assertIn("already reaches", met.notes[0]["en"])


class Alternatives(unittest.TestCase):

    def test_shared_tags(self):
        r = alternatives(engine("amira"), PROFILES["amira"], "NVDA", 10)
        self.assertEqual([s["moves"][0]["ticker"] for s in r.scenarios], ["MSFT", "GOOGL"])
        self.assertTrue(all(s["kind"] == "alternative" and not s["isBestFit"] for s in r.scenarios))
        self.assertIn("does not make two assets equivalent", r.scenarios[0]["rationale"]["en"])
        none = alternatives(engine("robert"), PROFILES["robert"], "TSLA", 25)  # no other electric_vehicles asset
        self.assertEqual(none.scenarios, [])


class Rebalance(unittest.TestCase):

    def test_removes_every_conflict(self):
        w = apply_move(weights_of(PROFILES["robert"]), "TSLA", 25, "pro_rata").weights
        r = rebalance(engine("robert"), with_portfolio("robert", w))
        self.assertEqual(len(r.scenarios), 1)
        s = r.scenarios[0]
        self.assertEqual((s["kind"], s["scenarioId"]), ("rebalance", "sc_rebalance"))
        self.assertEqual(s["counts"]["conflict"], 0)
        self.assertLessEqual(len(s["moves"]), 5)
        self.assertAlmostEqual(sum(p["weightPct"] for p in s["portfolioAfter"]["positions"]), 100.0, delta=1e-6)

    def test_not_needed(self):
        r = rebalance(engine("robert"), PROFILES["robert"])
        self.assertEqual(r.scenarios, [])
        self.assertIn("no rebalance is needed", r.notes[0]["en"])


class Frontier(unittest.TestCase):

    def test_solver_matches_two_asset_closed_form(self):
        S = [[0.04, 0.006], [0.006, 0.01]]
        w = solve(S, [([0, 1], 1.0)])
        expected = (0.01 - 0.006) / (0.04 + 0.01 - 2 * 0.006)
        self.assertAlmostEqual(w[0], expected, places=6)
        for got, want in zip(project_simplex([0.5, 0.2, -0.1], 1.0), (0.6 + 1 / 30, 0.2 + 2 / 15, 1 / 30)):
            self.assertAlmostEqual(got, want)
        for got, want in zip(project_simplex([1.0, 0.2, -0.5], 1.0), (0.9, 0.1, 0.0)):
            self.assertAlmostEqual(got, want)
        self.assertAlmostEqual(sum(project_simplex([3.0, -1.0, 0.5, 2.0], 2.0)), 2.0)

    def test_frontier_response(self):  # OPT-08: descriptive only
        f = a.FrontierResponse.model_validate(frontier(engine("robert"), PROFILES["robert"], {})).to_wire()
        self.assertEqual(len(f["minVarFrontier"]), 11)
        self.assertGreaterEqual(len(f["histMvFrontier"]), 2)
        for p in f["minVarFrontier"] + f["histMvFrontier"]:
            self.assertAlmostEqual(sum(x["weightPct"] for x in p["weights"]), 100.0, delta=1e-6)
            self.assertTrue(all(x["weightPct"] >= 0 for x in p["weights"]))
        self.assertTrue({"LIM_PAST_NOT_FUTURE", "LIM_MV_ILLUSTRATION", "LIM_SAMPLE_WINDOW"} <= set(f["limitations"]))
        self.assertAlmostEqual(f["portfolio"]["volPct"], 6.09, delta=0.005)
        self.assertEqual(f["volBudgetPct"], 9.0)
        lowest = min(p["volPct"] for p in f["minVarFrontier"])
        self.assertLessEqual(lowest, min(x["volPct"] for x in f["assets"]) + 1e-6)  # min variance never above the safest asset
        methods = {fact["method"]["id"] for fact in f["facts"].values()}
        self.assertEqual(methods, {"M_FRONTIER_MINVAR", "M_FRONTIER_HIST_MV"})
        groups = frontier(engine("amira"), PROFILES["amira"], {"universe": "asset_groups"})
        self.assertEqual([x["ticker"] for x in groups["assets"]], ["XIU.TO", "SPY", "QQQ", "XBB.TO", "AGG", "GLD"])


def tool_ctx(pid="robert", ledger=None):
    return ToolContext(run_id="run_x", profile=PROFILES[pid], lang="en", as_of="2026-11-12", gate=starter_snapshot().gate("2026-11-12"),
                       ledger=ledger or LocalLedger(), store=None, limits=SimpleNamespace(take=lambda *_: None), logger=None)


class Tools(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = ToolRegistry()
        register_domain_tools(cls.registry)

    def run_tool(self, ctx, role, name, args):
        r = self.registry.execute(role, name, args, ctx)
        self.assertTrue(r.ok, (name, r.error))
        facts = ctx.ledger.facts()
        for fid in r.fact_ids:
            self.assertIn(fid, facts)
        return r

    def test_catalog_coverage(self):
        self.assertEqual(set(HANDLERS), LOOKUP | QUANT | RISK)

    def test_lookup_tools(self):
        ctx = tool_ctx()
        r = self.run_tool(ctx, "planner", "universe.search", {"q": "tesla"})
        self.assertEqual(r.data["assets"][0]["ticker"], "TSLA")
        self.run_tool(ctx, "planner", "universe.get", {"ticker": "SPY"})
        p = self.run_tool(ctx, "planner", "profile.get", {})
        self.assertEqual(p.data["rules"][0]["threshold"]["value"], 10.0)
        d = self.run_tool(ctx, "planner", "data.describe", {"dataset_id": "fx_usdcad_daily"})
        self.assertEqual(d.data["limitations"], ["LIM_FX_FFILL"])
        mac = self.run_tool(ctx, "planner", "macro.series", {"series_id": "V39079"})
        self.assertEqual((mac.data["max"]["value"], mac.data["last"]["value"]), (5.0, 2.5))  # controls §10
        self.assertEqual(mac.data["first"]["date"], "2021-11-12")
        self.assertEqual(len(mac.fact_ids), 4 - (mac.data["first"]["factId"] == mac.data["min"]["factId"]))

    def test_quant_and_risk_tools(self):
        ctx = tool_ctx()
        moved = self.run_tool(ctx, "quant", "quant.apply_move",
                              {"move": {"ticker": "TSLA", "sizePct": 25, "funding": {"mode": "pro_rata"}}})
        variant = moved.data["variant"]
        self.assertEqual(moved.data["weights"][0]["after"]["value"], 25.0)
        metrics = self.run_tool(ctx, "quant", "quant.portfolio_metrics", {"variant": variant})
        self.assertAlmostEqual(metrics.data["vol.annualized"]["value"], 16.96, delta=0.005)
        check = self.run_tool(ctx, "risk_officer", "rules.check", {"variant": variant})
        self.assertEqual(check.data["counts"], {"pass": 1, "tension": 1, "conflict": 6, "nee": 0, "info": 3})
        size = self.run_tool(ctx, "risk_officer", "optimizer.max_compatible_size", {"ticker": "TSLA", "funding": {"mode": "pro_rata"}})
        self.assertEqual(size.data["maxCompatibleSizePct"]["value"], 6.0)
        self.assertNotIn("size.requested", {f.metric for f in ctx.ledger.facts().values()})
        rate = self.run_tool(ctx, "quant", "quant.stress_replay", {"variant": variant, "window_id": "rate_cycle"})
        self.assertAlmostEqual(rate.data["value"]["value"], 4.07, delta=0.005)
        cy = self.run_tool(ctx, "quant", "quant.calendar_year_return", {"ticker": "TSLA", "year": 2022})
        self.assertAlmostEqual(cy.data["values"][0]["value"], -65.0, delta=0.05)
        port = self.run_tool(ctx, "quant", "quant.calendar_year_return", {"ticker": "portfolio", "year": 2022})
        self.assertAlmostEqual(port.data["value"]["value"], -4.70, delta=0.005)
        self.run_tool(ctx, "quant", "quant.portfolio_snapshot", {"variant": variant})
        self.run_tool(ctx, "quant", "quant.asset_metrics", {"ticker": "SPY", "currency": "USD"})
        self.run_tool(ctx, "quant", "quant.correlation", {"tickers": ["SPY", "XIU.TO"]})
        self.run_tool(ctx, "quant", "quant.exposure", {"variant": variant, "theme": "electric_vehicles"})
        self.run_tool(ctx, "quant", "quant.price_move_after", {"ticker": "SPY", "date": "2022-06-30", "n_days": 5})
        fund = self.run_tool(ctx, "quant", "quant.compare_funding", {"ticker": "TSLA", "size_pct": 10})
        self.assertEqual(sum(o["recommended"] for o in fund.data["options"]), 1)
        derived = self.run_tool(ctx, "risk_officer", "optimizer.derive_thresholds",
                                {"risk_level": "high", "horizon": {"min": 15, "max": None}, "preferences": PROFILES["amira"].preferences.to_wire()})
        self.assertEqual(derived.data["rules"][0]["threshold"], 25.0)
        goals = self.run_tool(ctx, "risk_officer", "optimizer.goal_candidates", {"goal": goal(themes=["ai"]).to_wire()})
        self.assertEqual(len(goals.data["scenarios"]), 3)
        self.run_tool(ctx, "risk_officer", "optimizer.alternatives", {"ticker": "TSLA", "size_pct": 25})
        self.run_tool(ctx, "risk_officer", "optimizer.rebalance", {})

    def test_errors_are_results_and_roles_enforced(self):
        ctx = tool_ctx()
        bad = self.registry.execute("quant", "quant.portfolio_metrics", {"variant": "scenario:nope"}, ctx)
        self.assertFalse(bad.ok)
        self.assertIn("Unknown variant", bad.error)
        denied = self.registry.execute("planner", "quant.asset_metrics", {"ticker": "SPY"}, ctx)
        self.assertFalse(denied.ok)


class Controls(unittest.TestCase):

    def ctx(self, profile):
        return SimpleNamespace(gate=starter_snapshot().gate("2026-11-12"), ledger=LocalLedger(), profile=profile, as_of="2026-11-12")

    def run_controls(self, profile, request):
        c, ctx = DecisionControls(), self.ctx(profile)
        return c.risk(ctx, c.quant(ctx, request, {"code": "full"}, [], []))

    def test_goal_request(self):
        out = self.run_controls(PROFILES["robert"], {"type": "goal", "goal": goal(themes=["ai"], maxLossPct=15).to_wire()})
        self.assertEqual(out.selected_scenario_id, "sc_goal_googl")
        self.assertEqual([s.kind for s in out.scenarios], ["goal_candidate"] * 3)
        self.assertEqual(out.check.funding_used.mode, "pro_rata")
        with self.assertRaises(RuntimeError):
            self.run_controls(PROFILES["robert"], {"type": "goal", "goal": goal(themes=["ai"], maxVolPct=5).to_wire()})

    def test_conflicting_move_gets_alternatives(self):
        out = self.run_controls(PROFILES["amira"], {"type": "move", "move": {"ticker": "NVDA", "sizePct": 25, "funding": {"mode": "pro_rata"}}})
        kinds = [s.kind for s in out.scenarios]
        self.assertEqual(kinds[:2], ["requested", "max_compatible"])
        self.assertIn("alternative", kinds)
        self.assertEqual([s.rank for s in out.scenarios], list(range(1, len(kinds) + 1)))

    def test_baseline_conflict_adds_rebalance(self):
        w = apply_move(weights_of(PROFILES["robert"]), "TSLA", 25, "pro_rata").weights
        out = self.run_controls(with_portfolio("robert", w), {"type": "move", "move": {"ticker": "SPY", "sizePct": 1, "funding": {"mode": "pro_rata"}}})
        self.assertTrue(out.check.baseline_conflict)
        self.assertEqual(out.scenarios[-1].kind, "rebalance")
        self.assertLessEqual(len(out.scenarios), 6)


def _finite(x):
    return isinstance(x, float) and math.isfinite(x)


if __name__ == "__main__":
    unittest.main()
