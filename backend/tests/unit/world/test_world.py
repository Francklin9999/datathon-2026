"""WLD-01...WLD-08: ingestion parsers, identity, geography, importance, exposure, filters, layers.

Parser inputs below are synthetic payloads in the sources' formats (clearly not captures). The
packaged bundle, built from the real feeds, is checked for integrity and contract validity."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from aplomb.api.errors import NotFound, ServiceError
from aplomb.api.repositories import ProfileRepository
from aplomb.api.storage import MemoryStore
from aplomb.contracts import models as m
from aplomb.optimizer.services import build_domain_services
from aplomb.world import WorldDataError, WorldServiceImpl, load_bundle, world_passports
from aplomb.world import ingest as ing
from aplomb.world.dataset import WorldDataset
from aplomb.world.geo import UNKNOWN_COUNTRY, country_name, in_bbox, resolve_place_country

from tests.unit.datastore._support import starter_snapshot

SID = "s_6f1c2d3e-4a5b-4c6d-8e7f-0123456789ab"
BUILT = datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc)

USGS = json.dumps({"features": [
    {"id": "us1", "properties": {"mag": 7.1, "place": "12 km W of Petrolia, CA", "time": 1793000000000, "type": "earthquake",
                                 "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us1", "title": "M 7.1 - 12 km W of Petrolia, CA"},
     "geometry": {"coordinates": [-124.4, 40.3, 10.0]}},
    {"id": "us2", "properties": {"mag": 6.4, "place": "central Mid-Atlantic Ridge", "time": 1793100000000, "type": "earthquake",
                                 "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us2", "title": "M 6.4 - central Mid-Atlantic Ridge"},
     "geometry": {"coordinates": [-30.0, 1.0, 10.0]}},
    {"id": "bad", "properties": {"mag": 6.0, "place": "nowhere", "time": 1793100000000, "type": "earthquake", "title": "no url"},
     "geometry": {"coordinates": [0, 0, 0]}},
    {"id": "blast", "properties": {"mag": 6.0, "place": "X", "time": 1793100000000, "type": "explosion",
                                   "url": "https://earthquake.usgs.gov/earthquakes/eventpage/blast", "title": "M 6.0 Explosion"},
     "geometry": {"coordinates": [0, 0, 0]}},
]}).encode()

RSS = b"""<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>
<item><title>Federal Reserve issues FOMC statement</title>
<link><![CDATA[https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm?utm_source=rss]]></link>
<pubDate><![CDATA[Wed, 28 Oct 2026 18:00:00 GMT]]></pubDate></item>
<item><title>No link here</title><pubDate>Wed, 28 Oct 2026 18:00:00 GMT</pubDate></item>
</channel></rss>"""

RDF = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/"
 xmlns:dc="http://purl.org/dc/elements/1.1/">
<item rdf:about="x"><title>Bank of Canada maintains policy rate at 2&#188;%</title>
<link>https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/</link><dc:date>2026-10-28T09:45:00-04:00</dc:date></item>
<item rdf:about="y"><title>Bank of Canada announces appointment of a new Deputy Governor</title>
<link>https://www.bankofcanada.ca/2026/09/appointment/</link><dc:date>2026-09-10T10:00:00-04:00</dc:date></item>
</rdf:RDF>"""


# WLD-01 identity ---------------------------------------------------------------------------------


def test_event_id_is_stable_across_tracking_parameters_and_case():
    a = "https://Example.org/news/story?id=7&utm_source=x&fbclid=abc#top"
    b = "https://example.org/news/story?fbclid=zzz&id=7"
    assert ing.canonical_url(a) == ing.canonical_url(b) == "https://example.org/news/story?id=7"
    assert ing.event_id(a) == ing.event_id(b) and ing.event_id(a).startswith("evt_") and len(ing.event_id(a)) == 16
    assert ing.event_id("https://example.org/news/story?id=8") != ing.event_id(a)     # real query data is kept
    with pytest.raises(ValueError):
        ing.canonical_url("javascript:alert(1)")


def test_same_url_merges_publishers_and_same_headline_alone_does_not():
    base = dict(title="Shared headline", category="other", occurred="2026-11-01", published=None,
                location=ing._country_location("CAN"), origin="official", source_type="official")
    one = ing._event(url="https://example.org/a?utm_medium=feed", publisher="Agency A", **base)
    copy = ing._event(url="https://example.org/a", publisher="Agency A", **base)          # syndicated copy, same publisher
    other = ing._event(url="https://example.org/a", publisher="Agency B", **base)
    distinct = ing._event(url="https://example.org/b", publisher="Agency A", **base)       # same headline, different story
    merged = ing.merge_events([one, copy, other, distinct])
    assert len(merged) == 2
    first = next(e for e in merged if e["eventId"] == one["eventId"])
    assert first["sourceCount"] == 2 and [s["publisher"] for s in first["sources"]] == ["Agency A", "Agency B"]
    assert first["sources"][0]["url"] == "https://example.org/a?utm_medium=feed"            # deterministic primary source


