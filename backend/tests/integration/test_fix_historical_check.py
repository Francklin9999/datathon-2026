"""Regressions for the audit of historical checks: ``POST /check`` with a past ``asOf`` judges with
the rule set a replay of that date pins, a date after the data is refused, and the pinned rule
set (not only its thresholds) comes from the derivation at the cutoff. Offline; scripted model."""

from __future__ import annotations

import uuid

import pytest
from aplomb.api.app import create_default_app
from aplomb.api.errors import ServiceError
from aplomb.api.runtime import gate_factory
from aplomb.api.settings import Settings
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.contracts.catalog import FeatureFlag
from aplomb.optimizer.services import deriver, proposer
from aplomb.profiles.defaults import load_defaults
from aplomb.profiles.service import ProfileServiceImpl
from aplomb.timemachine import validate_asof
from aplomb.timemachine.service import rederive_at
from fastapi.testclient import TestClient
from tests.integration._scripted import ScriptedGateway
from tests.integration.test_review_regressions import Harness
from tests.unit.datastore._support import STARTER_VERSION, starter_root, starter_snapshot
from tests.unit.profiles.test_profiles import CLOCK, create_request, make_repo

NOW = "2026-11-14T23:45:00Z"
SID = "s_" + str(uuid.uuid4())
H = {"X-Aplomb-Session": SID}
NVDA_10 = {"ticker": "NVDA", "sizePct": 10, "funding": {"mode": "pro_rata"}}
QQQ_FROM_BONDS = {"ticker": "QQQ", "sizePct": 7, "funding": {"mode": "from_holdings", "fromTickers": ["XBB.TO"]}}
EQUITY_HEAVY = {"totalValue": 100000, "positions": [{"ticker": "SPY", "weightPct": 45}, {"ticker": "XIU.TO", "weightPct": 40},
                                                    {"ticker": "GLD", "weightPct": 8}, {"ticker": "XBB.TO", "weightPct": 7}]}
GROWTH_RULES = ["cap.growth_assets", "floor.fixed_income"]


@pytest.fixture(scope="module")
def client():
    features = {flag: False for flag in FeatureFlag}
    return TestClient(create_default_app(Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()), features=features)))


def post_check(client, **body):
    return client.post("/v1/check", json={"profileId": "robert", "move": None, **body}, headers=H)


def by_rule(checks) -> dict:
    return {c["ruleId"]: (c["threshold"], c["status"]) for c in checks}


def moderate_high_request(**over) -> a.CreateProfileRequest:
    """On the full window a 100% equity reference mix fits the 16% budget: no growth cap, a diversification floor."""
    return a.CreateProfileRequest.model_validate(create_request(rules=None, riskLevel="moderate_high", portfolio=EQUITY_HEAVY, **over))


def moderate_high() -> m.Profile:
    profiles = ProfileServiceImpl(make_repo(), starter_snapshot, clock=CLOCK, deriver=deriver, proposer=proposer)
    return profiles.create(SID, moderate_high_request())


def robert() -> m.Profile:
    return next(p for p in load_defaults() if p.profile_id == "robert")


def ids(profile: m.Profile) -> list[str]:
    return [r.rule_id for r in profile.rules]


def with_rule(profile: m.Profile, rule_id: str, **changes) -> m.Profile:
    data = profile.to_wire()
    data["rules"] = [{**r, **changes} if r["ruleId"] == rule_id else r for r in data["rules"]]
    return m.Profile.model_validate(data)


# Findings 0, 17, 35: a past asOf on /check uses the rule set of that date --------------------------


