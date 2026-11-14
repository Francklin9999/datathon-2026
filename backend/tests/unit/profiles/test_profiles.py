"""PRF-01..PRF-07 plus overview/performance (profiles SPEC §5, api.md §3)."""

from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone

from aplomb.api.errors import Conflict, NotFound, ServiceError
from aplomb.contracts import api as a
from aplomb.profiles.defaults import DEFAULTS_PATH, render_json
from aplomb.profiles.service import ProfileServiceImpl

from tests.unit.datastore._support import starter_snapshot

try:  # the real T03 repository (its file store needs POSIX fcntl; MemoryStore does not)
    from aplomb.api.repositories import ProfileRepository
    from aplomb.api.storage import MemoryStore

    def make_repo():
        return ProfileRepository(MemoryStore())
except ModuleNotFoundError:  # Windows without fcntl: same revision semantics, in memory
    class _Repo:
        def __init__(self):
            self.items = {}

        def get(self, sid, pid, overlay=False):
            return copy.deepcopy(self.items.get((sid, pid, overlay)))

        def list(self, sid):
            return [copy.deepcopy(v) for (s, _, _), v in self.items.items() if s == sid]

        def save(self, sid, pid, value, expected_version, overlay=False):
            old = self.items.get((sid, pid, overlay))
            if (old["revision"] if old else None) != expected_version:
                raise Conflict()
            saved = {"revision": (expected_version or 0) + 1, "value": copy.deepcopy(value), "profileId": pid, "overlay": overlay}
            self.items[(sid, pid, overlay)] = saved
            return copy.deepcopy(saved)

        def delete(self, sid, pid, expected_version):
            old = self.items.get((sid, pid, False))
            if (old["revision"] if old else None) != expected_version:
                raise Conflict()
            self.items.pop((sid, pid, False))

    def make_repo():
        return _Repo()


CLOCK = lambda: datetime(2026, 11, 14, 23, 30, tzinfo=timezone.utc)  # noqa: E731
A, B = "s_aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "s_bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def service(**kw):
    return ProfileServiceImpl(make_repo(), starter_snapshot, clock=CLOCK, **kw)


def create_request(**over):
    body = {"name": "Test", "age": None, "riskLevel": "moderate", "horizonYears": {"min": 5, "max": 10}, "objective": "balanced",
            "experience": "beginner", "reportingCurrency": "CAD",
            "preferences": {"themesOfInterest": [], "excludedSectors": [], "excludedAssetClasses": [], "esgFocus": False,
                            "avoidControversies": False, "avoidSpeculative": False, "cryptoInterest": "none",
                            "wantsDiversification": True, "notes": ""},
            "portfolio": {"totalValue": 1000, "positions": [{"ticker": "SPY", "weightPct": 60}, {"ticker": "XBB.TO", "weightPct": 40}]},
            "rules": [r.to_wire() for r in service().get(A, "robert").rules], "fromDraftRunId": None}
    body.update(over)
    return body


class Defaults(unittest.TestCase):

    def test_defaults_load_and_order(self):  # PRF-01
        items = service().list(A)
        self.assertEqual([p.profile_id for p in items], ["robert", "amira", "mateo"])
        for p in items:
            self.assertAlmostEqual(sum(x.weight_pct for x in p.portfolio.positions), 100.0, delta=0.01)
            self.assertTrue(p.portfolio.is_fictional)
            self.assertEqual(p.version, 1)
            self.assertTrue(all(r.label.fr for r in p.rules))
        self.assertEqual({p.profile_id: p.portfolio.total_value for p in items}, {"robert": 600000, "amira": 60000, "mateo": 250000})
        self.assertEqual(items[0].horizon_years.to_wire(), {"min": 3.0, "max": 5.0})
        self.assertIsNone(items[1].horizon_years.max)

    def test_defaults_json_has_no_drift(self):
        self.assertEqual(json.loads(DEFAULTS_PATH.read_text(encoding="utf-8")), json.loads(render_json()))

    def test_thresholds_match_controls(self):
        expected = {"robert": {"cap.position": 10, "cap.sector": 20, "cap.growth_assets": 55, "floor.fixed_income": 35,
                               "limit.volatility": 9, "limit.stress_2022": 9, "limit.drawdown": 18},
                    "mateo": {"cap.position": 15, "cap.sector": 30, "cap.growth_assets": 80, "floor.fixed_income": 10,
                              "limit.volatility": 12, "limit.stress_2022": 15, "limit.drawdown": 24, "cap.asset_class.crypto": 5},
                    "amira": {"cap.position": 25, "cap.sector": 40, "cap.asset_class.crypto": 15, "floor.diversifiers": 8,
                              "limit.volatility": 22, "limit.stress_2022": 33, "limit.drawdown": 44}}
        for pid, rules in expected.items():
            got = {r.rule_id: r.threshold for r in service().get(A, pid).rules}
            for rid, value in rules.items():
                self.assertEqual(got[rid], value, (pid, rid))


