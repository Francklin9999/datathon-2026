"""scripts/ingest_airports.py and scripts/ingest_facilities.py replay the retained captures offline."""
import importlib.util
import json
from pathlib import Path
from unittest import mock

import pytest
from aplomb.world.airports import DIRECTORY as AIRPORTS
from aplomb.world.facilities import DIRECTORY as FACILITIES

ROOT = Path(__file__).resolve().parents[4]


def load(name: str):
    spec = importlib.util.spec_from_file_location(f'aplomb_{name}_script', ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def no_network(*args, **kwargs):
    raise AssertionError('network call during an offline replay')


def manifest(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding='utf-8'))


def test_airports_rebuild_from_retained_captures_without_network(tmp_path):
    script, inputs, out = load('ingest_airports'), ROOT / 'data' / 'inputs' / 'airports', tmp_path / 'out'
    committed = manifest(AIRPORTS, 'airports_manifest.json')
    with mock.patch.object(script, 'http_get', no_network):
        script.main(['--out', str(out), '--capture', str(inputs / 'airports.csv.gz'),
                     '--crosswalk-capture', str(inputs / 'country_crosswalk.json.gz'),
                     '--captured-at', committed['capturedAt']])
    assert json.loads((out / 'airports.json').read_text()) == json.loads((AIRPORTS / 'airports.json').read_text())
    assert manifest(out, 'airports_manifest.json') == committed
    for name in ('airports.csv.gz', 'country_crosswalk.json.gz'):
        assert (out / name).read_bytes() == (inputs / name).read_bytes()


def test_facilities_rebuild_from_retained_projection_without_network(tmp_path):
    script, capture, out = load('ingest_facilities'), ROOT / 'data' / 'inputs' / 'eccc' / 'facilities_source.csv.gz', tmp_path / 'out'
    committed = manifest(FACILITIES, 'facilities_manifest.json')
    with mock.patch.object(script, 'urlopen', no_network):
        script.main(['--out', str(out), '--capture', str(capture), '--captured-at', committed['capturedAt']])
    assert json.loads((out / 'facilities.json').read_text()) == json.loads((FACILITIES / 'facilities.json').read_text())
    built = manifest(out, 'facilities_manifest.json')
    # The original download (with public contact columns) was not retained, so its hash is unknown on replay.
    assert built['originalSourceSha256'] is None
    assert {**built, 'originalSourceSha256': committed['originalSourceSha256']} == committed
    assert (out / 'facilities_source.csv.gz').read_bytes() == capture.read_bytes()


@pytest.mark.parametrize('name', ['ingest_airports', 'ingest_facilities'])
def test_captured_at_must_be_a_utc_timestamp(name, tmp_path):
    with pytest.raises(SystemExit):
        load(name).main(['--out', str(tmp_path / 'out'), '--captured-at', '2026-11-15'])
