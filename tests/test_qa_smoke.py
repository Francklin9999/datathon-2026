"""T16 harness regressions: failed commands and timeouts cannot produce a pass."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "qa_smoke", Path(__file__).resolve().parents[1] / "scripts/qa_smoke.py"
)
QA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QA)


class FailureEvidence(unittest.TestCase):
    def run_failure(self, timeout):
        def failed(command, **kwargs):
            kwargs["stdout"].write("Deliberately failed harness regression\n")
            if timeout:
                raise subprocess.TimeoutExpired(command, 1)
            return SimpleNamespace(returncode=7)

        with tempfile.TemporaryDirectory() as directory:
            with patch("sys.argv", ["qa_smoke.py", "--output", directory]), \
                 patch.object(QA.subprocess, "run", side_effect=failed), \
                 patch.object(QA.subprocess, "check_output", return_value="a" * 40), \
                 patch.object(QA, "static_export") as static:
                self.assertEqual(QA.main(), 1)
                static.assert_not_called()
            report = json.loads((Path(directory) / "report.json").read_text())
            self.assertFalse(report["passed"])
            self.assertFalse(report["releaseReady"])
            self.assertEqual([s["exitCode"] for s in report["stages"]], [124 if timeout else 7] * 3)
            for stage in report["stages"]:
                self.assertTrue((Path(directory) / stage["log"]).is_file())

    def test_failed_commands_are_retained_and_fail_the_gate(self):
        self.run_failure(False)

    def test_timeouts_are_retained_and_fail_the_gate(self):
        self.run_failure(True)

    def test_existing_report_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            report.write_text("original evidence")
            with patch("sys.argv", ["qa_smoke.py", "--output", directory]):
                with self.assertRaisesRegex(RuntimeError, "new output directory"):
                    QA.main()
            self.assertEqual(report.read_text(), "original evidence")


class StaticDisclaimer(unittest.TestCase):
    HEAD = ('<html><head><meta name="description" content="Fictional-profile portfolio decision audit. '
            'Simulation only. Not financial advice."/></head>')
    NOTE = ('<p class="sim-pill" role="note" title="Simulation only. Fictional profiles. Not financial advice."'
            ' data-tour="disclaimer"><svg></svg><span class="sim-text" aria-hidden="true">Simulation, not advice'
            '</span><span class="sr-only">Simulation only. Fictional profiles. Not financial advice.</span></p>')

    def test_rendered_note_satisfies_the_check(self):
        self.assertTrue(QA.has_disclaimer(self.HEAD + "<body><header>" + self.NOTE + "</header></body></html>"))

    def test_head_metadata_alone_does_not_count(self):
        self.assertFalse(QA.has_disclaimer(self.HEAD + "<body><main><h1>Home</h1></main></body></html>"))

    def test_phrases_outside_the_note_do_not_count(self):
        body = ('<body><p class="sim-pill" role="note" title="Simulation, not advice">Simulation, not advice</p>'
                '<p>Simulation only. Not financial advice.</p></body></html>')
        self.assertFalse(QA.has_disclaimer(self.HEAD + body))


if __name__ == "__main__":
    unittest.main()
