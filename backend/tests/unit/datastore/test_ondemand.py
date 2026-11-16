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
        self.assert_rejected(fetched(100, currency="ZZZ"), "not supported by the configured currency catalog")

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


GLOBAL_FX = "snap-20261115-globalfx"  # data/manifests/active.json: what dev:api serves


class OnDemandOnGlobalFx(unittest.TestCase):
    """T5.4: a parent published by global_fx.publish_global_fx carries boc_global_fx.json and the
    fx_boc_global dataset, which ingest rejects and cannot rebuild. Every on-demand fetch on the
    active snapshot was rejected ('unexpected input file boc_global_fx.json')."""

    @classmethod
    def setUpClass(cls):
        from aplomb.datastore.global_fx import materialize_pinned_global_fx

        from ._support import REPO

        cls.root = temp_root()
        materialize_pinned_global_fx(cls.root, REPO / "data", GLOBAL_FX)

    def setUp(self):
        self.before = tree_digest(self.root)

    def fetched_on_master(self, ticker: str = "NEWCO") -> FetchedAsset:
        snap = LocalDataStore(self.root).open(GLOBAL_FX)
        days = snap.gate(snap.data_as_of, "current").master_calendar().dates[-300:]
        rows = tuple({"date": d, "open": 10 + i / 100, "high": 11 + i / 100, "low": 9 + i / 100,
                      "close": 10 + i / 100, "adj_close": 10 + i / 100, "volume": 500} for i, d in enumerate(days))
        return fetched(300, ticker=ticker, rows=rows)

    def parent_unchanged(self, *, activated: bool = False):
        """Every file present before is byte-identical, the active pointer too unless activated."""
        after = tree_digest(self.root)
        for path, data in self.before.items():
            if not (activated and path == "manifests/active.json"):
                self.assertEqual(after.get(path), data, path)
        if not activated:
            self.assertEqual(after.get("manifests/active.json"), self.before.get("manifests/active.json"))

    def test_child_keeps_the_parent_global_fx_capture(self):
        from aplomb.datastore.service import DatastoreService

        version = "snap-20261115-od-newco-1"
        r = publish_on_demand(self.root, GLOBAL_FX, version, self.fetched_on_master(), clock=fixed_clock)
        self.assertTrue(r.accepted, r.rejected_reason)
        self.assertEqual(r.data_version, version)
        self.parent_unchanged()
        store = LocalDataStore(self.root)
        parent, child = store.open(GLOBAL_FX), store.open(version)
        self.assertEqual(child.manifest["parentVersion"], GLOBAL_FX)
        # The on-demand publication time (as for a plain ingest), not the FX capture's retrieval time.
        self.assertEqual(child.manifest["createdAt"], "2026-11-14T22:00:00Z")
        self.assertEqual(child.data_as_of, parent.data_as_of)
        fx_parent, fx_child = parent.manifest["datasets"]["fx_boc_global"], child.manifest["datasets"]["fx_boc_global"]
        self.assertEqual(fx_child["sha256"], fx_parent["sha256"])
        self.assertEqual(fx_child["details"], fx_parent["details"])
        raw = {s["file"]: s for s in child.manifest["sources"]}["boc_global_fx.json"]
        self.assertEqual(raw["sha256Bytes"], {s["file"]: s for s in parent.manifest["sources"]}["boc_global_fx.json"]["sha256Bytes"])
        current_parent, current_child = parent.gate(parent.data_as_of, "current"), child.gate(child.data_as_of, "current")
        self.assertEqual(current_child.global_fx("JPY").rows, current_parent.global_fx("JPY").rows)
        self.assertTrue(current_child.global_fx("JPY").rows)
        self.assertEqual(DatastoreService(lambda: child).reporting_currencies(),
                         DatastoreService(lambda: parent).reporting_currencies())
        self.assertEqual(len(DatastoreService(lambda: child).reporting_currencies()), 9)
        self.assertIn("NEWCO", current_child.universe())
        self.assertNotIn("NEWCO", current_parent.universe())
        # The intermediate ingest is never published, and no staging is left behind.
        self.assertEqual(sorted(p.name for p in (self.root / "manifests").glob("*.json") if "base" in p.name), [])
        self.assertFalse((self.root / ".staging").exists())

    def test_activation_and_a_second_fetch_on_the_child(self):
        first = publish_on_demand(self.root, GLOBAL_FX, "snap-20261115-od-alpha-1", self.fetched_on_master("ALPHA"),
                                  clock=fixed_clock, activate=True)
        self.assertTrue(first.accepted, first.rejected_reason)
        self.assertEqual(LocalDataStore(self.root).active_version(), "snap-20261115-od-alpha-1")
        second = publish_on_demand(self.root, "snap-20261115-od-alpha-1", "snap-20261115-od-beta-1",
                                   self.fetched_on_master("BETA"), clock=fixed_clock)
        self.assertTrue(second.accepted, second.rejected_reason)
        child = LocalDataStore(self.root).open("snap-20261115-od-beta-1")
        universe = child.gate(child.data_as_of, "current").universe()
        self.assertIn("ALPHA", universe)
        self.assertIn("BETA", universe)
        self.assertIn("fx_boc_global", child.manifest["datasets"])
        self.assertEqual(child.manifest["parentVersion"], "snap-20261115-od-alpha-1")
        self.assertEqual(LocalDataStore(self.root).active_version(), "snap-20261115-od-alpha-1")
        self.parent_unchanged(activated=True)

    def test_existing_version_is_rejected_without_writing(self):
        version = "snap-20261115-od-gamma-1"
        self.assertTrue(publish_on_demand(self.root, GLOBAL_FX, version, self.fetched_on_master("GAMMA"), clock=fixed_clock).accepted)
        self.before = tree_digest(self.root)
        again = publish_on_demand(self.root, GLOBAL_FX, version, self.fetched_on_master("DELTA"), clock=fixed_clock)
        self.assertFalse(again.accepted)
        self.assertIn("already exists", again.rejected_reason["en"])
        self.assertEqual(again.data_version, GLOBAL_FX)
        self.assertEqual(tree_digest(self.root), self.before)


class ProviderProtocol(unittest.TestCase):

    def test_live_adapter_matches_the_documented_protocol(self):
        import inspect

        from aplomb.datastore.ondemand import PriceProvider
        from aplomb.datastore.providers import TiingoProvider

        expected = list(inspect.signature(PriceProvider.fetch).parameters)
        self.assertEqual(expected, ["self", "ticker", "start", "end"])
        self.assertEqual(list(inspect.signature(TiingoProvider.fetch).parameters), expected)


if __name__ == "__main__":
    unittest.main()
