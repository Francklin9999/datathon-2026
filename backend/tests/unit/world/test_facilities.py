import csv
import gzip
import io
from pathlib import Path

import pytest
from aplomb.api.errors import ServiceError
from aplomb.world.facilities import (
    COLUMNS,
    DIRECTORY,
    ID,
    NAME,
    OPERATOR,
    TOTAL,
    YEAR,
    filter_facilities,
    load_facilities,
    normalize,
    project_source,
)


def test_real_snapshot_has_no_invented_security_matches_and_traceable_units():
    rows, meta = load_facilities()
    assert meta['rowCount'] == len(rows) == 1863
    assert meta['reportingYear'] == 2024 and meta['rejected'] == 16
    assert all(row['ticker'] is None and row['matchConfidence'] == 'none' for row in rows)
    assert all(row['emissionsTco2e'] >= 0 and row['countryIso3'] == 'CAN' for row in rows)
    assert filter_facilities(rows, {'ticker': 'RY.TO'}) == []
    assert filter_facilities(rows, {'country': ['JPN']}) == []
    large = filter_facilities(rows, {'minEmissions': 1_000_000})
    assert large and all(row['emissionsTco2e'] >= 1_000_000 for row in large)
    captured = gzip.decompress(Path('data/inputs/eccc/facilities_source.csv.gz').read_bytes())
    assert csv.DictReader(io.StringIO(captured.decode())).fieldnames == list(COLUMNS)
    rebuilt, rebuilt_meta = normalize(captured, meta['capturedAt'], original_sha256=meta['originalSourceSha256'])
    assert rebuilt == rows and rebuilt_meta == meta


def test_projection_omits_public_contact_fields_and_invalid_coordinates():
    stream = io.StringIO()
    writer = csv.DictWriter(stream, list(COLUMNS) + ['Public Contact Email'])
    writer.writeheader()
    base = {ID: '123', YEAR: '2024', NAME: 'Facility', OPERATOR: 'Operator', 'Latitude': 50, 'Longitude': -70, TOTAL: 100,
            'Public Contact Email': 'public-contact@example.org'}
    writer.writerow(base)
    writer.writerow({**base, ID: '456', 'Latitude': 'nan'})
    projection = project_source(stream.getvalue().encode())
    assert b'public-contact@example.org' not in projection and b'Public Contact Email' not in projection
    rows, meta = normalize(projection, '2026-11-15T00:00:00Z')
    assert len(rows) == 1 and meta['rejected'] == 1 and rows[0]['ticker'] is None


def test_corruption_or_incomplete_snapshot_never_loads(tmp_path):
    for filename in ['facilities.json', 'facilities_manifest.json']:
        (tmp_path / filename).write_bytes((DIRECTORY / filename).read_bytes())
    (tmp_path / 'facilities.json').write_text('[]')
    with pytest.raises(ValueError, match='integrity'):
        load_facilities(tmp_path)


def test_service_rejects_historical_reference_queries():
    from tests.unit.world.test_world import SID
    from tests.unit.world.test_world import world as world_fixture
    with pytest.raises(ServiceError, match='historical'):
        world_fixture.__wrapped__().facilities(SID, {'asOf': '2020-01-01'})
