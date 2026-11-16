"""Comparison service tests using real profiles, market data and storage."""

import copy

import pytest
from aplomb.api.errors import NotFound, ServiceError
from aplomb.api.repositories import ProfileRepository
from aplomb.api.storage import MemoryStore, Write
from aplomb.contracts import api as a
from aplomb.intelligence.investor_examples import (
    FILINGS_PARTITION,
    MAP_PARTITION,
    FilingComparisonRequest,
    InvestorExamples,
)
from aplomb.profiles.service import ProfileServiceImpl
from aplomb.quant import LocalLedger, QuantEngine
from tests.unit.datastore._support import starter_snapshot
from tests.unit.profiles.test_profiles import create_request

A = "s_aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "s_bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def holding(ticker, value, option=None):
    return {"ticker": ticker, "issuer": ticker, "shareClass": "COM", "cusip": ticker,
            "valueUsd": value, "shares": 1, "principal": None, "optionType": option,
            "sourceWeightPct": None}


def capture():
    long = [holding("AAPL", 75), holding("MSFT", 25)]
    return {"filingId": "test-filing", "manager": "Test manager", "associatedPerson": "Test",
            "cik": "0000000001", "accession": "0000000001-26-000001",
            "reportDate": "2026-06-30", "filingDate": "2026-08-15",
            "retrievedAt": "2026-11-15T00:00:00Z", "sourceUrl": "https://example.com",
            "secUrl": "https://example.com/sec", "sourceDataUrl": "https://example.com/data",
            "sourceSha256": "a" * 64, "reportedValueUsd": 150,
            "indexedLongValueUsd": 100, "indexedAllValueUsd": 150,
            "holdings": [*long, holding("AAPL", 50, "call")], "modeledHoldings": long,
            "limitations": [], "sourceKind": "third_party_indexed_transcription",
            "pointInTimeVerified": False}


def request(**kwargs):
    value = {"filingId": "test-filing", "strategy": {
        "kind": "contribute", "amount": 100, "frequency": "monthly", "allocation": "target",
        "costBps": 0}}
    value.update(kwargs)
    return FilingComparisonRequest.model_validate(value)


@pytest.fixture
def services():
    store = MemoryStore()
    store.transact([Write("cache", FILINGS_PARTITION, "FILING#test-filing",
                          {"revision": 1, "value": capture()}, None)])
    profiles = ProfileServiceImpl(ProfileRepository(store), starter_snapshot)
    return InvestorExamples(store, profiles), profiles, store


def test_common_post_filing_dates_and_buy_and_hold_benchmark(services):
    examples, profiles, _ = services
    result = examples.compare(A, "robert", request())
    dates = [p["date"] for p in result["benchmark"]["series"]]
    assert dates == [p["date"] for p in result["strategy"]["series"]]
    assert result["sample"] == {"start": dates[0], "end": dates[-1], "observations": len(dates)}
    assert dates[0] == "2026-08-17"  # first master day on or after Saturday filing date
    assert result["currency"] == "CAD"
    assert result["filing"]["optionCount"] == 1
    assert {h["ticker"] for h in result["benchmark"]["holdings"]} == {"AAPL", "MSFT"}
    assert result["filing"]["modeledCoveragePct"] == pytest.approx(100 / 150 * 100)

    profile = profiles.get(A, "robert")
    engine, _ = profiles._engine(profile, {"window": {"code": "full"}}, LocalLedger())
    start, end = (engine.market.index_of(day) for day in (dates[0], dates[-1]))
    apple = engine.market.window_levels("AAPL", start, end)
    microsoft = engine.market.window_levels("MSFT", start, end)
    expected = [100 * (0.75 * x / apple[0] + 0.25 * y / microsoft[0])
                for x, y in zip(apple, microsoft, strict=True)]
    assert [p["value"] for p in result["benchmark"]["series"]] == pytest.approx(expected)
    assert result["benchmark"]["returnPct"] == pytest.approx(expected[-1] - 100)
    assert "not actual fund" in result["limitations"][0]


def test_coverage_uses_all_captured_rows_including_options(services):
    examples, _, store = services
    value = capture()
    value["reportedValueUsd"] = 100
    store.transact([Write("cache", FILINGS_PARTITION, "FILING#test-filing",
                          {"revision": 2, "value": value}, 1)])

    filing = examples.compare(A, "robert", request())["filing"]
    assert filing["reportedValueUsd"] == 100
    assert filing["coverageValueUsd"] == 150
    assert filing["modeledValueUsd"] == 100
    assert filing["modeledCoveragePct"] == pytest.approx(66.6666666667)
    assert "including options" in filing["coverageBasis"]

    value["indexedAllValueUsd"] = 99
    store.transact([Write("cache", FILINGS_PARTITION, "FILING#test-filing",
                          {"revision": 3, "value": value}, 2)])
    with pytest.raises(ServiceError) as err:
        examples.capture("test-filing")
    assert err.value.code == "upstream_unavailable"


