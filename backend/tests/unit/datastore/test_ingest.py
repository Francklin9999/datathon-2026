"""DAT-01, DAT-02, DAT-03, DS-01, DS-02, DS-06 and snapshot integrity."""

from __future__ import annotations

import json
import os
import shutil
import unittest
from collections import Counter
from unittest import mock

from aplomb.datastore import LocalDataStore, SnapshotIntegrityError
from aplomb.datastore import ingest as ingest_mod
from aplomb.datastore.errors import IngestionError
from aplomb.datastore.ingest import ingest_bundle, ingest_starter
from aplomb.datastore.integrity import canonical_sha256, sha256_hex

from ._support import (
    METADATA_DIR,
    STARTER_DIR,
    STARTER_VERSION,
    encode_tables,
    fixed_clock,
    ingest_synthetic,
    starter_root,
    starter_snapshot,
    synthetic_tables,
    temp_root,
    tree_digest,
)


def manifest_of(root, version):
    return json.loads((root / "manifests" / f"{version}.json").read_text(encoding="utf-8"))


class StarterCounts(unittest.TestCase):
    """DAT-01 / DS-01: starter counts, keys and hashes (contracts/controls.md §1)."""

    @classmethod
    def setUpClass(cls):
        cls.root = starter_root()
        cls.m = manifest_of(cls.root, STARTER_VERSION)

    def test_row_counts_match_controls(self):
        counts = {k: v["rowCount"] for k, v in self.m["datasets"].items()}
        self.assertEqual(counts["assets_universe"], 31)
        self.assertEqual(counts["prices_daily"], 40049)
        self.assertEqual(counts["corporate_actions"], 658)
        self.assertEqual(counts["fx_usdcad_daily"], 1245)
        self.assertEqual(counts["macro_rates"], 8281)
        self.assertEqual(counts["asset_themes"], 44)
        self.assertNotIn("macro_release_dates", counts)  # O-05: no real release dates yet

    def test_rows_per_ticker_and_dates(self):
        per = self.m["datasets"]["prices_daily"]["details"]["rowsByTicker"]
        self.assertEqual(len(per), 31)
        self.assertEqual({t: n for t, n in per.items() if n != 1255}, {"BTC-USD": 1827, "ETH-USD": 1827})
        self.assertEqual(self.m["datasets"]["prices_daily"]["firstDate"], "2021-11-12")
        self.assertEqual(self.m["datasets"]["prices_daily"]["lastDate"], "2026-11-12")
        self.assertEqual(self.m["dataAsOf"], "2026-11-12")

    def test_corporate_action_split_and_dividend_counts(self):
        snap = LocalDataStore(self.root).open(STARTER_VERSION)
        rows = snap.gate("2026-11-12").dataset("corporate_actions", {}).rows
        self.assertEqual(Counter(r["action"] for r in rows), Counter({"dividend": 651, "split": 7}))

    def test_macro_series_counts(self):
        series = {s: c["rows"] for s, c in self.m["datasets"]["macro_rates"]["details"]["series"].items()}
        self.assertEqual(series, {
            "BD.CDN.10YR.DQ.YLD": 1245, "BD.CDN.2YR.DQ.YLD": 1245, "V39079": 1293, "DFF": 1826, "DGS10": 1248,
            "DGS2": 1248, "CPIAUCSL": 59, "UNRATE": 59, "STATIC_TOTALCPICHANGE": 58})

    def test_source_hashes_are_canonical_and_byte_exact(self):
        by_file = {s["file"]: s for s in self.m["sources"]}
        for name in ("assets_universe.csv", "prices_daily.csv", "corporate_actions.csv", "fx_usdcad_daily.csv",
                     "macro_rates.csv", "sources_metadata.csv", "data_quality_warnings.txt"):
            data = (STARTER_DIR / name).read_bytes()
            self.assertEqual(by_file[name]["sha256"], canonical_sha256(data), name)
            self.assertEqual(by_file[name]["sha256Bytes"], sha256_hex(data), name)
            self.assertEqual(by_file[name]["bytes"], len(data), name)
        for name in ("asset_themes.csv", "macro_series.csv"):
            self.assertEqual(by_file[name]["sha256"], canonical_sha256((METADATA_DIR / name).read_bytes()))

    def test_canonical_hash_ignores_crlf(self):
        self.assertEqual(canonical_sha256(b"a,b\r\n1,2\r\n"), canonical_sha256(b"a,b\n1,2\n"))

    def test_quality_flags_are_exactly_the_known_ones(self):
        flags = {(f["datasetId"], f["code"], f["ticker"], f["date"]) for f in self.m["qualityFlags"]}
        self.assertEqual(flags, {
            ("prices_daily", "zero_volume", "ZST.TO", "2022-07-06"),
            ("corporate_actions", "split_anomaly", "CNQ.TO", "2022-08-22"),
            ("macro_rates", "coverage_gap", "CPIAUCSL", None),
            ("macro_rates", "coverage_gap", "UNRATE", None),
        })
        gap = [f for f in self.m["qualityFlags"] if f["code"] == "coverage_gap"]
        self.assertTrue(all("2025-10" in f["detail"] for f in gap))

    def test_checks_timestamped_by_the_ingestion_clock(self):
        for ds in self.m["datasets"].values():
            for c in ds["checks"]:
                self.assertEqual(c["checkedAt"], "2026-11-14T22:00:00Z")
        self.assertEqual(self.m["createdAt"], "2026-11-14T22:00:00Z")


