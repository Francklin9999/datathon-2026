import hashlib
import json
from pathlib import Path

import pytest
from aplomb.datastore.cftc_cot import read_capture
from aplomb.datastore.errors import IngestionError

ROOT = Path(__file__).resolve().parents[4] / "data" / "inputs" / "risk-cftc"


def capture():
    return ((ROOT / "legacy-futures-202611.json").read_bytes(),
            json.loads((ROOT / "legacy-futures-202611.metadata.json").read_text()))


def test_real_capture_and_exact_contract_lookups():
    payload, metadata = capture()
    data = read_capture(payload, metadata)
    assert len(data.positions) == 100
    wheat = data.latest("001602", data.retrieved_at, "2026-11-03")
    assert wheat.open_interest == 534858
    assert wheat.net_noncommercial_contracts == -62538
    assert data.latest("001602", "2026-11-06T23:59:59Z", "2026-11-03") is None
    assert data.latest("WHEAT", data.retrieved_at, "2026-11-03") is None
    assert data.latest("001602", data.retrieved_at, "2026-11-02") is None


def test_rejects_duplicate_or_malformed_data():
    payload, metadata = capture()
    data = json.loads(payload)
    data.append(data[0])
    changed = json.dumps(data).encode()
    with pytest.raises(IngestionError):
        read_capture(changed, {**metadata, "rawSha256": hashlib.sha256(changed).hexdigest()})
    with pytest.raises(IngestionError):
        read_capture(payload, {**metadata, "report": "futures-and-options"})
