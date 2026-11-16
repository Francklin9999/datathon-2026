"""scripts/ingest_airports.py and scripts/ingest_facilities.py replay the retained captures offline."""
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from unittest import mock

import pytest
from aplomb.world.airports import DIRECTORY as AIRPORTS
from aplomb.world.facilities import COLUMNS, ID, NAME, OPERATOR, TOTAL, YEAR
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


def replay_capture(source: Path, tmp_path: Path, repacked: bool) -> Path:
    if not repacked:
        return source
    destination = tmp_path / source.name
    # A valid capture may come from a different gzip implementation or timestamp.
    destination.write_bytes(gzip.compress(gzip.decompress(source.read_bytes()), compresslevel=1, mtime=1234567890))
    return destination


def assert_same_capture(actual: Path, expected: Path):
    actual_bytes, expected_bytes = actual.read_bytes(), expected.read_bytes()
    if actual_bytes != expected_bytes:
        # A multi-megabyte pytest byte diff can hide the underlying replay failure.
        pytest.fail(
            f'{actual.name}: capture bytes changed; '
            f'actual sha256={hashlib.sha256(actual_bytes).hexdigest()}, '
            f'expected sha256={hashlib.sha256(expected_bytes).hexdigest()}',
            pytrace=False,
        )


@pytest.mark.parametrize('repacked', [False, True], ids=['retained', 'different-gzip-encoding'])
def test_airports_rebuild_from_retained_captures_without_network(tmp_path, repacked):
    script, inputs, out = load('ingest_airports'), ROOT / 'data' / 'inputs' / 'airports', tmp_path / 'out'
    captures = {
        name: replay_capture(inputs / name, tmp_path, repacked)
        for name in ('airports.csv.gz', 'country_crosswalk.json.gz')
    }
    committed = manifest(AIRPORTS, 'airports_manifest.json')
    with mock.patch.object(script, 'http_get', no_network):
        script.main(['--out', str(out), '--capture', str(captures['airports.csv.gz']),
                     '--crosswalk-capture', str(captures['country_crosswalk.json.gz']),
                     '--captured-at', committed['capturedAt']])
    assert json.loads((out / 'airports.json').read_text()) == json.loads((AIRPORTS / 'airports.json').read_text())
    assert manifest(out, 'airports_manifest.json') == committed
    for name, capture in captures.items():
        assert_same_capture(out / name, capture)


@pytest.mark.parametrize('repacked', [False, True], ids=['retained', 'different-gzip-encoding'])
def test_facilities_rebuild_from_retained_projection_without_network(tmp_path, repacked):
    script, capture, out = load('ingest_facilities'), ROOT / 'data' / 'inputs' / 'eccc' / 'facilities_source.csv.gz', tmp_path / 'out'
    capture = replay_capture(capture, tmp_path, repacked)
    committed = manifest(FACILITIES, 'facilities_manifest.json')
    with mock.patch.object(script, 'urlopen', no_network):
        script.main(['--out', str(out), '--capture', str(capture), '--captured-at', committed['capturedAt']])
    assert json.loads((out / 'facilities.json').read_text()) == json.loads((FACILITIES / 'facilities.json').read_text())
    built = manifest(out, 'facilities_manifest.json')
    # The original download (with public contact columns) was not retained, so its hash is unknown on replay.
    assert built['originalSourceSha256'] is None
    assert {**built, 'originalSourceSha256': committed['originalSourceSha256']} == committed
    assert_same_capture(out / 'facilities_source.csv.gz', capture)


@pytest.mark.parametrize('compressed', [False, True], ids=['plain', 'gzip'])
def test_facilities_original_capture_is_projected_before_retention(tmp_path, compressed):
    script, out = load('ingest_facilities'), tmp_path / 'out'
    stream = io.StringIO()
    writer = csv.DictWriter(stream, [*COLUMNS, 'Public Contact Email'])
    writer.writeheader()
    writer.writerow({
        ID: '123', YEAR: '2024', NAME: 'Facility', OPERATOR: 'Operator',
        'Latitude': 50, 'Longitude': -70, TOTAL: 100,
        'Public Contact Email': 'public-contact@example.org',
    })
    payload = stream.getvalue().encode()
    capture = tmp_path / ('original.csv.gz' if compressed else 'original.csv')
    capture.write_bytes(gzip.compress(payload, mtime=1234567890) if compressed else payload)
    with mock.patch.object(script, 'urlopen', no_network):
        script.main(['--out', str(out), '--capture', str(capture), '--captured-at', '2026-11-15T00:00:00Z'])
    retained = gzip.decompress((out / 'facilities_source.csv.gz').read_bytes())
    assert b'Public Contact Email' not in retained
    assert b'public-contact@example.org' not in retained
    assert manifest(out, 'facilities_manifest.json')['originalSourceSha256'] == hashlib.sha256(payload).hexdigest()
    rows = json.loads((out / 'facilities.json').read_text())
    assert len(rows) == 1 and rows[0]['facilityId'] == 'eccc_123'


@pytest.mark.parametrize('metadata_location', ['filename', 'empty-concatenated-member'])
def test_facilities_removes_contact_data_from_gzip_metadata(tmp_path, metadata_location):
    script, out = load('ingest_facilities'), tmp_path / 'out'
    payload = gzip.decompress((ROOT / 'data' / 'inputs' / 'eccc' / 'facilities_source.csv.gz').read_bytes())
    stream = io.BytesIO()
    with gzip.GzipFile(filename='public-contact@example.org', fileobj=stream, mode='wb', mtime=0) as archive:
        archive.write(payload if metadata_location == 'filename' else b'')
    captured_bytes = stream.getvalue()
    if metadata_location == 'empty-concatenated-member':
        captured_bytes = gzip.compress(payload, mtime=0) + captured_bytes
    assert gzip.decompress(captured_bytes) == payload
    capture = tmp_path / 'original.csv.gz'
    capture.write_bytes(captured_bytes)
    committed = manifest(FACILITIES, 'facilities_manifest.json')
    with mock.patch.object(script, 'urlopen', no_network):
        script.main(['--out', str(out), '--capture', str(capture), '--captured-at', committed['capturedAt']])
    retained = (out / 'facilities_source.csv.gz').read_bytes()
    assert b'public-contact@example.org' not in retained
    assert gzip.decompress(retained) == payload
    assert manifest(out, 'facilities_manifest.json')['originalSourceSha256'] is None


@pytest.mark.parametrize('name', ['ingest_airports', 'ingest_facilities'])
def test_captured_at_must_be_a_utc_timestamp(name, tmp_path):
    with pytest.raises(SystemExit):
        load(name).main(['--out', str(tmp_path / 'out'), '--captured-at', '2026-11-15'])
