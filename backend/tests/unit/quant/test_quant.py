"""QNT-01..QNT-08: quant engine against contracts/controls.md and synthetic edge cases."""

from __future__ import annotations

import unittest

from aplomb.contracts.models import Fact
from aplomb.datastore import LocalDataStore
from aplomb.datastore.ingest import ingest_bundle
from aplomb.quant import FundingError, LocalLedger, QuantEngine, apply_move, display

from tests.unit.datastore._support import (
    AAA_MISSING_INDEX,
    encode_tables,
    fixed_clock,
    ingest_synthetic,
    starter_snapshot,
    synthetic_tables,
    temp_root,
    weekdays,
)

NOW = "2026-11-14T23:00:00Z"
P = {
    "robert": {"XBB.TO": .30, "ZST.TO": .15, "AGG": .05, "XIU.TO": .15, "SPY": .10, "RY.TO": .05, "FTS.TO": .05,
               "ENB.TO": .04, "JNJ": .04, "PG": .04, "GLD": .03},
    "amira": {"NVDA": .08, "MSFT": .08, "GOOGL": .06, "SHOP.TO": .05, "AMZN": .05, "QQQ": .12, "SPY": .12, "XIU.TO": .10,
              "BTC-USD": .06, "ETH-USD": .03, "JPM": .04, "CNR.TO": .04, "ATD.TO": .04, "JNJ": .03, "XBB.TO": .05, "GLD": .05},
    "mateo": {"ESGV": .28, "XBB.TO": .25, "AGG": .07, "ZST.TO": .05, "MSFT": .05, "CNR.TO": .05, "RY.TO": .05, "FTS.TO": .04,
              "ATD.TO": .04, "JNJ": .04, "PG": .04, "GLD": .04},
}
_ENGINE = None


def engine(currency: str = "CAD", fresh: bool = False) -> QuantEngine:
    global _ENGINE
    if fresh or currency != "CAD":
        return QuantEngine(starter_snapshot().gate("2026-11-12"), LocalLedger(), currency=currency, subject_id="t", created_at=NOW)
    if _ENGINE is None:
        _ENGINE = QuantEngine(starter_snapshot().gate("2026-11-12"), LocalLedger(), currency="CAD", subject_id="t", created_at=NOW)
    return _ENGINE


_COUNTER = [0]


def risk(weights, e=None):
    _COUNTER[0] += 1  # one variant per portfolio: a FactKey names one number per ledger
    v = (e or engine()).view(weights, f"risk{_COUNTER[0]}", 1.0)
    m = v.metrics()
    return m.volatility_pct, m.max_drawdown_pct, m.stress2022_pct


class AssetControls(unittest.TestCase):
    """QNT-02: contracts/controls.md §4 (one-decimal tolerance ±0.05)."""

    TABLE = {
        "TSLA": (-65.0, -62.6, 59.4, -69.8), "NVDA": (-50.3, -46.9, 51.4, -63.5), "SPY": (-18.2, -12.6, 16.9, -22.2),
        "QQQ": (-32.6, -28.0, 23.1, -31.7), "ESGV": (-24.0, -18.9, 18.2, -26.7), "AGG": (-13.0, -7.1, 7.5, -12.8),
        "TLT": (-31.2, -26.5, 16.1, -39.7), "GLD": (-0.8, 6.0, 18.6, -26.0), "XIU.TO": (-6.3, -6.3, 13.2, -16.4),
        "XBB.TO": (-11.7, -11.7, 6.8, -15.5), "ZST.TO": (1.2, 1.2, 0.6, -0.4), "CNQ.TO": (52.9, 52.9, 30.7, -33.1),
        "RY.TO": (-1.5, -1.5, 15.6, -21.0), "SHOP.TO": (-73.0, -73.0, 65.1, -83.5), "BTC-USD": (-64.3, -61.8, 51.2, -73.7),
        "ETH-USD": (-67.5, -65.3, 68.7, -77.2),
    }

    def test_table(self):
        e = engine()
        for t, (listing, cad, vol, mdd) in self.TABLE.items():
            years = e.calendar_year_return(t, 2022)
            self.assertAlmostEqual(years[0].value, listing, delta=0.05, msg=t)
            self.assertAlmostEqual(years[-1].value, cad, delta=0.05, msg=t)
            am = e.asset_metrics(t)
            self.assertAlmostEqual(am["vol.annualized"].value, vol, delta=0.05, msg=t)
            self.assertAlmostEqual(-am["drawdown.max"].value, mdd, delta=0.05, msg=t)  # API positive, controls negative

    def test_crypto_listing_return_uses_dec_31(self):
        f = engine().ledger.get_fact(engine().calendar_year_return("BTC-USD", 2022)[0].fact_id)
        self.assertEqual(f.period.end, "2022-12-31")
        self.assertEqual(f.currency, "USD")
        tsla = engine().ledger.get_fact(engine().calendar_year_return("TSLA", 2022)[0].fact_id)
        self.assertEqual((tsla.period.start, tsla.period.end), ("2021-12-31", "2022-12-30"))
        self.assertEqual(tsla.method.params["baseDate"], "2021-12-31")

    def test_cnq_limitation(self):
        f = engine().ledger.get_fact(engine().calendar_year_return("CNQ.TO", 2022)[0].fact_id)
        self.assertIn("LIM_CNQ_FACTOR", f.limitations)

    def test_usd_reporting(self):
        e = engine("USD")
        spy = e.calendar_year_return("SPY", 2022)
        self.assertEqual(len(spy), 1)  # listing currency equals reporting currency
        self.assertAlmostEqual(spy[0].value, -18.2, delta=0.05)
        xiu = e.calendar_year_return("XIU.TO", 2022)
        self.assertEqual([e.ledger.get_fact(m.fact_id).currency for m in xiu], ["CAD", "USD"])


