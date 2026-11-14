"""DS-03, DS-04, DS-07, DS-08, DAT-04 and gate semantics."""

from __future__ import annotations

import unittest
from datetime import date

from aplomb.datastore import (
    DatasetMissing,
    DatasetNotFound,
    InvalidGateRequest,
    LocalDataStore,
    UnknownSeries,
    UnknownTicker,
)

from ._support import (
    AAA_MISSING_INDEX,
    STARTER_VERSION,
    US_HOLIDAY_INDEX,
    ingest_synthetic,
    read_starter_csv,
    starter_snapshot,
    temp_root,
    weekdays,
)


class StarterControls(unittest.TestCase):
    """Values read through the gate equal contracts/controls.md (AT-06 inputs)."""

    @classmethod
    def setUpClass(cls):
        cls.gate = starter_snapshot().gate("2026-11-12")

    def test_tsla_adjusted_closes(self):
        rows = {r["date"]: r["adj_close"] for r in self.gate.prices(["TSLA"], "2021-12-31", "2022-12-30").rows}
        self.assertAlmostEqual(rows["2021-12-31"], 352.26, places=2)
        self.assertAlmostEqual(rows["2022-12-30"], 123.18, places=2)

    def test_fx_controls(self):
        fx = self.gate.fx_series()
        for d, v in (("2021-12-31", 1.2678), ("2022-12-30", 1.3544), ("2026-11-12", 1.4255)):
            self.assertEqual(fx.rate_on(d), v)

    def test_cnq_rows_around_factor(self):
        rows = {r["date"]: r for r in self.gate.prices(["CNQ.TO"], "2022-08-19", "2022-08-22").rows}
        self.assertAlmostEqual(rows["2022-08-19"]["close"], 35.450539, places=6)
        self.assertAlmostEqual(rows["2022-08-19"]["adj_close"], 28.506203, places=6)
        self.assertAlmostEqual(rows["2022-08-22"]["close"], 35.665001, places=6)
        self.assertAlmostEqual(rows["2022-08-22"]["adj_close"], 29.298502, places=6)

    def test_values_equal_raw_file(self):
        raw = [r for r in read_starter_csv("prices_daily.csv") if r["ticker"] == "SHOP.TO"]
        got = self.gate.prices(["SHOP.TO"], None, "2026-11-12").rows
        self.assertEqual(len(got), len(raw))
        for a, b in zip(sorted(raw, key=lambda r: r["date"]), got):
            self.assertEqual(a["date"], b["date"])
            for k in ("open", "high", "low", "close", "adj_close", "volume"):
                self.assertEqual(float(a[k]), b[k])

    def test_cnq_limitation_only_when_window_spans_factor(self):
        spans = self.gate.prices(["CNQ.TO"], "2022-08-01", "2022-09-01")
        starts_on = self.gate.prices(["CNQ.TO"], "2022-08-22", "2022-09-01")
        other = self.gate.prices(["RY.TO"], "2022-08-01", "2022-09-01")
        self.assertIn("LIM_CNQ_FACTOR", spans.limitations)
        self.assertNotIn("LIM_CNQ_FACTOR", starts_on.limitations)
        self.assertNotIn("LIM_CNQ_FACTOR", other.limitations)
        self.assertIn("LIM_CNQ_FACTOR", self.gate.price_frame(["CNQ.TO"]).limitations)


