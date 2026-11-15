import hashlib
import json
from pathlib import Path

import pytest
from aplomb.datastore.errors import IngestionError
from aplomb.datastore.nyfed_sofr import read_capture

ROOT = Path(__file__).resolve().parents[4] / "data" / "inputs" / "risk-nyfed"


def capture():
    return ((ROOT / "sofr-202610.json").read_bytes(),
            json.loads((ROOT / "sofr-202610.metadata.json").read_text()))


def test_official_capture_and_observed_rate_change():
    body, metadata = capture()
    data = read_capture(body, metadata)
    assert len(data.observations) == 21
    assert data.latest(data.retrieved_at, "2026-10-30").percent_rate == 3.95
    assert data.change_basis_points(data.retrieved_at, "2026-10-29", "2026-10-30") == 1
    assert data.latest(data.retrieved_at, "2026-09-30") is None
    assert data.latest("2026-10-31T00:00:00Z", "2026-10-30") is None
    assert data.change_basis_points(data.retrieved_at, "2026-10-30", "2026-10-31") is None


def test_capture_rejects_corruption_duplicate_and_wrong_source():
    body, metadata = capture()
    with pytest.raises(IngestionError):
        read_capture(body + b" ", metadata)
    with pytest.raises(IngestionError):
        read_capture(body, {**metadata, "sourceUrl": "https://example.org/?startDate=2026-10-01&endDate=2026-10-30"})
    document = json.loads(body)
    document["refRates"].append(document["refRates"][0])
    duplicate = json.dumps(document).encode()
    with pytest.raises(IngestionError):
        read_capture(duplicate, {**metadata, "rawSha256": hashlib.sha256(duplicate).hexdigest()})
