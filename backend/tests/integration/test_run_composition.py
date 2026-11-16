"""The exported composition end to end over HTTP: real datastore, quant, rules, optimizer,
ledger, auditor, world bundle and time machine. Only the model is replaced, by a scripted
test gateway whose model ID says so; no network, AWS or model call is made."""

from __future__ import annotations

import time
import uuid

import pytest
from aplomb.api.app import create_app
from aplomb.api.domain import default_services
from aplomb.api.settings import Settings
from aplomb.contracts.catalog import FeatureFlag
from aplomb.contracts.registry import adapter
from fastapi.testclient import TestClient
from tests.integration._scripted import MODEL_ID, ScriptedGateway
from tests.unit.datastore._support import STARTER_VERSION, starter_root

TSLA_25 = {"type": "move", "move": {"ticker": "TSLA", "sizePct": 25, "funding": {"mode": "pro_rata"}}}
TERMINAL = {"succeeded", "failed", "cancelled", "waiting_input"}


def settings(**flags) -> Settings:
    features = {flag: True for flag in FeatureFlag}
    features[FeatureFlag.GUARDRAILS] = False
    features.update({FeatureFlag(k): v for k, v in flags.items()})
    return Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()), features=features)


def session() -> dict:
    return {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}


def make(gateway=None, **flags) -> TestClient:
    cfg = settings(**flags)
    return TestClient(create_app(cfg, default_services(cfg, gateway=gateway)))


def ok(response, contract, status=200):
    assert response.status_code == status, response.text
    return adapter(contract).validate_json(response.content).to_wire()


