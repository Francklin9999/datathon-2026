"""Expansion uses synthetic USGS payloads; source capture validation happens separately."""
import gzip
import json
from datetime import datetime, timezone

import pytest
from aplomb.world import ingest
from aplomb.world.dataset import load_bundle

from scripts import expand_world_events


def test_expansion_keeps_prior_sources_and_archive_and_updates_duplicate_identity(tmp_path, monkeypatch):
    base, out, captures = tmp_path / "base", tmp_path / "out", tmp_path / "captures"
    stamp = datetime(2026, 11, 1, tzinfo=timezone.utc)

    def quake(key, day, title):
        return ingest._event(
            url="https://earthquake.usgs.gov/earthquakes/eventpage/" + key,
            title=title, occurred=day, published=None, category="natural_disaster",
            location={"lat": 40, "lon": -124, "precision": "point", "countryIso3": None, "placeName": title},
            origin="usgs", publisher="U.S. Geological Survey", source_type="data",
        )

    older = quake("older", "2024-01-01", "Synthetic older event")
    duplicate = quake("recent", "2026-11-02", "Synthetic prior title")
    official = ingest._event(
        url="https://www.bankofcanada.ca/test-release", title="Synthetic policy release",
        occurred="2026-10-01", published=None, category="monetary_policy",
        location=ingest._country_location("CAN"), origin="official",
        publisher="Bank of Canada", source_type="official",
    )
    sources = [
        {"id": "usgs_earthquakes", "url": "https://earthquake.usgs.gov/prior", "retrievedAt": "2026-11-01T00:00:00Z",
         "filter": "magnitude >= 6", "status": "ok", "items": 2},
        {"id": "boc_press", "url": official["sources"][0]["url"], "retrievedAt": "2026-11-01T00:00:00Z",
         "status": "ok", "items": 1},
    ]
    ingest.write_bundle(ingest.build_bundle(
        [older, duplicate, official], [], sources, built_at=stamp,
        start="2024-01-01", end="2026-11-12",
    ), base)
    original = (base / "events.json").read_bytes()
    when = int(datetime(2026, 11, 2, tzinfo=timezone.utc).timestamp() * 1000)
    payload = json.dumps({"features": [
        {"id": key, "properties": {"title": title, "mag": 5.1, "time": when, "type": "earthquake",
                                  "place": "Synthetic place", "url": "https://earthquake.usgs.gov/earthquakes/eventpage/" + key},
         "geometry": {"coordinates": [-120, 35, 10]}}
        for key, title in [("recent", "Synthetic revised title"), ("new", "Synthetic new event")]
    ]}).encode()
    monkeypatch.setattr(expand_world_events, "http_get", lambda *_args, **_kwargs: payload)
    result = expand_world_events.expand(base, out, captures, "2026-01-01", "2026-11-12", 5)
    expanded = load_bundle(out)
    assert result["addedEvents"] == 1 and len(expanded.events) == 4
    assert expanded.event(older["eventId"])["title"] == older["title"]
    assert expanded.event(official["eventId"])["sources"] == official["sources"]
    assert expanded.event(duplicate["eventId"])["title"] == "Synthetic revised title"
    assert expanded.event(duplicate["eventId"])["location"]["lat"] == 35
    assert len(expanded.hazards) == 2
    assert gzip.decompress(next(captures.glob("*.gz")).read_bytes()) == payload
    assert (base / "events.json").read_bytes() == original
    source = next(item for item in expanded.manifest["sources"] if item["id"] == "usgs_earthquakes")
    assert source["items"] == 3 and source["parsedItems"] == 2 and source["previousCaptures"]
    with pytest.raises(ValueError, match="already exists"):
        expand_world_events.expand(base, out, captures, "2026-01-01", "2026-11-12", 5)


@pytest.mark.parametrize("start,end,minimum", [
    ("2026-11-12", "2026-01-01", 5), ("2024-01-01", "2026-01-01", 5),
    ("2026-01-01", "2026-11-12", 4), ("2026-01-01", "2026-11-12", float("nan")),
])
def test_invalid_expansion_window_is_rejected_before_network(tmp_path, start, end, minimum):
    with pytest.raises(ValueError, match="ordered window"):
        expand_world_events.expand(tmp_path / "base", tmp_path / "out", tmp_path, start, end, minimum)
