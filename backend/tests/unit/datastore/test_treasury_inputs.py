import hashlib
import json
from pathlib import Path

import pytest
from aplomb.datastore.errors import IngestionError
from aplomb.datastore.treasury_inputs import read_debt, read_par

ROOT = Path(__file__).resolve().parents[4] / 'data' / 'inputs' / 'risk-treasury'


def load(stem, suffix):
    return ((ROOT / (stem + suffix)).read_bytes(),
            json.loads((ROOT / (stem + '.metadata.json')).read_text()))


def test_official_par_curve_and_capture_gate():
    payload, metadata = load('par-202610', '.xml')
    capture = read_par(payload, metadata)
    assert len(capture.rows) == 21
    row = capture.latest(capture.retrieved_at, '2026-10-30')
    assert row['yieldsPercent']['1.5M'] == 4.09
    assert row['yieldsPercent']['10Y'] == 4.94
    assert len(row['yieldsPercent']) == 14
    assert capture.latest('2026-10-31T00:00:00Z', '2026-10-30') is None
    with pytest.raises(IngestionError):
        read_par(payload + b' ', metadata)


def test_official_debt_amounts_preserve_cents_and_sum():
    payload, metadata = load('debt-202610', '.json')
    capture = read_debt(payload, metadata)
    row = capture.latest(capture.retrieved_at, '2026-10-30')
    assert row['totalUsd'] == '40524510013062.41'
    assert row['heldByPublicUsd'] == '32738422032176.85'
    assert capture.latest('2026-10-31T00:00:00Z', '2026-10-30') is None
    doc = json.loads(payload)
    doc['data'][0]['tot_pub_debt_out_amt'] = '1.00'
    changed = json.dumps(doc).encode()
    with pytest.raises(IngestionError):
        read_debt(changed, {**metadata, 'rawSha256': hashlib.sha256(changed).hexdigest()})


def test_rejects_incomplete_page():
    payload, metadata = load('debt-202610', '.json')
    doc = json.loads(payload)
    doc['links']['next'] = 'next page'
    changed = json.dumps(doc).encode()
    with pytest.raises(IngestionError):
        read_debt(changed, {**metadata, 'rawSha256': hashlib.sha256(changed).hexdigest()})
