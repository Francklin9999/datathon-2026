"""Synthetic NASA-format records; not a claim of live provider access."""
import json
from datetime import datetime, timezone

from aplomb.contracts.models import WorldEvent
from aplomb.world.ingest import build_bundle, parse_eonet


def event(**extra):
    return {'title': 'Synthetic storm', 'link': 'https://eonet.gsfc.nasa.gov/api/v3/events/EONET_1',
            'geometry': [{'type': 'Point', 'coordinates': [140, -30], 'date': '2026-10-20T00:00:00Z'}], **extra}


def test_event_keeps_source_point_without_inferred_country_or_publication():
    found, rejected = parse_eonet(json.dumps({'events': [event()]}).encode())
    assert rejected == 0
    row = found[0]
    assert row['location']['countryIso3'] is None
    assert row['location']['lat'] == -30
    assert row['publishedAt'] is None and row['relatedTickers'] == []
    files = build_bundle(found, [], [], built_at=datetime(2026, 11, 15, tzinfo=timezone.utc), start='2026-01-01', end='2026-12-31')
    WorldEvent.model_validate(json.loads(files['events.json'])[0])


def test_invalid_point_polygon_and_untrusted_identity_are_rejected():
    records = [event(geometry=[{'type': 'Polygon', 'coordinates': []}]),
               event(geometry=[{'type': 'Point', 'coordinates': [200, 20], 'date': '2026-10-20T00:00:00Z'}]),
               event(link='https://example.org/fake')]
    found, rejected = parse_eonet(json.dumps({'events': records}).encode())
    assert found == [] and rejected == 3


def test_first_observation_is_used_not_latest_track_location():
    item = event()
    item['geometry'].insert(0, {'type': 'Point', 'coordinates': [1, 2], 'date': '2026-10-22T00:00:00Z'})
    found, _ = parse_eonet(json.dumps({'events': [item]}).encode())
    assert found[0]['occurredAt'] == '2026-10-20'
    assert found[0]['location']['lon'] == 140