class Edits(unittest.TestCase):

    def test_overlay_is_session_scoped(self):  # PRF-03
        svc = service()
        p = svc.patch_rule(A, "robert", "cap.position", 12, None)
        rule = next(r for r in p.rules if r.rule_id == "cap.position")
        self.assertEqual((rule.threshold, rule.origin, rule.derivation), (12.0, "user", None))
        self.assertEqual(p.version, 2)
        self.assertEqual(next(r for r in svc.get(B, "robert").rules if r.rule_id == "cap.position").threshold, 10.0)
        self.assertEqual(svc.get(A, "robert").version, 2)
        overlay = svc.repo.get(A, "robert", overlay=True)["value"]
        self.assertEqual(list(overlay["rules"]), ["cap.position"])  # only the changed rule is stored
        self.assertIsNone(overlay["portfolio"])

    def test_patch_validation(self):
        svc = service()
        with self.assertRaises(ServiceError) as ctx:
            svc.patch_rule(A, "robert", "cap.position", 60, None)
        self.assertEqual(ctx.exception.code, "validation_error")
        with self.assertRaises(Conflict):
            svc.patch_rule(A, "robert", "sim.only", None, False)
        with self.assertRaises(NotFound):
            svc.patch_rule(A, "robert", "cap.theme.ai", 10, None)
        p = svc.patch_rule(A, "robert", "exclude.asset_class.crypto", None, False)
        self.assertFalse(next(r for r in p.rules if r.rule_id == "exclude.asset_class.crypto").enabled)

    def test_create_validation(self):  # PRF-05
        svc = service()
        bad = create_request(portfolio={"totalValue": 1000, "positions": [{"ticker": "SPY", "weightPct": 60}, {"ticker": "XBB.TO", "weightPct": 39}]})
        with self.assertRaises(ServiceError) as ctx:
            svc.create(A, a.CreateProfileRequest.model_validate(bad))
        self.assertIn("99.00", ctx.exception.message)
        with self.assertRaises(NotFound):
            svc.create(A, a.CreateProfileRequest.model_validate(create_request(
                portfolio={"totalValue": 1000, "positions": [{"ticker": "NOPE", "weightPct": 100}]})))
        with self.assertRaises(ServiceError):
            svc.create(A, a.CreateProfileRequest.model_validate(create_request(rules=None)))  # no deriver injected yet

    def test_custom_lifecycle(self):  # PRF-06, PRF-07
        svc = service()
        p = svc.create(A, a.CreateProfileRequest.model_validate(create_request()))
        self.assertRegex(p.profile_id, r"^p_[0-9a-hjkmnp-tv-z]{10}$")
        self.assertEqual((p.version, p.origin, p.initial), (1, "user", "T"))
        self.assertEqual([x.profile_id for x in svc.list(A)][-1], p.profile_id)
        self.assertNotIn(p.profile_id, [x.profile_id for x in svc.list(B)])
        upd = a.UpdateProfileRequest.model_validate({**create_request(name="Renamed"), "version": 1})
        p2 = svc.replace(A, p.profile_id, upd, 1)
        self.assertEqual((p2.name, p2.version), ("Renamed", 2))
        with self.assertRaises(Conflict):
            svc.replace(A, p.profile_id, upd, 1)  # stale version
        with self.assertRaises(Conflict):
            svc.replace(A, "robert", upd, 1)
        with self.assertRaises(Conflict):
            svc.delete(A, "mateo")
        svc.delete(A, p.profile_id)
        with self.assertRaises(NotFound):
            svc.get(A, p.profile_id)

    def test_set_portfolio_on_default(self):
        svc = service()
        req = a.UpdatePortfolioRequest.model_validate({"totalValue": 500000, "positions": [{"ticker": "SPY", "weightPct": 100}], "version": 1})
        p = svc.set_portfolio(A, "robert", req, 1)
        self.assertEqual((p.portfolio.total_value, p.version), (500000, 2))
        self.assertEqual(svc.get(B, "robert").portfolio.total_value, 600000)
        with self.assertRaises(Conflict):
            svc.set_portfolio(A, "robert", req, 1)


