"""Universe normalization (datastore SPEC §5) and the wire ``Asset`` shape (schemas.md §3)."""

from __future__ import annotations

import unittest

from aplomb.datastore import InvalidGateRequest, UnknownTicker

from ._support import STARTER_VERSION, read_starter_csv, starter_snapshot

ASSET_KEYS = {"ticker", "name", "assetClass", "assetGroup", "market", "currency", "sector", "gicsSector", "isSingleName",
              "country", "themes", "tier", "history", "flags", "dataVersion", "datasetId"}
GROUP = {"equity": "equity", "etf_equity": "equity", "etf_bond": "fixed_income", "etf_commodity": "commodity",
         "crypto": "crypto"}


class StarterUniverse(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.snap = starter_snapshot()
        cls.u = cls.snap.gate("2026-11-12").universe()
        cls.raw = {r["ticker"]: r for r in read_starter_csv("assets_universe.csv")}

    def test_counts(self):
        self.assertEqual(self.u.counts(), {"total": 31, "byTier": {"starter": 31, "extended": 0, "on_demand": 0}})
        self.assertEqual([a.ticker for a in self.u.all()], list(self.raw))  # organizer order A01..A31

    def test_every_asset_normalized_from_source(self):
        for t, raw in self.raw.items():
            a = self.u.get(t)
            w = a.to_wire()
            self.assertEqual(set(w), ASSET_KEYS)
            self.assertEqual((w["name"], w["assetClass"], w["market"], w["currency"], w["sector"]),
                             (raw["name"], raw["asset_class"], raw["market"], raw["currency"], raw["sector"]))
            self.assertEqual(w["assetGroup"], GROUP[raw["asset_class"]])
            self.assertEqual(w["isSingleName"], raw["asset_class"] in ("equity", "crypto"))
            expected_country = None if raw["asset_class"] == "crypto" else ("CAN" if raw["market"] == "TSX" else "USA")
            self.assertEqual(w["country"], expected_country, t)
            self.assertEqual(w["tier"], "starter")
            self.assertEqual(w["dataVersion"], STARTER_VERSION)
            self.assertEqual(w["datasetId"], "prices_daily")
            self.assertEqual(w["history"]["nObsMaster"], 1228)
            self.assertEqual(w["history"]["nObs"], 1827 if raw["asset_class"] == "crypto" else 1255)
            self.assertEqual((w["history"]["firstDate"], w["history"]["lastDate"]), ("2021-11-12", "2026-11-12"))
            self.assertTrue(w["themes"], t)

    def test_gics_sector_only_for_gics_labels(self):
        self.assertEqual(self.u.get("TSLA").gics_sector, "Consumer Discretionary")
        self.assertEqual(self.u.get("GOOGL").gics_sector, "Communication Services")
        for t in ("XIU.TO", "SPY", "QQQ", "ESGV", "XBB.TO", "ZST.TO", "AGG", "TLT", "GLD", "BTC-USD", "ETH-USD"):
            self.assertIsNone(self.u.get(t).gics_sector, t)

    def test_zst_is_a_bond_fund_not_cash(self):
        z = self.u.get("ZST.TO")
        self.assertEqual((z.asset_class, z.asset_group), ("etf_bond", "fixed_income"))
        self.assertNotIn("cash_like", z.themes)
        self.assertEqual(z.flags, ("zero_volume_rows",))

    def test_flags(self):
        flagged = {a.ticker: a.flags for a in self.u.all() if a.flags}
        self.assertEqual(flagged, {
            "ZST.TO": ("zero_volume_rows",),
            "CNQ.TO": ("split_anomaly",),
            "BTC-USD": ("seven_day_calendar",),
            "ETH-USD": ("seven_day_calendar",),
        })

    def test_short_history_flag_in_early_historical_context(self):
        u = self.snap.gate("2022-06-30", "historical").universe()
        self.assertIn("short_history", u.get("SPY").flags)
        self.assertLess(u.get("SPY").history.n_obs_master, 252)
        self.assertEqual(u.get("SPY").history.last_date, "2022-06-30")
        # Theme tags were assigned in 2026: not visible as historical evidence.
        self.assertEqual(u.get("TSLA").themes, ())

    def test_search(self):
        self.assertEqual([a.ticker for a in self.u.search(q="tesla")], ["TSLA"])
        self.assertEqual([a.ticker for a in self.u.search(q="spy")], ["SPY"])
        self.assertEqual({a.ticker for a in self.u.search(theme="ai", limit=50)}, {"MSFT", "NVDA", "GOOGL"})
        self.assertEqual({a.ticker for a in self.u.search(asset_class="crypto")}, {"BTC-USD", "ETH-USD"})
        self.assertEqual(len(self.u.search(limit=500)), 31)
        self.assertEqual(self.u.search(tier="on_demand"), ())
        with self.assertRaises(InvalidGateRequest):
            self.u.search(limit=0)

    def test_cash_pseudo_assets(self):
        c = self.u.get("CASH.USD")
        self.assertEqual((c.asset_class, c.asset_group, c.currency, c.is_single_name), ("cash", "cash", "USD", False))
        self.assertEqual(c.history.n_obs_master, 1228)
        self.assertIn("CASH.CAD", self.u)
        self.assertNotIn("CASH.CAD", [a.ticker for a in self.u.all()])
        self.assertEqual(self.u.counts()["total"], 31)

    def test_unknown(self):
        with self.assertRaises(UnknownTicker):
            self.u.get("NOPE")
        self.assertNotIn("NOPE", self.u)

    def test_reads_reported(self):
        reads = {r.dataset_id: r for r in self.u.reads}
        self.assertEqual(reads["assets_universe"].rows, 31)
        self.assertEqual(reads["asset_themes"].rows, 44)


if __name__ == "__main__":
    unittest.main()
