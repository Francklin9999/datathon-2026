#!/usr/bin/env python3
"""Start the local API with the active snapshot and every implemented feature switched on.

    uv run python scripts/dev_api.py            # http://localhost:8000/v1
    uv run python scripts/dev_api.py --port 8001 --no-reload

It only fills in settings that are not already in the environment, so an explicit
``APLOMB_*`` variable always wins. It materializes the pinned snapshot under ``data/`` when it is
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
# Flags with an implemented provider. Sabotage, on-demand tickers, open-web research, guardrails
# and the facilities layer have none, so switching them on here would change nothing.
FEATURES = ("bilingual", "world_explorer", "world_layer_hazards", "time_machine", "profile_creator",
            "goal_requests", "frontier_chart")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    manifests = ROOT / "data" / "manifests"
    version = os.environ.get("APLOMB_DATA_VERSION") or json.loads((manifests / "active.json").read_text(encoding="utf-8"))["dataVersion"]
    manifest = json.loads((manifests / f"{version}.json").read_text(encoding="utf-8"))
    as_of = manifest["dataAsOf"]

    env = dict(os.environ)
    defaults = {
        "APLOMB_ENV": "local",
        "APLOMB_DATA_VERSION": version,
        "APLOMB_DATA_AS_OF": as_of,
        "APLOMB_DATA_DIR": str(ROOT / "data"),
        "APLOMB_LOCAL_STATE_FILE": str(ROOT / ".artifacts" / "aplomb-local-state.json"),
        "APLOMB_ALLOWED_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
        **{f"APLOMB_FEATURE_{flag.upper()}": "true" for flag in FEATURES},
    }
    for key, value in defaults.items():
        env.setdefault(key, value)

    # The ingestion runs in backend/ and the server in the repository root: one absolute directory for both.
    data_dir = Path(env["APLOMB_DATA_DIR"])
    if not data_dir.is_absolute():
        data_dir = (ROOT / data_dir).resolve()
        env["APLOMB_DATA_DIR"] = str(data_dir)
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