class FutureRowsWithheld(unittest.TestCase):
    """DS-03: rows after the cutoff are withheld and counted, for prices, FX and macro."""

    @classmethod
    def setUpClass(cls):
        cls.snap = starter_snapshot()
        cls.raw_prices = read_starter_csv("prices_daily.csv")
        cls.raw_fx = read_starter_csv("fx_usdcad_daily.csv")
        cls.raw_macro = read_starter_csv("macro_rates.csv")

    def test_prices_counts_match_raw_partition(self):
        for mode in ("current", "historical"):
            g = self.snap.gate("2022-06-30", mode)
            s = g.prices(["TSLA", "XIU.TO"], "2022-01-01", "2022-12-31")
            cand = [r for r in self.raw_prices if r["ticker"] in ("TSLA", "XIU.TO") and "2022-01-01" <= r["date"] <= "2022-12-31"]
            vis = [r for r in cand if r["date"] <= "2022-06-30"]
            self.assertEqual(s.rows_read, len(vis))
            self.assertEqual(s.rows_withheld, len(cand) - len(vis))
            self.assertEqual(s.last_visible_date, "2022-06-30")
            self.assertTrue(all(r["date"] <= "2022-06-30" for r in s.rows))

    def test_fx_withheld(self):
        g = self.snap.gate("2022-06-30", "historical")
        s = g.fx("2022-06-01", "2022-12-31")
        cand = [r for r in self.raw_fx if "2022-06-01" <= r["date"] <= "2022-12-31"]
        vis_in = [r for r in cand if r["date"] <= "2022-06-30"]
        self.assertEqual(s.rows_withheld, len(cand) - len(vis_in))
        self.assertEqual(s.rows_read, len(vis_in) + 1)  # plus the last rate before the window
        self.assertEqual(s.rows[0]["date"], max(r["date"] for r in self.raw_fx if r["date"] < "2022-06-01"))
        self.assertEqual(s.limitations, ("LIM_FX_FFILL",))

    def test_daily_macro_next_business_day(self):
        # A-22: a daily value dated Friday 2022-06-24 is usable from Monday 2022-06-27.
        fri = self.snap.gate("2022-06-26", "historical").macro("V39079", "2022-06-20", "2022-06-30")
        self.assertEqual(fri.last_visible_date, "2022-06-23")
        mon = self.snap.gate("2022-06-27", "historical").macro("V39079", "2022-06-20", "2022-06-30")
        self.assertEqual(mon.last_visible_date, "2022-06-24")  # Monday's own value waits until Tuesday
        self.assertEqual(mon.rows[-1]["available_at"], "2022-06-27T00:00:00.000Z")
        cand = [r for r in self.raw_macro if r["series_id"] == "V39079" and "2022-06-20" <= r["date"] <= "2022-06-30"]
        self.assertEqual(mon.rows_read + mon.rows_withheld, len(cand))

    def test_monthly_macro_45_day_lag_in_current_mode(self):
        # June 2022 Canada CPI: reference month ends 2022-06-30, usable 45 days later (2022-08-14).
        before = self.snap.gate("2022-08-13").macro("STATIC_TOTALCPICHANGE", None, None)
        on = self.snap.gate("2022-08-14").macro("STATIC_TOTALCPICHANGE", None, None)
        self.assertEqual(before.last_visible_date, "2022-05-01")
        self.assertEqual(on.last_visible_date, "2022-06-01")
        self.assertIn("LIM_MACRO_LAG_ASSUMED", on.limitations)
        row = on.rows[-1]
        self.assertEqual(row["date"], "2022-06-01")  # reference date kept
        self.assertIsNone(row["published_at"])        # no invented release date (DAT-04)
        self.assertEqual(row["available_at"], "2022-08-14T00:00:00.000Z")

    def test_historical_monthly_and_revised_withheld_without_release_metadata(self):
        g = self.snap.gate("2024-06-28", "historical")
        for sid in ("CPIAUCSL", "UNRATE", "STATIC_TOTALCPICHANGE"):
            s = g.macro(sid, None, None)
            self.assertEqual(s.rows_read, 0, sid)
            self.assertGreater(s.rows_withheld, 0, sid)
        for sid in ("DFF", "DGS2", "DGS10"):  # revised latest vintage, no vintage dates
            s = g.macro(sid, None, None)
            self.assertEqual(s.rows_read, 0, sid)
            self.assertIn("LIM_MACRO_REVISED", s.limitations)
        boc = g.macro("BD.CDN.10YR.DQ.YLD", None, None)
        self.assertGreater(boc.rows_read, 0)
        self.assertNotIn("LIM_MACRO_REVISED", boc.limitations)

    def test_current_mode_reads_revised_series_with_disclosure(self):
        s = self.snap.gate("2026-11-12").macro("DGS10", None, None)
        self.assertGreater(s.rows_read, 1000)
        self.assertIn("LIM_MACRO_REVISED", s.limitations)

    def test_gate_report_counts_cover_every_row(self):
        g = self.snap.gate("2022-06-30", "historical")
        summary = {x["datasetId"]: x for x in g.availability_summary()}
        manifest = self.snap.manifest
        for ds_id, x in summary.items():
            self.assertEqual(x["rowsVisible"] + x["rowsWithheld"], manifest["datasets"][ds_id]["rowCount"])
        self.assertEqual(summary["prices_daily"]["lastVisibleDate"], "2022-06-30")
        self.assertEqual(summary["asset_themes"]["rowsVisible"], 0)   # 2026 team assignment
        self.assertIsNone(summary["asset_themes"]["lastVisibleDate"])

    def test_before_any_data(self):
        g = self.snap.gate("2021-11-11", "historical")
        self.assertEqual(len(g.universe()), 0)
        self.assertEqual(g.master_calendar().dates, ())
        with self.assertRaises(UnknownTicker):
            g.prices(["TSLA"], None, None)
        self.assertEqual(g.fx_series().rate_on_or_before("2021-11-11"), None)