class PortfolioControls(unittest.TestCase):
    """QNT-03: §6 reference mixes, §8 baselines, §9 scenarios (two-decimal tolerance ±0.005)."""

    def close(self, a, b, msg=None):
        self.assertAlmostEqual(a, b, delta=0.005, msg=msg)

    def test_reference_mixes(self):
        table = {0: (6.75, -15.48, -11.66), 10: (6.48, -14.99, -11.30), 20: (6.51, -14.67, -10.96), 30: (6.84, -14.36, -10.65),
                 40: (7.44, -14.22, -10.37), 50: (8.25, -14.49, -10.12), 60: (9.21, -14.81, -9.89), 70: (10.28, -15.14, -9.69),
                 80: (11.43, -15.48, -9.52), 90: (12.64, -15.83, -9.38), 100: (13.88, -16.20, -9.27)}
        for eq, (vol, mdd, r22) in table.items():
            w = {k: v for k, v in {"XIU.TO": eq / 200, "SPY": eq / 200, "XBB.TO": 1 - eq / 100}.items() if v > 0}
            v, d, s = risk(w)
            self.close(v, vol, eq)
            self.close(-d, mdd, eq)
            self.close(s, r22, eq)
        for eq, vol in ((55, 8.71), (85, 12.03)):
            self.close(risk({"XIU.TO": eq / 200, "SPY": eq / 200, "XBB.TO": 1 - eq / 100})[0], vol)

    def test_baselines(self):
        expected = {"robert": (6.09, 9.60, -4.70, 50.0, 10.32, 10.60, -0.02),
                    "mateo": (8.72, 14.33, -8.11, 57.4, 12.84, 12.15, 4.00),
                    "amira": (19.52, 32.03, -25.26, 125.4, 10.95, 8.38, 15.27)}
        e = engine()
        for name, (vol, mdd, s22, total, ytd, y1, rate) in expected.items():
            v, d, s = risk(P[name])
            self.close(v, vol, name)
            self.close(d, mdd, name)
            self.close(s, s22, name)
            full = e.window({"code": "full"})
            self.assertAlmostEqual((e.portfolio_levels(P[name], full.i0, full.i1)[-1] - 1) * 100, total, delta=0.05)
            for code, value in (("ytd", ytd), ("1y", y1)):
                wr = e.window({"code": code})
                self.close((e.portfolio_levels(P[name], wr.i0, wr.i1)[-1] - 1) * 100, value, f"{name} {code}")
            self.close(e.view(P[name], f"base:{name}", 1).measure("stress.rate_cycle").value, rate, name)

    def test_baseline_weights(self):
        v = engine().view(P["amira"], "base:amira", 60000)
        self.close(v.measure("weight.position.max_single").value, 8.0)
        self.assertEqual(v.measure("weight.position.max_single").worst, {"type": "asset", "id": "NVDA"})
        self.close(v.measure("weight.sector.max").value, 21.0)
        self.close(v.measure("weight.asset_group", "crypto").value, 9.0)
        g = v.group_weights()
        self.close(g["equity"], 81.0)
        self.close(g["fixed_income"], 5.0)
        r = engine().view(P["robert"], "base:robert", 600000)
        self.assertEqual(r.measure("weight.sector.max").worst, {"type": "sector", "id": "Financials"})
        m = engine().view(P["mateo"], "base:mateo", 250000)
        self.close(m.measure("weight.sector.max").value, 8.0)
        self.assertEqual(m.measure("weight.sector.max").worst["id"], "Consumer Staples")

    def test_scenarios(self):
        def after(name, t, size, mode="pro_rata", donors=None):
            return risk(apply_move(P[name], t, size, mode, donors).weights)
        v, d, s = after("robert", "TSLA", 25)
        self.close(v, 16.96)
        self.close(d, 25.31)
        self.close(-s, 21.88)
        v, d, s = after("amira", "TSLA", 25)
        self.close(v, 26.30)
        self.close(d, 40.56)
        self.close(-s, 35.69)
        v, _, s = after("amira", "TSLA", 25, "from_holdings", ["QQQ", "SPY", "NVDA"])
        self.close(v, 26.27)
        self.close(-s, 36.51)
        v, _, s = after("amira", "TSLA", 25, "new_money")
        self.close(v, 24.58)
        self.close(-s, 33.65)
        v, d, s = after("mateo", "CNQ.TO", 10)
        self.close(v, 8.69)
        self.close(d, 10.22)
        self.close(-s, 2.73)
        v, d, s = after("mateo", "TSLA", 25)
        self.close(v, 18.89)
        self.close(d, 27.60)
        self.close(-s, 24.24)
        rc = engine().view(apply_move(P["robert"], "TSLA", 25, "pro_rata").weights, "rc", 1).measure("stress.rate_cycle")
        self.close(rc.value, 4.07)

    def test_robert_size_sweep_values(self):
        for size, vol, stress in ((2, 6.47, 6.12), (10, 9.36, 11.74)):
            v, _, s = risk(apply_move(P["robert"], "TSLA", size, "pro_rata").weights)
            self.close(v, vol)
            self.close(-s, stress)