def test_check_at_a_past_date_agrees_with_the_replay_of_that_date(client):
    as_of = "2022-11-22"
    check = post_check(client, move=NVDA_10, asOf=as_of)
    assert check.status_code == 200, check.text
    body = check.json()
    harness = Harness(ScriptedGateway())
    run, _ = harness.drive(harness.create({"kind": "replay", "profileId": "robert", "lang": "en", "asOf": as_of,
                                           "request": {"type": "move", "move": NVDA_10}}))
    assert run.status == "succeeded", run.error
    decision = run.result.replay.decision.to_wire()
    scenario = next(s for s in decision["scenarios"] if s["scenarioId"] == decision["selectedScenarioId"])
    assert by_rule(body["ruleChecks"]) == by_rule(scenario["ruleChecks"])
    assert (body["verdict"], body["counts"]) == (scenario["verdict"], scenario["counts"])
    assert body["maxCompatibleSizePct"] == decision["maxCompatibleSizePct"] == 0.0
    # The stored thresholds (55 and 35) come from the window that ends in 2026.
    assert by_rule(body["ruleChecks"])["cap.growth_assets"] == (35.0, "conflict")
    assert by_rule(body["ruleChecks"])["floor.fixed_income"] == (55.0, "conflict")
    assert body["baselineConflict"] is True and body["asOf"] == as_of


def test_check_at_a_past_date_uses_the_thresholds_a_replay_pins(client):
    body = post_check(client, asOf="2023-06-30").json()
    pinned = validate_asof("2023-06-30", robert(), starter_snapshot(), None, NOW).profile
    assert {c["ruleId"]: c["threshold"] for c in body["ruleChecks"]} == {r.rule_id: r.threshold for r in pinned.rules}
    assert by_rule(body["ruleChecks"])["cap.growth_assets"] == (45.0, "conflict")
    assert body["verdict"] == "conflict"                      # "compatible" against the 2026 threshold of 55
    current = post_check(client).json()
    assert by_rule(current["ruleChecks"])["cap.growth_assets"] == (55.0, "pass") and current["verdict"] == "compatible"


def test_request_overrides_still_apply_on_top_of_the_thresholds_of_that_date(client):
    body = post_check(client, asOf="2023-06-30", ruleOverrides=[{"ruleId": "cap.growth_assets", "threshold": 60}]).json()
    assert by_rule(body["ruleChecks"])["cap.growth_assets"] == (60.0, "pass")
    assert by_rule(body["ruleChecks"])["floor.fixed_income"][0] == 45.0


def test_a_past_date_without_enough_history_for_the_thresholds_is_insufficient_data(client):
    for as_of in ("2022-06-30", "2021-11-12", "1990-01-01"):
        response = post_check(client, asOf=as_of)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "insufficient_data"


# Findings 35, 55: a date after the data is refused ------------------------------------------------


@pytest.mark.parametrize("as_of", ["2026-11-13", "2027-01-01", "9999-12-31"])
def test_check_refuses_a_date_after_the_data_date(client, as_of):
    response = post_check(client, asOf=as_of)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation_error" and error["details"]["fields"][0]["path"] == "asOf"
    batch = client.post("/v1/check/batch", json={"items": [{"profileId": "robert", "move": None, "asOf": as_of},
                                                           {"profileId": "robert", "move": None}]}, headers=H)
    assert batch.status_code == 200, batch.text
    refused, served = batch.json()["results"]
    assert refused["error"]["code"] == "validation_error" and served["asOf"] == "2026-11-12"


def test_check_at_the_data_date_is_unchanged(client):
    assert post_check(client, asOf="2026-11-12").json()["ruleChecks"] == post_check(client).json()["ruleChecks"]


# Finding 8: the rule set of a replay is the one derived at the cutoff ------------------------------


