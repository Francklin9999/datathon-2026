"""Provider ingestion gates use synthetic fixtures; captured source validation is separate."""
import json

import pytest
from aplomb.world.providers import public
from aplomb.world.providers.ingest import SOURCES, collect
from aplomb.world.providers.snapshot import load_provider_snapshots, publish
from aplomb.world.providers.transport import Transport

STAMP = "2026-11-15T12:00:00Z"


def document(day="2026-11-13", key="1", **overrides):
    return {"document_number": key, "publication_date": day, "title": "Policy", "type": "Notice",
            "html_url": "https://www.federalregister.gov/documents/" + key, **overrides}


def page(*documents):
    return json.dumps({"results": list(documents)}).encode()


def test_policy_rejects_future_dated_documents_and_reports_partial_page():
    rows, quality = public.policy(json.dumps({"results": [
        document("2026-11-13", "1"), document("2026-11-16", "2")], "next_page_url": "next"}).encode(), STAMP)
    assert len(rows) == 1 and quality["rejected"] == 1
    assert not quality["coverageComplete"]
    assert rows[0]["latitude"] is None


def test_immutable_snapshot_roundtrip_temporal_gate_and_raw_corruption(tmp_path):
    payload = page(document())
    manifest = collect("policy", lambda _: payload, STAMP, tmp_path)
    rows, manifests = load_provider_snapshots(tmp_path)
    assert len(rows) == 1 and manifests[0]["dataVersion"] == manifest["dataVersion"]
    assert load_provider_snapshots(tmp_path, as_of="2026-11-14T00:00:00Z") == ((), ())
    assert len(load_provider_snapshots(tmp_path, as_of=STAMP)[0]) == 1
    assert collect("policy", lambda _: payload, STAMP, tmp_path) == manifest
    raw = tmp_path / manifest["dataVersion"] / "raw-000.bin"
    raw.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="raw capture checksum"):
        load_provider_snapshots(tmp_path)
    with pytest.raises(ValueError, match="Immutable"):
        collect("policy", lambda _: payload, STAMP, tmp_path)


def test_empty_failure_keeps_prior_snapshot(tmp_path):
    collect("policy", lambda _: page(document()), STAMP, tmp_path)
    with pytest.raises(ValueError, match="empty"):
        collect("policy", lambda _: page(), STAMP, tmp_path)
    assert len(load_provider_snapshots(tmp_path)[0]) == 1


def test_identity_count_and_normalized_corruption(tmp_path):
    payload = page(document())
    manifest = collect("policy", lambda _: payload, STAMP, tmp_path)
    path = tmp_path / manifest["dataVersion"] / "observations.json"
    path.write_bytes(b"[]")
    with pytest.raises(ValueError, match="observation checksum"):
        load_provider_snapshots(tmp_path)


def test_lenient_load_skips_only_the_damaged_source(tmp_path):
    policy_id, other_id = SOURCES["policy"]["datasetId"], "world_test_feed"
    collect("policy", lambda _: page(document()), STAMP, tmp_path)
    newer = collect("policy", lambda _: page(document()), "2026-11-15T13:00:00Z", tmp_path)
    rows, _ = public.policy(page(document()), STAMP)
    other = publish(tmp_path, [{**rows[0], "id": other_id + ":1", "sourceId": other_id}],
                    {"datasetId": other_id, "retrievedAt": STAMP}, [("https://example.org/feed", b"raw")])
    (tmp_path / newer["dataVersion"] / "raw-000.bin").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="raw capture checksum"):
        load_provider_snapshots(tmp_path)

    errors = []
    rows, manifests = load_provider_snapshots(tmp_path, errors=errors)
    # The intact source still loads; the damaged one is dropped, not replaced by its older valid version.
    assert [m["datasetId"] for m in manifests] == [other_id]
    assert {row["sourceId"] for row in rows} == {other_id}
    assert [source for source, _ in errors] == [policy_id]
    assert "raw capture checksum" in errors[0][1]

    (tmp_path / other["dataVersion"] / "manifest.json").write_bytes(b"{")
    errors = []
    assert load_provider_snapshots(tmp_path, errors=errors) == ((), ())
    assert sorted(source for source, _ in errors) == sorted([policy_id, other_id])  # name from the version directory


def test_publish_rejects_backdated_availability_duplicate_and_source_url(tmp_path):
    rows, _ = public.policy(page(document()), STAMP)
    meta = {k: v for k, v in SOURCES["policy"].items() if k != "parser"} | {"retrievedAt": STAMP}
    for bad in [{**rows[0], "availableAt": "2020-01-01T00:00:00Z"},
                {**rows[0], "sourceUrl": "file:///etc/passwd"}]:
        with pytest.raises(ValueError):
            publish(tmp_path, [bad], meta, [])
    with pytest.raises(ValueError, match="Duplicate"):
        publish(tmp_path, rows * 2, meta, [])


def test_transport_rejects_nonprovider_hosts_before_network():
    for url in ("http://api.weather.gov/", "https://evil.example/", "https://api.weather.gov:444/"):
        with pytest.raises(ValueError, match="allowlisted"):
            Transport()(url)