# WLD-02 nothing invented --------------------------------------------------------------------------


@pytest.mark.parametrize("place,expected", [
    ("12 km W of Petrolia, CA", "USA"), ("Bonin Islands, Japan region", "JPN"), ("48 km WNW of Pólis, Cyprus", None),
    ("central Mid-Atlantic Ridge", None), ("south of the Fiji Islands", None), ("10 km S of Tbilisi, Georgia", None),
    ("Kermadec Islands, New Zealand", "NZL"), ("near the coast of Nicaragua", None), (None, None), ("", None),
    ("30 km WSW of Lata, Solomon Islands", "SLB"), ("Alaska Peninsula", None), ("5 km N of Izmir, Türkiye", "TUR"),
])
def test_place_resolves_only_to_a_named_unambiguous_country(place, expected):
    assert resolve_place_country(place) == expected


@pytest.mark.parametrize("place", ["20 km N of Haifa, Israel", "Ramallah, Palestine", "Khan Younis, Gaza Strip", "Jenin, West Bank"])
def test_places_of_one_region_resolve_to_palestine(place):
    assert resolve_place_country(place) == "PSE"
    assert country_name("PSE") == {"en": "Palestine", "fr": "Palestine"}


@pytest.mark.parametrize("title,expected", [
    ("Apple harvest hits record in Ontario", []), ("Apple Inc. reports quarterly results", ["AAPL"]),
    ("Amazon rainforest fires spread", []), ("Regulator fines Amazon.com over warehouse rules", ["AMZN"]),
    ("Tesla coil exhibit opens", []), ("Tesla Inc recalls vehicles", ["TSLA"]),
    ("Royal Bank of Canada and Enbridge announce financing", ["RY.TO", "ENB.TO"]),
    ("Microsoftware conference", []), ("Fortis hospital expands", []),
])
def test_company_mentions_need_an_unambiguous_alias(title, expected):
    assert ing.related_tickers(title) == expected


def test_parsers_keep_verbatim_fields_and_reject_incomplete_items():
    events, hazards, rejected = ing.parse_usgs(USGS)
    assert (len(events), len(hazards), rejected) == (2, 2, 2)                    # no URL, and a non-earthquake
    quake = events[0]
    assert quake["title"] == "M 7.1 - 12 km W of Petrolia, CA" and quake["origin"] == "usgs"
    assert quake["location"] == {"lat": 40.3, "lon": -124.4, "countryIso3": "USA", "placeName": "12 km W of Petrolia, CA", "precision": "point"}
    assert quake["publishedAt"] is None and quake["sources"][0]["publishedAt"] is None     # unknown, not invented
    assert events[1]["location"]["countryIso3"] is None and events[1]["relatedCountries"] == []
    assert hazards[0]["hazardId"] == "usgs_us1" and hazards[0]["magnitude"] == 7.1

    fed, bad = ing.parse_feed(RSS, publisher="Federal Reserve Board", iso3="USA", default_category="monetary_policy")
    assert (len(fed), bad) == (1, 1)
    assert fed[0]["eventId"] == ing.event_id("https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm")
    assert fed[0]["location"]["precision"] == "country" and fed[0]["publishedAt"] == "2026-10-28T18:00:00Z"
    assert fed[0]["relatedThemes"] == ["bonds_us", "long_treasuries"] and fed[0]["relatedCountries"] == ["USA"]

    boc, _ = ing.parse_feed(RDF, publisher="Bank of Canada", iso3="CAN", default_category="other")
    assert [e["category"] for e in boc] == ["monetary_policy", "other"]
    assert boc[0]["title"] == "Bank of Canada maintains policy rate at 2¼%"
    assert boc[0]["occurredAt"] == "2026-10-28" and boc[0]["publishedAt"] == "2026-10-28T13:45:00Z"
    assert boc[1]["relatedThemes"] == []                                         # no theme proxy without a rate decision


def test_statcan_release_needs_a_real_page_title():
    row = {"sourceUrl": "https://www150.statcan.gc.ca/n1/daily-quotidien/220119/dq220119a-eng.htm", "publishedAt": "2022-01-19"}
    event = ing.statcan_event(row, b"<html><head><title>The Daily \xe2\x80\x94 Consumer Price Index, December 2021</title></head></html>")
    assert event["title"] == "Consumer Price Index, December 2021" and event["category"] == "macro_release"
    assert event["occurredAt"] == "2022-01-19" and event["location"]["countryIso3"] == "CAN"
    for page in (b"<html><title>301 Moved Permanently</title></html>", b"<html>no title</html>"):
        with pytest.raises(ValueError):
            ing.statcan_event(row, page)