class Funding(unittest.TestCase):
    """QNT-04: the four funding equations and their feasibility errors."""

    def test_pro_rata_unheld_and_held(self):
        r = apply_move(P["robert"], "TSLA", 25, "pro_rata").weights
        self.assertAlmostEqual(r["TSLA"], 0.25)
        self.assertAlmostEqual(r["XBB.TO"], 0.30 * 0.75)
        a = apply_move(P["amira"], "NVDA", 10, "pro_rata").weights
        self.assertAlmostEqual(a["NVDA"], 0.18)
        self.assertAlmostEqual(a["MSFT"], 0.08 * (1 - 0.08 - 0.10) / (1 - 0.08))
        self.assertAlmostEqual(sum(a.values()), 1.0)

    def test_new_money_denominator(self):
        res = apply_move(P["amira"], "TSLA", 25, "new_money")
        self.assertAlmostEqual(res.weights["TSLA"], 0.25 / 1.25)
        self.assertAlmostEqual(res.weights["QQQ"], 0.12 / 1.25)
        self.assertAlmostEqual(res.value_factor, 1.25)
        held = apply_move(P["amira"], "NVDA", 10, "new_money").weights
        self.assertAlmostEqual(held["NVDA"], 0.18 / 1.10)

    def test_from_holdings_ordered_depletion(self):
        res = apply_move(P["amira"], "TSLA", 25, "from_holdings", ["QQQ", "SPY", "NVDA"])
        self.assertNotIn("QQQ", res.weights)
        self.assertNotIn("SPY", res.weights)
        self.assertAlmostEqual(res.weights["NVDA"], 0.07)
        self.assertEqual(res.donors, ("QQQ", "SPY", "NVDA"))
        self.assertAlmostEqual(res.weights["MSFT"], 0.08)  # unlisted holdings untouched
        diversifiers = sum(res.weights[t] for t in ("XBB.TO", "GLD"))
        self.assertAlmostEqual(diversifiers, 0.10)

    def test_errors(self):
        cases = [
            (lambda: apply_move(P["amira"], "TSLA", 30, "from_holdings", ["QQQ", "SPY"]), "insufficient_donors"),
            (lambda: apply_move(P["amira"], "TSLA", 5, "from_holdings", ["QQQ", "QQQ"]), "donors_duplicate"),
            (lambda: apply_move(P["amira"], "TSLA", 5, "from_holdings", ["TSLA"]), "donor_is_target"),
            (lambda: apply_move(P["amira"], "TSLA", 5, "from_holdings", ["XOM"]), "donor_not_owned"),
            (lambda: apply_move(P["robert"], "TSLA", 5, "from_cash"), "insufficient_cash"),  # ZST.TO is not cash
            (lambda: apply_move(P["robert"], "TSLA", 0, "pro_rata"), "size_invalid"),
            (lambda: apply_move(P["robert"], "TSLA", -1, "pro_rata"), "size_invalid"),
            (lambda: apply_move(P["robert"], "TSLA", float("nan"), "pro_rata"), "size_invalid"),
            (lambda: apply_move(P["robert"], "TSLA", 101, "pro_rata"), "size_too_large"),
            (lambda: apply_move(P["amira"], "NVDA", 93, "pro_rata"), "size_too_large"),
            (lambda: apply_move(P["robert"], "TSLA", 101, "new_money"), "size_too_large"),
            (lambda: apply_move(P["robert"], "TSLA", 5, "auto"), "mode_invalid"),
            (lambda: apply_move({"SPY": 0.5}, "TSLA", 5, "pro_rata"), "weights_sum"),
        ]
        for fn, code in cases:
            with self.assertRaises(FundingError) as ctx:
                fn()
            self.assertEqual(ctx.exception.code, code)
            self.assertTrue(ctx.exception.reason["fr"])

    def test_from_cash_with_real_cash(self):
        w = {"SPY": 0.6, "CASH.CAD": 0.3, "CASH.USD": 0.1}
        res = apply_move(w, "TSLA", 20, "from_cash")
        self.assertAlmostEqual(res.weights["SPY"], 0.6)
        self.assertAlmostEqual(res.weights["CASH.CAD"], 0.3 * 0.2 / 0.4)
        self.assertAlmostEqual(res.weights["CASH.USD"], 0.1 * 0.2 / 0.4)
        self.assertAlmostEqual(res.weights["TSLA"], 0.2)


