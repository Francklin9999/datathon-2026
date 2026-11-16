"""Regression tests for the audit of the Sources page: passports and traps must describe what is
loaded now, and ``scripts/dev_api.py`` must neither move the tracked active pointer nor depend on
the directory it is started from."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from aplomb.contracts import models as m
from aplomb.datastore import LocalDataStore, passports
from aplomb.datastore import constants as C
from aplomb.datastore import ingest as ingest_cli

from ._support import REPO, STARTER_VERSION, ingest_synthetic, starter_snapshot, temp_root
from .test_sourced import SOURCED, sourced_snapshot

DEFAULTS = json.loads((REPO / "backend" / "aplomb" / "profiles" / "defaults.json").read_text(encoding="utf-8"))


def texts(passport: dict) -> str:
    return " | ".join(step[lang] for step in passport["processing"] for lang in ("en", "fr"))


class ReleaseDatesPassport(unittest.TestCase):

    def test_loaded_passport_describes_the_loaded_dataset(self):
        p = sourced_snapshot().passport("macro_release_dates")
        self.assertEqual((p["status"], p["rowCount"]), ("in_use", 58))
        self.assertNotIn("planned", p["accessMethod"])
        self.assertIn("data/metadata/macro_release_dates.csv", p["accessMethod"])
        self.assertNotIn("Not loaded", texts(p))
        self.assertNotIn("Non chargé", texts(p))
        self.assertIn("The Daily", texts(p))
        self.assertIn("Statistics Canada", p["source"])
        self.assertEqual(p["licence"], "Statistics Canada Open Licence")
        self.assertEqual(p["licenceUrl"], "https://www.statcan.gc.ca/en/terms-conditions/open-licence")
        m.DatasetPassport.model_validate(p)

    def test_retrieval_date_is_the_recorded_read_date_not_the_build_time(self):
        # data/SOURCES.md: the 58 articles were read on 2026-11-14; the test snapshot is built by a
        # clock fixed on the same day, the committed manifest was built on 2026-11-15 UTC.
        self.assertEqual(sourced_snapshot().passport("macro_release_dates")["retrievedOn"], "2026-11-14")
        committed = json.loads((REPO / "data" / "manifests" / f"{SOURCED}.json").read_text(encoding="utf-8"))
        self.assertEqual(committed["createdAt"][:10], "2026-11-15")
        self.assertEqual(passports.build_passport("macro_release_dates", committed)["retrievedOn"], "2026-11-14")

    def test_unrecorded_read_date_stays_unknown(self):
        root = temp_root()
        ingest_synthetic(root, with_releases=True)
        p = LocalDataStore(root).open("snap-20240101-syn").passport("macro_release_dates")
        self.assertEqual(p["status"], "in_use")
        self.assertIsNone(p["retrievedOn"])
        self.assertNotIn("Not loaded", texts(p))
        self.assertNotIn("Statistics Canada", p["source"] + texts(p))

    def test_snapshot_without_the_dataset_stays_planned(self):
        p = starter_snapshot().passport("macro_release_dates")
        self.assertEqual((p["status"], p["rowCount"], p["retrievedOn"]), ("planned", None, None))
        self.assertTrue(p["accessMethod"].startswith("planned"))
        self.assertTrue(p["processing"][0]["en"].startswith("Not loaded"))


class ThemesPassport(unittest.TestCase):

    def test_sourced_snapshot_names_the_quoted_pages(self):
        p = sourced_snapshot().passport("asset_themes")
        self.assertIn("36 of 44", p["source"])
        self.assertNotIn("no third-party content", p["licence"])
        self.assertIn("third-party pages", p["licence"])
        self.assertIsNone(p["sourceUrl"])
        self.assertIn("issuer or project page", texts(p))
        self.assertIn("page de l'émetteur ou du projet", texts(p))

    def test_starter_snapshot_keeps_the_universe_file_wording(self):
        p = starter_snapshot().passport("asset_themes")
        self.assertEqual(p["licence"], "Team-authored metadata; no third-party content")
        self.assertIn("based on the organizer universe file", p["source"])
        self.assertNotIn("issuer or project page", texts(p))


class DefaultProfilesPassport(unittest.TestCase):

    def test_in_use_with_the_shipped_personas(self):
        for snap in (starter_snapshot(), sourced_snapshot()):
            p = snap.passport("default_profiles")
            self.assertEqual(tuple(p), passports.PASSPORT_KEYS)
            self.assertEqual((p["status"], p["rowCount"]), ("in_use", len(DEFAULTS)))
            self.assertEqual(p["rowCount"], 3)
            self.assertTrue(p["licence"].lower().startswith("team-authored, fictional"))
            self.assertNotIn("unknown", p["licence"])
            self.assertIn("backend/aplomb/profiles/defaults.json", p["accessMethod"])
            self.assertEqual((p["dataVersion"], p["retrievedOn"], p["sourceUrl"]), (None, None, None))
            self.assertNotIn("Registered by T06", texts(p))
            self.assertEqual(p["limitations"], ["LIM_SIMULATION_ONLY"])
            (check,) = p["checks"]
            self.assertTrue(check["ok"])
            for profile in DEFAULTS:
                self.assertIn(profile["profileId"], check["detail"])
            m.DatasetPassport.model_validate(p)

    def test_planned_when_the_personas_cannot_be_read(self):
        broken = temp_root() / "defaults.json"
        for content in (None, "not json", "[]", json.dumps([{**DEFAULTS[0], "isDefault": False}])):
            if content is not None:
                broken.write_text(content, encoding="utf-8")
            with mock.patch.object(passports, "DEFAULT_PROFILES_PATH", broken):
                p = passports.build_passport("default_profiles", None)
            self.assertEqual((p["status"], p["rowCount"], p["checks"]), ("planned", None, []), content)
            self.assertEqual(p["licence"], "unknown (not yet reviewed)")


class Traps(unittest.TestCase):

    def test_fx_trap_is_handled_and_cites_existing_tests(self):
        by_code = {t["code"]: t for t in passports.traps()}
        fx = by_code[C.LIM_FX_FFILL]
        self.assertEqual(fx["status"], "handled")
        self.assertNotIn("pending", fx["handledBy"])
        self.assertNotIn("QNT-01", fx["handledBy"])
        quant_tests = (REPO / "backend" / "tests" / "unit" / "quant" / "test_quant.py").read_text(encoding="utf-8")
        for label in ("QNT-02", "QNT-06"):
            self.assertIn(label, fx["handledBy"])
            self.assertIn(f"{label}", quant_tests)
        # US monthly series still have no release data (data/SOURCES.md: "open until evidence exists").
        self.assertEqual(by_code[C.LIM_MACRO_LAG_ASSUMED]["status"], "open")


def load_dev_api():
    spec = importlib.util.spec_from_file_location("aplomb_dev_api_script", REPO / "scripts" / "dev_api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DevApiScript(unittest.TestCase):
    """The script is run with its two subprocess calls replaced; no server is started."""

    def run_script(self, env: dict[str, str], ingest, env_file: Path | None = None) -> dict:
        script = load_dev_api()
        script.ENV_FILE = env_file or temp_root() / "absent.env"  # never the developer's own .env
        seen: dict = {}

        def fake_run(command, cwd=None, env=None):
            seen["ingest"], seen["ingest_cwd"], seen["ingest_env"] = list(command), cwd, dict(env)
            return SimpleNamespace(returncode=ingest(list(command)))

        def fake_call(command, cwd=None, env=None):
            seen["server"], seen["server_env"] = list(command), dict(env)
            return 0

        clean = {k: v for k, v in os.environ.items() if not k.startswith("APLOMB_")}
        with mock.patch.dict(os.environ, {**clean, **env}, clear=True), \
                mock.patch.object(sys, "argv", ["dev_api.py", "--no-reload"]), \
                mock.patch.object(script.subprocess, "run", fake_run), \
                mock.patch.object(script.subprocess, "call", fake_call), \
                mock.patch("builtins.print"):
            seen["exit"] = script.main()
        return seen

    def test_relative_data_dir_is_resolved_against_the_repository_root(self):
        root = temp_root().resolve()
        try:
            relative = os.path.relpath(root, REPO)
        except ValueError:  # Windows: temporary directory on another drive
            self.skipTest("temporary directory and repository are on different drives")
        self.assertFalse(Path(relative).is_absolute())
        here = os.getcwd()
        os.chdir(REPO / "backend")  # the directory the ingestion subprocess runs in
        try:
            seen = self.run_script({"APLOMB_DATA_DIR": relative, "APLOMB_DATA_VERSION": SOURCED}, lambda command: 0)
        finally:
            os.chdir(here)
        data_root = Path(seen["ingest"][seen["ingest"].index("--data-root") + 1])
        self.assertTrue(data_root.is_absolute())
        self.assertEqual(data_root, root)
        for env in (seen["ingest_env"], seen["server_env"]):
            self.assertEqual(Path(env["APLOMB_DATA_DIR"]), root)

    def test_materializing_another_version_keeps_the_active_pointer(self):
        root = temp_root()
        shutil.copytree(REPO / "data" / "manifests", root / "manifests")
        shutil.copytree(REPO / "data" / "inputs" / STARTER_VERSION, root / "inputs" / STARTER_VERSION)
        pointer = root / "manifests" / "active.json"
        pointer.write_text(json.dumps({"dataVersion": SOURCED}), encoding="utf-8")
        before = pointer.read_bytes()

        def ingest(command: list[str]) -> int:
            return ingest_cli.main(command[command.index("aplomb.datastore.ingest") + 1:])

        seen = self.run_script({"APLOMB_DATA_DIR": str(root), "APLOMB_DATA_VERSION": STARTER_VERSION}, ingest)
        self.assertEqual(seen["exit"], 0)
        self.assertTrue((root / "normalized" / STARTER_VERSION).is_dir())
        self.assertEqual(pointer.read_bytes(), before)
        self.assertEqual(seen["server_env"]["APLOMB_DATA_VERSION"], STARTER_VERSION)

    def test_env_file_fills_missing_settings_and_never_overrides_the_environment(self):
        root = temp_root()
        env_file = root / ".env"
        env_file.write_text("# local\nAPLOMB_TIINGO_TOKEN='file-token'\nAPLOMB_FEATURE_BILINGUAL=false\n"
                            "APLOMB_EMPTY=\nOTHER_KEY=ignored\nnot a pair\n", encoding="utf-8")
        version = json.loads((REPO / "data" / "manifests" / "active.json").read_text(encoding="utf-8"))["dataVersion"]
        (root / "normalized" / version).mkdir(parents=True)  # nothing to materialize
        seen = self.run_script({"APLOMB_DATA_DIR": str(root), "APLOMB_FEATURE_BILINGUAL": "true"},
                               lambda command: 1, env_file=env_file)
        server = seen["server_env"]
        self.assertEqual(seen["exit"], 0)
        self.assertNotIn("ingest", seen)
        self.assertEqual(server["APLOMB_TIINGO_TOKEN"], "file-token")
        self.assertEqual(server["APLOMB_FEATURE_BILINGUAL"], "true")  # the environment wins
        self.assertEqual(server["APLOMB_FEATURE_ON_DEMAND_TICKERS"], "true")
        self.assertNotIn("APLOMB_EMPTY", server)
        self.assertNotIn("OTHER_KEY", server)

    def test_env_file_version_is_the_one_materialized_and_served(self):
        root = temp_root()
        env_file = root / ".env"
        env_file.write_text(f"APLOMB_DATA_VERSION={SOURCED}\n", encoding="utf-8")
        active = json.loads((REPO / "data" / "manifests" / "active.json").read_text(encoding="utf-8"))["dataVersion"]
        self.assertNotEqual(active, SOURCED)  # otherwise the test cannot tell the two sources apart
        (root / "normalized" / active).mkdir(parents=True)  # only the active version is present
        seen = self.run_script({"APLOMB_DATA_DIR": str(root)}, lambda command: 0, env_file=env_file)
        self.assertEqual(seen["exit"], 0)
        self.assertEqual(seen["ingest"][seen["ingest"].index("--version") + 1], SOURCED)
        self.assertEqual(seen["server_env"]["APLOMB_DATA_VERSION"], SOURCED)

    def test_unset_version_comes_from_the_datastore_active_pointer(self):
        root = temp_root()
        (root / "normalized" / SOURCED).mkdir(parents=True)  # nothing to materialize
        with mock.patch.object(LocalDataStore, "active_version", autospec=True, return_value=SOURCED) as active:
            seen = self.run_script({"APLOMB_DATA_DIR": str(root)}, lambda command: 1)
        self.assertEqual(seen["exit"], 0)
        self.assertEqual(Path(active.call_args.args[0].root), REPO / "data")  # the tracked pointer, not DATA_DIR
        self.assertNotIn("ingest", seen)
        self.assertEqual(seen["server_env"]["APLOMB_DATA_VERSION"], SOURCED)

    def test_env_example_copied_to_env_keeps_the_dev_api_flags_and_active_version(self):
        # README: dev:api reads the git-ignored .env; a verbatim copy of .env.example must not undo its defaults.
        root = temp_root()
        active = LocalDataStore(REPO / "data").active_version()
        (root / "normalized" / active).mkdir(parents=True)  # nothing to materialize
        seen = self.run_script({"APLOMB_DATA_DIR": str(root)}, lambda command: 1, env_file=REPO / ".env.example")
        server = seen["server_env"]
        self.assertEqual(seen["exit"], 0)
        self.assertNotIn("ingest", seen)
        self.assertEqual(server["APLOMB_DATA_VERSION"], active)
        script = load_dev_api()
        for flag in script.FEATURES:
            self.assertEqual(server[f"APLOMB_FEATURE_{flag.upper()}"], "true", flag)
        for flag in ("research_open_web", "guardrails"):  # opt-in only, in both places
            self.assertNotIn(flag, script.FEATURES)
            self.assertEqual(server[f"APLOMB_FEATURE_{flag.upper()}"], "false", flag)
        self.assertEqual(server["APLOMB_ALLOWED_ORIGINS"], "http://localhost:3000,http://127.0.0.1:3000")

    def test_missing_env_file_reads_nothing(self):
        self.assertEqual(load_dev_api().read_env_file(temp_root() / "absent.env"), {})


if __name__ == "__main__":
    unittest.main()