class MasterCalendar(unittest.TestCase):
    """DS-02: 1,228 master dates and the ten master days without a same-day USD/CAD rate."""

    @classmethod
    def setUpClass(cls):
        cls.snap = starter_snapshot()
        cls.gate = cls.snap.gate("2026-11-12")

    def test_master_calendar(self):
        cal = self.gate.master_calendar()
        self.assertEqual(len(cal.dates), 1228)
        self.assertEqual((cal.dates[0], cal.dates[-1]), ("2021-11-12", "2026-11-12"))
        per_year = Counter(d[:4] for d in cal.dates)
        self.assertEqual(dict(per_year), {"2021": 32, "2022": 245, "2023": 245, "2024": 247, "2025": 245, "2026": 214})
        self.assertIn("2021-12-31", cal.dates)
        self.assertEqual(max(d for d in cal.dates if d.startswith("2022")), "2022-12-30")
        self.assertEqual(cal.limitations, ("LIM_CALENDAR_INTERSECTION",))

    def test_ten_master_days_without_same_day_fx(self):
        expected = ["2022-09-30", "2022-11-11", "2023-10-02", "2023-11-13", "2024-09-30", "2024-11-11",
                    "2025-09-30", "2025-11-11", "2026-09-30", "2026-11-11"]
        fx = self.gate.fx_series()
        missing = [d for d in self.gate.master_calendar().dates if fx.rate_on(d) is None]
        self.assertEqual(missing, expected)
        m = self.snap.manifest
        self.assertEqual(m["datasets"]["fx_usdcad_daily"]["details"]["masterDaysWithoutSameDayRate"], expected)
        for d in expected:
            rate, published = fx.rate_on_or_before(d)
            self.assertLess(published, d)

    def test_every_listed_asset_matches_its_reference_calendar(self):
        check = [c for c in self.snap.manifest["datasets"]["prices_daily"]["checks"] if "reference calendar" in c["name"]]
        self.assertEqual(len(check), 1)
        self.assertTrue(check[0]["ok"])


class Idempotence(unittest.TestCase):
    """DAT-02: idempotent ingestion and stable source/normalized hashes."""

    def test_reingest_same_version_is_a_verified_noop(self):
        root = temp_root()
        first = ingest_synthetic(root)
        before = tree_digest(root)
        second = ingest_synthetic(root)
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(tree_digest(root), before)

    def test_two_roots_produce_identical_normalized_hashes(self):
        a, b = temp_root(), temp_root()
        ma = ingest_synthetic(a).manifest
        mb = ingest_bundle(encode_tables(synthetic_tables()), b, "snap-20240101-syn",
                           clock=lambda: fixed_clock().replace(hour=23)).manifest
        self.assertEqual({k: v["sha256"] for k, v in ma["datasets"].items()},
                         {k: v["sha256"] for k, v in mb["datasets"].items()})
        self.assertEqual(ma["sources"], mb["sources"])

    def test_clean_clone_materializes_from_committed_manifest(self):
        root = temp_root()
        m = ingest_synthetic(root).manifest
        shutil.rmtree(root / "raw")
        shutil.rmtree(root / "normalized")
        again = ingest_synthetic(root)
        self.assertFalse(again.created)
        self.assertEqual(again.manifest, m)
        LocalDataStore(root).open("snap-20240101-syn")  # verifies every checksum

    def test_starter_reingest_matches(self):
        root = temp_root()
        r = ingest_starter(STARTER_DIR, root, STARTER_VERSION, metadata_dir=METADATA_DIR, clock=fixed_clock)
        ref = manifest_of(starter_root(), STARTER_VERSION)
        self.assertEqual({k: v["sha256"] for k, v in r.manifest["datasets"].items()},
                         {k: v["sha256"] for k, v in ref["datasets"].items()})

    def test_same_version_with_different_sources_is_rejected(self):
        root = temp_root()
        ingest_synthetic(root)
        before = tree_digest(root)
        tables = synthetic_tables()
        tables["prices_daily.csv"][0][6] = "31.5"
        with self.assertRaises(IngestionError):
            ingest_bundle(encode_tables(tables), root, "snap-20240101-syn", clock=fixed_clock)
        self.assertEqual(tree_digest(root), before)


