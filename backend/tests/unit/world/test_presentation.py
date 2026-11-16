"""Team decision: Israel, the West Bank and Gaza are presented as Palestine (PSE) at load."""

from aplomb.world import load_bundle
from aplomb.world.geo import country_name, present_event, present_name, present_rows
from aplomb.world.providers import load_provider_snapshots


def test_names_are_replaced_as_whole_words_only():
    assert present_name("Gaza, Israel (General), Israel") == "Gaza, Palestine (General), Palestine"
    assert present_name("Jabaliya, Gaza Strip (General), Gaza Strip") == "Jabaliya, Palestine (General), Palestine"
    assert present_name("West Bank and Gaza political stability") == "Palestine political stability"
    assert present_name("Israeli shekel") == "Israeli shekel"
    assert present_name(None) is None
    assert country_name("ISR") == country_name("PSE") == {"en": "Palestine", "fr": "Palestine"}


def test_isr_rows_are_withheld_when_the_series_has_pse_and_relabelled_otherwise():
    rows = [{"countryIso3": "ISR", "series": "a", "value": 1}, {"countryIso3": "PSE", "series": "a", "value": 2},
            {"countryIso3": "ISR", "series": "b", "value": 3}, {"countryIso3": "CAN", "series": "a", "value": 4}]
    served, affected = present_rows(rows, lambda row: row["series"])
    assert affected == 2
    assert served == [{"countryIso3": "PSE", "series": "a", "value": 2}, {"countryIso3": "PSE", "series": "b", "value": 3},
                      {"countryIso3": "CAN", "series": "a", "value": 4}]
    assert rows[0]["countryIso3"] == "ISR"  # the source rows are not mutated


def test_event_countries_place_and_titles_are_presented():
    event = {"title": "M 6.1 - 10 km W of Eilat, Israel", "relatedCountries": ["ISR", "PSE", "JOR"],
             "location": {"lat": 29.5, "lon": 34.9, "countryIso3": "ISR", "placeName": "10 km W of Eilat, Israel",
                          "precision": "point"},
             "sources": [{"title": "M 6.1 - 10 km W of Eilat, Israel", "url": "https://earthquake.usgs.gov/x"}]}
    shown = present_event(event)
    assert shown["relatedCountries"] == ["PSE", "JOR"]
    assert shown["location"]["countryIso3"] == "PSE" and shown["location"]["placeName"] == "10 km W of Eilat, Palestine"
    assert shown["title"] == shown["sources"][0]["title"] == "M 6.1 - 10 km W of Eilat, Palestine"
    assert shown["sources"][0]["url"] == event["sources"][0]["url"] and event["location"]["countryIso3"] == "ISR"


def test_loaded_world_data_carries_no_isr_code_or_israel_name():
    ds = load_bundle()
    assert not any("ISR" in event["relatedCountries"] or event["location"]["countryIso3"] == "ISR" for event in ds.events)
    assert not any(row["countryIso3"] == "ISR" for row in ds.country_macro)
    assert {row["indicatorId"] for row in ds.country_macro if row["countryIso3"] == "PSE"}
    rows, manifests = load_provider_snapshots(errors=[])
    assert not any(row.get("countryIso3") == "ISR" or "Israel" in row["title"] for row in rows)
    wgi = next(m for m in manifests if m["datasetId"] == "world_wgi_political_stability_2024")
    assert wgi["presentation"] == {"renamedRows": 2, "isrRows": 1, "withheldIsrRows": 1}