class Units(unittest.TestCase):
    """QNT-05: percent units on the wire, positive drawdown, bilingual display."""

    def test_units_and_display(self):
        v = engine().view(P["robert"], "base:robert-units", 600000)
        f = engine().ledger.get_fact(v.measure("drawdown.max").fact_id)
        self.assertGreater(f.value, 0)
        self.assertEqual(f.unit, "pct")
        self.assertEqual(f.display.en, f"{f.value:.2f}%")
        s = engine().ledger.get_fact(v.measure("stress.replay_2022").fact_id)
        self.assertTrue(s.display.en.startswith("−"))
        self.assertEqual(display(-4.7, "pct"), {"en": "−4.70%", "fr": "−4,70 %"})
        self.assertEqual(display(6.0, "pts"), {"en": "6.0 pts", "fr": "6,0 pts"})
        self.assertEqual(display(600000, "cad", "CAD")["en"], "600,000 CAD")

    def test_snapshot_wire(self):
        res = apply_move(P["robert"], "TSLA", 25, "pro_rata")
        snap = engine().view(res.weights, "after:units", 600000 * res.value_factor).snapshot().to_wire()
        self.assertEqual(snap["byAssetGroup"][0], {"key": "equity", "weightPct": snap["byAssetGroup"][0]["weightPct"]})
        self.assertAlmostEqual(snap["byAssetGroup"][0]["weightPct"], 60.25)
        self.assertAlmostEqual(sum(p["marketValue"] for p in snap["positions"]), 600000)
        self.assertEqual(snap["bySector"][0]["key"], "Consumer Discretionary")
        self.assertAlmostEqual(snap["metrics"]["volatilityPct"], 16.96, delta=0.005)
        self.assertEqual(set(snap["metrics"]["factIds"]), {"volatility", "maxDrawdown", "stress2022"})


