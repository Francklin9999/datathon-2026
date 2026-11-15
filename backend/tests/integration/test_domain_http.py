"""The exported app serves the datastore, profile and check providers over HTTP."""

from __future__ import annotations

import uuid

import pytest
from aplomb.api.app import create_app, create_default_app
from aplomb.api.settings import Settings
from aplomb.contracts.catalog import FeatureFlag
from aplomb.contracts.registry import adapter
from fastapi.testclient import TestClient
from tests.unit.datastore._support import STARTER_VERSION, starter_root

SID = "s_" + str(uuid.UUID(int=0x1234_5678_9ABC_4DEF_8123_456789ABCDEF, version=4))
OTHER = "s_" + str(uuid.uuid4())
H = {"X-Aplomb-Session": SID}


def settings(**over):
    features = {flag: False for flag in FeatureFlag}
    features[FeatureFlag.PROFILE_CREATOR] = True
    values = {"data_version": STARTER_VERSION, "data_dir": str(starter_root()), "features": features}
    values.update(over)
    return Settings(**values)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_default_app(settings()))


def ok(response, contract, status=200):
    assert response.status_code == status, response.text
    return adapter(contract).validate_json(response.content).to_wire() if contract else response.json()


def test_meta_and_universe(client):
    meta = ok(client.get("/v1/meta"), "Meta")
    assert meta["universe"] == {"total": 31, "byTier": {"starter": 31, "extended": 0, "on_demand": 0}}
    assert meta["features"]["profile_creator"] is True
    assert meta["features"]["frontier_chart"] is False
    page = ok(client.get("/v1/assets", params={"limit": 10}, headers=H), "AssetsResponse")
    assert (len(page["items"]), page["total"], page["nextCursor"]) == (10, 31, "10")
    last = ok(client.get("/v1/assets", params={"limit": 10, "cursor": "30"}, headers=H), "AssetsResponse")
    assert (len(last["items"]), last["nextCursor"]) == (1, None)
    tesla = ok(client.get("/v1/assets", params={"q": "tesla"}, headers=H), "AssetsResponse")
    assert [x["ticker"] for x in tesla["items"]] == ["TSLA"]
    asset = ok(client.get("/v1/assets/CNQ.TO", headers=H), "Asset")
    assert asset["flags"] == ["split_anomaly"] and asset["history"]["nObsMaster"] == 1228
    assert client.get("/v1/assets/NOPE", headers=H).status_code == 404
    assert client.get("/v1/assets", params={"assetClass": "bonds"}, headers=H).status_code == 422
    assert client.post("/v1/assets/NEWCO/fetch", json={}, headers=H).status_code == 501  # flag off


def test_dataset_passports(client):
    body = ok(client.get("/v1/datasets", headers=H), "DatasetsResponse")
    assert {p["datasetId"] for p in body["items"]} >= {"prices_daily", "fx_boc_global", "world_bank_indicators"} and len(body["traps"]) == 9
    prices = ok(client.get("/v1/datasets/prices_daily", headers=H), "DatasetPassport")
    assert prices["rowCount"] == 40049 and prices["status"] == "in_use"
    assert client.get("/v1/datasets/nope", headers=H).status_code == 404


def test_profiles_rules_and_check(client):
    items = ok(client.get("/v1/profiles", headers=H), "ProfilesResponse")["items"]
    assert [p["profileId"] for p in items] == ["robert", "amira", "mateo"]
    check = ok(client.post("/v1/check", json={"profileId": "robert", "move": {"ticker": "TSLA", "sizePct": 25,
                                                                             "funding": {"mode": "pro_rata"}}}, headers=H), "CheckResult")
    assert check["counts"] == {"pass": 1, "tension": 1, "conflict": 6, "nee": 0, "info": 3}
    assert check["maxCompatibleSizePct"] == 6.0
    patched = ok(client.patch("/v1/profiles/robert/rules/limit.stress_2022", json={"threshold": 25}, headers=H), "RulePatchResponse")
    assert patched["profileVersion"] == 2
    again = ok(client.post("/v1/check", json={"profileId": "robert", "move": {"ticker": "TSLA", "sizePct": 25,
                                                                             "funding": {"mode": "pro_rata"}}}, headers=H), "CheckResult")
    assert {c["ruleId"]: c["status"] for c in again["ruleChecks"]}["limit.stress_2022"] == "pass"
    other = ok(client.get("/v1/profiles/robert", headers={"X-Aplomb-Session": OTHER}), "Profile")
    assert other["version"] == 1  # another session keeps the default
    derived = ok(client.post("/v1/profiles/robert/rules/derive", json={"reset": True}, headers=H), "DeriveRulesResponse")
    assert {r["ruleId"]: r["threshold"] for r in derived["rules"]}["limit.stress_2022"] == 9.0


def test_overview_performance_and_creator(client):
    overview = ok(client.get("/v1/profiles/amira/overview", headers=H), "OverviewResponse")
    assert overview["verdict"] == "compatible"
    assert abs(overview["risk"]["volatilityPct"] - 19.52) < 0.005
    perf = ok(client.get("/v1/profiles/robert/performance", params={"window": "ytd"}, headers=H), "PerformanceResponse")
    assert perf["series"][0] == {"date": "2025-12-31", "value": 600000.0}
    created = ok(client.post("/v1/profiles", json={
        "name": "Nora", "age": None, "riskLevel": "moderate", "horizonYears": {"min": 5, "max": 10}, "objective": "balanced",
        "experience": "beginner", "reportingCurrency": "CAD",
        "preferences": {"themesOfInterest": [], "excludedSectors": [], "excludedAssetClasses": [], "esgFocus": False,
                        "avoidControversies": False, "avoidSpeculative": False, "cryptoInterest": "none",
                        "wantsDiversification": True, "notes": ""},
        "portfolio": None, "rules": None, "fromDraftRunId": None}, headers=H), "Profile", 201)
    assert created["profileId"].startswith("p_") and created["rules"]
    listed = ok(client.get("/v1/profiles", headers=H), "ProfilesResponse")["items"]
    assert listed[-1]["profileId"] == created["profileId"]


