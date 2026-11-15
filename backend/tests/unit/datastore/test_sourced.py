"""snap-20261114-sourced: real Statistics Canada CPI release dates and sourced theme tags,
plus the frozen per-version inputs that keep every committed version reproducible."""

from __future__ import annotations

import csv
import json
import unittest
from datetime import date, timedelta
from urllib.parse import urlparse

from aplomb.datastore import LocalDataStore
from aplomb.datastore.ingest import ingest_starter
from aplomb.datastore.integrity import canonical_sha256

from ._support import REPO, STARTER_DIR, fixed_clock, temp_root

SOURCED = "snap-20261114-sourced"
INPUTS = REPO / "data" / "inputs"
_SNAP = None


def sourced_snapshot():
    global _SNAP
    if _SNAP is None:
        root = temp_root()
        ingest_starter(STARTER_DIR, root, SOURCED, metadata_dir=INPUTS / SOURCED, clock=fixed_clock)
        _SNAP = LocalDataStore(root).open(SOURCED)
    return _SNAP


class FrozenInputs(unittest.TestCase):

    def test_committed_manifests_match_frozen_inputs(self):
        for version in ("snap-20261113-starter", SOURCED):
            manifest = json.loads((REPO / "data" / "manifests" / f"{version}.json").read_text(encoding="utf-8"))
            for src in manifest["sources"]:
                frozen = INPUTS / version / src["file"]
                if frozen.exists():
                    self.assertEqual(canonical_sha256(frozen.read_bytes()), src["sha256"], (version, src["file"]))
                else:
                    self.assertEqual(canonical_sha256((STARTER_DIR / src["file"]).read_bytes()), src["sha256"], (version, src["file"]))

    def test_new_version_reproduces_committed_hashes(self):
        manifest = json.loads((REPO / "data" / "manifests" / f"{SOURCED}.json").read_text(encoding="utf-8"))
        got = sourced_snapshot().manifest
        self.assertEqual({k: v["sha256"] for k, v in got["datasets"].items()},
                         {k: v["sha256"] for k, v in manifest["datasets"].items()})


class ReleaseDates(unittest.TestCase):

    def test_release_rows(self):
        rows = list(csv.DictReader(open(INPUTS / SOURCED / "macro_release_dates.csv", encoding="utf-8")))
        self.assertEqual(len(rows), 58)
        self.assertEqual({r["seriesId"] for r in rows}, {"STATIC_TOTALCPICHANGE"})
        for r in rows:
            ref = date.fromisoformat(r["referenceDate"])
            month_end = (ref.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            self.assertGreater(date.fromisoformat(r["publishedAt"]), month_end)  # published after the month ends
            self.assertEqual(urlparse(r["sourceUrl"]).netloc, "www150.statcan.gc.ca")
            self.assertEqual(r["vintageAt"], "")  # not a revised series

    def test_historical_visibility_follows_the_real_release(self):
        snap = sourced_snapshot()
        before = snap.gate("2022-07-19", "historical").macro("STATIC_TOTALCPICHANGE", None, None)
        on = snap.gate("2022-07-20", "historical").macro("STATIC_TOTALCPICHANGE", None, None)
        self.assertEqual(before.last_visible_date, "2022-05-01")
        self.assertEqual(on.last_visible_date, "2022-06-01")
        self.assertEqual(on.rows[-1]["value"], 8.1)  # controls §10: 8.1% for June 2022
        self.assertEqual(on.rows[-1]["published_at"], "2022-07-20T00:00:00.000Z")
        self.assertEqual(on.rows[-1]["availability_basis"], "release_date")
        self.assertNotIn("LIM_MACRO_LAG_ASSUMED", on.limitations)
        us = snap.gate("2024-06-28", "historical").macro("CPIAUCSL", None, None)
        self.assertEqual(us.rows_read, 0)  # revised FRED series stay withheld

    def test_passport(self):
        p = sourced_snapshot().passport("macro_release_dates")
        self.assertEqual((p["status"], p["rowCount"]), ("in_use", 58))
        self.assertEqual(p["licenceUrl"], "https://www.statcan.gc.ca/en/terms-conditions/open-licence")
        self.assertIn("Statistics Canada", p["source"])


class Themes(unittest.TestCase):

    def test_sources(self):
        rows = list(csv.DictReader(open(INPUTS / SOURCED / "asset_themes.csv", encoding="utf-8")))
        self.assertEqual(len(rows), 44)
        sourced = [r for r in rows if r["sourceUrl"]]
        self.assertEqual(len(sourced), 36)
        for r in sourced:
            self.assertTrue(r["sourceUrl"].startswith("https://"))
            self.assertIn("checked 2026-11-14", r["justification"])
        for r in rows:
            if not r["sourceUrl"]:
                self.assertTrue(r["justification"].startswith("Universe file"), r)
            self.assertEqual(r["isAssumption"], "true")
        check = next(c for c in sourced_snapshot().passport("asset_themes")["checks"] if "source URL" in c["name"])
        self.assertIn("8 of 44", check["detail"])


if __name__ == "__main__":
    unittest.main()