# WLD-03 importance --------------------------------------------------------------------------------


def test_importance_is_reproducible_at_the_build_date():
    events, _, _ = ing.parse_usgs(USGS)
    ev = dict(events[0], occurredAt="2026-11-05")
    assert ing.importance(ev, date(2026, 11, 15)) == pytest.approx(0.45 + 0.35 / 5 + 0.20 * (1 - 10 / 30))
    assert ing.importance(ev, date(2026, 11, 15)) == ing.importance(ev, date(2026, 11, 15))
    assert ing.importance(dict(ev, occurredAt="2025-01-01"), date(2026, 11, 15)) == pytest.approx(0.52)
    news = dict(ev, sources=[dict(ev["sources"][0], sourceType="news")], sourceCount=7)
    assert ing.importance(news, date(2026, 11, 15)) == pytest.approx(0.35 + 0.20 * (1 - 10 / 30))


def test_bundle_build_is_deterministic_and_self_describing(tmp_path):
    events, hazards, _ = ing.parse_usgs(USGS)
    sources = [{"id": "usgs_earthquakes", "name": "USGS", "status": "ok", "items": 2, "filter": "magnitude >= 6.0"}]
    files = ing.build_bundle(events, hazards, sources, built_at=BUILT, start="2026-01-01", end="2026-12-31")
    again = ing.build_bundle(events, hazards, sources, built_at=BUILT, start="2026-01-01", end="2026-12-31")
    assert files == again
    ing.write_bundle(files, tmp_path)
    ds = load_bundle(tmp_path)
    assert ds.version == "snap-20261115-world" and len(ds.events) == 2 and ds.coverage["start"] <= ds.coverage["end"]
    assert all(e["dataVersion"] == ds.version and e["datasetId"] == "world_events" for e in ds.events)
    (tmp_path / "events.json").write_text((tmp_path / "events.json").read_text(encoding="utf-8").replace("M 7.1", "M 9.9"), encoding="utf-8")
    with pytest.raises(WorldDataError):
        load_bundle(tmp_path)                                                    # a tampered file is refused


# WLD-08 upstream failure ---------------------------------------------------------------------------


def test_a_failed_source_is_recorded_and_never_replaced(tmp_path):
    release_csv = tmp_path / "releases.csv"
    release_csv.write_text("seriesId,referenceDate,publishedAt,vintageAt,sourceUrl\n"
                           "S,2026-09-01,2026-10-19,,https://www150.statcan.gc.ca/a.htm\n", encoding="utf-8")

    def fetch(url):
        if "usgs" in url:
            return USGS
        raise TimeoutError("simulated outage")

    events, hazards, sources = ing.collect("2026-01-01", "2026-12-31", fetch=fetch, release_csv=release_csv, now=lambda: BUILT,
                                           pause=0, log=lambda _: None)
    status = {s["id"]: s["status"] for s in sources}
    assert status == {"usgs_earthquakes": "ok", "boc_press": "failed", "fed_monetary": "failed", "statcan_daily": "failed"}
    assert {e["origin"] for e in events} == {"usgs"} and len(hazards) == 2
    assert all("simulated outage" in s["error"] or "no release page" in s["error"] for s in sources if s["status"] == "failed")


# Service ------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def world():
    snap = starter_snapshot()
    profiles, _ = build_domain_services(ProfileRepository(MemoryStore()), lambda: snap)
    dataset = load_bundle()
    return WorldServiceImpl(profiles, lambda: snap, lambda: dataset, clock=lambda: BUILT)


def test_packaged_bundle_is_real_cited_and_contract_valid():
    ds = load_bundle()
    assert len(ds.events) >= 100 and ds.manifest["events"]["byOrigin"].keys() >= {"official", "usgs"}
    ids = set()
    for raw in ds.events:
        event = m.WorldEvent.model_validate(raw)
        assert event.event_id == ing.event_id(event.sources[0].url) and event.event_id not in ids
        ids.add(event.event_id)
        assert event.title.strip() and all(s.url.startswith("https://") for s in event.sources)
        assert event.importance == ing.importance(raw, date.fromisoformat(ds.built_at[:10]))
        if event.location.precision == "country":
            assert event.location.country_iso3 in event.related_countries
    for raw in ds.hazards:
        m.Hazard.model_validate(raw)
    assert all(s["status"] in ("ok", "failed") and s["retrievedAt"] for s in ds.manifest["sources"])
    assert {n["source"] for n in ds.manifest["notIngested"]} >= {"GDELT"}


