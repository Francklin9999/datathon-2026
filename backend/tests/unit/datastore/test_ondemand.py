"""DAT-06 (on-demand accept / short history / reject) and DS-05 (parent snapshot unchanged)."""

from __future__ import annotations

import json
import unittest

from aplomb.datastore import LocalDataStore
from aplomb.datastore.ondemand import FetchedAsset, publish_on_demand

from ._support import fixed_clock, ingest_synthetic, temp_root, tree_digest, weekdays

BASE = "snap-20240101-syn"


def fetched(n_rows: int, ticker: str = "NEWCO", currency: str = "USD", **overrides) -> FetchedAsset:
    days = weekdays()[:n_rows]
    rows = tuple({"date": d.isoformat(), "open": 10 + i, "high": 11 + i, "low": 9 + i, "close": 10 + i,
                  "adj_close": 10 + i, "volume": 500} for i, d in enumerate(days))
    fields = dict(ticker=ticker, name="New Company", asset_class="equity", market="NASDAQ", currency=currency,
                  sector=None, rows=rows, provider="synthetic-test-provider",
                  retrieved_at="2026-11-14T21:00:00Z", source_url="https://example.invalid/newco")
    fields.update(overrides)
    return FetchedAsset(**fields)


class OnDemand(unittest.TestCase):

    def setUp(self):
        self.root = temp_root()
        ingest_synthetic(self.root, BASE)
        self.before = tree_digest(self.root)

    def base_unchanged(self):
        after = tree_digest(self.root)
        for path, data in self.before.items():
            self.assertEqual(after.get(path), data, path)
        self.assertEqual(LocalDataStore(self.root).active_version(), BASE)

    def test_accept_publishes_new_version_and_keeps_parent(self):
        r = publish_on_demand(self.root, BASE, "snap-20261114-od1", fetched(270), clock=fixed_clock)
        self.assertTrue(r.accepted, r.rejected_reason)
        self.assertEqual(r.data_version, "snap-20261114-od1")
        a = r.asset
        self.assertEqual((a["tier"], a["sector"], a["gicsSector"], a["country"]), ("on_demand", "unknown", None, "USA"))
        self.assertIn("on_demand", a["flags"])
        self.assertIn("sector_label_unsourced", a["flags"])
        self.assertNotIn("short_history", a["flags"])
        self.assertGreaterEqual(a["history"]["nObsMaster"], 252)
        self.assertEqual(r.passport["dataVersion"], "snap-20261114-od1")
        self.assertTrue(any("NEWCO" in p["en"] for p in r.passport["processing"]))
        self.assertEqual(set(r.to_wire()), {"asset", "accepted", "rejectedReason", "passport"})
        # DS-05: the parent snapshot and the active pointer are untouched.
        self.base_unchanged()
        store = LocalDataStore(self.root)
        old = store.open(BASE).gate("2025-01-31").universe()
        self.assertNotIn("NEWCO", old)
        new = store.open("snap-20261114-od1")
        self.assertIn("NEWCO", new.gate("2025-01-31").universe())
        m = new.manifest
        self.assertEqual(m["parentVersion"], BASE)
        self.assertEqual(m["onDemand"][0]["provider"], "synthetic-test-provider")
        self.assertEqual(m["onDemand"][0]["retrievedAt"], "2026-11-14T21:00:00.000Z")

    def test_short_history_accepted_with_flag(self):
        r = publish_on_demand(self.root, BASE, "snap-20261114-od2", fetched(40), clock=fixed_clock)
        self.assertTrue(r.accepted)
        self.assertIn("short_history", r.asset["flags"])
        self.assertLess(r.asset["history"]["nObsMaster"], 252)

    def test_chained_on_demand_keeps_earlier_addition(self):
        publish_on_demand(self.root, BASE, "snap-20261114-od1", fetched(270), clock=fixed_clock)
        r = publish_on_demand(self.root, "snap-20261114-od1", "snap-20261114-od2", fetched(270, ticker="OTHER.TO", currency="CAD", market="TSX"),
                              clock=fixed_clock)
        self.assertTrue(r.accepted, r.rejected_reason)
        u = LocalDataStore(self.root).open("snap-20261114-od2").gate("2025-01-31").universe()
        self.assertIn("NEWCO", u)
        self.assertEqual(u.get("OTHER.TO").country, "CAN")
        self.assertEqual(u.counts()["byTier"]["on_demand"], 2)

    def test_activate_option(self):
        publish_on_demand(self.root, BASE, "snap-20261114-od1", fetched(270), clock=fixed_clock, activate=True)
        self.assertEqual(LocalDataStore(self.root).active_version(), "snap-20261114-od1")

    def assert_rejected(self, f, needle):
        r = publish_on_demand(self.root, BASE, "snap-20261114-bad", f, clock=fixed_clock)
        self.assertFalse(r.accepted)
        self.assertIn(needle, r.rejected_reason["en"])
        self.assertTrue(r.rejected_reason["fr"])
        self.assertEqual(r.data_version, BASE)
        self.assertFalse((self.root / "manifests" / "snap-20261114-bad.json").exists())
        self.base_unchanged()
        self.assertEqual(json.loads(json.dumps(r.to_wire())), r.to_wire())

    def test_reject_too_few_rows(self):
        self.assert_rejected(fetched(29), "at least 30")

    def test_reject_currency(self):
        self.assert_rejected(fetched(100, currency="EUR"), "not CAD or USD")

    def test_reject_duplicate_dates(self):
        f = fetched(100)
        rows = f.rows + (dict(f.rows[0]),)
        self.assert_rejected(fetched(100, rows=rows), "Duplicate date")

    def test_reject_nonpositive_price(self):
        f = fetched(100)
        rows = list(f.rows)
        rows[5] = {**rows[5], "close": 0}
        self.assert_rejected(fetched(100, rows=tuple(rows)), "Non-positive price")

    def test_reject_missing_retrieval_time(self):
        self.assert_rejected(fetched(100, retrieved_at="yesterday"), "Retrieval timestamp")

    def test_reject_already_present(self):
        r = publish_on_demand(self.root, BASE, "snap-20261114-bad", fetched(100, ticker="SPY"), clock=fixed_clock)
        self.assertFalse(r.accepted)
        self.assertEqual(r.asset["ticker"], "SPY")
        self.base_unchanged()


if __name__ == "__main__":
    unittest.main()
