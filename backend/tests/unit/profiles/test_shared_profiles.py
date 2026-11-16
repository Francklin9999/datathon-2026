import copy

import pytest
from aplomb.api.errors import Conflict, NotFound
from aplomb.api.repositories import ProfileRepository
from aplomb.api.storage import MemoryStore, Write
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.profiles.service import ProfileServiceImpl

from tests.unit.datastore._support import starter_snapshot

A = "s_aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "s_bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
PROFILE_ID = "p_123456789a"


def test_shared_profiles_are_live_and_session_overlays_are_private():
    store = MemoryStore()
    repo = ProfileRepository(store)
    service = ProfileServiceImpl(repo, starter_snapshot)
    seed = service.get(A, "robert").to_wire()
    seed.update(profileId=PROFILE_ID, name="Shared investor", initial="S")
    seed["accounts"] = [
        {"accountId": "acct_000000000001", "name": "Retirement", "portfolio": copy.deepcopy(seed["portfolio"])},
        {"accountId": "acct_000000000002", "name": "Taxable", "portfolio": copy.deepcopy(seed["portfolio"])},
    ]
    seed["activeAccountId"] = "acct_000000000001"
    m.Profile.model_validate(seed)

    def put_template(profile, revision, expected):
        store.transact([Write("profiles", "SHARED#PROFILES", f"PROFILE#{PROFILE_ID}",
                              {"revision": revision, "profileId": PROFILE_ID, "overlay": False, "value": profile}, expected)])

    # The service already exists: discovery must not depend on initialization.
    put_template(seed, 1, None)
    assert PROFILE_ID in [p.profile_id for p in service.list(A)]
    assert PROFILE_ID in [p.profile_id for p in service.list(B)]
    changed = service.patch_rule(A, PROFILE_ID, "cap.position", 12, None)
    assert changed.version == 2
    assert next(r for r in service.get(A, PROFILE_ID).rules if r.rule_id == "cap.position").threshold == 12
    assert next(r for r in service.get(B, PROFILE_ID).rules if r.rule_id == "cap.position").threshold == 10
    assert repo.get(B, PROFILE_ID, overlay=True) is None

    updated = copy.deepcopy(seed)
    updated["name"] = "Updated investor"
    updated["accounts"][1]["name"] = "Updated taxable"
    put_template(updated, 2, 1)
    assert service.get(A, PROFILE_ID).name == service.get(B, PROFILE_ID).name == "Updated investor"
    assert service.get(A, PROFILE_ID).accounts[1].name == "Updated taxable"
    assert service.get(A, PROFILE_ID).version == 2

    clone = service.duplicate(A, PROFILE_ID)
    assert not clone.is_default and clone.name == "Updated investor copy"
    assert len(clone.accounts) == 2
    assert {account.account_id for account in clone.accounts}.isdisjoint(
        {account["accountId"] for account in updated["accounts"]})
    assert clone.active_account_id == clone.accounts[0].account_id
    with pytest.raises(NotFound):
        service.get(B, clone.profile_id)
    with pytest.raises(Conflict):
        service.archive(A, PROFILE_ID, True, 2)
    with pytest.raises(Conflict):
        service.delete(A, PROFILE_ID)
    # Default protection is evaluated before request fields are used.
    with pytest.raises(Conflict):
        service.replace(A, PROFILE_ID, a.UpdateProfileRequest.model_validate({
            "name": seed["name"], "age": seed["age"], "riskLevel": seed["riskLevel"],
            "horizonYears": seed["horizonYears"], "objective": seed["objective"],
            "experience": seed["experience"], "reportingCurrency": seed["reportingCurrency"],
            "preferences": seed["preferences"], "portfolio": {
                "totalValue": seed["portfolio"]["totalValue"],
                "positions": [{"ticker": p["ticker"], "weightPct": p["weightPct"]}
                              for p in seed["portfolio"]["positions"]]},
            "rules": seed["rules"], "fromDraftRunId": None, "version": 2,
        }), 2)
