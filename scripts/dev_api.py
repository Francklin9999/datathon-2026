#!/usr/bin/env python3
"""Start the local API with the active snapshot and every implemented feature switched on.

    uv run python scripts/dev_api.py            # http://localhost:8000/v1
    uv run python scripts/dev_api.py --port 8001 --no-reload

It only fills in settings that are not already in the environment, so an explicit
``APLOMB_*`` variable always wins; next come ``APLOMB_*`` lines of the git-ignored ``.env``
(on-demand tickers need ``APLOMB_TIINGO_TOKEN`` there or in the environment). It materializes the pinned snapshot under ``data/`` when it is
missing (idempotent, verified against the committed manifest) and never changes
``data/manifests/active.json``. A relative ``APLOMB_DATA_DIR`` is read from the repository root.
Run state is kept in ``.artifacts/aplomb-local-state.json`` (git-ignored).

Runs (decision, replay, briefs, profile drafts) and free-text parsing call Amazon Bedrock. They
need ``APLOMB_MODEL_STRONG`` / ``APLOMB_MODEL_FAST`` and AWS credentials; without model IDs the
API answers ``503`` for those and everything deterministic still works. No fixture stands in.
Research tools additionally need ``APLOMB_SOURCE_USER_AGENT`` with a contact URL or email.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Flags switched on for local work; /meta still advertises each only when its provider is available
# (api/domain.py default_services): on-demand tickers needs APLOMB_TIINGO_TOKEN (the local data
# directory is writable) and sabotage_demo needs both model IDs. Left off: research_open_web (no provider
# since the AgentCore Browser tool was removed; /meta reports it false) and guardrails (the API refuses
# to start without APLOMB_GUARDRAIL_ID and _VERSION; set its APLOMB_FEATURE_* variable to opt in).
FEATURES = ("bilingual", "world_explorer", "world_layer_hazards", "world_layer_facilities", "time_machine", "profile_creator",
            "goal_requests", "frontier_chart", "on_demand_tickers", "sabotage_demo")
# Git-ignored local settings (for example APLOMB_TIINGO_TOKEN). Only APLOMB_* keys are read.
ENV_FILE = ROOT / ".env"


def read_env_file(path: Path) -> dict[str, str]:
    """``APLOMB_*`` assignments with a non-empty value from a ``KEY=VALUE`` file; missing file → {}."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.removeprefix("export ").split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key.startswith("APLOMB_") and value:
            values[key] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    env = dict(os.environ)
    for key, value in read_env_file(ENV_FILE).items():
        env.setdefault(key, value)
    # Resolved after the .env merge so the version materialized below is the one the server is given.
    # The tracked pointer is read through the datastore, which also checks the version label.
    from aplomb.datastore import LocalDataStore
    manifests = ROOT / "data" / "manifests"
    version = env.get("APLOMB_DATA_VERSION") or LocalDataStore(ROOT / "data").active_version()
    manifest = json.loads((manifests / f"{version}.json").read_text(encoding="utf-8"))
    as_of = manifest["dataAsOf"]
    defaults = {
        "APLOMB_ENV": "local",
        "APLOMB_DATA_VERSION": version,
        "APLOMB_DATA_AS_OF": as_of,
        "APLOMB_DATA_DIR": str(ROOT / "data"),
        "APLOMB_LOCAL_STATE_FILE": str(ROOT / ".artifacts" / "aplomb-local-state.json"),
        "APLOMB_ALLOWED_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
        **{f"APLOMB_FEATURE_{flag.upper()}": "true" for flag in FEATURES},
    }
    # These no-key sources publish terms permitting local, noncommercial research. Limit
    # defaults to the local loopback server; explicit environment settings always win.
    # Never carry these rights assertions into the AWS composition or a network listener.
    if env.get("APLOMB_ENV", "local") == "local" and args.host in ("127.0.0.1", "localhost", "::1"):
        defaults.update({
            "APLOMB_COINMETRICS_NONCOMMERCIAL": "1",  # CC BY-NC, attribution required
            "APLOMB_BINANCE_VISION_NONCOMMERCIAL": "1",  # CC BY-NC-SA, personal research only
            "APLOMB_DEXSCREENER_RIGHTS_CONFIRMED": "true",  # noncommercial, noncompetitive local use
        })
    for key, value in defaults.items():
        env.setdefault(key, value)

    # The ingestion runs in backend/ and the server in the repository root: one absolute directory for both.
    data_dir = Path(env["APLOMB_DATA_DIR"])
    if not data_dir.is_absolute():
        data_dir = (ROOT / data_dir).resolve()
        env["APLOMB_DATA_DIR"] = str(data_dir)
    manifest_path = ROOT / "data" / "manifests" / f"{version}.json"
    pinned = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if "fx_boc_global" in pinned.get("datasets", {}) and not (data_dir / "normalized" / version).exists():
        from aplomb.datastore.global_fx import materialize_pinned_global_fx
        materialize_pinned_global_fx(data_dir, ROOT / "data", version)
    if not (data_dir / "normalized" / version).exists():
        print(f"Materializing snapshot {version} under {data_dir} ...", flush=True)
        # --no-activate: serving another version for one session must not rewrite the tracked active.json.
        done = subprocess.run(
            [sys.executable, "-m", "aplomb.datastore.ingest", "--source", str(ROOT / "Datathon2026" / "alphaforge_starter"),
             "--data-root", str(data_dir), "--version", version, "--no-activate"], cwd=ROOT / "backend", env=env)
        if done.returncode != 0:
            return done.returncode

    models = env.get("APLOMB_MODEL_STRONG") and env.get("APLOMB_MODEL_FAST")
    print(f"Aplomb API on http://{args.host}:{args.port}/v1  (snapshot {version}, data date {env['APLOMB_DATA_AS_OF']})")
    print("Runs and free-text parsing: " + ("Bedrock models configured" if models
                                             else "DISABLED (set APLOMB_MODEL_STRONG and APLOMB_MODEL_FAST, plus AWS credentials)"))
    command = [sys.executable, "-m", "uvicorn", "aplomb.api.app:app", "--host", args.host, "--port", str(args.port)]
    if not args.no_reload:
        command += ["--reload", "--reload-dir", str(ROOT / "backend")]
    return subprocess.call(command, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