def test_not_ingested_reasons_match_the_loaded_layers():
    # The committed manifest carries the reasons build_bundle writes, and they name where facility
    # emissions and FIRMS detections are served instead of calling them "not loaded".
    built = json.loads(ing.build_bundle([], [], [], built_at=BUILT, start="2026-01-01", end="2026-01-02")["manifest.json"])
    committed = load_bundle().manifest["notIngested"]
    assert committed == built["notIngested"]
    reasons = {n["source"]: n["reason"] for n in committed}
    assert "emissions_facilities" in reasons["ECCC / EPA facility emissions"]
    assert "world_firms_" in reasons["NASA FIRMS wildfires"] and "key" not in reasons["NASA FIRMS wildfires"]
    from aplomb.world.facilities import load_facilities
    from aplomb.world.providers import load_provider_snapshots
    assert load_facilities()[1]["datasetId"] == "emissions_facilities"
    loaded = {m["datasetId"] for m in load_provider_snapshots(errors=[])[1]}
    assert {"world_firms_modis_europe", "world_gdelt_event_metadata"} <= loaded


def test_layers_report_what_is_loaded(world):
    layers = {layer.layer_id: layer for layer in world.layers(SID, {}).items}
    ds = world.dataset()
    assert layers["events"].available and layers["events"].count == len(ds.events)
    assert layers["events"].coverage.to_wire() == ds.coverage
    assert layers["exposure"].available and layers["hazards"].available and layers["hazards"].count == len(ds.hazards)
    assert layers["facilities"].available and layers["facilities"].count == 1863
    facilities = world.facilities(SID, {"limit": 3})
    assert facilities.total == 1863 and len(facilities.items) == 3
    assert all(row.ticker is None and row.match_confidence == "none" for row in facilities.items)

    def broken():
        raise WorldDataError("missing")

    offline = WorldServiceImpl(world.profiles, world.snapshot, broken)
    assert {layer.layer_id: layer.available for layer in offline.layers(SID, {}).items} == {
        "airports": True, "events": False, "exposure": True, "facilities": True, "hazards": False}
    with pytest.raises(ServiceError) as exc:
        offline.events(SID, {})
    assert exc.value.code == "upstream_unavailable"


def test_default_feed_is_the_last_thirty_days_of_the_dataset(world):
    page = world.events(SID, {"limit": 1000})
    coverage = world.dataset().coverage
    assert page.coverage.to_wire() == coverage and page.data_version == world.dataset().version
    assert page.total == len(page.items) > 0
    first = date.fromisoformat(coverage["end"]).toordinal() - 29
    assert all(first <= date.fromisoformat(e.occurred_at).toordinal() for e in page.items)
    scores = [e.importance for e in page.items]
    assert scores == sorted(scores, reverse=True)
    assert all(e.portfolio_relevant is None for e in page.items)                           # only with a profile


def test_explicit_historical_queries_exclude_current_only_world_capture(world):
    ds = world.dataset()
    before = (date.fromisoformat(ds.built_at[:10]) - timedelta(days=1)).isoformat()
    event = ds.events[0]
    query = {"from": event["occurredAt"], "to": event["occurredAt"], "asOf": before}
    assert world.events(SID, query).total == 0
    assert world.hazards(SID, {"asOf": before}).total == 0
    if event["location"]["countryIso3"]:
        assert world.country(SID, event["location"]["countryIso3"], query).events == []
    with pytest.raises(NotFound):
        world.event(SID, event["eventId"], {"asOf": before})
    assert world.events(SID, {"from": event["occurredAt"], "to": event["occurredAt"]}).total > 0


