"""OPT-01..OPT-06, POST /check acceptance rows and the optimizer adapters."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from aplomb.api.errors import NotFound, ServiceError
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.optimizer import search as search_mod
from aplomb.optimizer.check import CheckServiceImpl
from aplomb.optimizer.derive import derive_thresholds, floor5, round5
from aplomb.optimizer.search import compare_funding, max_compatible_size
from aplomb.optimizer.services import DecisionControls, deriver, proposer
from aplomb.profiles.service import ProfileServiceImpl
from aplomb.quant import LocalLedger, QuantEngine

from tests.unit.datastore._support import starter_snapshot
from tests.unit.profiles.test_profiles import A, create_request, make_repo
from tests.unit.rules._support import PROFILES, weights_of

CLOCK = lambda: datetime(2026, 11, 14, 23, 45, tzinfo=timezone.utc)  # noqa: E731
NOW = "2026-11-14T23:45:00Z"
TSLA_25 = {"ticker": "TSLA", "sizePct": 25, "funding": {"mode": "pro_rata"}}


def engine(pid="t"):
    return QuantEngine(starter_snapshot().gate("2026-11-12"), LocalLedger(), currency="CAD", subject_id=pid, created_at=NOW)


def services():
    profiles = ProfileServiceImpl(make_repo(), starter_snapshot, clock=CLOCK, deriver=deriver, proposer=proposer)
    return profiles, CheckServiceImpl(profiles, starter_snapshot, clock=CLOCK)


def check(body):
    return services()[1].check(A, a.CheckRequest.model_validate(body))


class Derivation(unittest.TestCase):
    """OPT-01 / PRF-04."""

    def test_defaults_reproduced(self):
        for pid, profile in PROFILES.items():
            d = derive_thresholds(profile, engine(pid), created_at=NOW)
            self.assertEqual([(r["code"], r["ruleId"], r["threshold"]) for r in d.rules],
                             [(r.code, r.rule_id, r.threshold) for r in profile.rules], pid)
            self.assertAlmostEqual(d.values["sigmaStockQ3Pct"], 31.22, delta=0.005)
            self.assertAlmostEqual(d.values["sigmaCryptoMedianPct"], 59.97, delta=0.005)
            self.assertEqual(d.issues, [])
        robert = derive_thresholds(PROFILES["robert"], engine(), created_at=NOW)
        self.assertEqual(robert.values["growthCapPct"], 55.0)
        self.assertEqual(robert.values["stressMultiplier"], 1.0)
        pos = next(r for r in robert.rules if r["ruleId"] == "cap.position")
        self.assertAlmostEqual(pos["derivation"]["inputs"]["sigmaStockQ3Pct"], 31.22, delta=0.005)

    def test_rounding(self):
        self.assertEqual(round5(12.5), 10.0)  # ties to even, as the reference scripts
        self.assertEqual(round5(17.5), 20.0)
        self.assertEqual(floor5(9.99), 5.0)
        self.assertEqual(floor5(10.0), 10.0)

    def test_low_risk_has_no_feasible_reference_mix(self):  # OPT-05
        low = m.Profile.model_validate({**PROFILES["robert"].to_wire(), "riskLevel": "low"})
        d = derive_thresholds(low, engine(), created_at=NOW)
        self.assertEqual([i["code"] for i in d.issues], ["no_feasible_reference_mix"])
        ids = [r["ruleId"] for r in d.rules]
        self.assertNotIn("cap.growth_assets", ids)
        self.assertNotIn("floor.fixed_income", ids)
        self.assertIn("limit.volatility", ids)

    def test_rederive_after_edit(self):  # PRF-04
        profiles, _ = services()
        profiles.patch_rule(A, "robert", "cap.position", 14, None)
        p, facts = profiles.rederive_rules(A, "robert", True, None)
        self.assertEqual({r.rule_id: r.threshold for r in p.rules}["cap.position"], 10.0)
        self.assertEqual(next(r for r in p.rules if r.rule_id == "cap.position").origin, "derived")
        self.assertIn("ref.sigma_single_stock_q3", {f.metric for f in facts.values()})
        self.assertEqual(p.version, 3)


class SizeSearch(unittest.TestCase):
    """OPT-02..OPT-05 against controls §9."""

    def size(self, pid, ticker, mode="pro_rata", donors=None):
        p = PROFILES[pid]
        return max_compatible_size(engine(pid), p.rules, weights_of(p), ticker, mode, donors, profile_id=pid)

    def test_boundaries(self):
        cases = [("robert", "TSLA", "pro_rata", None, 6.0), ("amira", "TSLA", "pro_rata", None, 11.0),
                 ("mateo", "TSLA", "pro_rata", None, 10.0), ("mateo", "CNQ.TO", "pro_rata", None, 0.0),
                 ("amira", "NVDA", "pro_rata", None, 10.0), ("robert", "TSLA", "new_money", None, 6.0),
                 ("mateo", "TSLA", "new_money", None, 11.0), ("amira", "TSLA", "new_money", None, 12.5),
                 ("amira", "TSLA", "from_holdings", ["QQQ", "SPY"], 12.0)]
        for pid, t, mode, donors, expected in cases:
            r = self.size(pid, t, mode, donors)
            self.assertEqual(r.max_size_pct, expected, (pid, t, mode))
            self.assertEqual(r.stopped_by, "conflict")
            self.assertEqual(r.first_conflict_pct, expected + 0.5)
        mateo = self.size("mateo", "TSLA")
        self.assertIn("evidence.controversy:nee", mateo.remaining_at_max)  # evidence gap stays attached

    def test_first_conflict_is_never_skipped(self):  # OPT-04, synthetic nonmonotone grid
        p = PROFILES["robert"]

        def fake(engine_, rules, weights, moved, evidence=(), profile_id="", variant="scan"):
            size = round(weights.get("TSLA", 0.0) * 100, 6)
            return {"r": "conflict" if abs(size - 2.0) < 1e-6 else "pass"}

        with mock.patch.object(search_mod, "evaluate", side_effect=fake):
            r = max_compatible_size(engine(), p.rules, weights_of(p), "TSLA", "pro_rata")
        self.assertEqual((r.max_size_pct, r.first_conflict_pct), (1.5, 2.0))
        self.assertEqual([s for s, _ in r.grid], [0.0, 0.5, 1.0, 1.5, 2.0])

    def test_baseline_conflict(self):  # OPT-05
        rules = [m.PolicyRule.model_validate({**r.to_wire(), "threshold": 4.0}) if r.rule_id == "cap.position" else r
                 for r in PROFILES["robert"].rules]
        r = max_compatible_size(engine(), rules, weights_of(PROFILES["robert"]), "TSLA", "pro_rata")
        self.assertEqual((r.max_size_pct, r.baseline_conflict), (0.0, True))

    def test_funding_ranking(self):  # OPT-03, OPT-06
        p = PROFILES["amira"]
        ev = compare_funding(engine("amira"), p.rules, weights_of(p), "TSLA", 25, profile_id="amira")
        by = {e.mode: e for e in ev}
        self.assertFalse(by["from_cash"].feasible)  # no real cash; ZST.TO/XBB.TO are not cash
        self.assertEqual(by["new_money"].rank, 1)
        self.assertEqual(by["from_holdings"].rank, 2)
        self.assertEqual(by["pro_rata"].rank, 3)
        self.assertEqual(by["from_holdings"].funding["fromTickers"], ["QQQ", "SPY", "XIU.TO"])
        self.assertEqual(sum(1 for e in ev if e.rank == 1), 1)
        nm = search_mod.counts(by["new_money"].statuses)
        self.assertEqual((nm["conflict"], nm["tension"]), (2, 1))
        named = compare_funding(engine("amira"), p.rules, weights_of(p), "TSLA", 25, profile_id="amira",
                                named_donors=["QQQ", "SPY", "NVDA"])
        fh = search_mod.counts(next(e for e in named if e.mode == "from_holdings").statuses)
        self.assertEqual((fh["conflict"], fh["tension"]), (2, 2))  # controls §9.2 table

    def test_auto_donors_skip_excluded(self):
        p = PROFILES["mateo"]
        donors, enough = search_mod.auto_donors(engine("mateo"), p.rules, weights_of(p), "TSLA", 10)
        self.assertTrue(enough)
        self.assertTrue(all(t not in ("CNQ.TO", "ENB.TO", "XOM") for t in donors))
        self.assertNotIn("XBB.TO", donors)  # only growth assets fund a move automatically


class CheckEndpoint(unittest.TestCase):

    def test_at01(self):
        r = check({"profileId": "robert", "move": TSLA_25}).to_wire()
        self.assertEqual(r["verdict"], "conflict")
        self.assertEqual(r["counts"], {"pass": 1, "tension": 1, "conflict": 6, "nee": 0, "info": 3})
        self.assertEqual(r["maxCompatibleSizePct"], 6.0)
        self.assertFalse(r["baselineConflict"])
        self.assertEqual(r["fundingOptions"], [])
        self.assertEqual((r["asOf"], r["dataVersion"]), ("2026-11-12", "snap-20261113-starter"))
        self.assertLess(r["computeMs"], 1500)
        refs = {c["valueFactId"] for c in r["ruleChecks"]} | {c["thresholdFactId"] for c in r["ruleChecks"]}
        self.assertTrue({x for x in refs if x} <= set(r["facts"]))
        metrics = {f["metric"] for f in r["facts"].values()}
        self.assertTrue({"size.max_compatible", "size.requested", "count.rules"} <= metrics)
        self.assertAlmostEqual(r["portfolioAfter"]["metrics"]["volatilityPct"], 16.96, delta=0.005)
        self.assertEqual(r["portfolioAfter"]["totalValue"], 600000.0)

    def test_at02_compare_profiles(self):
        for size, expected in ((25, ("conflict", "conflict")), (10, ("conflict", "tension"))):
            got = tuple(check({"profileId": pid, "move": {**TSLA_25, "sizePct": size}}).verdict for pid in ("robert", "amira"))
            self.assertEqual(got, expected, size)

    def test_at03_and_baseline(self):
        r = check({"profileId": "mateo", "move": {"ticker": "CNQ.TO", "sizePct": 10, "funding": {"mode": "pro_rata"}}})
        self.assertEqual((r.verdict, r.max_compatible_size_pct), ("conflict", 0.0))
        base = check({"profileId": "mateo", "move": None})
        self.assertEqual(base.verdict, "insufficient")
        self.assertEqual(base.portfolio_before.to_wire(), base.portfolio_after.to_wire())

    def test_auto_funding(self):
        r = check({"profileId": "amira", "move": {**TSLA_25, "funding": {"mode": "auto"}}}).to_wire()
        self.assertEqual(r["fundingUsed"], {"mode": "new_money"})
        self.assertEqual(sum(1 for o in r["fundingOptions"] if o["recommended"]), 1)
        self.assertEqual(r["maxCompatibleSizePct"], 12.5)
        self.assertAlmostEqual(r["portfolioAfter"]["totalValue"], 75000.0)  # 60,000 + 25 points of new money

    def test_new_money_and_held_target(self):  # AT-18
        r = check({"profileId": "amira", "move": {"ticker": "NVDA", "sizePct": 10, "funding": {"mode": "new_money"}}}).to_wire()
        nvda = next(p for p in r["portfolioAfter"]["positions"] if p["ticker"] == "NVDA")
        self.assertAlmostEqual(nvda["weightPct"], 18 / 1.1, delta=1e-9)

    def test_errors(self):
        with self.assertRaises(NotFound):
            check({"profileId": "robert", "move": {**TSLA_25, "ticker": "NOPE", "sizePct": 5}})
        cases = [
            {"profileId": "amira", "move": {"ticker": "NVDA", "sizePct": 93, "funding": {"mode": "pro_rata"}}},
            {"profileId": "robert", "move": {**TSLA_25, "sizePct": 5, "funding": {"mode": "from_cash"}}},
            {"profileId": "robert", "move": {**TSLA_25, "sizePct": 5}, "ruleOverrides": [{"ruleId": "cap.position", "threshold": 99}]},
        ]
        for body in cases:
            with self.assertRaises(ServiceError) as ctx:
                check(body)
            self.assertEqual(ctx.exception.code, "validation_error")

    def test_overrides_and_history(self):
        r = check({"profileId": "robert", "move": TSLA_25, "ruleOverrides": [{"ruleId": "limit.stress_2022", "threshold": 25}]})
        self.assertEqual({c.rule_id: c.status for c in r.rule_checks}["limit.stress_2022"], "pass")
        h = check({"profileId": "robert", "move": None, "asOf": "2022-06-30"})
        statuses = {c.rule_id: (c.status, c.nee_reason) for c in h.rule_checks}
        self.assertEqual(statuses["limit.stress_2022"], ("nee", "not_visible_at_asof"))
        self.assertEqual(h.as_of, "2022-06-30")


class Adapters(unittest.TestCase):

    def test_create_custom_with_derivation_and_proposal(self):
        profiles, checks = services()
        p = profiles.create(A, a.CreateProfileRequest.model_validate(create_request(rules=None, portfolio=None)))
        self.assertAlmostEqual(sum(x.weight_pct for x in p.portfolio.positions), 100.0, delta=1e-9)
        self.assertEqual(p.portfolio.total_value, 100000.0)
        self.assertTrue(all(x.ticker in ("XIU.TO", "SPY", "XBB.TO", "GLD", "CASH.CAD") for x in p.portfolio.positions))
        self.assertIn("limit.volatility", [r.rule_id for r in p.rules])
        r = checks.check(A, a.CheckRequest.model_validate({"profileId": p.profile_id, "move": None}))
        self.assertNotEqual(r.verdict, "conflict")

    def test_decision_controls(self):
        profile = PROFILES["robert"]
        ctx = SimpleNamespace(gate=starter_snapshot().gate("2026-11-12"), ledger=LocalLedger(), profile=profile, as_of="2026-11-12")
        controls = DecisionControls()
        computed = controls.quant(ctx, {"type": "move", "move": TSLA_25}, m.WindowSpec.model_validate({"code": "full"}), [], [])
        outcome = controls.risk(ctx, computed)
        self.assertEqual(outcome.check.counts.to_wire(), {"pass": 1, "tension": 1, "conflict": 6, "nee": 0, "info": 3})
        self.assertEqual([s.scenario_id for s in outcome.scenarios], ["sc_requested", "sc_max_compatible"])
        self.assertEqual(outcome.scenarios[1].moves[0].size_pct, 6.0)
        self.assertEqual(outcome.scenarios[1].verdict, "tension")
        self.assertIn("LIM_SIMULATION_ONLY", outcome.limitations)
        with self.assertRaises(RuntimeError):
            controls.quant(ctx, {"type": "other"}, {"code": "full"}, [], [])  # unknown request type


if __name__ == "__main__":
    unittest.main()
