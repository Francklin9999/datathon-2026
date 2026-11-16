"""Investor Lab's public flow against the pinned starter dataset."""
import copy
import itertools
import uuid
from dataclasses import replace

import pytest
from aplomb.api.app import create_default_app
from aplomb.api.settings import Settings
from aplomb.contracts.catalog import FeatureFlag
from aplomb.contracts.models import Profile
from fastapi.testclient import TestClient
from tests.unit.datastore._support import STARTER_VERSION, starter_root


@pytest.fixture(scope="module")
def client():
    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()),
                        features={FeatureFlag.PROFILE_CREATOR: True})
    app = create_default_app(settings)
    # Tests execute dozens of user interactions in one second.
    ticks = itertools.count()
    app.state.limiter.clock = lambda: next(ticks)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def headers():
    return {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}


def checked(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def situation(**over):
    result = {"name": "Morgan", "objective": "balanced", "horizonYears": 5,
              "cashNeedPct": 20, "cashNeedMonths": 24, "riskCapacity": "low",
              "riskWillingness": "high", "experience": "intermediate", "interest": "Technology",
              "reportingCurrency": "CAD", "capital": 100000, "holdings": []}
    result.update(over)
    return result


def start(client, headers, mode="new", profile=None, **over):
    body = {"mode": mode, "situation": situation(**over)}
    if profile:
        body.update(profileId=profile["profileId"], profileVersion=profile["version"])
    return checked(client.post("/v1/investor-lab", headers=headers, json=body), 201)


def decision(pct, action="hold", reason="cash_need"):
    return {"action": action, "targetPct": pct, "reason": reason,
            "explanation": "This allocation supports the stated goal."}


def post(client, headers, lab, action, **body):
    return client.post(f'/v1/investor-lab/{lab["labId"]}/{action}', headers=headers,
                       json={"version": lab["version"], **body})


def progress(client, headers, lab):
    while lab["stage"] == "initial":
        assert lab["evidence"] == [] and lab["reveal"] == [] and lab["settings"] == []
        d = decision(lab["focusPct"])
        lab = checked(post(client, headers, lab, "initial", decision=d))
        assert lab["stage"] == "research"
        lab = checked(post(client, headers, lab, "consult", evidenceId="macro",
                           why="The market environment matters to my choice."))
        lab = checked(post(client, headers, lab, "final", decision=d,
                           revisitTrigger="I will revisit if my cash needs change."))
        lab = checked(post(client, headers, lab, "contrast", decision=d))
    assert lab["stage"] == "review"
    return lab


def confirmation(lab):
    return {"accepted": [{"key": setting["key"]} for setting in lab["settings"]],
            "principle": "Keep my allocation consistent with my goals.",
            "revisitTrigger": "Revisit when my cash needs change.",
            "explanation": "I reviewed these settings and accept them."}


def test_new_full_flow_masked_confirmation_and_engine(client, headers):
    before = checked(client.get("/v1/profiles", headers=headers))
    lab = start(client, headers, capital=250000)
    assert lab["checkpointCount"] == 3
    assert checked(client.get("/v1/profiles", headers=headers)) == before
    serialized = str(lab)
    for secret in ("2022-05-17", "2022-11-02", "2023-06-02", "MSFT", "Microsoft", "FY2023"):
        assert secret not in serialized
    other = {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}
    assert client.get(f'/v1/investor-lab/{lab["labId"]}', headers=other).status_code == 404
    assert post(client, headers, lab, "initial", decision=decision(lab["focusPct"], "buy")).status_code == 422
    bad = copy.deepcopy(lab)
    bad["version"] += 1
    assert post(client, headers, bad, "initial", decision=decision(lab["focusPct"])).status_code == 409
    lab = progress(client, headers, lab)
    assert checked(client.get("/v1/profiles", headers=headers)) == before
    assert any("Microsoft" in x for x in lab["reveal"])
    portfolio_setting = next(s for s in lab["settings"] if s["key"] == "portfolio")
    assert portfolio_setting["required"] and "CAD 250,000" in portfolio_setting["proposed"]
    assert post(client, headers, lab, "confirm", **{**confirmation(lab), "accepted": []}).status_code == 422
    saved = checked(post(client, headers, lab, "confirm", **confirmation(lab)))
    assert saved["portfolio"]["totalValue"] == 250000
    assert saved["riskLevel"] == "high"
    assert saved["investorContext"]["riskCapacity"] == "low"
    assert len(saved["investorContext"]["playbook"]["reviews"]) == 1
    assert checked(post(client, headers, lab, "confirm", **confirmation(lab))) == saved
    pid = saved["profileId"]
    checked(client.get(f"/v1/profiles/{pid}/overview", headers=headers))
    checked(client.post("/v1/check", headers=headers, json={"profileId": pid, "move": None}))


def test_existing_default_copy_and_stale_profile(client, headers):
    original = checked(client.get("/v1/profiles/robert", headers=headers))
    lab = start(client, headers, mode="quick", profile=original, reportingCurrency=original["reportingCurrency"])
    assert lab["checkpointCount"] == 1
    lab = progress(client, headers, lab)
    saved = checked(post(client, headers, lab, "confirm", **confirmation(lab)))
    assert saved["profileId"] != original["profileId"] and not saved["isDefault"]
    assert [(p["ticker"], p["weightPct"]) for p in saved["portfolio"]["positions"]] == [
        (p["ticker"], p["weightPct"]) for p in original["portfolio"]["positions"]]
    assert saved["portfolio"]["totalValue"] == original["portfolio"]["totalValue"]
    assert checked(client.get("/v1/profiles/robert", headers=headers)) == original

    lab2 = start(client, headers, mode="quick", profile=saved, reportingCurrency=saved["reportingCurrency"])
    lab2 = progress(client, headers, lab2)
    update = {"version": saved["version"], "principle": "A revised principle for the portfolio.",
              "revisitTrigger": "Revisit if circumstances change.", "explanation": "I chose to revise this playbook."}
    changed = checked(client.put(f'/v1/profiles/{saved["profileId"]}/playbook', headers=headers, json=update))
    assert changed["version"] == saved["version"] + 1
    assert post(client, headers, lab2, "confirm", **confirmation(lab2)).status_code == 409


def test_custom_profile_accounts_and_reject_invalid_confirmation(client, headers):
    initial = start(client, headers, holdings=[{"ticker": "MSFT", "weightPct": 35},
                                                 {"ticker": "AGG", "weightPct": 65}])
    initial = progress(client, headers, initial)
    profile = checked(post(client, headers, initial, "confirm", **confirmation(initial)))
    pid = profile["profileId"]
    profile = checked(client.post(f"/v1/profiles/{pid}/accounts", headers=headers, json={
        "version": profile["version"], "name": "Second account", "currency": "CAD",
        "portfolio": {"totalValue": 20000, "positions": [
            {"ticker": "SPY", "weightPct": 70}, {"ticker": "CASH.CAD", "weightPct": 30}]}}), 201)
    lab = start(client, headers, "full", profile, reportingCurrency="CAD")
    lab = progress(client, headers, lab)
    confirm = confirmation(lab)
    duplicate = copy.deepcopy(confirm)
    duplicate["accepted"] = [{"key": lab["settings"][0]["key"]}] * 2
    assert post(client, headers, lab, "confirm", **duplicate).status_code == 422
    unknown = copy.deepcopy(confirm)
    unknown["accepted"].append({"key": "not-a-setting"})
    assert post(client, headers, lab, "confirm", **unknown).status_code == 422
    cap = next(s for s in lab["settings"] if s["key"] == "rule.cap.position")
    invalid = copy.deepcopy(confirm)
    next(x for x in invalid["accepted"] if x["key"] == cap["key"])["value"] = cap["maximum"] + 1
    assert post(client, headers, lab, "confirm", **invalid).status_code == 422
    unchanged = checked(client.get(f"/v1/profiles/{pid}", headers=headers))
    assert unchanged == profile
    # An update may accept no optional settings while explicitly confirming its playbook.
    confirm["accepted"] = []
    saved = checked(post(client, headers, lab, "confirm", **confirm))
    assert saved["version"] == profile["version"] + 1
    assert saved["activeAccountId"] == profile["activeAccountId"]
    for after, before in zip(saved["accounts"], profile["accounts"], strict=True):
        assert after["accountId"] == before["accountId"]
        assert after["portfolio"]["totalValue"] == before["portfolio"]["totalValue"]
        assert [(p["ticker"], p["weightPct"]) for p in after["portfolio"]["positions"]] == [
            (p["ticker"], p["weightPct"]) for p in before["portfolio"]["positions"]]
    assert Profile.model_validate(saved).rules == Profile.model_validate(profile).rules
    checked(client.get(f"/v1/profiles/{pid}/overview", headers=headers))


def test_research_unlocks_only_past_evidence_and_rebalances(client, headers):
    lab = start(client, headers)
    target = lab["focusPct"] + 5
    lab = checked(post(client, headers, lab, "initial", decision=decision(target, "buy")))
    assert post(client, headers, lab, "consult", evidenceId="company", why="This matters to me.").status_code == 422
    assert post(client, headers, lab, "consult", evidenceId="disclosure", why="This matters to me.").status_code == 422
    assert all(x not in str(lab) for x in ("Microsoft", "2022-10-25", "2023-04-25", "rose 11%", "rose 7%"))
    lab = checked(post(client, headers, lab, "final", decision=decision(target, "buy"),
                       revisitTrigger="Revisit when the investment thesis changes."))
    lab = checked(post(client, headers, lab, "contrast", decision=decision(target, "buy")))
    assert lab["checkpoint"] == 2 and lab["stage"] == "initial"
    assert lab["focusPct"] != pytest.approx(10.0)
    lab = checked(post(client, headers, lab, "initial", decision=decision(lab["focusPct"])))
    company = next(item for item in lab["evidence"] if item["evidenceId"] == "company")
    assert company["available"] and "rose 11%" in company["summary"]
    assert "rose 7%" not in str(lab) and "Microsoft" not in str(lab)


def test_confirmation_transaction_failure_leaves_profile_and_lab_unchanged(client, headers, monkeypatch):
    lab = progress(client, headers, start(client, headers))
    before = checked(client.get("/v1/profiles", headers=headers))
    store = client.app.state.services.runs.repository.store
    transact = store.transact

    def conflict_on_lab(writes):
        if len(writes) > 1 and writes[-1].pk.startswith("INVESTOR_LAB#"):
            writes = [*writes[:-1], replace(writes[-1], expected=writes[-1].expected + 1)]
        return transact(writes)

    with monkeypatch.context() as patch:
        patch.setattr(store, "transact", conflict_on_lab)
        assert post(client, headers, lab, "confirm", **confirmation(lab)).status_code == 409
    assert checked(client.get("/v1/profiles", headers=headers)) == before
    restored = checked(client.get(f'/v1/investor-lab/{lab["labId"]}', headers=headers))
    assert restored["stage"] == "review" and restored["version"] == lab["version"]
    assert checked(post(client, headers, lab, "confirm", **confirmation(lab)))["profileId"]
