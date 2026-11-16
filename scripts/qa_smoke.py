"""Credential-free T16 gate with retained logs, HTTP controls and latency samples.

Run with `uv run python scripts/qa_smoke.py --output .artifacts/t16`.
No deployment, provider call, model stand-in or persistent application data is used.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
VERSION = "snap-20261113-starter"


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def summary(samples, target):
    ordered = sorted(samples)
    return {
        "n": len(samples), "samplesMs": samples,
        "medianMs": (ordered[(len(ordered) - 1) // 2] + ordered[len(ordered) // 2]) / 2,
        "p95Ms": ordered[math.ceil(len(ordered) * .95) - 1], "maxMs": max(samples),
        "targetMs": target, "allBelowTarget": max(samples) < target,
    }


def probe():
    # Explicit settings ignore any operator AWS/model configuration in the environment.
    from aplomb.api.app import create_default_app
    from aplomb.api.settings import Settings
    from aplomb.contracts.registry import adapter
    from aplomb.datastore.ingest import ingest_starter
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory(prefix="aplomb-t16-") as directory:
        ingest_starter(ROOT / "Datathon2026/alphaforge_starter", Path(directory), VERSION,
                       metadata_dir=ROOT / "data/inputs" / VERSION)
        started = time.perf_counter()
        app = create_default_app(Settings(data_version=VERSION, data_dir=directory))
        construction_ms = (time.perf_counter() - started) * 1000
        headers = {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}
        with TestClient(app) as client:
            def call(method, path, contract, body=None):
                start = time.perf_counter()
                response = client.request(method, "/v1" + path, headers=headers, json=body)
                elapsed = (time.perf_counter() - start) * 1000
                require(response.status_code == 200, f"{method} {path}: {response.status_code}")
                return adapter(contract).validate_json(response.content).to_wire(), elapsed

            _, first_read = call("GET", "/profiles", "ProfilesResponse")
            scenarios = [
                ("robert", "TSLA", 25, "conflict", 6.0),
                ("amira", "TSLA", 25, "conflict", 11.0),
                ("robert", "TSLA", 10, "conflict", 6.0),
                ("amira", "TSLA", 10, "tension", 11.0),
                ("mateo", "CNQ.TO", 10, "conflict", 0.0),
                ("robert", "BTC-USD", 5, "conflict", 0.0),
            ]

            def check_case(case):
                pid, ticker, size, verdict, cap = case
                body = {"profileId": pid, "move": {"ticker": ticker, "sizePct": size,
                                                       "funding": {"mode": "pro_rata"}}}
                result, elapsed = call("POST", "/check", "CheckResult", body)
                require((result["verdict"], result["maxCompatibleSizePct"]) == (verdict, cap),
                        f"Unexpected verdict/boundary for {pid}/{ticker}/{size}")
                return result, elapsed

            results = [check_case(case) for case in scenarios]
            robert = results[0][0]
            require(robert["counts"] == {"pass": 1, "tension": 1, "conflict": 6, "nee": 0, "info": 3}, "AT-01 counts")
            for key, expected in {"volatilityPct": 16.96, "maxDrawdownPct": 25.31,
                                  "stress2022Pct": -21.88}.items():
                require(abs(robert["portfolioAfter"]["metrics"][key] - expected) < .005, key)
            mateo = {c["ruleId"]: c for c in results[4][0]["ruleChecks"]}
            require(mateo["exclude.sector.energy"]["status"] == "conflict", "AT-03 Energy")
            require(mateo["evidence.controversy"]["status"] == "nee", "AT-03 missing evidence")
            crypto = {c["ruleId"]: c for c in results[5][0]["ruleChecks"]}
            require(crypto["exclude.asset_class.crypto"]["status"] == "conflict", "AT-05 crypto")
            for pid, verdict in (("robert", "compatible"), ("amira", "compatible"), ("mateo", "insufficient")):
                base, _ = call("POST", "/check", "CheckResult", {"profileId": pid, "move": None})
                require(base["verdict"] == verdict, f"AT-04 {pid}")
            held, _ = call("POST", "/check", "CheckResult", {
                "profileId": "amira", "move": {"ticker": "NVDA", "sizePct": 10,
                                                  "funding": {"mode": "new_money"}}})
            position = next(p for p in held["portfolioAfter"]["positions"] if p["ticker"] == "NVDA")
            require(abs(position["weightPct"] - 18 / 1.1) < 1e-9, "AT-18 denominator")
            require(abs(held["portfolioAfter"]["totalValue"] - 66000) < 1e-6, "AT-18 value")
            # Rotate personas and sizes: this is not twenty repeats of a single result.
            reads = [call("GET", f"/profiles/{pid}", "Profile")[1]
                     for pid in ("robert", "amira", "mateo", "robert") * 5]
            checks = [check_case(scenarios[i % len(scenarios)])[1] for i in range(20)]
            require(client.get("/v1/runs", headers=headers).json()["items"] == [], "Checks created runs")
    return {
        "environment": "in-process ASGI HTTP; temporary ingested starter snapshot; no models/providers",
        "dataVersion": VERSION, "asOf": "2026-11-12", "reportingCurrency": "CAD",
        "functionalControls": ["AT-01", "AT-02", "AT-03", "AT-04", "AT-05", "AT-18"],
        "scope": "HTTP control assertions only; UI and other requirements remain in acceptance.md",
        "constructionMs": construction_ms, "firstReadMs": first_read,
        "firstCheckMs": results[0][1], "warmReads": summary(reads, 500),
        "warmChecks": summary(checks, 1500),
        "coldStart": "Not measured: first local calls are not Lambda cold starts.",
    }


# The top-bar simulation note (SimPill): its title and sr-only text carry the full disclaimer.
SIM_NOTE = re.compile(r'<p\b(?=[^>]*\bclass="(?:[^"]* )?sim-pill[ "])(?=[^>]*\brole="note")[^>]*>.*?</p>', re.S)


def has_disclaimer(html):
    """True when the page body renders the simulation note with both phrases; <head> metadata does not count."""
    note = SIM_NOTE.search(html.partition("</head>")[2])
    return bool(note) and all(phrase in note.group(0) for phrase in ("Simulation only.", "Not financial advice."))


def static_export():
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    export = ROOT / "web/out"
    routes = ["/" + str(p.parent.relative_to(ROOT / "web/src/app")).replace(".", "").strip("/")
              for p in sorted((ROOT / "web/src/app").rglob("page.tsx"))]
    handler = functools.partial(QuietHandler, directory=str(export))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checked = []
    assets = set()
    try:
        for route in routes:
            url = f"http://127.0.0.1:{server.server_port}" + route.rstrip("/") + "/"
            with urlopen(url, timeout=10) as response:
                html = response.read().decode()
                require(response.status == 200, f"Static route failed: {route}")
                require(has_disclaimer(html), f"Missing disclaimer: {route}")
                assets.update(re.findall(r'(?:src|href)="(/_next/static/[^"?]+)', html))
            checked.append(route or "/")
        require(bool(assets), "No static assets found")
        for asset in sorted(assets):
            with urlopen(f"http://127.0.0.1:{server.server_port}{asset}", timeout=10) as response:
                require(response.status == 200 and bool(response.read()), f"Missing asset: {asset}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    return {"routes": checked, "assetsChecked": len(assets),
            "scope": "Direct static HTTP loads and disclaimer; hydration/keyboard/mobile not tested"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".artifacts/t16")
    parser.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe:
        save(args.output, probe())
        return 0
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / "report.json").exists(), "Choose a new output directory to retain earlier evidence")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    npm = shutil.which("npm")
    require(npm is not None, "npm is required")
    report = {"revision": revision, "workingTree": dirty.splitlines(),
              "startedAt": datetime.now(UTC).isoformat(), "platform": platform.platform(),
              "python": sys.version, "node": subprocess.check_output(["node", "--version"], text=True).strip(),
              "dataVersion": VERSION, "stages": [], "releaseReady": False,
              "scope": "Offline integration gate; does not certify all acceptance rows or cloud execution"}
    env = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1"}
    # Fixture mode must never silently replace this build's normal API client.
    env.pop("NEXT_PUBLIC_APLOMB_FIXTURES", None)
    commands = [("integration", [npm, "run", "check"], 900),
                ("static-build", [npm, "run", "build:web"], 300),
                ("http-controls", [sys.executable, str(Path(__file__).resolve()), "--probe",
                                   "--output", str(output / "http-controls.json")], 180)]
    for name, command, timeout in commands:
        print(f"Running {name} (log: {output / (name + '.log')})", flush=True)
        started = time.perf_counter()
        log = output / (name + ".log")
        with log.open("w", encoding="utf-8") as stream:
            try:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout, check=False)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
                stream.write(f"\nStage timed out after {timeout} seconds\n")
        report["stages"].append({"name": name, "command": command, "exitCode": code,
                                 "durationSeconds": time.perf_counter() - started,
                                 "log": log.name, "sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
        save(output / "report.json", report)
    if report["stages"][1]["exitCode"] == 0:
        try:
            report["staticExport"] = static_export()
        except Exception as exc:
            report["staticExport"] = {"error": str(exc)}
    report["finishedAt"] = datetime.now(UTC).isoformat()
    report["passed"] = (all(s["exitCode"] == 0 for s in report["stages"])
                        and "error" not in report.get("staticExport", {"error": "build failed"}))
    save(output / "report.json", report)
    print(f"{'PASS' if report['passed'] else 'FAIL'}: offline gate; {output / 'report.json'}", flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
