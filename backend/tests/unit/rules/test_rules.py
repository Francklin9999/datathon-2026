"""RUL-01..RUL-12 against contracts/controls.md §8–§9."""

from __future__ import annotations

import unittest

from aplomb.contracts.models import Evidence, PolicyRule
from aplomb.rules.definitions import FIXED, rule_def
from aplomb.rules.engine import compare, explain_difference
from aplomb.rules.templates import TEMPLATES

from ._support import PROFILES, evaluate


def statuses(checks):
    return {rid: c.status for rid, c in checks.items()}


def counted(counts):
    return (counts.conflict, counts.tension, counts.pass_)


def evidence(ticker: str, tier: int, status: str, eid: str = "E-001") -> Evidence:
    return Evidence.model_validate({
        "id": eid, "type": "news", "tier": tier, "title": "t", "publisher": "p", "url": "https://example.invalid/x",
        "publishedAt": None, "retrievedAt": "2026-11-14T10:00:00Z", "lang": "en", "quote": "q",
        "claim": {"en": "controversy", "fr": "controverse"}, "subject": {"type": "asset", "id": ticker},
        "tool": "web.fetch", "documentRef": None, "licence": "unknown",
        "verification": {"status": status, "checks": []}})


class Baselines(unittest.TestCase):
    """RUL-01 / AT-04."""

    def test_baselines(self):
        for pid, verdict in (("robert", "compatible"), ("amira", "compatible"), ("mateo", "insufficient")):
            v, counts, checks, _ = evaluate(pid)
            self.assertEqual(v, verdict, pid)
            self.assertEqual((counts.conflict, counts.tension), (0, 0), pid)
        _, counts, checks, _ = evaluate("mateo")
        self.assertEqual(checks["evidence.controversy"].status, "nee")
        self.assertEqual(checks["evidence.controversy"].nee_reason, "no_evidence_loaded")
        self.assertEqual(counts.nee, 1)
        _, counts, _, _ = evaluate("robert")
        self.assertEqual((counts.pass_, counts.info), (8, 3))


