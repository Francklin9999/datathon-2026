import re
import shutil
from pathlib import Path

from aplomb.datastore.financial_inputs_api import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_source_inputs_historical_day_does_not_see_later_capture():
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get('/v1/risk/source-inputs?asOf=2026-11-12')
    assert response.status_code == 200
    sources = {item['id']: item for item in response.json()['sources']}
    assert sources['sofr']['status'] == 'not_available_as_of'
    assert sources['cftc-cot']['status'] == 'not_available_as_of'
    assert sources['fama-french']['status'] == 'capture_unavailable'


REPO_ROOT = Path(__file__).resolve().parents[4]
CAPTURE_IDS = {'sofr', 'cftc-cot', 'cftc-swaps', 'treasury-par', 'treasury-debt'}


def test_inputs_resolve_to_repo_data_inputs_in_the_repo_layout():
    from aplomb.datastore import financial_inputs_api

    assert financial_inputs_api.INPUTS == REPO_ROOT / 'data' / 'inputs'


def test_inputs_resolve_to_task_root_in_the_lambda_artifact_layout(tmp_path):
    from aplomb.datastore.financial_inputs_api import resolve_inputs

    # /var/task/aplomb/datastore/financial_inputs_api.py -> /var/task/data/inputs
    task = tmp_path / 'var' / 'task'
    module = task / 'aplomb' / 'datastore' / 'financial_inputs_api.py'
    module.parent.mkdir(parents=True)
    module.touch()
    assert resolve_inputs(module) == tmp_path / 'var' / 'data' / 'inputs'  # nothing packaged yet
    (task / 'data' / 'inputs').mkdir(parents=True)
    assert resolve_inputs(module) == task / 'data' / 'inputs'


def test_packaged_capture_folders_serve_every_capture(monkeypatch, tmp_path):
    """Only CAPTURE_FOLDERS are shipped; with just those, no capture may be unavailable."""
    from aplomb.datastore import financial_inputs_api

    for folder in financial_inputs_api.CAPTURE_FOLDERS:
        shutil.copytree(REPO_ROOT / 'data' / 'inputs' / folder, tmp_path / folder)
    monkeypatch.setattr(financial_inputs_api, 'INPUTS', tmp_path)
    app = FastAPI()
    app.include_router(router)
    sources = {item['id']: item for item in
               TestClient(app).get('/v1/risk/source-inputs?asOf=2026-11-14').json()['sources']}
    assert set(sources) == CAPTURE_IDS | {'fama-french'}
    for name in CAPTURE_IDS:
        assert sources[name]['status'] != 'capture_unavailable', name


def test_package_script_ships_exactly_the_capture_folders():
    from aplomb.datastore.financial_inputs_api import CAPTURE_FOLDERS

    script = (REPO_ROOT / 'infra' / 'scripts' / 'package-backend.sh').read_text(encoding='utf-8')
    match = re.search(r'^risk_captures=\(([^)]*)\)$', script, re.MULTILINE)
    assert match, 'package-backend.sh must declare risk_captures=(...)'
    assert tuple(match.group(1).split()) == CAPTURE_FOLDERS
    assert 'cp -R "data/inputs/$folder" "$artifact/data/inputs/$folder"' in script


def test_source_inputs_missing_capture_is_explicit(monkeypatch, tmp_path):
    from aplomb.datastore import financial_inputs_api

    monkeypatch.setattr(financial_inputs_api, 'INPUTS', tmp_path)
    app = FastAPI()
    app.include_router(router)
    result = TestClient(app).get('/v1/risk/source-inputs').json()
    assert all(item['status'] == 'capture_unavailable' for item in result['sources'])