def test_custom_window_reads(client):
    custom = {"window": "custom", "start": "2023-01-01", "end": "2026-01-01"}
    spec = {"code": "custom", "start": "2023-01-01", "end": "2026-01-01"}
    overview = ok(client.get("/v1/profiles/robert/overview", params=custom, headers=H), "OverviewResponse")
    assert overview["window"] == spec
    vol = overview["facts"][overview["risk"]["factIds"]["volatility"]]
    assert vol["key"].endswith("|custom:2023-01-01..2026-01-01")
    perf = ok(client.get("/v1/profiles/robert/performance", params={**custom, "benchmark": "SPY"}, headers=H),
              "PerformanceResponse")
    assert perf["window"] == spec and perf["benchmark"]["ticker"] == "SPY"
    assert perf["series"][0]["date"] == "2022-12-30" and perf["series"][-1]["date"] == "2025-12-31"

    def error(params):
        response = client.get("/v1/profiles/robert/performance", params=params, headers=H)
        assert response.status_code == 422, response.text
        return response.json()["error"]

    swapped = error({**custom, "start": "2026-01-01", "end": "2023-01-01"})
    assert (swapped["code"], swapped["details"]["fields"]) == ("validation_error", ["start", "end"])
    assert error({"window": "custom", "start": "2023-01-01"})["code"] == "validation_error"  # rejected by query parsing
    early = error({**custom, "start": "2020-01-01"})
    assert (early["code"], early["details"]["historyStart"]) == ("insufficient_data", "2021-11-12")


def test_unconfigured_and_bare_app_keep_previous_behaviour():
    bare = TestClient(create_app(settings()))
    assert bare.get("/v1/profiles", headers=H).status_code == 503
    unconfigured = TestClient(create_default_app(Settings()))
    assert unconfigured.get("/v1/meta").status_code == 503


def test_missing_snapshot_files_are_unavailable(tmp_path):
    broken = TestClient(create_default_app(settings(data_dir=str(tmp_path))))
    response = broken.get("/v1/profiles/robert/overview", headers=H)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"


def test_strategy_simulation(client):
    """api.md §3.13: three standing strategies simulated on history, validated against the contract."""
    url = "/v1/profiles/robert/strategies/simulate"
    rebalance = ok(client.post(url, json={"strategy": {"kind": "rebalance", "trigger": "calendar"}}, headers=H), "StrategySimulation")
    assert rebalance["strategy"] == {"kind": "rebalance", "trigger": "calendar", "frequency": "quarterly", "costBps": 0.0}
    assert rebalance["method"] == "M_STRATEGY_SIM" and "LIM_STRATEGY_COSTS" in rebalance["limitations"]
    assert len(rebalance["series"]) == len(rebalance["baseline"]) == 1228 and rebalance["invested"] is None
    assert rebalance["series"][0]["value"] == rebalance["baseline"][0]["value"] == 600_000
    assert rebalance["metrics"]["actions"] == len(rebalance["actions"]) > 10          # about one per quarter
    assert rebalance["baselineMetrics"]["actions"] == 0 and rebalance["baselineMetrics"]["turnoverPct"] == 0
    assert rebalance["plan"]["monthsChecked"] > 50
    assert rebalance["actions"][0]["reason"]["fr"].startswith("Fin de trimestre")

    contribute = ok(client.post(url, json={"strategy": {"kind": "contribute", "amount": 1000, "frequency": "monthly",
                                                         "allocation": "underweight"}}, headers=H), "StrategySimulation")
    months = len(contribute["actions"])
    assert contribute["metrics"]["invested"] == 600_000 + 1000 * months
    assert contribute["invested"][-1]["value"] == contribute["metrics"]["invested"]
    assert all(t["amount"] >= 0 for a in contribute["actions"] for t in a["trades"])

    guard = ok(client.post(url, json={"strategy": {"kind": "risk_guard", "triggerDrawdownPct": 5, "shiftPct": 50,
                                                    "reentryDrawdownPct": 1}, "window": {"code": "custom", "start": "2022-01-01", "end": "2024-01-01"}},
                           headers=H), "StrategySimulation")
    assert guard["strategy"]["safeTicker"] == "XBB.TO"                                # the largest bond fund held
    assert guard["window"] == {"code": "custom", "start": "2022-01-01", "end": "2024-01-01"}
    assert [a["kind"] for a in guard["actions"]][:1] == ["de_risk"]

    bad = client.post(url, json={"strategy": {"kind": "risk_guard", "triggerDrawdownPct": 5, "shiftPct": 50, "reentryDrawdownPct": 9}}, headers=H)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    unknown = client.post(url, json={"strategy": {"kind": "risk_guard", "triggerDrawdownPct": 5, "shiftPct": 50,
                                                   "reentryDrawdownPct": 1, "safeTicker": "TSLA"}}, headers=H)
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "validation_error"
    assert client.post("/v1/profiles/p_0000000000/strategies/simulate", json={"strategy": {"kind": "rebalance", "trigger": "band"}},
                       headers=H).status_code == 404