class Facts(unittest.TestCase):

    def test_every_fact_validates_and_inputs_resolve(self):
        e = engine(fresh=True)
        v = e.view(apply_move(P["amira"], "TSLA", 25, "pro_rata").weights, "after", 60000)
        v.snapshot()
        for m in ("weight.position.max_single", "weight.sector.max", "weight.diversifiers", "stress.rate_cycle"):
            v.measure(m)
        e.asset_metrics("TSLA")
        e.correlation(["TSLA", "SPY", "BTC-USD"])
        facts = e.ledger.facts()
        self.assertGreater(len(facts), 15)
        keys = set()
        for fid, f in facts.items():
            Fact.model_validate(f.to_wire())
            self.assertNotIn(f.key, keys)
            keys.add(f.key)
            for ref in f.inputs:
                self.assertIn(ref, facts)
        vol = facts[v.metrics().fact_ids["vol.annualized"]]
        self.assertEqual(vol.n_obs, 1228)
        self.assertEqual(vol.period.start, "2021-11-12")
        self.assertIn("LIM_FX_FFILL", vol.limitations)
        self.assertEqual({s.dataset_id for s in vol.sources}, {"prices_daily", "fx_usdcad_daily"})
        self.assertEqual(vol.available_at, "2026-11-12T23:59:59.999Z")  # crypto day ends after the exchange close

    def test_same_key_same_value_is_reused(self):
        e = engine(fresh=True)
        a = e.view(P["robert"], "before", 1).measure("vol.annualized").fact_id
        b = e.view(dict(P["robert"]), "before", 1).measure("vol.annualized").fact_id
        self.assertEqual(a, b)

    def test_correlation_bounds(self):
        out = engine().correlation(["SPY", "XIU.TO"])
        self.assertTrue(-1 <= out[("SPY", "XIU.TO")].value <= 1)


