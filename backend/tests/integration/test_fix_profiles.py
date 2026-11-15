"""Regressions for the profile audit: no schema-valid profile, portfolio or rule payload may make
overview, performance, check or derive answer 500 (contracts/catalog.md §7). Over HTTP on the
starter snapshot; every test uses its own session."""

from __future__ import annotations

import copy
import uuid

import pytest
from aplomb.api.app import create_default_app
from aplomb.api.settings import Settings
from aplomb.contracts.catalog import FeatureFlag
from aplomb.contracts.registry import adapter
from fastapi.testclient import TestClient
from tests.unit.datastore._support import STARTER_VERSION, starter_root

PREFS = {"themesOfInterest": [], "excludedSectors": [], "excludedAssetClasses": [], "esgFocus": False,
         "avoidControversies": False, "avoidSpeculative": False, "cryptoInterest": "none",
         "wantsDiversification": True, "notes": ""}


@pytest.fixture(scope="module")
def client():
    features = {flag: False for flag in FeatureFlag}
    features[FeatureFlag.PROFILE_CREATOR] = True
    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()), features=features)
    return TestClient(create_default_app(settings), raise_server_exceptions=False)


@pytest.fixture()
def h():
    return {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}


def portfolio(*rows, total=1000):
    return {"totalValue": total, "positions": [{"ticker": t, "weightPct": w} for t, w in rows]}


def body(**over):
    out = {"name": "Nora", "age": None, "riskLevel": "moderate", "horizonYears": {"min": 5, "max": 10},
           "objective": "balanced", "experience": "beginner", "reportingCurrency": "CAD", "preferences": dict(PREFS),
           "portfolio": portfolio(("SPY", 60), ("XBB.TO", 40)), "rules": None, "fromDraftRunId": None}
    out.update(over)
    return out


def prefs(**over):
    return {**PREFS, **over}


def ok(response, contract, status=200):
    assert response.status_code == status, response.text
    return adapter(contract).validate_json(response.content).to_wire()


def rejected(response, code="validation_error", status=422, field=None):
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == code, error
    if field:
        assert field in error["details"]["fields"], error
    return error


def answers(client, h, profile_id):
    """Overview, performance and the current-portfolio check all answer for a stored profile."""
    overview = ok(client.get(f"/v1/profiles/{profile_id}/overview", headers=h), "OverviewResponse")
    ok(client.get(f"/v1/profiles/{profile_id}/performance", headers=h), "PerformanceResponse")
    check = ok(client.post("/v1/check", json={"profileId": profile_id, "move": None}, headers=h), "CheckResult")
    return overview, check


def robert_rules(client, h):
    return copy.deepcopy(ok(client.get("/v1/profiles/robert", headers=h), "Profile")["rules"])


# Zero-weight positions (findings 1, 22) ---------------------------------------------------------

def test_zero_weight_position_keeps_overview(client, h):
    created = ok(client.post("/v1/profiles", json=body(portfolio=portfolio(("XBB.TO", 60), ("XIU.TO", 40), ("SPY", 0))),
                             headers=h), "Profile", 201)
    assert [p["weightPct"] for p in created["portfolio"]["positions"]] == [60.0, 40.0, 0.0]  # a 0 % row stays valid input
    overview, _ = answers(client, h, created["profileId"])
    assert [p["ticker"] for p in overview["concentration"]["topPositions"]] == ["XBB.TO", "XIU.TO"]


def test_zero_weight_position_on_default_profile(client, h):
    put = {**portfolio(("XBB.TO", 25), ("XIU.TO", 25), ("SPY", 25), ("GLD", 25), ("TSLA", 0), total=600000), "version": 1}
    assert client.put("/v1/profiles/robert/portfolio", json=put, headers=h).status_code == 200
    overview, _ = answers(client, h, "robert")
    assert len(overview["concentration"]["topPositions"]) == 4


# Weight sum inside the contract tolerance (finding 3) -------------------------------------------

@pytest.mark.parametrize("rows", [
    (("SPY", 33.333), ("XBB.TO", 33.333), ("GLD", 33.333)),   # 99.999
    (("SPY", 33.33), ("XBB.TO", 33.33), ("GLD", 33.33)),      # 99.99: abs(99.99 - 100) > 0.01 in floating point
    (("SPY", 60.01), ("XBB.TO", 40)),                         # 100.01
])
def test_weights_within_tolerance_are_stored_summing_to_100(client, h, rows):
    created = ok(client.post("/v1/profiles", json=body(portfolio=portfolio(*rows)), headers=h), "Profile", 201)
    assert abs(sum(p["weightPct"] for p in created["portfolio"]["positions"]) - 100.0) < 1e-9
    answers(client, h, created["profileId"])
    moved = client.post("/v1/check", json={"profileId": created["profileId"], "move": {
        "ticker": "TSLA", "sizePct": 5, "funding": {"mode": "pro_rata"}}}, headers=h)
    ok(moved, "CheckResult")


