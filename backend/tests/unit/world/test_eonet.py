"""Synthetic NASA-format records; not a claim of live provider access."""
import hashlib
import json
from datetime import datetime, timezone

from aplomb.contracts.models import WorldEvent
from aplomb.world import ingest
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


def test_rebuild_fetches_eonet_and_labels_the_version(tmp_path, monkeypatch):
    payload = json.dumps({'events': [event()]}).encode()
    release_csv = tmp_path / 'releases.csv'
    release_csv.write_text('seriesId,referenceDate,publishedAt,vintageAt,sourceUrl\n', encoding='utf-8')
    requested = []

    def fetch(url):
        requested.append(url)
        if url.startswith('https://eonet.gsfc.nasa.gov/'):
            return payload
        raise TimeoutError('simulated outage')

    real_collect = ingest.collect

    def collect(start, end, **kwargs):
        return real_collect(start, end, fetch=fetch, release_csv=release_csv, pause=0, log=lambda _: None, **kwargs)

    events, _, sources = collect('2021-11-12', '2026-11-12', eonet_days=ingest.EONET_DEFAULT_DAYS)
    eonet = next(s for s in sources if s['id'] == 'nasa_eonet')
    assert eonet['status'] == 'ok' and eonet['items'] == 1 and eonet['rejected'] == 0
    assert eonet['url'] == ingest.eonet_url('2026-10-15', '2026-11-12') and eonet['url'] in requested
    assert eonet['payloadSha256'] == hashlib.sha256(payload).hexdigest()
    assert [e['origin'] for e in events] == ['eonet']
    assert ingest.eonet_version_suffix(sources) == '-eonet-' + eonet['payloadSha256'][:8]
    assert ingest.eonet_version_suffix([{**eonet, 'status': 'failed'}]) == ''

    # The documented CLI rebuild includes EONET by default and labels the version with its payload.
    monkeypatch.setattr(ingest, 'collect', collect)
    out = tmp_path / 'bundle'
    assert ingest.main(['--start', '2021-11-12', '--end', '2026-11-12', '--out', str(out)]) == 0
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['worldVersion'].endswith('-eonet-' + eonet['payloadSha256'][:8])
    assert manifest['events']['byOrigin'] == {'eonet': 1}
    assert any(s['id'] == 'nasa_eonet' and s['status'] == 'ok' for s in manifest['sources'])


def test_first_observation_is_used_not_latest_track_location():
    item = event()
    item['geometry'].insert(0, {'type': 'Point', 'coordinates': [1, 2], 'date': '2026-10-22T00:00:00Z'})
    found, _ = parse_eonet(json.dumps({'events': [item]}).encode())
    assert found[0]['occurredAt'] == '2026-10-20'
    assert found[0]['location']['lon'] == 140
