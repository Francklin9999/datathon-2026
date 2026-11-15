import json
from datetime import datetime, timezone

import pytest
from aplomb.world.country_macro import INDICATORS, load_snapshot, parse_indicator
from aplomb.world.dataset import load_bundle

from tests.unit.world.test_world import world as world  # fixture

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


def test_bundled_world_bank_snapshot_is_verified_and_country_panel_consumes_it(world):
    dataset = load_bundle()
    assert dataset.country_macro_manifest['countryCount'] >= 200
    result = world.country('unused', 'GBR', {})
    assert len(result.macro) == 4
    assert all(f.available_at[:10] == '2026-11-15' for f in result.macro)
    assert all(f.sources[0].dataset_id == 'world_bank_indicators' for f in result.macro)
    assert world._macro_facts('GBR', as_of='2025-01-01') == []


def test_wdi_rejects_partial_pages_and_future_years():
    indicator = next(iter(INDICATORS))
    row = {'indicator': {'id': indicator}, 'countryiso3code': 'GBR', 'date': '2026', 'value': 3}
    body = [{'page': 1, 'pages': 1, 'total': 1}, [row]]
    parsed, meta = parse_indicator(json.dumps(body).encode(), indicator, retrieved_at=NOW, countries={'GBR'})
    assert parsed == [] and meta['rejected'] == 1
    body[0]['pages'] = 2
    with pytest.raises(ValueError):
        parse_indicator(json.dumps(body).encode(), indicator, retrieved_at=NOW, countries={'GBR'})


def test_wdi_snapshot_checksum_is_enforced(tmp_path):
    (tmp_path / 'country_macro.json').write_text('[]')
    (tmp_path / 'country_macro_manifest.json').write_text(json.dumps({'sha256': '0' * 64, 'rowCount': 0}))
    with pytest.raises(ValueError, match='checksum'):
        load_snapshot(tmp_path)