def test_observations_are_geolocated_paginated_and_capture_gated(world):
    service = WorldServiceImpl(world.profiles, world.snapshot, world.dataset, clock=lambda: BUILT)
    service._provider_capture = (({
        "id": "world_test:station", "sourceId": "world_test", "category": "aviation",
        "title": "Sydney station report", "sourceUrl": "https://example.org/station",
        "retrievedAt": "2026-11-15T01:00:00Z", "availableAt": "2026-11-15T01:00:00Z",
        "observedAt": "2026-11-14T23:00:00Z", "publishedAt": None,
        "latitude": -33.9, "longitude": 151.2, "countryIso3": "AUS",
        "properties": {"stationId": "YSSY", "metar": "YSSY sample", "geographicRole": "weather_station"},
    },), ({"dataVersion": "world-test-1", "retrievedAt": "2026-11-15T01:00:00Z"},))
    current = service.observations(SID, {"mode": "aviation", "country": ["AUS"]})
    assert current.total == 1 and current.items[0].location.lat < 0
    assert current.items[0].source.url == "https://example.org/station"
    assert next(m for m in current.modes if m.mode == "aviation").available
    assert service.observations(SID, {"mode": "aviation", "asOf": "2026-11-14"}).total == 0
    assert service.observations(SID, {"mode": "aviation", "bbox": "100,-40,160,-20"}).total == 1
    assert service.observations(SID, {"mode": "aviation", "bbox": "-100,-40,-80,-20"}).total == 0
    page = service.observations(SID, {"mode": "hazards", "limit": 1})
    assert page.total > 1 and page.next_cursor
    second = service.observations(SID, {"mode": "hazards", "limit": 1, "cursor": page.next_cursor})
    assert page.items[0].id != second.items[0].id
    with pytest.raises(ServiceError):
        service.observations(SID, {"mode": "news", "cursor": page.next_cursor})


def test_unlocated_policy_publication_is_in_feed_but_not_on_map(world):
    service = WorldServiceImpl(world.profiles, world.snapshot, world.dataset, clock=lambda: BUILT)
    service._provider_capture = (({
        "id": "world_federal_register:notice", "sourceId": "world_federal_register",
        "category": "policy", "title": "Federal notice",
        "sourceUrl": "https://www.federalregister.gov/documents/notice",
        "retrievedAt": "2026-11-15T01:00:00Z", "availableAt": "2026-11-15T01:00:00Z",
        "observedAt": None, "publishedAt": "2026-11-13",
        "latitude": None, "longitude": None, "countryIso3": "USA",
        "properties": {"geographicRole": "national_jurisdiction"},
    },), ({"dataVersion": "policy-test-1", "retrievedAt": "2026-11-15T01:00:00Z",
             "datasetId": "world_federal_register", "name": "Federal Register"},))
    feed = service.observations(SID, {"mode": "news", "q": "Federal notice"})
    assert feed.total == 1
    assert feed.items[0].location is None
    assert feed.items[0].time_basis == "event_date"
    assert feed.items[0].published_at == "2026-11-13T00:00:00Z"
    assert feed.items[0].source.name == "Federal Register"
    assert service.observations(SID, {"mode": "news", "bbox": "-130,20,-60,55",
                                      "q": "Federal notice"}).total == 0
    assert service.observations(SID, {"mode": "news", "q": "Federal notice",
                                      "asOf": "2026-11-14"}).total == 0


def test_overview_balances_sources_and_places_without_duplicate_event_markers(world):
    service = WorldServiceImpl(world.profiles, world.snapshot, world.dataset, clock=lambda: BUILT)
    stamp = "2026-11-15T01:00:00Z"

    def row(source, key, lat, lon):
        return {
            "id": key, "sourceId": source, "category": "news", "title": key,
            "sourceUrl": "https://example.org/" + key, "retrievedAt": stamp,
            "availableAt": stamp, "observedAt": None, "publishedAt": None,
            "latitude": lat, "longitude": lon, "countryIso3": None, "properties": {},
        }

    dense = [row("large_registry", f"dense-{n:03}", 40, 40) for n in range(20)]
    other_place = row("large_registry", "other-place", -40, -100)
    small = [row("small_feed", "small-1", 20, 100), row("small_feed", "small-2", -20, -100)]
    unlocated = row("unlocated_source", "unlocated", None, None)
    sources = tuple({"datasetId": name, "dataVersion": name + "-1", "retrievedAt": stamp}
                    for name in ("large_registry", "small_feed", "unlocated_source"))
    service._provider_capture = (tuple(dense + [other_place] + small + [unlocated]), sources)
    query = {"scope": "providers", "mapOnly": True, "order": "coverage", "limit": 4}
    first = service.observations(SID, query)
    assert first.total == 23 and first.next_cursor
    assert {item.dataset_id for item in first.items} == {"large_registry", "small_feed"}
    assert {item.id for item in first.items} >= {"other-place", "small-1", "small-2"}
    assert all(item.location is not None and not item.id.startswith("evt_") for item in first.items)
    ids = [item.id for item in first.items]
    cursor = first.next_cursor
    while cursor:
        page = service.observations(SID, {**query, "cursor": cursor})
        ids.extend(item.id for item in page.items)
        cursor = page.next_cursor
    assert len(ids) == len(set(ids)) == 23
    assert service.observations(SID, {**query, "mapOnly": False}).total == 24
    for change in ({"scope": "all"}, {"mapOnly": False}, {"order": "date"}):
        with pytest.raises(ServiceError):
            service.observations(SID, {**query, **change, "cursor": first.next_cursor})
    assert service.observations(SID, {**query, "asOf": "2026-11-14"}).total == 0


