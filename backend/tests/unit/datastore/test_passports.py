"""DAT-05 (traps mapped to passports), DAT-07 (passport metadata for GET /datasets) and the
catalog values copied in ``aplomb.datastore.constants``."""

from __future__ import annotations

import json
import re
import unittest

from aplomb.datastore import DatasetNotFound
from aplomb.datastore import constants as C
from aplomb.datastore.passports import PASSPORT_KEYS

from ._support import REPO, STARTER_VERSION, starter_snapshot

CATALOG = (REPO / "contracts" / "catalog.md").read_text(encoding="utf-8")
SCHEMAS = (REPO / "contracts" / "schemas.md").read_text(encoding="utf-8")


def catalog_section(title: str) -> str:
    m = re.search(rf"## \d+\. {re.escape(title)}.*?(?=\n## |\Z)", CATALOG, re.S)
    assert m, title
    return m.group(0)


class CatalogMirror(unittest.TestCase):
    """The datastore's copies of catalog lists equal contracts/catalog.md."""

    def test_dataset_ids(self):
        ids = tuple(re.findall(r"^\| `([a-z_]+)` \|", catalog_section("Dataset IDs"), re.M))
        self.assertEqual(ids, C.DATASET_IDS)

    def test_limitation_codes(self):
        codes = set(re.findall(r"^\| `(LIM_[A-Z0-9_]+)` \|", catalog_section("Limitation codes"), re.M))
        self.assertEqual(codes, set(C.LIMITATION_CODES))

    def test_theme_tags(self):
        tags = set(re.findall(r"`([a-z_]+)`", catalog_section("Theme tags").split("\n\n", 2)[-1]))
        self.assertEqual(tags, set(C.THEME_TAGS))

    def test_asset_flags(self):
        self.assertEqual(set(re.findall(r"`([a-z_]+)`", catalog_section("Asset flags"))), set(C.ASSET_FLAGS))

    def test_passport_keys_match_schema(self):
        block = re.search(r"interface DatasetPassport \{(.*?)\n\}", SCHEMAS, re.S).group(1)
        keys = re.findall(r"^\s+([a-zA-Z]+)\??:", block, re.M)
        self.assertEqual(tuple(keys), PASSPORT_KEYS)


class Passports(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.snap = starter_snapshot()
        cls.items = cls.snap.passports()
        cls.by_id = {p["datasetId"]: p for p in cls.items}

    def test_every_catalog_dataset_has_a_passport(self):
        self.assertEqual([p["datasetId"] for p in self.items], list(C.DATASET_IDS))
        for p in self.items:
            self.assertEqual(tuple(p), PASSPORT_KEYS)
            self.assertIn(p["status"], ("in_use", "planned", "rejected"))
            for key in ("name", "role", "availabilityRule"):
                self.assertTrue(p[key]["en"] and p[key]["fr"], (p["datasetId"], key))
            for item in p["processing"]:
                self.assertTrue(item["en"] and item["fr"])
            self.assertTrue(set(p["limitations"]) <= C.LIMITATION_CODES, p["datasetId"])

    def test_loaded_vs_planned(self):
        in_use = {p["datasetId"] for p in self.items if p["status"] == "in_use"}
        # default_profiles is not in the snapshot: its passport follows the personas file shipped with the app.
        self.assertEqual(in_use, {"assets_universe", "prices_daily", "corporate_actions", "fx_usdcad_daily",
                                  "macro_rates", "asset_themes", "default_profiles"})
        for p in self.items:
            if p["status"] == "planned":
                self.assertIsNone(p["rowCount"])
                self.assertIsNone(p["dataVersion"])
                self.assertIsNone(p["retrievedOn"])  # never pre-filled for an integration that has not run
                self.assertEqual(p["checks"], [])

    def test_in_use_metadata_from_actual_ingestion(self):
        prices = self.by_id["prices_daily"]
        self.assertEqual(prices["rowCount"], 40049)
        self.assertEqual(prices["coverage"], {"start": "2021-11-12", "end": "2026-11-12"})
        self.assertEqual(prices["dataVersion"], STARTER_VERSION)
        self.assertEqual(prices["retrievedOn"], "2026-11-13")
        self.assertEqual(prices["sourceUrl"], "https://finance.yahoo.com")
        self.assertEqual(prices["licenceUrl"], "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html")
        self.assertEqual(self.by_id["corporate_actions"]["licenceUrl"], prices["licenceUrl"])
        self.assertEqual(self.by_id["fx_usdcad_daily"]["licenceUrl"], "https://www.bankofcanada.ca/terms/")
        self.assertIsNone(self.by_id["assets_universe"]["coverage"])
        self.assertEqual(self.by_id["asset_themes"]["retrievedOn"], "2026-11-14")
        for p in self.items:
            for c in p["checks"]:
                self.assertEqual(set(c), {"name", "ok", "detail", "checkedAt"})
                if p["datasetId"] != "default_profiles":  # checked when the passport is built, not at ingestion
                    self.assertEqual(c["checkedAt"], "2026-11-14T22:00:00Z")
        names = [c["name"] for c in prices["checks"]]
        self.assertIn("No zero-volume observations", names)
        zero = next(c for c in prices["checks"] if c["name"] == "No zero-volume observations")
        self.assertFalse(zero["ok"])
        self.assertIn("ZST.TO 2022-07-06", zero["detail"])

    def test_schema_lists_columns_without_internal_availability(self):
        cols = [c["name"] for c in self.by_id["prices_daily"]["schema"]]
        self.assertEqual(cols, ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "currency"])

    def test_round_trips_as_json(self):
        body = self.snap.datasets_response()
        self.assertEqual(json.loads(json.dumps(body)), body)
        self.assertEqual(set(body), {"items", "traps"})

    def test_traps_mapped_to_passports(self):
        used = {code for p in self.items if p["status"] == "in_use" for code in p["limitations"]}
        traps = self.snap.traps()
        self.assertEqual(len({t["code"] for t in traps}), len(traps))
        for t in traps:
            self.assertEqual(set(t), {"code", "handledBy", "status"})
            self.assertIn(t["status"], ("handled", "disclosed", "open"))
            self.assertIn(t["code"], C.LIMITATION_CODES)
            self.assertIn(t["code"], used, t["code"])

    def test_describe_through_gate(self):
        g = self.snap.gate("2026-11-12")
        self.assertEqual(g.describe("fx_usdcad_daily"), self.by_id["fx_usdcad_daily"])
        with self.assertRaises(DatasetNotFound):
            g.describe("unknown")


if __name__ == "__main__":
    unittest.main()
