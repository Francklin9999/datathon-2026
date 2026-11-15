"""Holdings screens for source records and optional globe references, without invented exposure."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest
from aplomb.api.errors import NotFound, ServiceError
from aplomb.api.repositories import ProfileRepository
from aplomb.api.storage import MemoryStore
from aplomb.contracts import api as a
from aplomb.optimizer.services import build_domain_services
from aplomb.world import WorldServiceImpl, load_bundle
from aplomb.world.assessment import source_context
from aplomb.world.dataset import WorldDataset

from tests.unit.datastore._support import starter_snapshot

SID = "s_6f1c2d3e-4a5b-4c6d-8e7f-0123456789ab"
NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


@pytest.fixture
def world():
    snapshot = starter_snapshot()
    profiles, _ = build_domain_services(ProfileRepository(MemoryStore()), lambda: snapshot)
    dataset = load_bundle()
    return WorldServiceImpl(profiles, lambda: snapshot, lambda: dataset, clock=lambda: NOW)


@pytest.mark.parametrize("record,properties,expected", [
    ({"title": "Epicenter", "sourceId": "world_usgs_geojson"}, {"place": "Bonin Islands, Japan region"}, ["JPN"]),
    ({"title": "Epicenter", "sourceId": "world_usgs_geojson"}, {"place": "Alaska Peninsula"}, []),
    ({"title": "Ambiguous location"}, {"place": "Tbilisi, Georgia"}, []),
    ({"title": "Location mention", "sourceId": "world_gdelt_event_metadata"},
     {"sourceCountryFips": "CH"}, ["CHN"]),  # FIPS CH is China, not ISO CH (Switzerland)
    ({"title": "Location mention", "sourceId": "world_gdelt_gkg_locations"},
     {"sourceCountryFips": "AS"}, ["AUS"]),  # FIPS AS is Australia, not American Samoa
    ({"title": "Location mention", "sourceId": "world_gdelt_geographic_mentions"},
     {"sourceLocationName": "Kingfield, Maine, United States", "sourceCountryFips": "US"}, ["USA"]),
    ({"title": "Unmapped code", "sourceId": "world_gdelt_event_metadata"}, {"sourceCountryFips": "XX"}, []),
    ({"title": "Other code system"}, {"sourceCountryFips": "CA"}, []),
    ({"title": "No listing country", "countryIso3": "ZZZ", "relatedCountries": ["ZZZ"]}, {}, []),
    ({"title": "Source area"}, {"sourceCountries": ["Japan", "Canada", "Japan"]}, ["CAN", "JPN"]),
    ({"title": "Australian search-area pixel", "sourceId": "world_firms_modis_australia_area",
      "latitude": -30, "longitude": 145}, {}, []),  # coordinates and search area do not create a country
])
def test_countries_use_explicit_source_evidence(record, properties, expected):
    assert source_context(record, properties=properties)["relatedCountries"] == expected


def test_company_fields_are_name_mentions_without_mutating_registry_relationships():
    row = {"name": "Reporting site", "operator": "Royal Bank of Canada", "ticker": None,
           "matchConfidence": "none", "countryIso3": "CAN"}
    before = copy.deepcopy(row)
    context = source_context(row)
    assert context["relatedTickers"] == ["RY.TO"]
    assert row == before and row["ticker"] is None and row["matchConfidence"] == "none"
    assert source_context({"title": "Apple harvest near an Amazon rainforest"})["relatedTickers"] == []
    assert source_context({"title": "Plant"}, properties={"reportedOwner": "Fortis Inc."})["relatedTickers"] == ["FTS.TO"]


@pytest.mark.parametrize("record,properties,themes", [
    ({"title": "Foreign reference", "sourceId": "energy_wri_plants"}, {"primaryFuel": "Gas"}, ["fossil_energy", "utilities"]),
    ({"title": "Foreign reference", "sourceId": "energy_wri_plants"}, {"primaryFuel": "Hydro"}, ["utilities"]),
    ({"title": "Solar generation", "sourceId": "world_ember_monthly_generation_2026"}, {}, ["utilities"]),
    ({"title": "Policy rate decision", "countryIso3": "CAN"}, {}, ["bonds_canada"]),
    ({"title": "Unattributed policy rate decision"}, {}, []),
    ({"title": "Gold Coast Airport"}, {}, []),
    ({"title": "Cloud cover observation"}, {}, []),
    ({"title": "Mineral estimate"}, {"commodity": "GOLD"}, ["gold"]),
    ({"title": "Mineral estimate"}, {"commodity": None}, []),
])
def test_theme_rules_use_supported_financial_context(record, properties, themes):
    assert source_context(record, properties=properties)["relatedThemes"] == themes


def provider_row(key, *, title, country=None, source="test_reference", props=None, located=True):
    return {
        "id": key, "sourceId": source, "category": "energy" if source == "energy_wri_plants" else "news",
        "title": title, "sourceUrl": "https://example.org/" + key,
        "retrievedAt": "2026-11-15T01:00:00Z", "availableAt": "2026-11-15T01:00:00Z",
        "observedAt": None, "publishedAt": None,
        "latitude": 35 if located else None, "longitude": 139 if located else None,
        "countryIso3": country, "properties": props or {},
    }


def test_every_source_record_is_screened_and_matches_are_unique(world):
    rows = (
        provider_row("named", title="Royal Bank of Canada bulletin", country="JPN"),
        provider_row("theme", title="Foreign plant", country="JPN", source="energy_wri_plants",
                     props={"primaryFuel": "Gas", "capacityMw": 100}),
        provider_row("country", title="National reference", country="USA", located=False),
        provider_row("unknown", title="Ocean observation"),
        provider_row("negative", title="Foreign reference", country="JPN"),
    )
    original = copy.deepcopy(rows)
    world._provider_capture = (rows, ({"dataVersion": "test-1", "retrievedAt": "2026-11-15T01:00:00Z"},))
    page = world.observations(SID, {"profileId": "robert", "scope": "providers", "limit": 20})
    assessed = {row.id: row.assessment for row in page.items}
    assert page.total == 5 and set(assessed) == {row["id"] for row in rows}
    for assessment in assessed.values():
        assert assessment.profile_id == "robert" and assessment.holdings_checked == 11
        assert assessment.assessed_at == "2026-11-15T12:00:00Z"
        assert assessment.matched_weight_pct == pytest.approx(sum(row.weight_pct for row in assessment.exposures))
        assert len({row.ticker for row in assessment.exposures}) == len(assessment.exposures)
        assert all(row.impact == "not_established" and not row.evidence_ids for row in assessment.exposures)
    assert [(row.ticker, row.link_type) for row in assessed["named"].exposures] == [("RY.TO", "named_in_source")]
    assert assessed["theme"].matched_weight_pct == 9
    assert {row.ticker for row in assessed["theme"].exposures} == {"FTS.TO", "ENB.TO"}
    assert all(row.link_type == "theme" for row in assessed["theme"].exposures)
    assert assessed["country"].matched_weight_pct == 26
    assert assessed["negative"].exposures == [] and assessed["negative"].holdings_checked == 11
    assert assessed["unknown"].exposures == [] and assessed["unknown"].related_countries == []
    assert any("Geographic matching is limited" in note.en for note in assessed["unknown"].limitations)
    assert next(row for row in page.items if row.id == "country").location is None
    assert next(row for row in page.items if row.id == "unknown").country_iso3 is None
    assert rows == original  # request-time screens never rewrite source evidence
    assert all(row.assessment is None for row in world.observations(SID, {"scope": "providers"}).items)


@pytest.mark.parametrize("profile_id,count", [("robert", 11), ("amira", 16), ("mateo", 12)])
def test_every_loaded_dataset_has_a_completed_screen(world, profile_id, count):
    page = world.observations(SID, {"profileId": profile_id, "scope": "providers", "order": "coverage", "limit": 500})
    assert {row.dataset_id for row in page.items} == {row["sourceId"] for row in world._provider_capture[0]}
    assert all(row.assessment.profile_id == profile_id and row.assessment.holdings_checked == count for row in page.items)
    assert any(row.location is None and row.assessment is not None for row in page.items)
    assert any(row.assessment.exposures for row in page.items) and any(not row.assessment.exposures for row in page.items)
    if profile_id == "amira":
        assert all(any("9% of this portfolio has no listing country" in text.en for text in row.assessment.limitations)
                   for row in page.items)


@pytest.mark.parametrize("endpoint", ["airports", "facilities", "hazards"])
def test_optional_layer_records_are_all_assessed_without_creating_ownership(world, endpoint):
    read = getattr(world, endpoint)
    page = read(SID, {"profileId": "robert", "limit": 2000})
    assert page.items
    assert all(row.assessment.profile_id == "robert" and row.assessment.holdings_checked == 11 for row in page.items)
    if endpoint == "facilities":
        assert all(row.ticker is None and row.match_confidence == "none" for row in page.items)
        assert all(row.assessment.matched_weight_pct >= 74 for row in page.items)  # listing-country screen
    assert read(SID, {"limit": 1}).items[0].assessment is None


@pytest.mark.parametrize("endpoint", ["observations", "events"])
def test_profile_switch_and_portfolio_edit_cannot_reuse_assessed_cursors(world, endpoint):
    read = getattr(world, endpoint)
    query = {"profileId": "robert", "limit": 1}
    first = read(SID, query)
    assert first.next_cursor
    assert read(SID, {**query, "cursor": first.next_cursor}).items
    with pytest.raises(ServiceError) as exc:
        read(SID, {**query, "profileId": "amira", "cursor": first.next_cursor})
    assert exc.value.code == "validation_error"
    request = a.UpdatePortfolioRequest.model_validate({
        "totalValue": 500000, "positions": [{"ticker": "SPY", "weightPct": 100}], "version": 1,
    })
    world.profiles.set_portfolio(SID, "robert", request, 1)
    with pytest.raises(ServiceError) as exc:
        read(SID, {**query, "cursor": first.next_cursor})
    assert exc.value.code == "validation_error"
    fresh = read(SID, query)
    assert fresh.items
    if endpoint == "observations":
        assert fresh.items[0].assessment.holdings_checked == 1
        assert {row.ticker for row in fresh.items[0].assessment.exposures} <= {"SPY"}


@pytest.mark.parametrize("endpoint", ["observations", "airports", "facilities", "hazards"])
def test_unowned_profile_is_not_silently_reported_as_a_negative_screen(world, endpoint):
    with pytest.raises(NotFound):
        getattr(world, endpoint)(SID, {"profileId": "p_aaaaaaaaaa", "limit": 1})


def test_event_feed_and_popup_agree_on_a_theme_match_without_a_country_match(world):
    ds = world.dataset()
    event = dict(ds.events[0], relatedTickers=[], relatedCountries=[], relatedThemes=["utilities"])
    dataset = WorldDataset(ds.version, ds.built_at, (event,), (), ds.manifest)
    world._dataset = lambda: dataset
    detail = world.event(SID, event["eventId"], {"profileId": "robert"})
    page = world.events(SID, {"profileId": "robert", "from": event["occurredAt"], "to": event["occurredAt"]})
    assert page.items[0].portfolio_relevant is True
    assert detail.assessment.holdings_checked == 11 and detail.assessment.matched_weight_pct == 5
    assert [(row.ticker, row.link_type) for row in detail.exposures] == [("FTS.TO", "theme")]
    assert detail.assessment.exposures == detail.exposures