def test_rules_the_derivation_creates_at_the_cutoff_are_pinned_and_stamped():
    profile = moderate_high()
    assert "floor.diversifiers" in ids(profile) and not set(GROWTH_RULES) & set(ids(profile))
    pinned = validate_asof("2022-12-30", profile, starter_snapshot(), None, NOW).profile
    rules = {r.rule_id: r for r in pinned.rules}
    assert (rules["cap.growth_assets"].threshold, rules["floor.fixed_income"].threshold) == (85.0, 5.0)
    assert "floor.diversifiers" not in rules                  # it stood in for a growth cap that applies at this date
    assert ids(pinned)[:4] == ["cap.position", "cap.sector", *GROWTH_RULES]
    assert [r.code for r in pinned.rules] == [f"R{i}" for i in range(1, len(pinned.rules) + 1)]
    derived = [r for r in pinned.rules if r.origin == "derived"]
    assert all(r.derivation.inputs["asOf"] == "2022-12-30" for r in derived) and len(derived) == 7
    private = {"dataVersion": STARTER_VERSION, "asOf": "2022-12-30", "mode": "historical", "profile": pinned.to_wire()}
    assert gate_factory(starter_snapshot)(private).mode == "historical"
    kept = {r.rule_id: r.to_wire() for r in profile.rules if r.origin != "derived" and r.rule_id != "floor.diversifiers"}
    assert {rid: {**rules[rid].to_wire(), "code": kept[rid]["code"]} for rid in kept} == kept


def test_a_cutoff_with_the_same_structure_keeps_rule_ids_and_codes():
    profile = moderate_high()
    pinned = validate_asof("2023-06-30", profile, starter_snapshot(), None, NOW).profile
    assert [(r.code, r.rule_id) for r in pinned.rules] == [(r.code, r.rule_id) for r in profile.rules]


def test_a_growth_cap_without_a_bond_floor_and_the_way_back():
    snap, profile = starter_snapshot(), moderate_high()
    partial = rederive_at(profile, snap, "2023-06-12", NOW)   # growth cap 95: the fixed-income floor is zero, so no rule
    assert "cap.growth_assets" in ids(partial) and not {"floor.fixed_income", "floor.diversifiers"} & set(ids(partial))
    capped = rederive_at(profile, snap, "2022-12-30", NOW)
    back = rederive_at(capped, snap, "2023-06-30", NOW)       # growth cap 100 again: the growth rules leave, the floor returns
    assert [(r.code, r.rule_id, r.threshold) for r in back.rules] == [(r.code, r.rule_id, r.threshold) for r in profile.rules]


def test_rules_the_user_edited_are_kept_whatever_the_derivation_says():
    snap = starter_snapshot()
    profile = with_rule(with_rule(moderate_high(), "floor.diversifiers", origin="user", threshold=12.0),
                        "cap.position", origin="user", threshold=7.0, derivation=None)
    pinned = {r.rule_id: r for r in rederive_at(profile, snap, "2022-12-30", NOW).rules}
    assert (pinned["floor.diversifiers"].threshold, pinned["cap.position"].threshold) == (12.0, 7.0)
    assert pinned["cap.position"].origin == "user" and pinned["cap.growth_assets"].threshold == 85.0
    authored = profile
    for rule_id in ("cap.sector", "limit.volatility", "limit.stress_2022", "limit.drawdown"):
        authored = with_rule(authored, rule_id, origin="user", derivation=None)
    assert rederive_at(authored, snap, "2022-12-30", NOW) is authored        # no derived rule left: nothing to recompute


def test_a_derived_rule_that_cannot_be_recomputed_still_rejects():
    with pytest.raises(ServiceError) as exc:
        rederive_at(robert(), starter_snapshot(), "2022-06-30", NOW)
    assert exc.value.code == "insufficient_data" and exc.value.details["asOf"] == "2022-06-30"


def test_a_replay_checks_the_growth_cap_and_bond_floor_of_its_cutoff():
    harness = Harness(ScriptedGateway())
    profile = harness.profiles.create(harness.session, moderate_high_request())
    run, _ = harness.drive(harness.create({"kind": "replay", "profileId": profile.profile_id, "lang": "en", "asOf": "2022-12-30",
                                           "request": {"type": "move", "move": QQQ_FROM_BONDS}}))
    assert run.status == "succeeded", run.error
    decision = run.result.replay.decision.to_wire()
    checks = by_rule(next(s for s in decision["scenarios"] if s["scenarioId"] == decision["selectedScenarioId"])["ruleChecks"])
    assert checks["cap.growth_assets"] == (85.0, "conflict")  # 92% of growth assets after the move
    assert checks["floor.fixed_income"] == (5.0, "conflict")  # no bond left
    assert "floor.diversifiers" not in checks
