import csv
import io
import json

import pytest
from aplomb.api.errors import ServiceError
from aplomb.world.airports import DIRECTORY, filter_airports, load_airports, parse_airports


def test_snapshot_validated_global_coverage_and_exact_country_filter():
    rows, manifest = load_airports()
    assert len(rows) == manifest['rowCount'] == 1154
    assert len({row['countryIso3'] for row in rows if row['countryIso3']}) > 150
    japan = filter_airports(rows, country='JPN')
    assert japan and all(row['countryIso3'] == 'JPN' for row in japan)
    assert filter_airports(rows, query='heathrow')[0]['ident'] == 'EGLL'
    assert all(r['lon'] >= 170 or r['lon'] <= -170 for r in filter_airports(rows, bbox=(170, -90, -170, 90)))


def test_snapshot_tamper_is_rejected(tmp_path):
    for name in ('airports.json', 'airports_manifest.json'):
        (tmp_path / name).write_bytes((DIRECTORY / name).read_bytes())
    data = json.loads((tmp_path / 'airports.json').read_text())
    data[0]['lat'] = 91
    (tmp_path / 'airports.json').write_text(json.dumps(data))
    with pytest.raises(ValueError, match='integrity'):
        load_airports(tmp_path)


def test_parser_does_not_invent_coordinates_or_country():
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=['id', 'ident', 'name', 'type', 'scheduled_service', 'latitude_deg', 'longitude_deg', 'iso_country'])
    writer.writeheader()
    base = dict(id='1', ident='ABCD', name='Airport', type='large_airport', scheduled_service='yes', latitude_deg='10', longitude_deg='20', iso_country='ZZ')
    writer.writerow(base)
    writer.writerow({**base, 'id': '2', 'latitude_deg': 'nan'})
    writer.writerow({**base, 'id': '3', 'longitude_deg': '181'})
    crosswalk = json.dumps([{'pages': 1}, [{'iso2Code': 'JP', 'id': 'JPN', 'region': {'id': 'EAS'}}]]).encode()
    rows, meta = parse_airports(stream.getvalue().encode(), crosswalk, '2026-11-15T00:00:00Z')
    assert len(rows) == 1 and rows[0]['countryIso3'] is None
    assert meta['rejected'] == 2


def test_service_is_current_reference_and_bounded():
    from tests.unit.world.test_world import SID
    from tests.unit.world.test_world import world as world_fixture
    world = world_fixture.__wrapped__()
    result = world.airports(SID, {'country': ['JPN'], 'limit': 2})
    assert result.total > 2 and len(result.items) == 2
    assert all(row.country_iso3 == 'JPN' for row in result.items)
    with pytest.raises(ServiceError, match='historical'):
        world.airports(SID, {'asOf': '2020-01-01'})
