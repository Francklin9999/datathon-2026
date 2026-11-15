"""Synthetic records exercise source availability; they are not real disclosures."""
import hashlib
from dataclasses import replace

import pytest
from aplomb.timemachine.records import PointInTimeRecord, PointInTimeRecords


def record(kind="filing", revision="original", available="2023-04-10T14:00:00Z"):
    payload = "synthetic content"
    return PointInTimeRecord("issuer:123", revision, kind, "2023-03-31", "2023-04-10T13:00:00Z",
                             available, "2026-11-15T00:00:00Z", "test-v1", "https://example.test/source",
                             hashlib.sha256(payload.encode()).hexdigest(), payload)


@pytest.mark.parametrize("kind", ["security", "fundamental", "news", "ownership", "filing"])
def test_record_is_withheld_until_available_and_revisions_do_not_leak(kind):
    original = record(kind)
    revised = replace(original, revision_id="revision", available_at="2023-06-01T12:00:00Z")
    unknown = replace(original, record_id="unknown", available_at=None)
    bundle = PointInTimeRecords("test-v1", (original, revised, unknown))
    assert bundle.select("2023-04-09") == ()
    assert bundle.select("2023-04-10") == (original,)
    assert bundle.select("2023-05-31") == (original,)
    assert bundle.select("2023-06-01") == (revised,)
    assert bundle.digest() == bundle.digest()


def test_source_hash_and_revision_conflicts_fail_closed():
    original = record()
    with pytest.raises(ValueError, match="hash"):
        replace(original, payload="changed")
    with pytest.raises(ValueError, match="duplicate"):
        PointInTimeRecords("test-v1", (original, original))
    with pytest.raises(ValueError, match="ambiguous"):
        PointInTimeRecords("test-v1", (original, replace(original, revision_id="another"))).select("2024-01-01")