def run_to_end(client, headers, body, expect=202) -> dict:
    created = client.post("/v1/runs", json=body, headers=headers)
    assert created.status_code == expect, created.text
    run_id = created.json()["runId"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        run = ok(client.get(f"/v1/runs/{run_id}", headers=headers), "Run")
        if run["status"] in TERMINAL:
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


@pytest.fixture(scope="module")
def client():
    return make(ScriptedGateway())


@pytest.fixture(scope="module")
def decision(client):
    headers = session()
    run = run_to_end(client, headers, {"kind": "decision", "profileId": "robert", "lang": "en", "request": TSLA_25})
    return headers, run


# Without a configured model ---------------------------------------------------------------------


def test_without_a_model_runs_are_refused_and_deterministic_endpoints_work():
    client, headers = make(), session()
    meta = ok(client.get("/v1/meta"), "Meta")
    assert meta["models"] == {"strong": None, "fast": None}
    assert {k for k, v in meta["features"].items() if v} == {
        "bilingual", "frontier_chart", "goal_requests", "profile_creator", "time_machine", "world_explorer", "world_layer_hazards", "world_layer_facilities"}
    refused = client.post("/v1/runs", json={"kind": "decision", "profileId": "robert", "lang": "en", "request": TSLA_25}, headers=headers)
    assert refused.status_code == 503 and refused.json()["error"]["code"] == "upstream_unavailable"
    assert ok(client.get("/v1/runs", headers=headers), "RunsResponse")["items"] == []      # nothing was persisted
    assert client.post("/v1/requests/parse", json={"profileId": "robert", "text": "25% Tesla", "lang": "en"},
                       headers=headers).status_code == 503
    assert ok(client.get("/v1/profiles/robert/brief", headers=headers), "CachedBriefResponse") == {"run": None, "stale": False}
    check = ok(client.post("/v1/check", json={"profileId": "robert", "move": TSLA_25["move"]}, headers=headers), "CheckResult")
    assert (check["verdict"], check["maxCompatibleSizePct"]) == ("conflict", 6.0)
    # Sabotage and on-demand fetching have no provider, so their flags stay off even when configured on.
    assert not meta["features"]["sabotage_demo"] and not meta["features"]["on_demand_tickers"]
    assert meta["features"]["world_layer_facilities"]  # verified ECCC provider is now present


# World and replay over HTTP ---------------------------------------------------------------------


def test_world_endpoints_validate_against_the_contract(client):
    headers = session()
    layers = ok(client.get("/v1/world/layers", headers=headers), "WorldLayersResponse")
    assert [layer["layerId"] for layer in layers["items"]] == ["events", "exposure", "facilities", "hazards"]
    page = ok(client.get("/v1/world/events", params={"profileId": "robert", "limit": 5}, headers=headers), "WorldEventsResponse")
    assert len(page["items"]) == 5 and page["total"] > 5 and page["nextCursor"]
    nxt = ok(client.get("/v1/world/events", params={"profileId": "robert", "limit": 5, "cursor": page["nextCursor"]}, headers=headers),
             "WorldEventsResponse")
    assert not {e["eventId"] for e in nxt["items"]} & {e["eventId"] for e in page["items"]}
    multi = ok(client.get("/v1/world/events?category=monetary_policy&category=macro_release&country=CAN&from=2026-01-01&to=2026-11-12",
                          headers=headers), "WorldEventsResponse")
    assert multi["total"] > 0 and {e["category"] for e in multi["items"]} <= {"monetary_policy", "macro_release"}
    event_id = multi["items"][0]["eventId"]
    detail = ok(client.get(f"/v1/world/events/{event_id}", params={"profileId": "robert"}, headers=headers), "WorldEventResponse")
    assert detail["exposures"] and all(x["impact"] == "not_established" for x in detail["exposures"])
    assert detail["assessment"]["profileId"] == "robert" and detail["assessment"]["holdingsChecked"] == 11
    assert detail["assessment"]["exposures"] == detail["exposures"]
    assert detail["geographicRelationships"][0]["relation"] == "EVENT_OCCURRED_AT"
    observation_page = ok(client.get("/v1/world/observations", params={"profileId": "robert", "mode": "environment", "limit": 2},
                                     headers=headers), "WorldObservationsResponse")
    assert observation_page["total"] > 2 and len(observation_page["items"]) == 2
    assert observation_page["nextCursor"]
    assert all(item["source"]["url"].startswith("https://") for item in observation_page["items"])
    assert all(item["timeBasis"] == "event_date" for item in observation_page["items"] if item["datasetId"] == "world_events")
    assert all(item["assessment"]["holdingsChecked"] == 11 for item in observation_page["items"])
    historical_observations = ok(client.get("/v1/world/observations", params={"mode": "environment", "asOf": "2026-11-14"},
                                             headers=headers), "WorldObservationsResponse")
    assert historical_observations["total"] == 0
    assert [mode["mode"] for mode in historical_observations["modes"]] == ["news", "macro", "environment"]
    policy = ok(client.get("/v1/world/observations", params={"mode": "news", "q": "Federal Register"},
                           headers=headers), "WorldObservationsResponse")
    assert policy["total"] == 20
    assert all(row["location"] is None and row["timeBasis"] == "event_date"
               for row in policy["items"])
    macro = ok(client.get("/v1/world/observations", params={"mode": "macro", "scope": "providers", "limit": 1},
                          headers=headers), "WorldObservationsResponse")
    # SDMX 3, BIS 4, BLS 12, ECB assets 52, ECB press 4, Fed 4, ILO 3, NY Fed 12, StatCan 12 and WGI 206
    # (its ISR row withheld: the source's own PSE row is served).
    assert macro["total"] == 312
    environment = ok(client.get("/v1/world/observations", params={"mode": "environment", "limit": 1},
                                headers=headers), "WorldObservationsResponse")
    # 1,207 provider rows (Climate TRACE 12, EPA 438, Global Carbon Budget 469, CMR 5, GIBS 1, POWER 186,
    # OpenAQ 96) and the 668 feed earthquakes of magnitude 6.0 or more.
    assert environment["total"] == 1875
    exposure = ok(client.get("/v1/world/exposure", params={"profileId": "amira"}, headers=headers), "WorldExposureResponse")
    assert sum(i["weightPct"] for i in exposure["items"]) == pytest.approx(100)
    country = ok(client.get("/v1/world/countries/CAN", params={"profileId": "robert"}, headers=headers), "WorldCountryResponse")
    assert country["exposure"]["weightPct"] > 0 and len([f for f in country["macro"] if f["sources"][0]["datasetId"] == "macro_rates"]) == 2
    facilities = ok(client.get("/v1/world/facilities", params={"profileId": "robert", "limit": 3}, headers=headers), "FacilitiesResponse")
    assert facilities["total"] == 1863 and facilities["reportingYear"] == 2024
    assert all(row["ticker"] is None for row in facilities["items"])
    assert all(row["assessment"]["exposures"] for row in facilities["items"])
    hazards = ok(client.get("/v1/world/hazards", params={"profileId": "amira", "limit": 3}, headers=headers), "HazardsResponse")
    assert len(hazards["items"]) == 3 and hazards["total"] > 3
    assert all(row["assessment"]["profileId"] == "amira" and row["assessment"]["holdingsChecked"] == 16
               for row in hazards["items"])
    assert client.get("/v1/world/airports", headers=headers).status_code == 404
    for path, status in (("/v1/world/events/evt_000000000000", 404), ("/v1/world/exposure", 422),
                         ("/v1/world/events?from=2020-01-01&to=2026-01-01", 422), ("/v1/world/events?country=can", 422),
                         ("/v1/world/countries/canada", 422), ("/v1/world/events?profileId=p_aaaaaaaaaa", 404),
                         ("/v1/world/observations?profileId=p_aaaaaaaaaa", 404),
                         ("/v1/world/facilities?profileId=p_aaaaaaaaaa", 404),
                         ("/v1/world/hazards?profileId=p_aaaaaaaaaa", 404)):
        response = client.get(path, headers=headers)
        assert response.status_code == status, (path, response.text)
        adapter("ApiError").validate_json(response.content)
    passports = ok(client.get("/v1/datasets", headers=headers), "DatasetsResponse")
    status = {p["datasetId"]: p["status"] for p in passports["items"]}
    assert (status["world_events"], status["natural_hazards"], status["emissions_facilities"]) == ("in_use", "in_use", "in_use")
    for dataset_id, count in (("world_federal_register", 20), ("world_nasa_power", 186),
                              ("world_wgi_political_stability_2024", 206)):
        assert status[dataset_id] == "in_use"
        assert ok(client.get(f"/v1/datasets/{dataset_id}", headers=headers),
                  "DatasetPassport")["rowCount"] == count
    # Retired ids stay valid on the wire for this release (catalog §10); nothing is loaded or served.
    for dataset_id in ("world_aviation_weather", "world_noaa_alerts", "energy_wri_plants", "world_ucdp_ged_ukraine_2025"):
        retired = ok(client.get(f"/v1/datasets/{dataset_id}", headers=headers), "DatasetPassport")
        assert status[dataset_id] == "planned" and retired["rowCount"] is None
        assert retired["source"].startswith("Not served")
    natural_hazards = ok(client.get("/v1/datasets/natural_hazards", headers=headers), "DatasetPassport")
    assert "wildfire" not in natural_hazards["role"]["en"]
    assert natural_hazards["processing"][0]["en"].endswith("wildfire detections (NASA FIRMS) are not served.")
    assert ok(client.get("/v1/datasets/world_events", headers=headers), "DatasetPassport")["rowCount"] == next(layer["count"] for layer in layers["items"] if layer["layerId"] == "events")


def test_world_serves_persona_modes_and_presents_palestine(client):
    headers = session()
    for removed in ("aviation", "trade", "conflicts", "infrastructure", "energy", "hazards"):
        assert client.get("/v1/world/observations", params={"mode": removed}, headers=headers).status_code == 422
    events = ok(client.get("/v1/world/events", params={"from": "2025-11-13", "to": "2026-11-12", "limit": 1000},
                           headers=headers), "WorldEventsResponse")
    assert {e["origin"] for e in events["items"] if e["category"] == "natural_disaster"} == {"usgs"}
    # Team decision: ISR is presented as Palestine; the panel serves the World Bank's own PSE series.
    palestine = ok(client.get("/v1/world/countries/ISR", headers=headers), "WorldCountryResponse")
    assert palestine["countryIso3"] == "PSE" and palestine["name"]["en"] == "Palestine"
    wdi = [f for f in palestine["macro"] if f["sources"][0]["datasetId"] == "world_bank_indicators"]
    assert wdi and all(f["subject"]["id"].startswith("wdi:PSE:") and "locations=PSE" in f["sources"][0]["sourceUrl"] for f in wdi)
    assert ok(client.get("/v1/world/countries/PSE", headers=headers), "WorldCountryResponse") == palestine
    wgi = ok(client.get("/v1/world/observations", params={"mode": "macro", "country": "ISR", "q": "political stability"},
                        headers=headers), "WorldObservationsResponse")
    assert [row["countryIso3"] for row in wgi["items"]] == ["PSE"]
    assert "West Bank" not in wgi["items"][0]["title"] and "Palestine" in wgi["items"][0]["title"]
    gdelt = ok(client.get("/v1/world/observations", params={"mode": "news", "q": "Tel Aviv"}, headers=headers),
               "WorldObservationsResponse")
    assert gdelt["items"] and all("Israel" not in row["title"] for row in gdelt["items"])
    wgi_passport = ok(client.get("/v1/datasets/world_wgi_political_stability_2024", headers=headers), "DatasetPassport")
    assert any("presented as Palestine (PSE)" in note["en"] for note in wgi_passport["processing"])
    assert any("1 ISR-coded row(s) are withheld" in note["en"] for note in wgi_passport["processing"])


def test_disabled_flags_answer_501():
    client, headers = make(ScriptedGateway(), world_explorer=False, time_machine=False), session()
    for path in ("/v1/world/layers", "/v1/world/events", "/v1/world/hazards", "/v1/replay/presets"):
        response = client.get(path, headers=headers)
        assert response.status_code == 501 and response.json()["error"]["code"] == "feature_disabled", path
    body = {"kind": "replay", "profileId": "robert", "lang": "en", "request": TSLA_25, "asOf": "2023-06-30"}
    assert client.post("/v1/runs", json=body, headers=headers).status_code == 501
    assert client.post("/v1/runs", json={"kind": "event_brief", "profileId": "robert", "lang": "en", "eventId": "evt_000000000000"},
                       headers=headers).status_code == 501
    meta = ok(client.get("/v1/meta"), "Meta")
    assert not meta["features"]["world_explorer"] and not meta["features"]["time_machine"]


# Decision (AT-01, AT-07, AT-09) -----------------------------------------------------------------


def test_decision_runs_through_the_real_controls_and_audit(decision):
    _, run = decision
    assert run["status"] == "succeeded", run["error"]
    result = run["result"]["decision"]
    assert result["verdict"] == "conflict" and result["maxCompatibleSizePct"] == 6.0
    assert result["counts"] == {"pass": 1, "tension": 1, "conflict": 6, "nee": 0, "info": 3}
    assert [s["scenarioId"] for s in result["scenarios"]][:2] == ["sc_requested", "sc_max_compatible"]
    assert [s["type"] for s in run["steps"]] == ["plan", "quant", "risk_check", "write", "audit", "sign"]
    assert all(s["status"] == "done" and s["durationMs"] is not None for s in run["steps"])
    assert [s["actor"] for s in run["steps"]] == ["llm", "code", "code", "llm", "code+llm", "code"]
    assert run["steps"][0]["model"] == MODEL_ID and run["steps"][1]["model"] is None
    assert run["usage"]["llmCalls"] == 3 and not run["flags"]["fixture"]
    # Summaries are code templates with counts, in both languages.
    assert run["steps"][2]["summary"]["en"].startswith("Checked 11 rule(s) on 2 scenario(s): 6 conflict, 1 tension, 1 fit")
    assert "en conflit" in run["steps"][2]["summary"]["fr"]
    assert run["steps"][5]["summary"]["en"] == f"Result signed. Ledger hash {result['brief']['audit']['ledgerHash'][:8]}."
    after = result["scenarios"][0]["portfolioAfter"]["metrics"]
    assert round(after["volatilityPct"], 2) == 16.96 and round(after["maxDrawdownPct"], 2) == 25.31


def test_every_numeric_segment_resolves_to_a_verified_fact_of_the_same_run(client, decision):
    headers, run = decision
    brief = run["result"]["decision"]["brief"]
    assert brief["audit"]["status"] == "passed" and brief["audit"]["sentencesStruck"] == 0
    assert {s["id"] for s in brief["sections"]} >= {"facts", "assumptions", "limits"}
    cited = [seg["factId"] for section in brief["sections"] for sentence in section["sentences"]
             for seg in sentence["segments"] if seg["t"] == "fact"]
    assert cited
    assert all(fact["verification"]["status"] == "verified" for fact in run["facts"].values())
    for fact_id in cited:
        detail = ok(client.get(f"/v1/runs/{run['runId']}/facts/{fact_id}", headers=headers), "FactResponse")
        assert detail["fact"]["id"] == fact_id and detail["usedBy"]["sentenceIds"]
        assert detail["fact"]["method"]["id"] and detail["fact"]["asOf"] == run["asOf"]
    # Every rule in conflict or tension is named in the assumptions section (A12).
    named = {seg["ruleId"] for section in brief["sections"] if section["id"] == "assumptions"
             for sentence in section["sentences"] for seg in sentence["segments"] if seg["t"] in ("rule", "status")}
    flagged = {c["ruleId"] for c in run["result"]["decision"]["scenarios"][0]["ruleChecks"] if c["status"] in ("conflict", "tension")}
    assert flagged and flagged <= named


def test_runs_are_listed_and_isolated_by_session(client, decision):
    headers, run = decision
    listed = ok(client.get("/v1/runs", headers=headers), "RunsResponse")["items"]
    assert [r["runId"] for r in listed] == [run["runId"]] and listed[0]["verdict"] == "conflict"
    other = session()
    assert client.get(f"/v1/runs/{run['runId']}", headers=other).status_code == 404
    assert ok(client.get("/v1/runs", headers=other), "RunsResponse")["items"] == []
    conflict = client.post(f"/v1/runs/{run['runId']}/reveal", json={}, headers=headers)
    assert conflict.status_code == 409                                             # reveal needs a replay


def test_a_model_failure_keeps_the_executed_steps_and_figures_visible():
    client, headers = make(ScriptedGateway(fail_role="writer")), session()
    run = run_to_end(client, headers, {"kind": "decision", "profileId": "robert", "lang": "en", "request": TSLA_25})
    assert run["status"] == "failed" and run["result"] is None and run["error"]["code"] == "upstream_unavailable"
    assert [(s["type"], s["status"]) for s in run["steps"]] == [
        ("plan", "done"), ("quant", "done"), ("risk_check", "done"), ("write", "failed")]
    assert len(run["facts"]) > 30                                                  # computed figures persist


def test_idempotent_creation_returns_the_same_run(client):
    headers = {**session(), "Idempotency-Key": "k-" + uuid.uuid4().hex}
    body = {"kind": "decision", "profileId": "amira", "lang": "en", "request": TSLA_25}
    first = client.post("/v1/runs", json=body, headers=headers)
    second = client.post("/v1/runs", json=body, headers=headers)
    assert first.status_code == 202 and second.json()["runId"] == first.json()["runId"]
    changed = client.post("/v1/runs", json={**body, "profileId": "robert"}, headers=headers)
    assert changed.status_code == 409


def test_french_brief_is_requested_in_french():
    gateway = ScriptedGateway()
    client, headers = make(gateway), session()
    run = run_to_end(client, headers, {"kind": "decision", "profileId": "amira", "lang": "fr", "request": TSLA_25})
    assert run["status"] == "succeeded" and run["result"]["decision"]["brief"]["lang"] == "fr"
    writer = next(prompt for role, prompt in gateway.prompts if role == "writer")
    assert writer["language"] == "French" and writer["instruction"].startswith("Write in French.")


# Replay and reveal (AT-13) ----------------------------------------------------------------------


def test_replay_presets_and_date_validation(client):
    headers = session()
    presets = ok(client.get("/v1/replay/presets", headers=headers), "ReplayPresetsResponse")
    assert presets["earliestAsOf"] == "2022-11-22" and len(presets["presets"]) >= 4
    for bad in ("2022-01-03", "2026-11-12"):
        body = {"kind": "replay", "profileId": "robert", "lang": "en", "request": TSLA_25, "asOf": bad}
        response = client.post("/v1/runs", json=body, headers=headers)
        assert response.status_code == 422 and response.json()["error"]["details"]["earliestAsOf"] == "2022-11-22"


def test_replay_uses_only_pre_cutoff_data_and_reveal_is_separate():
    gateway = ScriptedGateway()
    client, headers = make(gateway), session()
    as_of = "2022-12-01"
    run = run_to_end(client, headers, {"kind": "replay", "profileId": "robert", "lang": "en", "request": TSLA_25, "asOf": as_of})
    assert run["status"] == "succeeded", run["error"]
    assert run["asOf"] == as_of and run["flags"]["timeMachine"] and run["result"]["kind"] == "replay"
    assert "research" not in [s["type"] for s in run["steps"]]
    replay = run["result"]["replay"]
    assert replay["asOf"] == as_of and replay["revealAvailableUntil"] == "2026-11-12"
    assert {"LIM_LLM_KNOWLEDGE", "LIM_SAMPLE_WINDOW", "LIM_SURVIVORSHIP", "LIM_YAHOO_NOT_CERTIFIED"} <= set(replay["notices"])
    gate = {d["datasetId"]: d for d in replay["gate"]["datasets"]}
    assert gate["prices_daily"]["rowsWithheld"] > 0 and gate["prices_daily"]["lastVisibleDate"] == as_of
    # No fact of the signed decision uses a row or a period after the cutoff (A11).
    for fact in run["facts"].values():
        assert fact["asOf"] == as_of
        assert fact["availableAt"] is None or fact["availableAt"][:10] <= as_of
        assert fact["period"] is None or fact["period"]["end"] <= as_of
    checks = {c["ruleId"]: c for c in replay["decision"]["scenarios"][0]["ruleChecks"]}
    assert (checks["limit.stress_2022"]["status"], checks["limit.stress_2022"]["neeReason"]) == ("nee", "not_visible_at_asof")
    assert next(p for role, p in gateway.prompts if role == "planner")["information_cutoff"] == as_of
    assert "researcher" not in gateway.roles
    signed = replay["decision"]["brief"]["audit"]["ledgerHash"]

    reveal = ok(client.post(f"/v1/runs/{run['runId']}/reveal", json={"until": "2023-12-29"}, headers=headers), "RevealResult")
    repeated = ok(client.post(f"/v1/runs/{run['runId']}/reveal", json={"until": "2023-12-29"}, headers=headers), "RevealResult")
    assert repeated == reveal
    assert (reveal["asOf"], reveal["until"]) == (as_of, "2023-12-29")
    assert [o["scenarioId"] for o in reveal["outcomes"]][:2] == ["sc_unchanged", "sc_requested"]
    assert all(o["series"][0]["value"] == 100.0 and o["factIds"] for o in reveal["outcomes"])
    # Outcome facts are the Time Machine's; the reveal ledger also holds their input receipts.
    assert all(reveal["facts"][fid]["createdBy"] == "timemachine" for o in reveal["outcomes"] for fid in o["factIds"])
    after = ok(client.get(f"/v1/runs/{run['runId']}", headers=headers), "Run")
    assert after == run and after["result"]["replay"]["decision"]["brief"]["audit"]["ledgerHash"] == signed
    assert client.post(f"/v1/runs/{run['runId']}/reveal", json={"until": as_of}, headers=headers).status_code == 422
    assert client.post(f"/v1/runs/{run['runId']}/reveal", json={}, headers=session()).status_code == 404


# Portfolio brief (Home) and event brief ---------------------------------------------------------


def test_portfolio_brief_is_cached_per_profile_version(client):
    headers = session()
    assert ok(client.get("/v1/profiles/robert/brief", headers=headers), "CachedBriefResponse")["run"] is None
    body = {"kind": "portfolio_brief", "profileId": "robert", "lang": "en"}
    run = run_to_end(client, headers, body)
    assert run["status"] == "succeeded", run["error"]
    result = run["result"]["portfolioBrief"]
    assert result["verdict"] == "compatible" and result["horizonBand"] == "medium" and len(result["focusCards"]) == 3
    assert [s["type"] for s in run["steps"]] == ["plan", "quant", "risk_check", "write", "audit", "sign"]
    for card in result["focusCards"]:
        for sentence in card["body"]:
            for seg in sentence["segments"]:
                if seg["t"] == "fact":
                    assert run["facts"][seg["factId"]]["display"]["en"] == seg["display"]
    assert result["focusCards"][0]["factIds"] and result["focusCards"][1]["factIds"]
    again = client.post("/v1/runs", json=body, headers=headers)
    assert again.status_code == 200 and again.json() == {"runId": run["runId"], "status": "succeeded"}
    cached = ok(client.get("/v1/profiles/robert/brief", headers=headers), "CachedBriefResponse")
    assert cached["run"]["runId"] == run["runId"] and cached["stale"] is False
    assert ok(client.get("/v1/profiles/robert/brief", params={"lang": "fr"}, headers=headers), "CachedBriefResponse")["run"] is None
    # A threshold edit changes the effective profile version: the brief is stale and a new one is written.
    patched = client.patch("/v1/profiles/robert/rules/cap.position", json={"threshold": 12}, headers=headers)
    assert patched.status_code == 200, patched.text
    assert ok(client.get("/v1/profiles/robert/brief", headers=headers), "CachedBriefResponse")["stale"] is True
    fresh = run_to_end(client, headers, body)
    assert fresh["runId"] != run["runId"] and fresh["status"] == "succeeded"
    # Another session never sees this session's brief.
    assert ok(client.get("/v1/profiles/robert/brief", headers=session()), "CachedBriefResponse")["run"] is None


def test_event_brief_states_no_impact(client):
    headers = session()
    page = client.get("/v1/world/events", params={"category": "monetary_policy", "country": "CAN", "from": "2026-01-01",
                                                  "to": "2026-11-12", "limit": 1}, headers=headers).json()
    event_id = page["items"][0]["eventId"]
    run = run_to_end(client, headers, {"kind": "event_brief", "profileId": "robert", "lang": "en", "eventId": event_id})
    assert run["status"] == "succeeded", run["error"]
    assert [s["type"] for s in run["steps"]] == ["plan", "quant", "write", "audit", "sign"]
    result = run["result"]["eventBrief"]
    assert result["event"]["eventId"] == event_id and result["exposures"]
    assert all(x["impact"] == "not_established" and x["impactFactId"] is None for x in result["exposures"])
    assert result["impactStatement"]["en"] == "Potential exposure identified. Financial impact not established."
    assert result["brief"]["audit"]["status"] == "passed"
    metrics = {f["metric"] for f in run["facts"].values()}
    assert {"count.sources", "weight.position"} <= metrics and "return.period" not in metrics
    missing = client.post("/v1/runs", json={"kind": "event_brief", "profileId": "robert", "lang": "en", "eventId": "evt_000000000000"},
                          headers=headers)
    assert missing.status_code == 404


def test_profile_draft_and_parser_use_the_configured_gateway():
    parsed = {"request": TSLA_25, "interpretation": {"en": "Add 25 points to TSLA.", "fr": "Ajouter 25 points à TSLA."},
              "confidence": "high", "missing": [], "warnings": [], "refused": None}
    gateway = ScriptedGateway(parsed=parsed, draft_profile={"profile": {"occupation": "teacher"}, "explanations": [], "unresolved": []})
    client, headers = make(gateway), session()
    out = ok(client.post("/v1/requests/parse", json={"profileId": "robert", "text": "25% into Tesla", "lang": "en"}, headers=headers),
             "ParsedRequest")
    assert out["request"] == TSLA_25 and out["refused"] is None
    run = run_to_end(client, headers, {"kind": "profile_draft", "lang": "en", "text": "I work as a teacher."})
    assert run["status"] == "succeeded", run["error"]
    assert run["profileId"] is None and [s["type"] for s in run["steps"]] == ["plan", "audit", "sign"]
    draft = run["result"]["draft"]
    assert draft["profile"] == {"occupation": "teacher"}
    assert {u["field"] for u in draft["unresolved"]} >= {"riskLevel", "horizonYears"}     # never invented
    titles = [r["title"]["en"] for r in ok(client.get("/v1/runs", headers=headers), "RunsResponse")["items"]]
    assert titles == ["Profile draft"]


def test_goal_request_returns_at_most_three_candidates(client):
    """AT-17. A goal search registers more facts than one repository checkpoint may carry."""
    headers = session()
    goal = {"type": "goal", "goal": {"themes": ["ai"], "assetClasses": [], "tickers": [], "targetExposurePct": None,
                                     "maxLossPct": None, "maxVolPct": None, "notes": ""}}
    run = run_to_end(client, headers, {"kind": "decision", "profileId": "amira", "lang": "en", "request": goal})
    assert run["status"] == "succeeded", run["error"]
    assert len(run["facts"]) > 97
    result = run["result"]["decision"]
    scenarios = result["scenarios"]
    assert 1 <= len(scenarios) <= 3 and all(s["kind"] == "goal_candidate" for s in scenarios)
    assert sum(s["isBestFit"] for s in scenarios) == 1 and result["selectedScenarioId"] == scenarios[0]["scenarioId"]
    assert all(fid in run["facts"] for s in scenarios for fid in s["keyFactIds"])
    assert result["brief"]["audit"]["status"] == "passed"
    listed = ok(client.get("/v1/runs", headers=headers), "RunsResponse")["items"]
    assert listed[0]["title"] == {"en": "Goal: ai", "fr": "Objectif : ai"}


@pytest.mark.parametrize(("profile", "lang", "goal", "reason"), [
    ("amira", "en", {"themes": ["ai"], "tickers": [], "targetExposurePct": 15}, "already reaches the target"),
    ("amira", "fr", {"themes": ["ai"], "tickers": [], "targetExposurePct": 15}, "already reaches the target"),
    # Robert excludes crypto: no screened asset can serve the goal.
    ("robert", "en", {"themes": [], "tickers": ["BTC-USD"], "targetExposurePct": None}, "Only 0 candidate(s)"),
])
def test_goal_without_a_candidate_signs_an_unchanged_portfolio(client, profile, lang, goal, reason):
    """A target the portfolio already meets, or a goal no asset can serve, is a normal outcome:
    the run succeeds with one no-change scenario (no invented trade) carrying the reason."""
    headers = session()
    body = {"type": "goal", "goal": {"assetClasses": [], "maxLossPct": None, "maxVolPct": None, "notes": "", **goal}}
    run = run_to_end(client, headers, {"kind": "decision", "profileId": profile, "lang": lang, "request": body})
    assert run["status"] == "succeeded", run["error"]
    result = run["result"]["decision"]
    [scenario] = result["scenarios"]
    assert scenario["kind"] == "goal_candidate" and scenario["moves"] == [] and scenario["isBestFit"]
    assert result["selectedScenarioId"] == scenario["scenarioId"] == "sc_goal_no_change"
    assert reason in scenario["rationale"]["en"] and scenario["rationale"]["fr"]
    before, after = result["portfolioBefore"], scenario["portfolioAfter"]
    assert after["positions"] == before["positions"] and after["totalValue"] == before["totalValue"]
    assert scenario["verdict"] == result["verdict"] and scenario["counts"] == result["counts"]
    assert all(fid in run["facts"] for fid in scenario["keyFactIds"])
    assert result["brief"]["audit"]["status"] == "passed"
    if goal["themes"]:
        [exposure] = scenario["exposure"]
        assert exposure["beforePct"] == exposure["afterPct"] >= 15


@pytest.mark.parametrize("profile_id", ["robert", "amira", "mateo"])
def test_portfolio_focus_cards_are_distinct_and_evidence_linked(client, profile_id):
    run = run_to_end(client, session(), {"kind": "portfolio_brief", "profileId": profile_id, "lang": "en"})
    assert run["status"] == "succeeded", run["error"]
    cards = run["result"]["portfolioBrief"]["focusCards"]
    assert len(cards) == 3
    assert len({c["title"]["en"] for c in cards}) == 3
    horizons = [next(s for s in c["body"] if s["id"].endswith("-HORIZON"))["segments"][0]["text"] for c in cards]
    assert len(set(horizons)) == 3
    assert all(fid in run["facts"] and run["facts"][fid]["verification"]["status"] == "verified"
               for c in cards for fid in c["factIds"])
    bond = next((c for c in cards if c["title"]["en"] == "Interest-rate evidence"), None)
    if bond:
        assert bond["factIds"] and run["facts"][bond["factIds"][0]]["metric"] == "weight.asset_group"


def _sabotage(client, headers, parent_id, mode, lang):
    created = client.post(f"/v1/runs/{parent_id}/sabotage", json={"mode": mode, "lang": lang}, headers=headers)
    assert created.status_code == 202, created.text
    child_id = created.json()["runId"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        child = client.get(f"/v1/runs/{child_id}", headers=headers).json()
        if child["status"] in TERMINAL:
            break
        time.sleep(.05)
    assert child["status"] == "succeeded", child.get("error")
    return child


def test_sabotage_child_is_isolated_and_reports_actual_strike():
    # The scripted writer stands in for a model that would refuse: it is never asked to lie.
    calls = []

    def writer(message):
        from tests.integration._scripted import default_draft
        calls.append(message)
        return default_draft(message)

    client = make(ScriptedGateway(writer=writer))
    headers = session()
    parent = run_to_end(client, headers, {"kind": "decision", "profileId": "robert", "lang": "en", "request": TSLA_25})
    assert parent["status"] == "succeeded", parent["error"]
    parent_id = parent["runId"]
    writer_calls = len(calls)
    assert client.post(f"/v1/runs/{parent_id}/sabotage", json={"mode": "invented_number", "lang": "fr"}, headers=headers).status_code == 409
    child = _sabotage(client, headers, parent_id, "invented_number", "en")
    assert len(calls) == writer_calls  # the false sentence is written by code, not by the writer model
    result = child["result"]["sabotage"]
    assert result["briefBeforeAudit"]["status"] == "unaudited"
    ids = [s["id"] for section in result["briefBeforeAudit"]["sections"] for s in section["sentences"]]
    assert ids.count("S-INJECTED") == 1 and all(i == "S-INJECTED" or i.startswith("BASE-") for i in ids)
    assert result["caught"] and any(c["code"] == "A02" for c in result["failedChecks"])
    assert result["injectedInstruction"].startswith("Controlled test, written by code")
    write = next(step for step in child["steps"] if step["type"] == "write")
    assert write["actor"] == "code" and write["status"] == "done"
    assert client.get(f"/v1/runs/{parent_id}", headers=headers).json() == parent
    assert client.get(f"/v1/runs/{child['runId']}", headers=session()).status_code == 404


@pytest.mark.parametrize("lang", ["en", "fr"])
@pytest.mark.parametrize("mode,code", [("invented_number", "A02"), ("false_comparison", "A03"),
                                       ("unsupported_interpretation", "A14")])
def test_every_sabotage_mode_is_inserted_and_caught_by_the_real_audit(mode, code, lang):
    client = make(ScriptedGateway())
    headers = session()
    parent = run_to_end(client, headers, {"kind": "decision", "profileId": "robert", "lang": lang, "request": TSLA_25})
    assert parent["status"] == "succeeded", parent["error"]
    result = _sabotage(client, headers, parent["runId"], mode, lang)["result"]["sabotage"]
    injected = [s for section in result["briefBeforeAudit"]["sections"] for s in section["sentences"] if s["id"] == "S-INJECTED"]
    assert len(injected) == 1
    after = next(s for section in result["briefAfterAudit"]["sections"] for s in section["sentences"] if s["id"] == "S-INJECTED")
    assert after["audit"]["status"] == "struck" and code in after["audit"]["failedChecks"]
    assert result["caught"] is True and any(c["code"] == code and not c["ok"] for c in result["failedChecks"])
    # Only the inserted sentence is new: every other sentence is the parent's preserved, audited text.
    assert result["briefAfterAudit"]["audit"]["status"] != "failed"


@pytest.mark.parametrize("user_agent,registered", [
    (None, False),
    ("Aplomb datathon demo (github.com/example/repo)", False),   # no https:// and no email: research tools are absent
    ("Aplomb datathon demo (+https://example.org/contact)", True),
])
def test_open_web_is_never_advertised_and_research_needs_a_contact_user_agent(user_agent, registered):
    from aplomb.api.runtime import build_registry

    cfg = settings().model_copy(update={"source_user_agent": user_agent})  # every flag on, research_open_web too
    client = TestClient(create_app(cfg, default_services(cfg, gateway=ScriptedGateway())))
    meta = client.get("/v1/meta", headers=session()).json()
    assert meta["features"]["research_open_web"] is False  # no provider since the browser tool was removed
    assert bool(build_registry(cfg).schemas({"web.fetch"})) is registered


# Composition pins: brief cache identity, pinned snapshot date, Guardrail flag, AWS dispatch ------


def test_runtime_release_or_manifest_change_makes_the_cached_brief_stale():
    from types import SimpleNamespace

    from aplomb.api.runtime import brief_lookup
    from aplomb.api.storage import MemoryStore
    from tests.unit.datastore._support import starter_snapshot

    store, headers = MemoryStore(), session()
    sid = headers["X-Aplomb-Session"]
    body = {"kind": "portfolio_brief", "profileId": "robert", "lang": "en"}
    cfg = settings()
    old = TestClient(create_app(cfg, default_services(cfg, store=store, gateway=ScriptedGateway())))
    run = run_to_end(old, headers, body)
    assert run["status"] == "succeeded", run["error"]
    assert old.post("/v1/runs", json=body, headers=headers).status_code == 200        # same runtime: cache hit
    # A code-only redeploy (another build revision, same models, Guardrail, limits and flags) keeps
    # serving the brief: zero new runs while the data version is unchanged.
    redeployed = cfg.model_copy(update={"build_revision": "a" * 40})
    same = TestClient(create_app(redeployed, default_services(redeployed, store=store, gateway=ScriptedGateway())))
    kept = ok(same.get("/v1/profiles/robert/brief", headers=headers), "CachedBriefResponse")
    assert kept["run"]["runId"] == run["runId"] and kept["stale"] is False
    again = same.post("/v1/runs", json=body, headers=headers)
    assert again.status_code == 200 and again.json()["runId"] == run["runId"]
    # A runtime release (here a limit; equally a model, fallback, Guardrail, flag or data-prefix change)
    # with the same data and profile versions must not serve the brief the previous runtime wrote.
    released = redeployed.model_copy(update={"max_llm_calls": cfg.max_llm_calls - 1})
    services = default_services(released, store=store, gateway=ScriptedGateway())
    new = TestClient(create_app(released, services))
    cached = ok(new.get("/v1/profiles/robert/brief", headers=headers), "CachedBriefResponse")
    assert cached["run"]["runId"] == run["runId"] and cached["stale"] is True
    fresh = run_to_end(new, headers, body)                                            # 202: a new brief
    assert fresh["runId"] != run["runId"] and fresh["status"] == "succeeded", fresh["error"]
    assert ok(new.get("/v1/profiles/robert/brief", headers=headers), "CachedBriefResponse")["stale"] is False
    # Same data version but another pinned manifest digest: stale as well.
    repository = services.runs.repository
    current = brief_lookup(repository, services.profiles, starter_snapshot, released)
    assert current(sid, "robert", "en")[1] is False
    changed = SimpleNamespace(data_version=STARTER_VERSION, manifest={"tampered": True})
    found, stale = brief_lookup(repository, services.profiles, lambda: changed, released)(sid, "robert", "en")
    assert found.run_id == fresh["runId"] and stale is True


def test_a_brief_recorded_before_the_brief_identity_is_not_stale_on_a_redeploy():
    """Records written before ``briefIdentity`` was pinned are not compared on runtime, as the
    release that wrote them did not."""
    from aplomb.api.runtime import brief_lookup
    from aplomb.api.storage import MemoryStore
    from tests.unit.datastore._support import starter_snapshot

    store, headers = MemoryStore(), session()
    sid = headers["X-Aplomb-Session"]
    cfg = settings()
    services = default_services(cfg, store=store, gateway=ScriptedGateway())
    run = run_to_end(TestClient(create_app(cfg, services)), headers,
                     {"kind": "portfolio_brief", "profileId": "robert", "lang": "en"})
    repository = services.runs.repository
    record = repository.get(sid, run["runId"])
    assert "briefIdentity" in record.private
    # Rewrite the STATE item as an older release stored it (no briefIdentity).
    state = store.get("runs", f"RUN#{run['runId']}", "STATE")
    state["private"] = {k: v for k, v in state["private"].items() if k != "briefIdentity"}
    store._items[store._key("runs", f"RUN#{run['runId']}", "STATE")]["value"] = state
    assert brief_lookup(repository, services.profiles, starter_snapshot, cfg)(sid, "robert", "en")[1] is False
    # Review 2026-11-15: the deployed release never compared runtime, and its signature carries the
    # build revision; the first redeploy must not turn every existing brief stale.
    released = cfg.model_copy(update={"build_revision": "c" * 40})
    assert brief_lookup(repository, services.profiles, starter_snapshot, released)(sid, "robert", "en")[1] is False


@pytest.mark.parametrize("body", [
    {"kind": "portfolio_brief", "profileId": "robert", "lang": "en"},
    {"kind": "replay", "profileId": "robert", "lang": "en", "request": TSLA_25, "asOf": "2023-06-30"},
])
def test_worker_reopens_a_pinned_version_with_that_snapshot_date(body):
    """A run pinned to an older version is reopened with that version's own dataAsOf, not the date of
    the snapshot the worker currently serves (SnapshotProvider refuses a mismatched date)."""
    from types import SimpleNamespace

    from aplomb.api.composition import create_repositories
    from aplomb.api.errors import ServiceError
    from aplomb.api.runtime import RunPreparerImpl, gate_factory
    from aplomb.api.storage import MemoryStore
    from aplomb.contracts import api as a
    from aplomb.optimizer.services import build_domain_services
    from tests.unit.datastore._support import starter_snapshot

    cfg = settings()
    profile_repo, _ = create_repositories(cfg, MemoryStore())
    profiles, _ = build_domain_services(profile_repo, starter_snapshot)
    model = a.CreatePortfolioBriefRunRequest if body["kind"] == "portfolio_brief" else a.CreateReplayRunRequest
    prepared = RunPreparerImpl(profiles, starter_snapshot, models_configured=True, settings=cfg)(
        "s_" + str(uuid.uuid4()), model.model_validate(body))
    assert prepared.private["dataAsOf"] == starter_snapshot().data_as_of
    served = SimpleNamespace(data_version="snap-20261120-newer", data_as_of="2026-11-20")
    open_gate = gate_factory(lambda: served, cfg.model_copy(update={"data_as_of": "2026-11-20"}))
    gate = open_gate(prepared.private)
    assert gate.mode == ("historical" if body["kind"] == "replay" else "current")
    unpinned = {k: v for k, v in prepared.private.items() if k != "dataAsOf"}
    with pytest.raises(ServiceError, match="APLOMB_DATA_AS_OF"):
        open_gate(unpinned)


def test_guardrail_policy_follows_its_flag():
    from aplomb.agents.guardrails import BedrockOutputPolicy
    from aplomb.api.composition import create_repositories
    from aplomb.api.runtime import build_agent_services
    from aplomb.api.storage import MemoryStore
    from tests.unit.datastore._support import starter_snapshot

    configured = settings().model_copy(update={"guardrail_id": "abc123", "guardrail_version": "1"})
    _, repository = create_repositories(configured, MemoryStore())
    off = build_agent_services(configured, repository, starter_snapshot, gateway=ScriptedGateway())
    assert off.guardrail is None                       # an ID and version alone do not enable it
    enabled = configured.model_copy(update={"features": {**configured.features, FeatureFlag.GUARDRAILS: True}})
    on = build_agent_services(enabled, repository, starter_snapshot, gateway=ScriptedGateway())
    assert isinstance(on.guardrail, BedrockOutputPolicy)


def test_aws_api_composition_builds_no_worker_services(monkeypatch):
    import aplomb.api.runtime as runtime
    from aplomb.api.composition import create_repositories
    from aplomb.api.dispatcher import LambdaDispatcher, LocalDispatcher
    from aplomb.api.storage import MemoryStore
    from aplomb.optimizer.services import build_domain_services
    from tests.unit.datastore._support import starter_snapshot

    built = []
    original = runtime.build_agent_services
    monkeypatch.setattr(runtime, "build_agent_services", lambda *args, **kw: built.append(1) or original(*args, **kw))
    aws = settings().model_copy(update={"environment": "aws", "data_bucket": "bucket", "profiles_table": "profiles",
                                        "runs_table": "runs", "cache_table": "cache", "worker_function": "worker"})
    profile_repo, run_repo = create_repositories(settings(), MemoryStore())
    profiles, _ = build_domain_services(profile_repo, starter_snapshot)
    coordinator, _, _ = runtime.build_run_services(aws, run_repo, profiles, starter_snapshot, gateway=ScriptedGateway())
    assert isinstance(coordinator.dispatcher, LambdaDispatcher) and built == []
    coordinator, _, _ = runtime.build_run_services(settings(), run_repo, profiles, starter_snapshot,
                                                   gateway=ScriptedGateway())
    assert isinstance(coordinator.dispatcher, LocalDispatcher) and built == [1]