def test_currency_conversion_applies_to_both_benchmark_series(services):
    examples, profiles, _ = services
    usd = profiles.create(A, a.CreateProfileRequest.model_validate(create_request(reportingCurrency="USD")))
    cad_result = examples.compare(A, "robert", request())
    usd_result = examples.compare(A, usd.profile_id, request())
    assert usd_result["currency"] == "USD"
    assert usd_result["sample"] == cad_result["sample"]
    engine, _ = profiles._engine(usd, {"window": {"code": "full"}}, LocalLedger())
    i0 = engine.market.index_of(usd_result["sample"]["start"])
    i1 = engine.market.index_of(usd_result["sample"]["end"])
    apple = engine.market.window_levels("AAPL", i0, i1)
    microsoft = engine.market.window_levels("MSFT", i0, i1)
    expected = 100 * (0.75 * apple[-1] / apple[0] + 0.25 * microsoft[-1] / microsoft[0])
    assert usd_result["benchmark"]["series"][-1]["value"] == pytest.approx(expected)
    assert usd_result["benchmark"]["returnPct"] != pytest.approx(cad_result["benchmark"]["returnPct"])


def test_contributions_are_not_treated_as_returns(services, monkeypatch):
    examples, _, _ = services
    monkeypatch.setattr(QuantEngine, "asset_returns", lambda self, ticker, i0, i1: [0.0] * (i1 - i0))
    result = examples.compare(A, "robert", request())
    assert len({p["date"][:7] for p in result["strategy"]["series"]}) > 1
    assert result["strategy"]["returnPct"] == pytest.approx(0)
    assert all(p["value"] == pytest.approx(100) for p in result["strategy"]["series"])


def test_invalid_coverage_and_pre_filing_window_fail_closed(services):
    examples, _, store = services
    with pytest.raises(ServiceError) as err:
        examples.compare(A, "robert", request(window={"code": "custom", "start": "2026-07-01", "end": "2026-08-01"}))
    assert err.value.code == "insufficient_data"

    empty = capture()
    empty["modeledHoldings"] = []
    store.transact([Write("cache", FILINGS_PARTITION, "FILING#test-filing",
                          {"revision": 2, "value": empty}, 1)])
    with pytest.raises(ServiceError) as err:
        examples.compare(A, "robert", request())
    assert err.value.code == "insufficient_data"

    malformed = copy.deepcopy(empty)
    malformed["modeledHoldings"] = [malformed["holdings"][-1]]
    store.transact([Write("cache", FILINGS_PARTITION, "FILING#test-filing",
                          {"revision": 3, "value": malformed}, 2)])
    with pytest.raises(ServiceError) as err:
        examples.compare(A, "robert", request())
    assert err.value.code == "upstream_unavailable"


def test_private_profile_cannot_be_compared_by_another_session(services):
    examples, profiles, _ = services
    private = profiles.duplicate(A, "robert")
    assert examples.compare(A, private.profile_id, request())["currency"] == private.reporting_currency
    with pytest.raises(NotFound):
        examples.compare(B, private.profile_id, request())


def test_public_map_uses_shared_accounts_even_when_session_overlay_is_older(services):
    examples, profiles, store = services
    profile_id = "p_0000000001"
    seed = profiles.get(A, "robert").to_wire()
    seed.update(profileId=profile_id, name="Shared example", initial="S")
    seed["accounts"] = [
        {"accountId": f"acct_{i:012d}", "name": f"Wallet {i}",
         "portfolio": copy.deepcopy(seed["portfolio"])}
        for i in (1, 2)
    ]
    seed["activeAccountId"] = "acct_000000000001"
    location = {"profileId": profile_id, "name": "Shared example", "investorType": "retiree",
                "home": {"label": "Montréal", "country": "CA", "lat": 45.5, "lon": -73.6},
                "wallets": [{"accountId": "acct_000000000002", "label": "London",
                             "country": "GB", "lat": 51.5, "lon": -0.1}]}
    store.transact([
        Write("profiles", "SHARED#PROFILES", f"PROFILE#{profile_id}",
              {"revision": 1, "profileId": profile_id, "overlay": False, "value": seed}, None),
        Write("profiles", MAP_PARTITION, f"INVESTOR#{profile_id}",
              {"revision": 1, "value": location}, None),
    ])
    # A session overlay can predate a newly added shared account.
    profiles.repo.save(A, profile_id, {"accounts": seed["accounts"][:1]}, None, overlay=True)
    assert len(profiles.get(A, profile_id).accounts) == 1
    assert examples.investors(A) == examples.investors(B)
    assert examples.investors(A)["investors"][0]["wallets"][0]["accountId"] == "acct_000000000002"
