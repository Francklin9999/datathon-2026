#!/usr/bin/env python3
"""Offline checks for spec links, wire fixtures and selected numeric controls.

This does not validate a product implementation or replace the Pydantic contract suite.
"""
import contextlib
import hashlib
import io
import json
import math
import os
import re
import runpy
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []


def check(ok, message):
    if not ok:
        ERRORS.append(message)


def required(obj, names, where):
    check(isinstance(obj, dict), f"{where}: expected object")
    if isinstance(obj, dict):
        check(set(names.split()) <= obj.keys(), f"{where}: missing {set(names.split()) - obj.keys()}")


def close(actual, expected, tolerance, where):
    check(isinstance(actual, (int, float)) and math.isfinite(actual)
          and abs(actual - expected) <= tolerance, f"{where}: {actual} != {expected}")


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key}")
        result[key] = value
    return result


def load_fixture(name):
    return json.loads((ROOT / "contracts/fixtures" / name).read_text(encoding="utf-8"),
                      object_pairs_hook=no_duplicate_keys,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def check_links():
    documents = [ROOT / "README.md"]
    ignored = {"node_modules", ".venv", ".next", "out", "__pycache__", ".pytest_cache",
               "cdk.out", ".build", ".artifacts"}
    for folder in ("docs", "contracts", "backend", "data", "infra", "web", "tests"):
        for directory, subdirs, names in os.walk(ROOT / folder):
            subdirs[:] = [name for name in subdirs if name not in ignored]
            documents.extend(Path(directory) / name for name in names if name.endswith(".md"))
    for path in documents:
        content = path.read_text(encoding="utf-8")
        check(content.strip() not in ("pending", "TODO", ""), f"{path}: placeholder document")
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", content):
            target = target.strip().strip("<>")
            if urlsplit(target).scheme or target.startswith("#"):
                continue
            local = unquote(target.split("#")[0])
            check((path.parent / local).exists(), f"{path.relative_to(ROOT)}: broken link {target}")
    return len(documents)


def check_profiles(profiles):
    check([p["profileId"] for p in profiles] == ["robert", "amira", "mateo"], "profile order")
    for p in profiles:
        pid = p["profileId"]
        required(p, "profileId isDefault origin name initial age occupation riskLevel horizonYears objective objectiveText experience reportingCurrency preferences blurb personaTest portfolio rules version createdAt updatedAt", pid)
        close(sum(v["weightPct"] for v in p["portfolio"]["positions"]), 100, .01, f"{pid} weights")
        tickers = [v["ticker"] for v in p["portfolio"]["positions"]]
        check(len(tickers) == len(set(tickers)), f"{pid} duplicate holding")
        check(all(v["weightPct"] >= 0 for v in p["portfolio"]["positions"]), f"{pid} negative holding")
        check(p["portfolio"]["isFictional"] is True, f"{pid} not fictional")
        rule_ids = [r["ruleId"] for r in p["rules"]]
        check(len(rule_ids) == len(set(rule_ids)), f"{pid} duplicate rule")
        for i, rule in enumerate(p["rules"], 1):
            required(rule, "ruleId code type enabled label rationale metric target comparator threshold unit editable bounds origin isAssumption derivation countsInVerdict updatedAt", f"{pid} rule")
            check(rule["code"] == f"R{i}", f"{pid} rule order")
            check(set(rule["label"]) == {"en", "fr"}, f"{pid} bilingual labels")


def check_run(run, profiles):
    required(run, "runId kind status sessionId profileId parentRunId lang asOf dataVersion input steps facts evidence question result error flags usage createdAt updatedAt", "Run")
    check(run["flags"]["fixture"] is True, "fixture must be labelled")
    check(run["usage"]["llmCalls"] == 0, "fixture cannot claim model execution")
    facts = run["facts"]
    kinds = {"observed", "computed", "assumption", "input", "scenario", "rule_check", "evidence"}
    keys = []
    catalog = (ROOT / "contracts/catalog.md").read_text(encoding="utf-8")
    for fid, fact in facts.items():
        required(fact, "id key kind metric label value unit currency display subject period window asOf availableAt method inputs nObs sources limitations verification createdBy createdAt", fid)
        check(fid == fact["id"] and re.fullmatch(r"F-\d{3,}", fid), f"invalid Fact ID {fid}")
        check(fact["kind"] in kinds, f"{fid}: invalid FactKind {fact['kind']}")
        check(f"`{fact['metric']}`" in catalog, f"{fid}: unknown metric")
        check(f"`{fact['method']['id']}`" in catalog, f"{fid}: unknown method")
        keys.append(fact["key"])
        for source in fact["sources"]:
            required(source, "datasetId dataVersion sourceName sourceUrl retrievedOn licence rowsRead", fid + " source")
        check(set(fact["inputs"]) <= facts.keys(), f"{fid}: dangling inputs")
        if fact["availableAt"] is not None:
            check(fact["availableAt"][:10] <= run["asOf"], f"{fid}: future fact")
    check(len(keys) == len(set(keys)), "duplicate FactKey")
    visiting, visited = set(), set()

    def visit(fid):
        if fid in visiting:
            check(False, f"fact dependency cycle at {fid}")
            return
        if fid in visited:
            return
        visiting.add(fid)
        for child in facts[fid]["inputs"]:
            if child in facts:
                visit(child)
        visiting.remove(fid)
        visited.add(fid)

    for fid in facts:
        visit(fid)
    d = run["result"]["decision"]
    scenario = next(s for s in d["scenarios"] if s["scenarioId"] == d["selectedScenarioId"])
    rules = {r["ruleId"]: r for r in profiles[0]["rules"]}
    checks = scenario["ruleChecks"]
    check({c["ruleId"] for c in checks} == set(rules), "not every enabled rule checked")
    for c in checks:
        required(c, "ruleId code status value threshold unit comparator headroom worst valueFactId thresholdFactId detail neeReason evidenceIds", c["ruleId"])
        for key in ("valueFactId", "thresholdFactId"):
            check(c[key] is None or c[key] in facts, f"dangling {key} for {c['ruleId']}")
    for status in ("pass", "tension", "conflict", "nee", "info"):
        check(d["counts"][status] == sum(c["status"] == status for c in checks), f"wrong {status} count")
    check(d["verdict"] == "conflict" and d["counts"]["conflict"] == 6, "Robert verdict")
    for snap in (d["portfolioBefore"], scenario["portfolioAfter"]):
        close(sum(p["weightPct"] for p in snap["positions"]), 100, .000001, "snapshot weights")
        for fid in snap["metrics"]["factIds"].values():
            check(fid in facts, "snapshot dangling fact")
        check(snap["metrics"]["maxDrawdownPct"] >= 0, "API drawdown sign")
    brief = d["brief"]
    check({"facts", "assumptions", "limits"} <= {s["id"] for s in brief["sections"]}, "missing brief sections")
    for section in brief["sections"]:
        for sentence in section["sentences"]:
            for seg in sentence["segments"]:
                if seg["t"] == "fact":
                    check(seg["factId"] in facts, "brief dangling fact")
                    check(seg["display"] == facts[seg["factId"]]["display"]["en"], "brief display mismatch")
                elif seg["t"] in ("rule", "status"):
                    check(seg["ruleId"] in rules, "brief dangling rule")
                elif seg["t"] == "evidence":
                    check(seg["evidenceId"] in run["evidence"], "brief dangling evidence")
    canonical = json.dumps({"facts": facts, "evidence": run["evidence"]}, sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    check(hashlib.sha256(canonical.encode()).hexdigest() == brief["audit"]["ledgerHash"], "ledger hash mismatch")
    check([s["seq"] for s in run["steps"]] == list(range(1, len(run["steps"]) + 1)), "step ordering")
    for step in run["steps"]:
        check(set(step["factIds"]) <= facts.keys(), "step dangling fact")


def check_controls(profiles, run):
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(ROOT / "contracts/controls/controls.py"), str(ROOT / "Datathon2026/alphaforge_starter")]
        with contextlib.redirect_stdout(io.StringIO()):
            ref = runpy.run_path(sys.argv[0])
    finally:
        sys.argv = old_argv
    check(len(ref["master"]) == 1228, "master calendar changed")
    check(sum(len(rows) for rows in ref["px"].values()) == 40049, "price count changed")
    for profile in profiles:
        pid = profile["profileId"]
        close(sum(ref["P"][pid].values()), 1, 1e-9, pid + " reference weights")
        check({p["ticker"] for p in profile["portfolio"]["positions"]} == set(ref["P"][pid]), pid + " holdings changed")
        for p in profile["portfolio"]["positions"]:
            close(p["weightPct"], 100 * ref["P"][pid][p["ticker"]], 1e-9, pid + " fixture weight")
    s = ref["stats"](ref["move_prorata"](ref["P"]["robert"], "TSLA", .25))
    close(s["vol"] * 100, 16.96, .005, "Robert volatility control")
    close(-s["mdd"] * 100, 25.31, .005, "Robert drawdown control")
    close(-s["r22"] * 100, 21.88, .005, "Robert stress control")
    metrics = run["result"]["decision"]["scenarios"][0]["portfolioAfter"]["metrics"]
    for name, value in (("volatilityPct", s["vol"] * 100), ("maxDrawdownPct", -s["mdd"] * 100), ("stress2022Pct", s["r22"] * 100)):
        close(metrics[name], value, 1e-9, name + " fixture consistency")


def check_delivery():
    """Listed delivery artifacts must exist, retain provenance and match their recorded hashes."""
    folder = ROOT / "docs/deliverables"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    files = {artifact["file"] for artifact in manifest["artifacts"]}
    check({"README.md", "demo.md", "technical.md", "one-pager.md"} <= files,
          "delivery: incomplete artifact manifest")
    for artifact in manifest["artifacts"]:
        path = (folder / artifact["file"]).resolve()
        check(path.is_relative_to(ROOT) and path.is_file(), "delivery: missing/outside artifact")
        if path.is_relative_to(ROOT) and path.is_file():
            check(hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"],
                  f"delivery: changed artifact {artifact['file']}; refresh manifest")
        check(bool(re.fullmatch(r"[0-9a-f]{40}", artifact["codeRevision"])),
              "delivery: revision must be a full git hash")
        captured = datetime.fromisoformat(artifact["capturedAt"].replace("Z", "+00:00"))
        check(captured.utcoffset() is not None and captured.utcoffset().total_seconds() == 0,
              "delivery: capture time must be UTC")
        check(artifact["kind"] in {"runtime", "offline-check", "historical-runtime", "illustrative"},
              "delivery: unknown evidence kind")


def main():
    count = check_links()
    profiles = load_fixture("profiles.json")["items"]
    run = load_fixture("run.decision.robert-tsla-25.json")
    world = load_fixture("world.events.sample.json")
    check_profiles(profiles)
    check_run(run, profiles)
    check_controls(profiles, run)
    check_delivery()
    required(world, "items nextCursor total coverage dataVersion", "world response")
    check(world["total"] == len(world["items"]), "world count")
    for event in world["items"]:
        check(bool(event["sources"]), "event missing source")
        source_url = event["sources"][0]["url"]
        check(event["eventId"] == "evt_" + hashlib.sha1(source_url.encode()).hexdigest()[:12], "event ID hash")
    if ERRORS:
        print("\n".join("FAIL: " + error for error in ERRORS))
        return 1
    print(f"PASS: {count} specification documents linked; 3 fixtures validated; numeric controls reproduced.")
    print("PASS: delivery artifact hashes and provenance validated.")
    print("Application runtime, live sources and AWS execution are not verified by this check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