class Scenarios(unittest.TestCase):

    def test_robert_tsla_25(self):  # RUL-02 / AT-01
        v, counts, checks, ledger = evaluate("robert", ("TSLA", 25, "pro_rata"))
        self.assertEqual(v, "conflict")
        self.assertEqual(counted(counts), (6, 1, 1))
        self.assertEqual(counts.info, 3)
        self.assertEqual(statuses(checks), {
            "cap.position": "conflict", "cap.sector": "conflict", "cap.growth_assets": "conflict", "floor.fixed_income": "tension",
            "limit.volatility": "conflict", "limit.stress_2022": "conflict", "limit.drawdown": "conflict",
            "exclude.asset_class.crypto": "pass", "flag.attention": "info", "flag.rate_cycle": "info", "sim.only": "info"})
        expected = {"cap.position": 25.0, "cap.sector": 25.0, "cap.growth_assets": 60.25, "floor.fixed_income": 37.5,
                    "limit.volatility": 16.96, "limit.stress_2022": 21.88, "limit.drawdown": 25.31}
        for rid, value in expected.items():
            self.assertAlmostEqual(checks[rid].value, value, delta=0.005, msg=rid)
        c = checks["cap.position"]
        self.assertEqual(c.worst.id, "TSLA")
        self.assertAlmostEqual(c.headroom, -15.0)
        self.assertEqual(c.detail.en, "Largest single position would be TSLA at 25.00%, above the 10.00% cap.")
        self.assertEqual(c.detail.fr, "La plus grande position serait TSLA à 25,00 %, au-dessus du plafond de 10,00 %.")
        self.assertAlmostEqual(checks["floor.fixed_income"].headroom, 2.5)
        stress = ledger.get_fact(checks["limit.stress_2022"].value_fact_id)
        self.assertGreater(stress.value, 0)
        self.assertEqual(len(stress.inputs), 1)
        self.assertLess(ledger.get_fact(stress.inputs[0]).value, 0)
        self.assertEqual(ledger.get_fact(checks["cap.position"].threshold_fact_id).value, 10.0)
        self.assertEqual(checks["flag.rate_cycle"].value, checks["flag.rate_cycle"].value)
        self.assertAlmostEqual(checks["flag.rate_cycle"].value, 4.07, delta=0.005)

    def test_amira_tsla_25(self):  # RUL-03 / AT-02
        v, counts, checks, _ = evaluate("amira", ("TSLA", 25, "pro_rata"))
        self.assertEqual(v, "conflict")
        self.assertEqual(counted(counts), (3, 2, 2))
        self.assertEqual(checks["cap.position"].status, "tension")  # exactly at the cap is tension
        self.assertAlmostEqual(checks["cap.sector"].value, 28.75, delta=0.005)
        self.assertAlmostEqual(checks["floor.diversifiers"].value, 7.5, delta=0.005)
        self.assertEqual(checks["floor.diversifiers"].status, "conflict")
        self.assertEqual(checks["limit.drawdown"].status, "tension")

    def test_at02_size_10(self):
        rv, *_ = evaluate("robert", ("TSLA", 10, "pro_rata"))
        av, *_ = evaluate("amira", ("TSLA", 10, "pro_rata"))
        self.assertEqual((rv, av), ("conflict", "tension"))

    def test_mateo_cnq(self):  # RUL-04 / AT-03
        v, counts, checks, _ = evaluate("mateo", ("CNQ.TO", 10, "pro_rata"))
        self.assertEqual(v, "conflict")
        self.assertEqual((counts.conflict, counts.nee), (1, 1))
        self.assertEqual(checks["exclude.sector.energy"].status, "conflict")
        self.assertEqual(checks["exclude.sector.energy"].worst.id, "CNQ.TO")
        financial = ["cap.position", "cap.sector", "cap.growth_assets", "floor.fixed_income", "limit.volatility",
                     "limit.stress_2022", "limit.drawdown", "cap.asset_class.crypto"]
        self.assertTrue(all(checks[r].status == "pass" for r in financial))
        self.assertEqual(checks["evidence.controversy"].status, "nee")

    def test_robert_small_and_crypto(self):  # RUL-05, RUL-06 / AT-05
        v, *_ = evaluate("robert", ("TSLA", 2, "pro_rata"))
        self.assertEqual(v, "compatible")
        v, _, checks, _ = evaluate("robert", ("BTC-USD", 5, "pro_rata"))
        self.assertEqual(v, "conflict")
        self.assertEqual(checks["exclude.asset_class.crypto"].status, "conflict")
        self.assertEqual(checks["cap.growth_assets"].status, "tension")
        self.assertEqual(checks["limit.stress_2022"].status, "tension")

    def test_mateo_tsla_25(self):
        _, _, checks, _ = evaluate("mateo", ("TSLA", 25, "pro_rata"))
        for rid in ("cap.position", "limit.volatility", "limit.stress_2022", "limit.drawdown"):
            self.assertEqual(checks[rid].status, "conflict", rid)


class Edits(unittest.TestCase):

    def edited(self, pid, rule_id, **changes):
        rules = []
        for r in PROFILES[pid].rules:
            data = r.to_wire()
            if r.rule_id == rule_id:
                data.update(changes)
            rules.append(PolicyRule.model_validate(data))
        return rules

    def test_disabled_rule_removed(self):  # RUL-07
        rules = self.edited("mateo", "evidence.controversy", enabled=False)
        v, counts, checks, _ = evaluate("mateo", rules=rules)
        self.assertNotIn("evidence.controversy", checks)
        self.assertEqual(v, "compatible")

    def test_raised_stress_limit(self):  # RUL-08
        rules = self.edited("robert", "limit.stress_2022", threshold=25.0)
        v, _, checks, _ = evaluate("robert", ("TSLA", 25, "pro_rata"), rules=rules)
        self.assertEqual(checks["limit.stress_2022"].status, "pass")
        self.assertEqual(v, "conflict")


class Unavailable(unittest.TestCase):

    def test_metric_unavailable_gives_nee(self):  # RUL-09
        v, counts, checks, _ = evaluate("robert", as_of="2022-06-30", mode="historical")
        self.assertEqual(checks["limit.stress_2022"].status, "nee")
        self.assertEqual(checks["limit.stress_2022"].nee_reason, "not_visible_at_asof")
        self.assertEqual(checks["cap.position"].status, "pass")
        self.assertEqual(checks["limit.volatility"].status, "nee")  # fewer than 252 master observations
        self.assertEqual(checks["limit.volatility"].nee_reason, "short_history")
        self.assertEqual(v, "insufficient")


