import hashlib
import json
from pathlib import Path

import pytest
from aplomb.datastore.cftc_swaps import read_capture
from aplomb.datastore.errors import IngestionError

ROOT = Path(__file__).resolve().parents[4] / 'data' / 'inputs' / 'risk-cftc'


def test_weekly_swaps_report_and_capture_time():
    raw = (ROOT / 'swaps-irs-202610.html').read_bytes()
    metadata = json.loads((ROOT / 'swaps-irs-202610.metadata.json').read_text())
    capture = read_capture(raw, metadata)
    assert capture.latest('2026-10-30T00:00:00Z', '2026-10-23') is None
    obs = capture.latest(capture.retrieved_at, '2026-10-23')
    assert obs['totalMillionsUsd'] == 458648986
    assert obs['clearedMillionsUsd'] == 400821743
    changed = raw.replace(b'458,648,986', b'458,648,900', 1)
    with pytest.raises(IngestionError):
        read_capture(changed, {**metadata, 'rawSha256': hashlib.sha256(changed).hexdigest()})
