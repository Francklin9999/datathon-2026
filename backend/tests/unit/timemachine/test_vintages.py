"""Synthetic real-time periods; these values are not FRED/ALFRED observations."""
from decimal import Decimal

import pytest
from aplomb.timemachine.vintages import parse_observations, visible_at


def parse(rows):
    return parse_observations({"observations": rows}, series_id="TEST", retrieved_at="2026-11-15T12:00:00Z",
                              dataset_version="synthetic-v1",
                              source_url="https://api.stlouisfed.org/fred/series/observations")


def test_revisions_are_selected_by_availability_not_observation_date():
    rows = parse([
        {"date": "2020-01-01", "value": "2.0", "realtime_start": "2020-02-15", "realtime_end": "2020-03-14"},
        {"date": "2020-01-01", "value": "3.0", "realtime_start": "2020-03-15", "realtime_end": "9999-12-31"},
        {"date": "2020-02-01", "value": ".", "realtime_start": "2020-03-15", "realtime_end": "9999-12-31"},
    ])
    assert visible_at(rows, "2020-02-14") == ()
    old = visible_at(rows, "2020-03-14")
    assert old[0].value == Decimal("2.0") and old[0].available_at == "2020-02-15T23:59:59.999Z"
    assert old[0].publication_at is None and old[0].retrieved_at == "2026-11-15T12:00:00.000Z"
    assert visible_at(rows, "2020-03-15")[0].value == Decimal("3.0")


def test_overlapping_revisions_are_rejected():
    with pytest.raises(ValueError, match="overlapping"):
        parse([{"date": "2020-01-01", "value": "1", "realtime_start": "2020-02-01", "realtime_end": "2020-03-01"},
               {"date": "2020-01-01", "value": "2", "realtime_start": "2020-03-01", "realtime_end": "2020-04-01"}])


def test_source_metadata_cannot_contain_secret_query_parameters():
    with pytest.raises(ValueError, match="query"):
        parse_observations({"observations": []}, series_id="TEST", retrieved_at="2026-11-15T12:00:00Z",
                           dataset_version="test", source_url="https://api.stlouisfed.org/fred/series/observations?api_key=secret")