class Evidence_(unittest.TestCase):

    def test_controversy_evidence(self):  # RUL-10
        _, _, checks, _ = evaluate("mateo", ("CNQ.TO", 10, "pro_rata"), evidence=[evidence("CNQ.TO", 2, "verified")])
        c = checks["evidence.controversy"]
        self.assertEqual(c.status, "tension")
        self.assertEqual(c.evidence_ids, ["E-001"])
        _, _, checks, _ = evaluate("mateo", ("CNQ.TO", 10, "pro_rata"), evidence=[evidence("CNQ.TO", 3, "verified")])
        self.assertEqual((checks["evidence.controversy"].status, checks["evidence.controversy"].nee_reason), ("nee", "evidence_unverified"))
        _, _, checks, _ = evaluate("mateo", ("CNQ.TO", 10, "pro_rata"), evidence=[evidence("CNQ.TO", 1, "unverified")])
        self.assertEqual(checks["evidence.controversy"].status, "nee")
        _, _, checks, _ = evaluate("mateo", ("CNQ.TO", 10, "pro_rata"), evidence=[evidence("XOM", 1, "verified")])
        self.assertEqual(checks["evidence.controversy"].nee_reason, "no_evidence_loaded")  # not a moved asset


class Compare(unittest.TestCase):

    def test_explain_difference(self):  # RUL-11
        _, _, a, _ = evaluate("robert", ("TSLA", 25, "pro_rata"))
        _, _, b, _ = evaluate("amira", ("TSLA", 25, "pro_rata"))
        diff = {d["ruleId"]: d for d in explain_difference(list(a.values()), list(b.values()))}
        self.assertEqual(diff["cap.position"]["reason"], "threshold_differs")
        self.assertEqual((diff["cap.position"]["statusA"], diff["cap.position"]["statusB"]), ("conflict", "tension"))
        self.assertEqual(diff["cap.growth_assets"]["reason"], "rule_only_in_a")
        self.assertEqual(diff["floor.diversifiers"]["reason"], "rule_only_in_b")
        self.assertEqual(diff["sim.only"]["reason"], "same")


class TemplatesAndComparisons(unittest.TestCase):

    def test_every_pair_has_both_languages(self):  # RUL-12
        for key, text in TEMPLATES.items():
            self.assertTrue(text["en"] and text["fr"], key)
        needed = [("cap.position", s) for s in ("pass", "tension", "conflict")] + [("cap.sector", s) for s in ("pass", "tension", "conflict")] \
            + [("cap.group", s) for s in ("pass", "tension", "conflict")] + [("floor", s) for s in ("pass", "tension", "conflict")] \
            + [(f, s) for f in ("limit.volatility", "limit.stress_2022", "limit.drawdown") for s in ("pass", "tension", "conflict")] \
            + [("exclude", "pass"), ("exclude", "conflict"), ("evidence", "nee"), ("evidence", "tension"), ("sim", "info"),
               ("flag.attention", "info"), ("flag.attention", "info_missing"), ("flag.rate_cycle", "info"), ("flag.rate_cycle", "info_missing")] \
            + [("any", f"nee:{r}") for r in ("short_history", "not_visible_at_asof", "asset_unknown", "dataset_missing")]
        for key in needed:
            self.assertIn(key, TEMPLATES)

    def test_compare_band(self):
        self.assertEqual(compare("cap", 25.0, 25.0), "tension")
        self.assertEqual(compare("cap", 22.5, 25.0), "pass")
        self.assertEqual(compare("cap", 22.6, 25.0), "tension")
        self.assertEqual(compare("cap", 25.0000001, 25.0), "conflict")
        self.assertEqual(compare("floor", 35.0, 35.0), "tension")
        self.assertEqual(compare("floor", 38.5, 35.0), "pass")
        self.assertEqual(compare("floor", 34.99, 35.0), "conflict")
        self.assertEqual(compare("exclude", 0.0, 0.0), "pass")
        self.assertEqual(compare("exclude", 0.01, 0.0), "conflict")

    def test_definitions(self):
        self.assertEqual(rule_def("exclude.sector.energy").target_key, "Energy")
        self.assertEqual(rule_def("cap.theme.ai").key, "ai")
        for rid, d in FIXED.items():
            self.assertTrue(d.label["en"] and d.label["fr"], rid)


if __name__ == "__main__":
    unittest.main()