def test_weights_within_tolerance_on_default_profile(client, h):
    put = {**portfolio(("SPY", 59.995), ("XBB.TO", 40), total=600000), "version": 1}
    stored = ok(client.put("/v1/profiles/robert/portfolio", json=put, headers=h), "Profile")
    assert abs(sum(p["weightPct"] for p in stored["portfolio"]["positions"]) - 100.0) < 1e-9
    answers(client, h, "robert")


def test_exact_weights_are_stored_unchanged_and_wrong_sums_rejected(client, h):
    rows = (("SPY", 0.07), ("XBB.TO", 59.93), ("GLD", 40))
    created = ok(client.post("/v1/profiles", json=body(portfolio=portfolio(*rows)), headers=h), "Profile", 201)
    assert [(p["ticker"], p["weightPct"]) for p in created["portfolio"]["positions"]] == [(t, float(w)) for t, w in rows]
    for rows in ((("SPY", 60), ("XBB.TO", 39.98)), (("SPY", 60.02), ("XBB.TO", 40))):
        rejected(client.post("/v1/profiles", json=body(portfolio=portfolio(*rows)), headers=h), field="positions")


# Unknown tickers (finding 46) -------------------------------------------------------------------

def test_unknown_ticker_is_a_validation_error(client, h):
    error = rejected(client.post("/v1/profiles", json=body(portfolio=portfolio(("TSLA", 50), ("NOPE", 50))), headers=h),
                     field="positions")
    assert error["details"]["unknown"] == ["NOPE"]
    rejected(client.put("/v1/profiles/robert/portfolio", json={**portfolio(("NOPE", 100)), "version": 1}, headers=h),
             field="positions")
    missing = client.put("/v1/profiles/p_0000000000/portfolio", json={**portfolio(("SPY", 100)), "version": 1}, headers=h)
    rejected(missing, code="not_found", status=404)  # an unknown profile stays a 404


# Profile name (findings 57, 73) -----------------------------------------------------------------

@pytest.mark.parametrize("name", [" ", "\t", "   ", " "])
def test_blank_name_is_rejected(client, h, name):
    rejected(client.post("/v1/profiles", json=body(name=name), headers=h), field="name")
    rejected(client.post("/v1/profiles", json=body(name=name, portfolio=None), headers=h), field="name")
    created = ok(client.post("/v1/profiles", json=body(), headers=h), "Profile", 201)
    replaced = client.put(f"/v1/profiles/{created['profileId']}", json={**body(name=name), "version": 1}, headers=h)
    rejected(replaced, field="name")
    assert ok(client.get(f"/v1/profiles/{created['profileId']}", headers=h), "Profile")["name"] == "Nora"


def test_name_whose_capital_is_two_letters(client, h):
    created = ok(client.post("/v1/profiles", json=body(name=" ßen"), headers=h), "Profile", 201)
    assert created["initial"] == "S"


# Caller-supplied rules (findings 12, 56) --------------------------------------------------------

def test_supplied_rules_round_trip(client, h):
    for profile_id in ("robert", "amira", "mateo"):
        rules = copy.deepcopy(ok(client.get(f"/v1/profiles/{profile_id}", headers=h), "Profile")["rules"])
        created = ok(client.post("/v1/profiles", json=body(rules=rules), headers=h), "Profile", 201)
        assert [(r["ruleId"], r["threshold"]) for r in created["rules"]] == [(r["ruleId"], r["threshold"]) for r in rules]
        answers(client, h, created["profileId"])


def _edit(rules, rule_id, **changes):
    out = copy.deepcopy(rules)
    next(r for r in out if r["ruleId"] == rule_id).update(changes)
    return out