class CryptoBoundary(unittest.TestCase):
    """Crypto day D is visible at as_of D (stamped 23:59:59.999Z); D+1 is not."""

    def test_end_of_day_policy(self):
        g = starter_snapshot().gate("2022-01-01", "historical")
        btc = g.prices(["BTC-USD"], "2021-12-30", "2022-01-03")
        self.assertEqual([r["date"] for r in btc.rows], ["2021-12-30", "2021-12-31", "2022-01-01"])
        self.assertEqual(btc.rows_withheld, 2)
        self.assertEqual(btc.rows[-1]["available_at"], "2022-01-01T23:59:59.999Z")
        eq = g.prices(["SPY"], "2021-12-30", "2022-01-03")
        self.assertEqual(eq.rows[-1]["date"], "2021-12-31")
        self.assertEqual(eq.rows[-1]["available_at"], "2021-12-31T21:00:00.000Z")


class SyntheticEdges(unittest.TestCase):
    """DS-04 with synthetic release dates, DS-07 no price fill, no prior FX."""

    @classmethod
    def setUpClass(cls):
        root = temp_root()
        ingest_synthetic(root, with_releases=True)
        cls.snap = LocalDataStore(root).open("snap-20240101-syn")

    def test_release_dates_gate_historical_monthly(self):
        before = self.snap.gate("2024-02-13", "historical").macro("MONTHLYX", None, None)
        after = self.snap.gate("2024-02-14", "historical").macro("MONTHLYX", None, None)
        self.assertEqual(before.rows_read, 0)
        self.assertEqual([r["date"] for r in after.rows], ["2024-01-01"])
        self.assertEqual(after.rows[0]["published_at"], "2024-02-14T13:30:00.000Z")
        # 2023-11 and 2023-12 have no release metadata: withheld in historical mode.
        self.assertEqual(after.rows_withheld, 2)

    def test_revised_series_needs_vintage(self):
        g_pub = self.snap.gate("2024-02-10", "historical").macro("REVX", None, None)
        g_vint = self.snap.gate("2024-03-01", "historical").macro("REVX", None, None)
        self.assertEqual(g_pub.rows_read, 0)          # published 2024-02-02 but vintage 2024-03-01
        self.assertEqual([r["date"] for r in g_vint.rows], ["2024-01-01"])
        # 2023-12 has a release date but no vintage: withheld even long after publication.
        self.assertEqual(self.snap.gate("2025-01-01", "historical").macro("REVX", None, None).rows_read, 1)

    def test_current_mode_prefers_release_date(self):
        s = self.snap.gate("2024-02-14").macro("MONTHLYX", None, None)
        self.assertEqual(s.rows[-1]["availability_basis"], "release_date")
        self.assertIn("2023-12-01", [r["date"] for r in s.rows])  # A-22 lag: 2023-12-31 + 45 = 2024-02-14

    def test_release_dataset_is_published(self):
        p = self.snap.passport("macro_release_dates")
        self.assertEqual(p["status"], "in_use")
        self.assertEqual(p["rowCount"], 3)

    def test_master_calendar_and_no_fill(self):
        g = self.snap.gate("2025-01-31")
        wd = weekdays()
        frame = g.price_frame(["AAA.TO", "SPY", "BTC-USD", "CASH.CAD"])
        self.assertNotIn(wd[US_HOLIDAY_INDEX].isoformat(), frame.dates)
        missing_day = wd[AAA_MISSING_INDEX].isoformat()
        self.assertIn(missing_day, frame.dates)
        self.assertEqual(frame.missing_dates("AAA.TO"), (missing_day,))
        self.assertTrue(frame.complete("SPY"))
        self.assertTrue(frame.complete("BTC-USD"))  # crypto sampled on master days
        self.assertEqual(set(frame.column("CASH.CAD")), {1.0})
        self.assertEqual(frame.currencies["CASH.CAD"], "CAD")
        self.assertIn("LIM_CASH_NO_INTEREST", frame.limitations)

    def test_union_calendar_keeps_own_dates(self):
        g = self.snap.gate("2025-01-31")
        frame = g.price_frame(["BTC-USD"], None, "2024-01-10", calendar="union")
        self.assertEqual(len(frame.dates), 9)  # 2024-01-02 .. 2024-01-10, every calendar day

    def test_no_prior_fx_rate(self):
        g = self.snap.gate("2025-01-31")
        fx = g.fx_series()
        first_day = weekdays()[0].isoformat()
        self.assertIsNone(fx.rate_on_or_before(first_day))   # never the first future rate
        self.assertIsNotNone(fx.rate_on_or_before(weekdays()[1].isoformat()))