class SyntheticEdges(unittest.TestCase):
    """QNT-06 (missing history, cash, foreign cash, no prior FX), QNT-07 (future perturbation)."""

    @classmethod
    def setUpClass(cls):
        root = temp_root()
        ingest_synthetic(root)
        cls.snap = LocalDataStore(root).open("snap-20240101-syn")

    def eng(self, as_of="2025-01-31", currency="CAD", snap=None):
        return QuantEngine((snap or self.snap).gate(as_of), LocalLedger(), currency=currency, subject_id="s", created_at=NOW)

    def test_missing_observation_makes_risk_unavailable(self):
        v = self.eng().view({"AAA.TO": 0.5, "SPY": 0.5}, "x", 1)
        m = v.measure("vol.annualized")
        self.assertIsNone(m.value)
        self.assertEqual(m.nee_reason, "short_history")
        self.assertIsNotNone(v.measure("weight.position.max_single").value)  # weights unaffected

    def test_short_history_a21(self):
        e = self.eng(as_of="2024-03-29")  # < 252 master observations visible
        m = e.view({"SPY": 1.0}, "x", 1).measure("vol.annualized")
        self.assertEqual(m.nee_reason, "short_history")

    def test_cash(self):
        e = self.eng()
        v = e.view({"CASH.CAD": 1.0}, "x", 1)
        self.assertEqual(v.measure("vol.annualized").value, 0.0)
        self.assertEqual(v.measure("drawdown.max").value, 0.0)
        self.assertIn("LIM_CASH_NO_INTEREST", e.ledger.get_fact(v.measure("vol.annualized").fact_id).limitations)
        no_prior = e.view({"CASH.USD": 1.0}, "y0", 1).measure("vol.annualized")
        self.assertEqual(no_prior.nee_reason, "short_history")  # no USD/CAD rate before the first day
        later = {"code": "custom", "start": weekdays()[1].isoformat(), "end": "2025-01-31"}
        usd_cash = e.view({"CASH.USD": 1.0}, "y", 1, window=later).measure("vol.annualized")
        self.assertGreater(usd_cash.value, 0.0)  # foreign cash carries the FX return
        self.assertEqual(self.eng(currency="USD").view({"CASH.USD": 1.0}, "z", 1).measure("vol.annualized").value, 0.0)
        corr = e.correlation(["CASH.CAD", "SPY"])
        self.assertIsNone(corr[("CASH.CAD", "SPY")].value)  # zero variance: null, never NaN

    def test_no_prior_fx_rate(self):
        series = self.eng().market.series("SPY")
        self.assertIsNone(series.levels[0])        # first master day precedes the first USD/CAD rate
        self.assertIsNotNone(series.levels[1])
        self.assertEqual(self.eng(currency="USD").market.series("SPY").levels[0], 400.0)

    def test_future_perturbation_does_not_change_history(self):
        cutoff = weekdays()[270].isoformat()
        tables = synthetic_tables()
        for row in tables["prices_daily.csv"]:
            if row[0] > cutoff:
                row[6] = str(float(row[6]) * 3.7)
        for row in tables["fx_usdcad_daily.csv"]:
            if row[0] > cutoff:
                row[1] = "2.0"
                row[2] = "0.5"
        root = temp_root()
        ingest_bundle(encode_tables(tables), root, "snap-20240102-perturbed", clock=fixed_clock)
        other = LocalDataStore(root).open("snap-20240102-perturbed")
        w = {"SPY": 0.4, "XIU.TO": 0.4, "BTC-USD": 0.2}
        start = weekdays()[1].isoformat()  # first day with a prior USD/CAD rate
        win = {"code": "custom", "start": start, "end": cutoff}
        a = self.eng(cutoff, snap=self.snap).view(w, "x", 1, window=win)
        b = self.eng(cutoff, snap=other).view(w, "x", 1, window=win)
        self.assertIsNotNone(a.measure("vol.annualized").value)
        self.assertEqual(a.measure("vol.annualized").value, b.measure("vol.annualized").value)
        self.assertEqual(a.measure("drawdown.max").value, b.measure("drawdown.max").value)
        later_win = {"code": "custom", "start": start, "end": weekdays()[-1].isoformat()}
        later = self.eng(weekdays()[-1].isoformat(), snap=other).view(w, "x", 1, window=later_win)
        self.assertNotEqual(a.measure("vol.annualized").value, later.measure("vol.annualized").value)

    def test_missing_day_not_filled(self):
        levels = self.eng().market.series("AAA.TO").levels
        day = weekdays()[AAA_MISSING_INDEX].isoformat()
        self.assertIsNone(levels[self.eng().market.index_of(day)])


class Stress2022(unittest.TestCase):
    """QNT-08: signed stress return; unavailable before the end of 2022."""

    def test_signed_and_gated(self):
        e = engine()
        s = e.view(P["robert"], "base:robert-stress", 1).measure("stress.replay_2022")
        self.assertLess(s.value, 0)
        f = e.ledger.get_fact(s.fact_id)
        self.assertEqual(f.kind, "scenario")
        self.assertEqual((f.period.start, f.period.end), ("2021-12-31", "2022-12-30"))
        early = QuantEngine(starter_snapshot().gate("2022-06-30", "historical"), LocalLedger(), currency="CAD",
                            subject_id="h", created_at=NOW)
        m = early.view(P["robert"], "x", 1).measure("stress.replay_2022")
        self.assertIsNone(m.value)
        self.assertEqual(m.nee_reason, "not_visible_at_asof")
        rate = early.view(P["robert"], "x", 1).measure("stress.rate_cycle")
        self.assertEqual(rate.nee_reason, "not_visible_at_asof")

    def test_windows(self):
        e = engine()
        self.assertEqual(e.window({"code": "5y"}).period, {"start": "2021-11-12", "end": "2026-11-12"})
        self.assertEqual(e.window({"code": "3y"}).period["start"], "2023-11-10")
        c = e.window({"code": "custom", "start": "2022-03-02", "end": "2023-07-13"})
        self.assertEqual(c.period, {"start": "2022-03-02", "end": "2023-07-13"})
        early = QuantEngine(starter_snapshot().gate("2023-01-31", "historical"), LocalLedger(), currency="CAD",
                            subject_id="h", created_at=NOW)
        m = early.view(P["robert"], "x", 1, window={"code": "3y"}).measure("vol.annualized")
        self.assertEqual(m.nee_reason, "short_history")  # a 3-year window is never relabelled


if __name__ == "__main__":
    unittest.main()