@pytest.mark.parametrize("label,mutate", [
    ("cap without a threshold", lambda rules: _edit(rules, "cap.position", threshold=None)),
    ("disabled limit without a threshold", lambda rules: _edit(rules, "limit.volatility", threshold=None, enabled=False)),
    ("exclusion without a threshold", lambda rules: _edit(rules, "exclude.asset_class.crypto", threshold=None)),
    ("type contradicting the rule ID", lambda rules: _edit(rules, "cap.position", type="floor")),
    ("threshold above the definition", lambda rules: _edit(rules, "cap.position", threshold=500.0)),
    ("negative threshold", lambda rules: _edit(rules, "floor.fixed_income", threshold=-5.0)),
    ("rule ID without a definition", lambda rules: _edit(rules, "flag.attention", ruleId="flag.short_history")),
    ("sector missing from the universe", lambda rules: _edit(rules, "exclude.asset_class.crypto", ruleId="exclude.sector.tech")),
    ("repeated rule ID", lambda rules: rules + [copy.deepcopy(rules[0])]),
])
def test_supplied_rules_are_checked_against_the_definitions(client, h, label, mutate):
    rules = mutate(robert_rules(client, h))
    rejected(client.post("/v1/profiles", json=body(rules=rules), headers=h), field="rules")
    created = ok(client.post("/v1/profiles", json=body(), headers=h), "Profile", 201)
    replaced = client.put(f"/v1/profiles/{created['profileId']}", json={**body(rules=rules), "version": 1}, headers=h)
    rejected(replaced, field="rules")
    assert [p["profileId"] for p in ok(client.get("/v1/profiles", headers=h), "ProfilesResponse")["items"]][3:] == [created["profileId"]]


# Derivation over a short custom window (finding 57) ---------------------------------------------

def test_derive_over_two_day_window_is_insufficient_data(client, h):
    def derive(end):
        window = {"code": "custom", "start": "2026-01-05", "end": end}
        return client.post("/v1/profiles/amira/rules/derive", json={"reset": False, "window": window}, headers=h)

    rejected(derive("2026-01-05"), code="insufficient_data")
    rejected(derive("2026-01-06"), code="insufficient_data")  # one return: no volatility
    assert ok(client.get("/v1/profiles/amira", headers=h), "Profile")["version"] == 1  # nothing stored
    ok(derive("2026-01-07"), "DeriveRulesResponse")


# Excluded asset classes (finding 19) ------------------------------------------------------------

def _classes(client, h, profile):
    known = {}
    for position in profile["portfolio"]["positions"]:
        if position["ticker"].startswith("CASH."):
            known[position["ticker"]] = "cash"
        else:
            known[position["ticker"]] = ok(client.get(f"/v1/assets/{position['ticker']}", headers=h), "Asset")["assetClass"]
    return known


@pytest.mark.parametrize("excluded,risk,diversify", [
    (["etf_equity"], "moderate", True),
    (["etf_bond"], "moderate", True),
    (["cash", "etf_equity", "cash"], "moderate", True),
    (["etf_commodity", "etf_equity"], "moderate", False),
])
def test_excluded_asset_classes_become_rules_and_stay_out_of_the_proposal(client, h, excluded, risk, diversify):
    request = body(portfolio=None, riskLevel=risk, preferences=prefs(excludedAssetClasses=excluded, wantsDiversification=diversify))
    created = ok(client.post("/v1/profiles", json=request, headers=h), "Profile", 201)
    rule_ids = [r["ruleId"] for r in created["rules"]]
    assert len(set(rule_ids)) == len(rule_ids)
    for asset_class in set(excluded):
        rule = next(r for r in created["rules"] if r["ruleId"] == f"exclude.asset_class.{asset_class}")
        assert (rule["type"], rule["origin"], rule["enabled"], rule["threshold"]) == ("exclude", "profile_preference", True, 0.0)
    assert not set(_classes(client, h, created).values()) & set(excluded)
    assert abs(sum(p["weightPct"] for p in created["portfolio"]["positions"]) - 100.0) < 1e-9
    overview, _ = answers(client, h, created["profileId"])
    assert overview["verdict"] != "conflict"


def test_excluded_asset_class_flags_a_later_move(client, h):
    request = body(portfolio=None, preferences=prefs(excludedAssetClasses=["etf_equity"]))
    created = ok(client.post("/v1/profiles", json=request, headers=h), "Profile", 201)
    check = ok(client.post("/v1/check", json={"profileId": created["profileId"], "move": {
        "ticker": "SPY", "sizePct": 5, "funding": {"mode": "pro_rata"}}}, headers=h), "CheckResult")
    status = {c["ruleId"]: (c["status"], c["value"]) for c in check["ruleChecks"]}["exclude.asset_class.etf_equity"]
    assert status[0] == "conflict" and abs(status[1] - 5.0) < 1e-9