class FailureIsolation(unittest.TestCase):
    """DAT-03 / DS-06: rejected or interrupted ingestion never corrupts the active version."""

    def setUp(self):
        self.root = temp_root()
        ingest_synthetic(self.root)
        self.before = tree_digest(self.root)

    def assert_unchanged(self):
        self.assertEqual(tree_digest(self.root), self.before)
        self.assertFalse((self.root / "manifests" / "snap-20240102-bad.json").exists())
        self.assertFalse((self.root / ".staging").exists())
        store = LocalDataStore(self.root)
        self.assertEqual(store.active_version(), "snap-20240101-syn")
        store.open("snap-20240101-syn")

    def reject(self, mutate, needle):
        tables = synthetic_tables()
        mutate(tables)
        with self.assertRaises(IngestionError) as ctx:
            ingest_bundle(encode_tables(tables), self.root, "snap-20240102-bad", clock=fixed_clock)
        self.assertIn(needle, str(ctx.exception))
        self.assert_unchanged()

    def test_duplicate_price_key(self):
        self.reject(lambda t: t["prices_daily.csv"].append(list(t["prices_daily.csv"][0])), "duplicate (date, ticker)")

    def test_nonpositive_adjusted_price(self):
        def m(t):
            t["prices_daily.csv"][3][6] = "0"
        self.reject(m, "non-positive adj_close")

    def test_malformed_date(self):
        def m(t):
            t["prices_daily.csv"][3][0] = "2024-02-30"
        self.reject(m, "invalid calendar date")

    def test_nonfinite_value(self):
        def m(t):
            t["prices_daily.csv"][3][2] = "nan"
        self.reject(m, "not finite")

    def test_unknown_ticker(self):
        def m(t):
            t["prices_daily.csv"][3][1] = "ZZZ"
        self.reject(m, "unknown ticker ZZZ")

    def test_currency_mismatch(self):
        def m(t):
            t["prices_daily.csv"][3][8] = "USD"
        self.reject(m, "differs from listing currency")

    def test_unknown_currency_in_universe(self):
        def m(t):
            t["assets_universe.csv"][2][5] = "EUR"
        self.reject(m, "not CAD or USD")

    def test_duplicate_fx_date(self):
        self.reject(lambda t: t["fx_usdcad_daily.csv"].append(list(t["fx_usdcad_daily.csv"][0])), "duplicate date")

    def test_duplicate_macro_key(self):
        self.reject(lambda t: t["macro_rates.csv"].append(list(t["macro_rates.csv"][0])), "duplicate (date, series_id)")

    def test_macro_series_without_metadata(self):
        def m(t):
            t["macro_rates.csv"][0][1] = "NEWSERIES"
        self.reject(m, "no entry in macro_series.csv")

    def test_unknown_theme_tag(self):
        def m(t):
            t["asset_themes.csv"][0][1] = "moonshots"
        self.reject(m, "not in catalog")

    def test_missing_calendar_reference(self):
        def m(t):
            t["assets_universe.csv"] = [r for r in t["assets_universe.csv"] if r[1] != "SPY"]
            t["prices_daily.csv"] = [r for r in t["prices_daily.csv"] if r[1] != "SPY"]
        self.reject(m, "calendar reference ticker SPY")

    def test_wrong_header(self):
        bundle = encode_tables(synthetic_tables())
        bundle.files["fx_usdcad_daily.csv"] = b"date,usd_cad,cad_usd\n2024-01-03,1.35,0.740741\n"
        with self.assertRaises(IngestionError) as ctx:
            ingest_bundle(bundle, self.root, "snap-20240102-bad", clock=fixed_clock)
        self.assertIn("does not match expected", str(ctx.exception))
        self.assert_unchanged()

    def test_crash_before_manifest_commit_rolls_back(self):
        with mock.patch.object(ingest_mod, "_write_manifest", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                ingest_bundle(encode_tables(synthetic_tables()), self.root, "snap-20240102-bad", clock=fixed_clock)
        self.assertFalse((self.root / "raw" / "snap-20240102-bad").exists())
        self.assertFalse((self.root / "normalized" / "snap-20240102-bad").exists())
        self.assert_unchanged()

    def test_invalid_version_label(self):
        with self.assertRaises(IngestionError):
            ingest_bundle(encode_tables(synthetic_tables()), self.root, "latest", clock=fixed_clock)
        self.assert_unchanged()


class Integrity(unittest.TestCase):
    """Loaders reject tampered, partial or unknown-schema snapshots."""

    def setUp(self):
        self.root = temp_root()
        ingest_synthetic(self.root)

    def test_tampered_dataset_rejected(self):
        path = self.root / "normalized" / "snap-20240101-syn" / "prices_daily.csv"
        os.chmod(path, 0o644)
        path.write_bytes(path.read_bytes().replace(b"30.0,", b"31.0,", 1))
        with self.assertRaises(SnapshotIntegrityError):
            LocalDataStore(self.root).open("snap-20240101-syn")

    def test_unknown_schema_version_rejected(self):
        path = self.root / "manifests" / "snap-20240101-syn.json"
        m = json.loads(path.read_text(encoding="utf-8"))
        m["datasets"]["prices_daily"]["schemaVersion"] = 99
        path.write_text(json.dumps(m), encoding="utf-8")
        with self.assertRaises(SnapshotIntegrityError):
            LocalDataStore(self.root).open("snap-20240101-syn")

    def test_partial_snapshot_rejected(self):
        path = self.root / "manifests" / "snap-20240101-syn.json"
        m = json.loads(path.read_text(encoding="utf-8"))
        del m["datasets"]["fx_usdcad_daily"]
        path.write_text(json.dumps(m), encoding="utf-8")
        with self.assertRaises(SnapshotIntegrityError):
            LocalDataStore(self.root).open("snap-20240101-syn")

    def test_missing_file_rejected(self):
        (self.root / "normalized" / "snap-20240101-syn" / "fx_usdcad_daily.csv").unlink()
        with self.assertRaises(SnapshotIntegrityError):
            LocalDataStore(self.root).open("snap-20240101-syn")

    def test_unknown_version_rejected(self):
        with self.assertRaises(SnapshotIntegrityError):
            LocalDataStore(self.root).open("snap-20240101-other")


class CachedObjectStoreTest(unittest.TestCase):
    """S3-shaped reader: downloads verified by checksum, cached read-only, re-fetched if corrupt."""

    def test_fetch_verify_and_cache(self):
        from aplomb.datastore import CachedObjectStore

        root = temp_root()
        ingest_synthetic(root)
        calls = []

        def fetch(key):
            calls.append(key)
            return (root / key).read_bytes()

        cache = temp_root()
        store = CachedObjectStore(fetch, cache)
        self.assertEqual(store.active_version(), "snap-20240101-syn")
        snap = store.open("snap-20240101-syn")
        self.assertEqual(snap.data_version, "snap-20240101-syn")
        n = len(calls)
        CachedObjectStore(fetch, cache).open("snap-20240101-syn")
        self.assertEqual(len(calls), n + 1)  # only the manifest is fetched again; datasets come from cache
        cached = next((cache / "snap-20240101-syn").glob("*prices_daily.csv"))
        self.assertFalse(os.access(cached, os.W_OK))

    def test_corrupt_download_rejected(self):
        from aplomb.datastore import CachedObjectStore

        root = temp_root()
        ingest_synthetic(root)

        def fetch(key):
            data = (root / key).read_bytes()
            return data.replace(b"30.0", b"99.0", 1) if key.endswith("prices_daily.csv") else data

        with self.assertRaises(SnapshotIntegrityError):
            CachedObjectStore(fetch, temp_root()).open("snap-20240101-syn")


if __name__ == "__main__":
    unittest.main()
