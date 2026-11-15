"""Temporary starter-data API for T16 browser QA; no models, fixtures or AWS config.

Run `uv run python tests/browser_api.py`. Ctrl-C removes the ingested snapshot.
"""

import tempfile
from pathlib import Path

import uvicorn
from aplomb.api.app import create_default_app
from aplomb.api.settings import Settings
from aplomb.datastore.ingest import ingest_starter

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="aplomb-t16-browser-data-") as directory:
        ingest_starter(ROOT / "Datathon2026/alphaforge_starter", Path(directory),
                       "snap-20261113-starter",
                       metadata_dir=ROOT / "data/inputs/snap-20261113-starter")
        app = create_default_app(Settings(
            data_version="snap-20261113-starter", data_dir=directory,
            allowed_origins=["http://127.0.0.1:8765"],
            features={"world_explorer": True, "time_machine": True,
                      "profile_creator": True, "frontier_chart": True},
        ))
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