def test_unsatisfiable_class_exclusions_answer_insufficient_data(client, h):
    request = body(portfolio=None, riskLevel="low", preferences=prefs(excludedAssetClasses=["etf_bond", "cash"]))
    rejected(client.post("/v1/profiles", json=request, headers=h), code="insufficient_data")


# Excluded sectors (finding 23) ------------------------------------------------------------------

@pytest.mark.parametrize("entries", [["Tech"], ["!!!"], ["É"], ["S&P 500"], [""], ["Energy", "Oil & Gas"]])
def test_unknown_sector_labels_are_rejected(client, h, entries):
    for portfolio_value in (portfolio(("SPY", 60), ("XBB.TO", 40)), None):
        error = rejected(client.post("/v1/profiles", json=body(portfolio=portfolio_value, preferences=prefs(excludedSectors=entries)),
                                     headers=h), field="preferences.excludedSectors")
        assert "Information Technology" in error["details"]["valid"] and "Energy" in error["details"]["valid"]
    supplied = body(rules=robert_rules(client, h), preferences=prefs(excludedSectors=entries))
    rejected(client.post("/v1/profiles", json=supplied, headers=h), field="preferences.excludedSectors")


def test_sector_labels_are_canonical_and_unique(client, h):
    entries = ["energy", "Information Technology", " Énergie ", "ENERGY", "technologies de l'information", "Santé"]
    created = ok(client.post("/v1/profiles", json=body(preferences=prefs(excludedSectors=entries)), headers=h), "Profile", 201)
    assert created["preferences"]["excludedSectors"] == ["Energy", "Information Technology", "Health Care"]
    sector_rules = [r["ruleId"] for r in created["rules"] if r["ruleId"].startswith("exclude.sector.")]
    assert sector_rules == ["exclude.sector.energy", "exclude.sector.information_technology", "exclude.sector.health_care"]
    check = ok(client.post("/v1/check", json={"profileId": created["profileId"], "move": {
        "ticker": "NVDA", "sizePct": 5, "funding": {"mode": "pro_rata"}}}, headers=h), "CheckResult")
    statuses = {c["ruleId"]: c["status"] for c in check["ruleChecks"]}
    assert statuses["exclude.sector.information_technology"] == "conflict"
    assert statuses["exclude.sector.energy"] == "pass"
    off = client.patch(f"/v1/profiles/{created['profileId']}/rules/exclude.sector.information_technology",
                       json={"enabled": False}, headers=h)
    assert off.status_code == 200, off.text
    again = ok(client.post("/v1/check", json={"profileId": created["profileId"], "move": {
        "ticker": "NVDA", "sizePct": 5, "funding": {"mode": "pro_rata"}}}, headers=h), "CheckResult")
    assert "exclude.sector.information_technology" not in {c["ruleId"] for c in again["ruleChecks"]}


# Default personas and acceptance numbers stay as they were --------------------------------------

def test_default_personas_and_acceptance_numbers_unchanged(client, h):
    expected = {
        "robert": ({"pass": 8, "tension": 0, "conflict": 0, "nee": 0, "info": 3}, "compatible", 6.09),
        "amira": (None, "compatible", 19.52),
        "mateo": (None, "insufficient", None),
    }
    for profile_id, (counts, verdict, vol) in expected.items():
        profile = ok(client.get(f"/v1/profiles/{profile_id}", headers=h), "Profile")
        derived = ok(client.post(f"/v1/profiles/{profile_id}/rules/derive", json={"reset": True}, headers=h), "DeriveRulesResponse")
        assert [(r["code"], r["ruleId"], r["threshold"]) for r in derived["rules"]] == \
            [(r["code"], r["ruleId"], r["threshold"]) for r in profile["rules"]]
        overview = ok(client.get(f"/v1/profiles/{profile_id}/overview", headers=h), "OverviewResponse")
        assert overview["verdict"] == verdict
        if counts:
            assert overview["counts"] == counts
        if vol:
            assert abs(overview["risk"]["volatilityPct"] - vol) < 0.005
    check = ok(client.post("/v1/check", json={"profileId": "robert", "move": {
        "ticker": "TSLA", "sizePct": 25, "funding": {"mode": "pro_rata"}}}, headers=h), "CheckResult")
    assert check["counts"] == {"pass": 1, "tension": 1, "conflict": 6, "nee": 0, "info": 3}
    assert check["maxCompatibleSizePct"] == 6.0
