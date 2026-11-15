"""Local HTTP target workflow; fresh inference is supplied through official AWS MCP.

Service each request-NNN.json via Bedrock Converse, writing its matching response.
Financial inputs are unchanged competition starter observations, not live prices.
This harness does not access AWS credentials or deploy an application.
"""

import argparse
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from aplomb.api.app import create_app
from aplomb.api.domain import default_services
from aplomb.api.settings import Settings
from aplomb.api.storage import FileStore
from aplomb.datastore.ingest import ingest_starter
from fastapi.testclient import TestClient
from live_agents_smoke import McpFileGateway, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--kind", choices=["rebalance", "portfolio_brief"], default="rebalance")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    model = "us.anthropic.claude-sonnet-4-6"
    gateway = McpFileGateway(args.directory, model, model)
    with TemporaryDirectory(prefix="aplomb-a2-live-data-") as data:
        version = "snap-20261113-starter"
        ingest_starter(root / "Datathon2026/alphaforge_starter", Path(data), version,
                       metadata_dir=root / "data/inputs" / version)
        settings = Settings(data_version=version, data_dir=data, model_strong=model, model_fast=model)
        store = FileStore(args.directory / "state.json")
        services = default_services(settings, store=store, gateway=gateway)
        session = "s_" + str(uuid.uuid4())
        headers = {"X-Aplomb-Session": session, "Idempotency-Key": "a2-live-" + args.kind}
        profile = services.profiles.get(session, "robert")
        body = {"kind": args.kind, "profileId": profile.profile_id, "lang": "en"}
        if args.kind == "rebalance":
            body.update(profileVersion=profile.version,
                        positions=[p.to_wire() for p in profile.portfolio.positions])
        with TestClient(create_app(settings, services)) as client:
            response = client.post("/v1/runs", headers=headers, json=body)
            assert response.status_code == 202, response.text
            run_id = response.json()["runId"]
            duplicate = client.post("/v1/runs", headers=headers, json=body)
            assert duplicate.json()["runId"] == run_id
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                run = client.get("/v1/runs/" + run_id, headers=headers).json()
                if run["status"] in {"succeeded", "failed", "cancelled"}:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Bounded workflow deadline elapsed")
            foreign = client.get("/v1/runs/" + run_id,
                                 headers={"X-Aplomb-Session": "s_" + str(uuid.uuid4())})
            assert foreign.status_code == 404
        run.pop("sessionId", None)
        write_json(args.directory / "sanitized-run.json", {
            "transport": "Fresh Bedrock Converse through official AWS MCP file bridge",
            "financialInputs": "Unchanged competition starter dataset, not live prices",
            "applicationStackDeployed": False,
            "checks": {"idempotency": True, "crossSessionRejection": foreign.status_code},
            "run": run,
        })
        print(f"Final status: {run['status']}; {run['usage']['llmCalls']} actual inference calls", flush=True)
        assert run["status"] == "succeeded", "Inspect sanitized-run.json for the preserved failure"


if __name__ == "__main__":
    main()