def test_one_damaged_provider_capture_disables_only_its_own_mode(world, tmp_path, monkeypatch):
    import shutil

    import aplomb.world.providers as providers
    from aplomb.world.providers.snapshot import DIRECTORY

    def capture(source):
        return next(path for path in sorted(DIRECTORY.iterdir()) if path.name.startswith(source + "-2"))

    hazard, aviation = capture("world_firms_modis_europe"), capture("world_aviation_weather")
    for path in (hazard, aviation):
        shutil.copytree(path, tmp_path / path.name)
    strict = providers.load_provider_snapshots
    monkeypatch.setattr(providers, "load_provider_snapshots",
                        lambda directory=None, **kw: strict(tmp_path, **kw))

    def statuses():
        service = WorldServiceImpl(world.profiles, world.snapshot, world.dataset, clock=lambda: BUILT)
        page = service.observations(SID, {"scope": "providers"})
        return service, page, {s.mode: s for s in page.modes}

    (tmp_path / hazard.name / "observations.json").write_bytes(b"[]")
    service, page, modes = statuses()
    assert [source for source, _ in service._provider_failures] == ["world_firms_modis_europe"]
    assert {item.dataset_id for item in page.items} == {"world_aviation_weather"}
    assert modes["aviation"].available and modes["aviation"].reason is None
    assert not modes["hazards"].available
    assert modes["hazards"].reason == "Provider capture failed integrity validation."
    assert modes["macro"].reason == "No geolocated authorized capture is loaded."

    # A damaged source whose mode cannot be told from its ID: every empty mode may be the affected one.
    shutil.rmtree(tmp_path / hazard.name)
    (tmp_path / aviation.name / "observations.json").write_bytes(b"[]")
    service, page, modes = statuses()
    assert page.total == 0 and [source for source, _ in service._provider_failures] == ["world_aviation_weather"]
    assert all(s.reason == "Provider capture failed integrity validation." for s in modes.values())


@pytest.mark.parametrize("query", [
    {"scope": "unverified"}, {"order": "random"}, {"mapOnly": "true"},
])
def test_observation_overview_options_are_validated(world, query):
    with pytest.raises(ServiceError):
        world.observations(SID, query)


def test_event_geography_is_evidenced_without_ownership(world):
    event = next(e for e in world.dataset().events if e["location"]["precision"] == "point")
    detail = world.event(SID, event["eventId"], {}).to_wire()
    edge = detail["geographicRelationships"][0]
    assert edge["relation"] == "EVENT_OCCURRED_AT"
    assert edge["subjectId"] == event["eventId"]
    assert edge["objectId"].startswith("point:")
    assert edge["sourceUrl"] == event["sources"][0]["url"]
    assert len(edge["normalizedRecordSha256"]) == 64


