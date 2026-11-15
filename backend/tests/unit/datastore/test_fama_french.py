"""Synthetic provider-format inputs, not an official data capture."""
import hashlib
import io
import zipfile

import pytest
from aplomb.datastore.errors import IngestionError
from aplomb.datastore.fama_french import SOURCE, read_capture


def zipped(text):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("F-F_Research_Data_Factors_daily.csv", text)
    return out.getvalue()


def metadata(payload):
    return {"rawSha256": hashlib.sha256(payload).hexdigest(), "sourceUrl": SOURCE,
            "retrievedAt": "2026-11-15T16:00:00Z"}


def test_percent_units_and_capture_availability():
    raw = zipped("Description\n,Mkt-RF,SMB,HML,RF\n20261112, 1.50,-0.20,0.30,0.02\n")
    data = read_capture(raw, metadata(raw))
    assert data.observations[0].market_excess == 0.015
    assert data.observations[0].size == -0.002
    assert data.through("2026-11-12T23:59:59Z", "2026-11-12") == ()
    assert len(data.through(data.retrieved_at, "2026-11-12")) == 1


def test_missing_factor_and_duplicate_dates_rejected():
    for body in ("20261112,-99.99,0,0,0\n", "20261112,1,0,0,0\n20261112,1,0,0,0\n"):
        raw = zipped(",Mkt-RF,SMB,HML,RF\n" + body)
        with pytest.raises(IngestionError):
            read_capture(raw, metadata(raw))
