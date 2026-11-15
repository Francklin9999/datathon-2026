"""Provider ingestion gates use synthetic fixtures; captured source validation is separate."""
import json

import pytest
from aplomb.world.providers import public
from aplomb.world.providers.ingest import SOURCES, collect
from aplomb.world.providers.snapshot import load_provider_snapshots, publish
from aplomb.world.providers.transport import Transport

STAMP = "2026-11-15T12:00:00Z"


def metar(**overrides):
    return {"icaoId": "RJTT", "name": "Tokyo", "lat": 35.55, "lon": 139.77,
            "obsTime": 1794744000, "receiptTime": STAMP, "rawOb": "METAR RJTT", **overrides}


def test_aviation_rejects_bad_coordinates_duplicate_and_preserves_weather_role():
    rows, quality = public.aviation(json.dumps([metar(), metar(), metar(icaoId="BAD", lat=91)]).encode(), STAMP)
    assert len(rows) == 1 and quality["rejected"] == 2
    assert rows[0]["properties"]["aircraftTracking"] is False
    assert rows[0]["countryIso3"] is None  # ICAO prefix alone is not a country crosswalk.
    assert rows[0]["availableAt"] == STAMP


def test_aviation_country_crosswalk_uses_source_country_code_in_station_name():
    rows, _ = public.aviation(json.dumps([metar(name="Tokyo/Haneda Intl, 13, JP")]).encode(), STAMP)
    assert rows[0]["countryIso3"] == "JPN"
    assert rows[0]["properties"]["sourceCountryCode"] == "JP"


def test_noaa_keeps_polygon_and_rejects_missing_geometry():
    props = {"id": "1", "headline": "Warning", "event": "Flood", "sent": STAMP,
             "effective": STAMP, "severity": "Severe", "certainty": "Observed",
             "expires": STAMP, "areaDesc": "Area"}
    geometry = {"type": "Polygon", "coordinates": [[[-80, 40], [-79, 40], [-79, 41], [-80, 40]]]}
    rows, quality = public.noaa(json.dumps({"type": "FeatureCollection", "features": [
        {"id": "https://api.weather.gov/alerts/1", "properties": props, "geometry": geometry},
        {"id": "https://api.weather.gov/alerts/2", "properties": props, "geometry": None},
    ]}).encode(), STAMP)
    assert quality["rejected"] == 1
    assert rows[0]["properties"]["geometry"] == geometry
    assert rows[0]["properties"]["geographicRole"] == "alert_polygon_representative_anchor"


def test_policy_rejects_future_dated_documents_and_reports_partial_page():
    def document(day, key):
        return {"document_number": key, "publication_date": day, "title": "Policy", "type": "Notice",
                "html_url": "https://www.federalregister.gov/documents/" + key}
    rows, quality = public.policy(json.dumps({"results": [
        document("2026-11-13", "1"), document("2026-11-16", "2")], "next_page_url": "next"}).encode(), STAMP)
    assert len(rows) == 1 and quality["rejected"] == 1
    assert not quality["coverageComplete"]
    assert rows[0]["latitude"] is None


def test_portwatch_rejects_projected_coordinates_and_truncated_page():
    for body in [{"features": [], "spatialReference": {"wkid": 3857}},
                 {"features": [], "exceededTransferLimit": True}]:
        with pytest.raises(ValueError):
            public.ports([json.dumps(body).encode()], STAMP)


def test_immutable_snapshot_roundtrip_temporal_gate_and_raw_corruption(tmp_path):
    payload = json.dumps([metar()]).encode()
    manifest = collect("aviation", lambda _: payload, STAMP, tmp_path)
    rows, manifests = load_provider_snapshots(tmp_path)
    assert len(rows) == 1 and manifests[0]["dataVersion"] == manifest["dataVersion"]
    assert load_provider_snapshots(tmp_path, as_of="2026-11-14T00:00:00Z") == ((), ())
    assert len(load_provider_snapshots(tmp_path, as_of=STAMP)[0]) == 1
    assert collect("aviation", lambda _: payload, STAMP, tmp_path) == manifest
    raw = tmp_path / manifest["dataVersion"] / "raw-000.bin"
    raw.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="raw capture checksum"):
        load_provider_snapshots(tmp_path)
    with pytest.raises(ValueError, match="Immutable"):
        collect("aviation", lambda _: payload, STAMP, tmp_path)


def test_empty_failure_keeps_prior_snapshot(tmp_path):
    collect("aviation", lambda _: json.dumps([metar()]).encode(), STAMP, tmp_path)
    with pytest.raises(ValueError, match="empty"):
        collect("aviation", lambda _: b"[]", STAMP, tmp_path)
    assert len(load_provider_snapshots(tmp_path)[0]) == 1


def test_identity_count_and_normalized_corruption(tmp_path):
    payload = json.dumps([metar()]).encode()
    manifest = collect("aviation", lambda _: payload, STAMP, tmp_path)
    path = tmp_path / manifest["dataVersion"] / "observations.json"
    path.write_bytes(b"[]")
    with pytest.raises(ValueError, match="observation checksum"):
        load_provider_snapshots(tmp_path)


def test_publish_rejects_backdated_availability_duplicate_and_source_url(tmp_path):
    rows, _ = public.aviation(json.dumps([metar()]).encode(), STAMP)
    meta = {k: v for k, v in SOURCES["aviation"].items() if k != "parser"} | {"retrievedAt": STAMP}
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


def test_static_plant_reference_has_no_fuzzy_security_relationship():
    payload = b"gppd_idnr,name,country,latitude,longitude,capacity_mw,primary_fuel,owner,source,url\nx,Plant,JPN,35,139,100,Gas,Company,Registry,https://example.com\n"
    rows, quality = public.plants(payload, STAMP)
    assert quality["rejected"] == 0
    assert rows[0]["properties"]["capacityMw"] == 100
    assert rows[0]["properties"]["securityRelationship"] is None