class Analytics(unittest.TestCase):

    def test_overview_robert(self):
        o = service().overview(A, "robert", {}).to_wire()
        self.assertEqual((o["asOf"], o["dataVersion"], o["window"]), ("2026-11-12", "snap-20261113-starter", {"code": "full"}))
        self.assertAlmostEqual(o["risk"]["volatilityPct"], 6.09, delta=0.005)
        self.assertAlmostEqual(o["risk"]["maxDrawdownPct"], 9.60, delta=0.005)
        self.assertAlmostEqual(o["risk"]["stress2022Pct"], -4.70, delta=0.005)
        self.assertEqual(o["risk"]["riskCategory"], "low_moderate")  # lowest budget at or above 6.09%
        self.assertAlmostEqual(o["returns"]["ytdPct"], 10.32, delta=0.005)
        self.assertAlmostEqual(o["returns"]["y1Pct"], 10.60, delta=0.005)
        self.assertIsNotNone(o["returns"]["y5Pct"])
        self.assertEqual(o["verdict"], "compatible")
        self.assertEqual(o["counts"], {"pass": 8, "tension": 0, "conflict": 0, "nee": 0, "info": 3})
        self.assertEqual(len(o["concentration"]["topPositions"]), 5)
        self.assertEqual(o["concentration"]["topPositions"][0]["ticker"], "XBB.TO")
        self.assertIsNotNone(o["correlation"])
        for c in o["ruleChecks"]:
            for ref in (c["valueFactId"], c["thresholdFactId"]):
                if ref:
                    self.assertIn(ref, o["facts"])
        self.assertIn("LIM_SIMULATION_ONLY", o["limitations"])
        self.assertIn("LIM_CONSTANT_WEIGHTS", o["limitations"])

    def test_overview_windows_and_errors(self):
        o = service().overview(A, "amira", {"window": "1y"}).to_wire()
        self.assertEqual(o["window"], {"code": "1y"})
        with self.assertRaises(ServiceError):
            service().overview(A, "amira", {"window": "10y"})
        mateo = service().overview(A, "mateo", {}).to_wire()
        self.assertEqual(mateo["verdict"], "insufficient")

    def test_performance(self):
        p = service().performance(A, "robert", {"window": "ytd", "benchmark": "SPY"}).to_wire()
        self.assertEqual(p["series"][0], {"date": "2025-12-31", "value": 600000.0})
        self.assertAlmostEqual(p["series"][-1]["value"] / 600000 - 1, 0.1032, delta=0.00005)
        self.assertEqual(p["benchmark"]["series"][0]["value"], 600000.0)
        self.assertEqual(len(p["series"]), len(p["benchmark"]["series"]))
        self.assertIn("LIM_CONSTANT_WEIGHTS", p["limitations"])
        with self.assertRaises(NotFound):
            service().performance(A, "robert", {"benchmark": "NOPE"})


if __name__ == "__main__":
    unittest.main()