def test_filters_pagination_and_cursor_binding(world):
    q = {"from": "2025-11-13", "to": "2026-11-12"}
    everything = world.events(SID, {**q, "limit": 1000})
    expected_ids = {event["eventId"] for event in world.dataset().events
                    if q["from"] <= event["occurredAt"] <= q["to"]}
    assert everything.total == len(expected_ids)
    assert len(everything.items) == min(everything.total, 1000)
    assert (everything.next_cursor is not None) == (everything.total > 1000)
    seen, cursor, pages = [], None, 0
    while True:
        page = world.events(SID, {**q, "limit": 40, **({"cursor": cursor} if cursor else {})})
        seen += [e.event_id for e in page.items]
        pages += 1
        assert page.total == everything.total
        cursor = page.next_cursor
        if cursor is None:
            break
    assert seen[:len(everything.items)] == [e.event_id for e in everything.items]
    assert len(seen) == len(set(seen)) == everything.total and set(seen) == expected_ids
    assert pages == -(-everything.total // 40)
    first_cursor = world.events(SID, {**q, "limit": 40}).next_cursor
    for bad in ({**q, "limit": 40, "cursor": "garbage"}, {**q, "category": ["monetary_policy"], "limit": 40, "cursor": first_cursor}):
        with pytest.raises(ServiceError) as exc:
            world.events(SID, bad)
        assert exc.value.code == "validation_error"

    policy = world.events(SID, {**q, "category": ["monetary_policy"], "country": ["CAN"]})
    assert policy.total > 0 and all(e.category == "monetary_policy" and "CAN" in e.related_countries for e in policy.items)
    assert all(e.origin == "usgs" for e in world.events(SID, {**q, "origin": ["usgs"]}).items)
    by_date = world.events(SID, {**q, "sort": "date"}).items
    assert [e.occurred_at for e in by_date] == sorted((e.occurred_at for e in by_date), reverse=True)
    text = world.events(SID, {**q, "q": "federal reserve"})
    assert text.total > 0 and all("federal reserve" in (e.title + e.sources[0].publisher).lower() for e in text.items)
    themed = world.events(SID, {**q, "theme": "bonds_canada"})
    assert themed.total > 0 and all("bonds_canada" in e.related_themes for e in themed.items)
    assert world.events(SID, {**q, "ticker": "TSLA"}).total == 0
    box = world.events(SID, {**q, "bbox": "120,20,150,50", "limit": 1000})
    assert box.total > 0 and all(120 <= e.location.lon <= 150 and 20 <= e.location.lat <= 50 for e in box.items)
    for bad in ({"from": "2024-01-01", "to": "2026-01-01"}, {"origin": ["rumour"]}):
        with pytest.raises(ServiceError):
            world.events(SID, bad)


def test_bbox_crossing_the_dateline_is_two_boxes():
    assert in_bbox(-17.0, 179.0, (170.0, -30.0, -170.0, 0.0)) and in_bbox(-17.0, -175.0, (170.0, -30.0, -170.0, 0.0))
    assert not in_bbox(-17.0, 0.0, (170.0, -30.0, -170.0, 0.0)) and not in_bbox(10.0, 179.0, (170.0, -30.0, -170.0, 0.0))


# WLD-04 exposure ----------------------------------------------------------------------------------


@pytest.mark.parametrize("profile_id", ["robert", "amira", "mateo"])
def test_country_weights_sum_to_the_portfolio_with_an_unknown_bucket(world, profile_id):
    body = world.exposure(SID, {"profileId": profile_id}).to_wire()
    assert sum(i["weightPct"] for i in body["items"]) == pytest.approx(100.0)
    assert all(i["basis"] == "listing_country" for i in body["items"])
    for item in body["items"]:
        assert sum(h["weightPct"] for h in item["holdings"]) == pytest.approx(item["weightPct"])
        fact = next(f for f in body["facts"].values() if f["subject"]["id"] == item["countryIso3"])
        assert fact["value"] == pytest.approx(item["weightPct"]) and fact["metric"] == "weight.country"
        assert fact["createdBy"] == "world" and fact["sources"][0]["datasetId"] == "assets_universe"
    assert "LIM_ETF_NO_LOOKTHROUGH" in body["limitations"] and UNKNOWN_COUNTRY in body["basisNote"]["en"]
    universe = starter_snapshot().gate("2026-11-12").universe()
    unknown = next((i for i in body["items"] if i["countryIso3"] == UNKNOWN_COUNTRY), None)
    if unknown:
        assert body["items"][-1] is unknown                                       # shown separately, last
        assert all(universe.get(h["ticker"]).country is None for h in unknown["holdings"])
    assert country_name(UNKNOWN_COUNTRY)["en"].startswith("No listing country")


def test_amira_holds_crypto_so_her_unknown_bucket_is_not_redistributed(world):
    items = {i.country_iso3: i for i in world.exposure(SID, {"profileId": "amira"}).items}
    assert UNKNOWN_COUNTRY in items and {h.ticker for h in items[UNKNOWN_COUNTRY].holdings} <= {"BTC-USD", "ETH-USD"}


# WLD-07 links without impact ----------------------------------------------------------------------


def test_event_links_are_code_matches_with_no_impact_claim(world):
    ds = world.dataset()
    event = next(e for e in reversed(ds.events) if e["category"] == "monetary_policy" and e["relatedCountries"] == ["CAN"])
    detail = world.event(SID, event["eventId"], {"profileId": "robert"}).to_wire()
    assert detail["event"]["eventId"] == event["eventId"]
    assert detail["exposures"], "Robert holds Canadian listings"
    assert all(x["impact"] == "not_established" and x["impactFactId"] is None and x["evidenceIds"] == [] for x in detail["exposures"])
    assert {x["linkType"] for x in detail["exposures"]} <= {"named_in_source", "theme", "listing_country"}
    assert all("not established" in x["note"]["en"] for x in detail["exposures"])
    themed = [x for x in detail["exposures"] if x["linkType"] == "theme"]
    assert themed and all("team assumption" in x["note"]["en"] for x in themed)
    tickers = [x["ticker"] for x in detail["exposures"]]
    assert len(tickers) == len(set(tickers))                                       # strongest link per holding
    assert len(detail["related"]) <= 10 and all(e["eventId"] != event["eventId"] for e in detail["related"])
    assert world.event(SID, event["eventId"], {}).exposures == []                   # no profile, no exposure rows
    with pytest.raises(NotFound):
        world.event(SID, "evt_000000000000", {})


def test_portfolio_relevance_is_a_documented_match(world):
    q = {"from": "2025-11-13", "to": "2026-11-12", "limit": 1000, "profileId": "robert"}
    items = world.events(SID, q).items
    assert all(e.portfolio_relevant is not None for e in items)
    exposed = {i.country_iso3 for i in world.exposure(SID, {"profileId": "robert"}).items} - {UNKNOWN_COUNTRY}
    for e in items:
        assert e.portfolio_relevant == bool(set(e.related_countries) & exposed or e.related_tickers)
    assert any(e.portfolio_relevant for e in items) and any(not e.portfolio_relevant for e in items)


def test_country_panel(world):
    panel = world.country(SID, "CAN", {"profileId": "robert"}).to_wire()
    assert panel["name"] == {"en": "Canada", "fr": "Canada"} and panel["exposure"]["countryIso3"] == "CAN"
    assert 0 < len(panel["events"]) <= 20 and all("CAN" in e["relatedCountries"] for e in panel["events"])
    assert [f["subject"]["id"] for f in panel["macro"] if f["sources"][0]["datasetId"] == "macro_rates"] == ["V39079", "STATIC_TOTALCPICHANGE"]
    for fact in [f for f in panel["macro"] if f["sources"][0]["datasetId"] == "macro_rates"]:
        assert fact["kind"] == "observed" and fact["method"]["id"] == "M_OBSERVED_ROW" and fact["sources"][0]["datasetId"] == "macro_rates"
        assert fact["period"]["end"] <= "2026-11-12" and fact["availableAt"]
    japan = world.country(SID, "JPN", {"profileId": "robert"}).to_wire()
    assert japan["exposure"] is None and len(japan["macro"]) == 4 and japan["name"]["fr"] == "Japon"
    assert world.country(SID, "XKX", {}).to_wire()["name"] == {"en": "XKX", "fr": "XKX"}   # unknown code is not guessed
    for bad in ("can", "CA", "C4N"):
        with pytest.raises(ServiceError):
            world.country(SID, bad, {})


def test_hazards_filters(world):
    ds = world.dataset()
    everything = world.hazards(SID, {"limit": 2000})
    assert everything.total == len(ds.hazards)
    assert len(everything.items) == min(2000, everything.total)
    recent = world.hazards(SID, {"from": "2026-01-01", "to": "2026-11-12", "limit": 2000})
    assert 0 < recent.total < everything.total and all(h.occurred_at[:4] == "2026" for h in recent.items)
    assert world.hazards(SID, {"type": "wildfire"}).total == 0
    assert len(world.hazards(SID, {"limit": 5}).items) == 5 and world.hazards(SID, {"limit": 5}).total == everything.total
    with pytest.raises(ServiceError):
        world.hazards(SID, {"type": "flood"})


def test_search_tool_respects_the_as_of_date(world):
    found = world.search_events(q="Consumer Price Index", country="CAN", as_of="2023-06-30", limit=50)
    assert found and all(e["occurredAt"] <= "2023-06-30" for e in found)
    assert world.search_events(q="Consumer Price Index", country="CAN", as_of="2023-06-30",
                               historical=True) == []


def test_passports_describe_the_loaded_bundle(world):
    ds = world.dataset()
    passports = world_passports(ds)
    for dataset_id in ("world_events", "natural_hazards"):
        body = m.DatasetPassport.model_validate({"datasetId": dataset_id, "name": {"en": "-", "fr": "-"}, "role": {"en": "-", "fr": "-"},
                                                 **passports[dataset_id]}).to_wire()
        assert body["status"] == "in_use" and body["dataVersion"] == ds.version and body["retrievedOn"] == ds.built_at[:10]
    assert passports["world_events"]["rowCount"] == len(ds.events)
    assert any("GDELT" in p["en"] for p in passports["world_events"]["processing"])            # what is not loaded is stated
    empty = WorldDataset(ds.version, ds.built_at, (), (), ds.manifest)
    assert world_passports(empty) == {}


@pytest.mark.parametrize("query", [{"from": "9999-12-01"}, {"to": "0001-01-10"}, {"from": "0001-01-01"}, {"to": "9999-12-31"},
                                   {"from": "2027-01-01"}, {"to": "2020-01-01"}])
def test_bounds_far_outside_the_dataset_select_nothing_and_never_overflow(world, query):
    page = world.events(SID, dict(query))
    panel = world.country(SID, "CAN", dict(query))
    if query.get("from", "") > "2026-11-12" or query.get("to", "9999") < "2021-11-14":
        assert page.total == 0 and panel.events == []
    else:
        assert page.total >= 0
