"""Custom date-range windows on the deterministic profile reads (overview, performance, frontier)."""

from __future__ import annotations

import unittest

from aplomb.api.errors import ServiceError

from tests.unit.profiles.test_profiles import A, service

START, END = "2023-01-01", "2026-01-01"  # 2023-01-01 is a Sunday: the base close is Friday 2022-12-30
CUSTOM = {"window": "custom", "start": START, "end": END}
SPEC = {"code": "custom", "start": START, "end": END}
TOKEN = f"custom:{START}..{END}"


class CustomWindow(unittest.TestCase):

    def test_overview_echoes_custom_window_and_measures_on_it(self):
        svc = service()
        full = svc.overview(A, "robert", {}).to_wire()
        o = svc.overview(A, "robert", CUSTOM).to_wire()
        self.assertEqual(o["window"], SPEC)
        self.assertNotAlmostEqual(o["risk"]["volatilityPct"], full["risk"]["volatilityPct"], delta=0.01)
        self.assertNotAlmostEqual(o["risk"]["maxDrawdownPct"], full["risk"]["maxDrawdownPct"], delta=0.01)
        for name in ("volatility", "maxDrawdown", "worst12m"):
            fact = o["facts"][o["risk"]["factIds"][name]]
            self.assertTrue(fact["key"].endswith("|" + TOKEN), fact["key"])
            self.assertEqual(fact["window"], SPEC)
            self.assertEqual(fact["period"], {"start": "2022-12-30", "end": "2025-12-31"})
        self.assertTrue(o["correlation"])
        corr = [f for f in o["facts"].values() if f["metric"] == "corr.pair"]
        self.assertTrue(corr and all(f["key"].endswith("|" + TOKEN) for f in corr))
        # Fixed horizons and the named 2022 stress replay do not follow the request window.
        self.assertEqual({k: v for k, v in o["returns"].items() if k != "factIds"},
                         {k: v for k, v in full["returns"].items() if k != "factIds"})
        self.assertEqual(o["risk"]["stress2022Pct"], full["risk"]["stress2022Pct"])
        self.assertEqual(o["verdict"], "compatible")
        # The same spec passed as a window dict is equivalent.
        self.assertEqual(svc.overview(A, "robert", {"window": SPEC}).to_wire()["risk"], o["risk"])

    def test_selected_return_matches_custom_chart(self):
        svc = service()
        overview = svc.overview(A, "robert", CUSTOM).to_wire()
        series = svc.performance(A, "robert", CUSTOM).to_wire()["series"]
        fact = overview["facts"][overview["returns"]["factIds"]["selectedPct"]]
        self.assertAlmostEqual(fact["value"], (series[-1]["value"] / series[0]["value"] - 1) * 100)
        self.assertEqual(fact["window"], SPEC)
        self.assertEqual(fact["period"], {"start": series[0]["date"], "end": series[-1]["date"]})

    def test_range_seeded_from_a_preset_period_keeps_its_figures(self):
        # The web seeds a new custom Range with the period the preset's selectedPct fact reports
        # (web/src/lib/ui/scope.ts::defaultRange), so switching to Range alone must change no figure.
        svc = service()
        for code in ("full", "1y", "3y"):
            with self.subTest(code):
                preset = svc.overview(A, "robert", {"window": code}).to_wire()
                period = preset["facts"][preset["returns"]["factIds"]["selectedPct"]]["period"]
                custom = svc.overview(A, "robert", {"window": "custom", "start": period["start"], "end": period["end"]}).to_wire()
                fact = custom["facts"][custom["returns"]["factIds"]["selectedPct"]]
                self.assertEqual(fact["period"], period)
                self.assertAlmostEqual(fact["value"], preset["facts"][preset["returns"]["factIds"]["selectedPct"]]["value"])
                self.assertAlmostEqual(custom["risk"]["volatilityPct"], preset["risk"]["volatilityPct"])
                self.assertAlmostEqual(custom["risk"]["maxDrawdownPct"], preset["risk"]["maxDrawdownPct"])

    def test_value_chart_starts_at_the_fictional_capital(self):
        # Home labels snapshot.totalValue "Fictional capital ... The history chart starts from this amount"
        # (contracts/api.md: the series starts at the portfolio's total value on the first date).
        svc = service()
        for query in ({}, {"window": "1y"}, CUSTOM):
            with self.subTest(query.get("window", "full")):
                capital = svc.overview(A, "robert", query).to_wire()["snapshot"]["totalValue"]
                self.assertEqual(svc.performance(A, "robert", query).to_wire()["series"][0]["value"], capital)

    def test_performance_series_inside_custom_range(self):
        p = service().performance(A, "robert", CUSTOM).to_wire()
        self.assertEqual(p["window"], SPEC)
        dates = [x["date"] for x in p["series"]]
        self.assertEqual(p["series"][0], {"date": "2022-12-30", "value": 600000.0})  # last master day on/before start
        self.assertTrue(all(START <= d <= END for d in dates[1:]), (dates[1], dates[-1]))
        self.assertEqual(dates[-1], "2025-12-31")
        self.assertIsNone(p["benchmark"])
        # A start on a trading day is the first date itself.
        q = service().performance(A, "robert", {"window": "custom", "start": "2023-01-03", "end": "2025-12-31"}).to_wire()
        self.assertEqual((q["series"][0]["date"], q["series"][-1]["date"]), ("2023-01-03", "2025-12-31"))

    def test_performance_benchmark_on_custom_range(self):
        p = service().performance(A, "robert", {**CUSTOM, "benchmark": "SPY"}).to_wire()
        self.assertEqual(p["window"], SPEC)
        self.assertEqual(p["benchmark"]["ticker"], "SPY")
        self.assertEqual([x["date"] for x in p["benchmark"]["series"]], [x["date"] for x in p["series"]])
        self.assertEqual(p["benchmark"]["series"][0]["value"], 600000.0)
        ytd = service().performance(A, "robert", {"window": "ytd", "benchmark": "SPY"}).to_wire()
        self.assertNotEqual(p["benchmark"]["series"][-1]["value"], ytd["benchmark"]["series"][-1]["value"])

    def test_malformed_custom_window_is_a_validation_error(self):
        svc = service()
        cases = {
            "start after end": {"window": "custom", "start": END, "end": START},
            "missing end": {"window": "custom", "start": START},
            "missing start": {"window": "custom", "end": END},
            "not ISO": {"window": "custom", "start": "2023/01/01", "end": END},
            "compact ISO": {"window": "custom", "start": "20230101", "end": END},
            "impossible day": {"window": "custom", "start": "2023-02-30", "end": END},
        }
        for label, query in cases.items():
            for method in (svc.overview, svc.performance):
                with self.subTest(label, method=method.__name__), self.assertRaises(ServiceError) as ctx:
                    method(A, "robert", query)
                self.assertEqual((ctx.exception.code, ctx.exception.status), ("validation_error", 422))
                self.assertEqual(ctx.exception.details["fields"], ["start", "end"])
        with self.assertRaises(ServiceError) as ctx:
            svc.overview(A, "robert", CUSTOM | {"start": END, "end": START})
        self.assertIn("must be on or before", ctx.exception.message)

    def test_custom_window_outside_history_is_insufficient_data(self):
        svc = service()
        for query in ({"window": "custom", "start": "2020-01-01", "end": END},   # before the first visible day
                      {"window": "custom", "start": "2027-01-01", "end": "2027-06-01"}):  # after as-of
            for method in (svc.overview, svc.performance):
                with self.subTest(query["start"], method=method.__name__), self.assertRaises(ServiceError) as ctx:
                    method(A, "robert", query)
                self.assertEqual((ctx.exception.code, ctx.exception.status), ("insufficient_data", 422))
                self.assertEqual(ctx.exception.details["fields"], ["start", "end"])
                self.assertEqual(ctx.exception.details["historyStart"], "2021-11-12")
                self.assertIn("visible history 2021-11-12..2026-11-12", ctx.exception.message)

    def test_frontier_on_custom_window(self):
        f = service().frontier(A, "robert", {**CUSTOM, "lang": "en"}).to_wire()
        self.assertEqual(f["window"], SPEC)
        self.assertTrue(all(x["key"].endswith("|" + TOKEN) for x in f["facts"].values()))
        full = service().frontier(A, "robert", {"lang": "en"}).to_wire()
        self.assertEqual(full["window"], {"code": "full"})
        self.assertNotAlmostEqual(f["portfolio"]["volPct"], full["portfolio"]["volPct"], delta=0.01)


if __name__ == "__main__":
    unittest.main()