class Isolation(unittest.TestCase):
    """DS-08: read contexts cannot see each other's cutoff, version or mutations."""

    def test_two_gates_independent(self):
        snap = starter_snapshot()
        early = snap.gate("2022-01-31", "historical")
        late = snap.gate("2026-11-12", "current")
        a = early.prices(["SPY"], None, None)
        b = late.prices(["SPY"], None, None)
        self.assertEqual(a.last_visible_date, "2022-01-31")
        self.assertEqual(b.last_visible_date, "2026-11-12")
        self.assertEqual(early.prices(["SPY"], None, None).rows_read, a.rows_read)
        a.rows[0]["adj_close"] = -1.0
        self.assertGreater(late.prices(["SPY"], None, None).rows[0]["adj_close"], 0)
        self.assertGreater(early.prices(["SPY"], None, None).rows[0]["adj_close"], 0)

    def test_two_versions_independent(self):
        root = temp_root()
        ingest_synthetic(root, version="snap-20240101-syn")
        ingest_synthetic(root, version="snap-20240102-syn2", with_releases=True)
        store = LocalDataStore(root)
        v1, v2 = store.open("snap-20240101-syn"), store.open("snap-20240102-syn2")
        self.assertEqual(v1.gate("2025-01-01").data_version, "snap-20240101-syn")
        self.assertEqual(v2.gate("2025-01-01").data_version, "snap-20240102-syn2")
        with self.assertRaises(DatasetMissing):
            v1.gate("2025-01-01").dataset("macro_release_dates", {})
        self.assertEqual(v2.gate("2025-01-01").dataset("macro_release_dates", {}).rows_read, 3)

    def test_manifest_copy_cannot_alter_snapshot(self):
        snap = starter_snapshot()
        m = snap.manifest
        m["datasets"]["prices_daily"]["rowCount"] = 0
        self.assertEqual(snap.manifest["datasets"]["prices_daily"]["rowCount"], 40049)


class GenericReads(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.gate = starter_snapshot().gate("2026-11-12")

    def test_dataset_filters(self):
        s = self.gate.dataset("corporate_actions", {"ticker": "CNQ.TO", "action": "split"})
        self.assertEqual([(r["ex_date"], r["value"]) for r in s.rows], [("2022-08-22", 1.021), ("2024-06-11", 2.0)])
        s = self.gate.dataset("prices_daily", {"ticker": "TSLA", "start": "2022-12-30", "end": "2022-12-30"})
        self.assertEqual(s.rows_read, 1)

    def test_errors(self):
        with self.assertRaises(DatasetNotFound):
            self.gate.dataset("nope", {})
        with self.assertRaises(DatasetMissing):
            self.gate.dataset("etf_holdings", {})
        with self.assertRaises(InvalidGateRequest):
            self.gate.dataset("corporate_actions", {"colour": "red"})
        with self.assertRaises(InvalidGateRequest):
            self.gate.dataset("asset_themes", {"start": "2022-01-01"})
        with self.assertRaises(InvalidGateRequest):
            self.gate.prices(["TSLA"], "2022-12-31", "2022-01-01")
        with self.assertRaises(InvalidGateRequest):
            self.gate.prices(["TSLA"], "2022-13-01", None)
        with self.assertRaises(UnknownTicker):
            self.gate.prices(["NOPE"], None, None)
        with self.assertRaises(UnknownTicker):
            self.gate.prices(["CASH.CAD"], None, None)
        with self.assertRaises(UnknownSeries):
            self.gate.macro("NOPE", None, None)
        with self.assertRaises(InvalidGateRequest):
            starter_snapshot().gate("2026-11-12", "replay")

    def test_rows_hide_internal_availability_columns(self):
        row = self.gate.prices(["TSLA"], "2022-12-30", "2022-12-30").rows[0]
        self.assertNotIn("available_at_historical", row)
        self.assertEqual(row["available_at"], "2022-12-30T21:00:00.000Z")

    def test_dataset_read_wire_shape(self):
        s = self.gate.prices(["TSLA"], "2022-01-01", "2022-01-31")
        self.assertEqual(s.dataset_read().to_wire(), {"datasetId": "prices_daily", "dataVersion": STARTER_VERSION,
                                                      "rows": s.rows_read, "rowsWithheld": 0})

    def test_accepts_date_objects(self):
        a = self.gate.prices(["TSLA"], date(2022, 1, 1), date(2022, 1, 31))
        b = self.gate.prices(["TSLA"], "2022-01-01", "2022-01-31")
        self.assertEqual(a.rows, b.rows)


if __name__ == "__main__":
    unittest.main()
