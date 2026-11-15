"""Regressions for defects found by the independent review of the run composition (2026-11-15):
resume around the audit step, event-brief provenance, timeless facts, query validation, replay
theme goals, brief research, link notes and macro labels. Offline; the model is scripted."""

from __future__ import annotations

import uuid

import pytest
from aplomb.agents.workflow import execute_run
from aplomb.api.app import create_app
from aplomb.api.domain import SnapshotProvider, default_services
from aplomb.api.errors import ServiceError
from aplomb.api.repositories import ProfileRepository, RunRepository
from aplomb.api.runtime import RunPreparerImpl, build_agent_services
from aplomb.api.services import RunCoordinator
from aplomb.api.settings import Settings
from aplomb.api.storage import MemoryStore
from aplomb.contracts import models as m
from aplomb.contracts.catalog import FeatureFlag
from aplomb.contracts.registry import adapter
from aplomb.ledger.core import TIMELESS_METHODS, is_timeless
from aplomb.optimizer.services import build_domain_services
from aplomb.world import WorldServiceImpl, load_bundle
from aplomb.world import ingest as ing
from aplomb.world.dataset import WorldDataset
from fastapi.testclient import TestClient
from tests.integration._scripted import MODEL_ID, ScriptedGateway, default_draft
from tests.unit.datastore._support import STARTER_VERSION, starter_root

TSLA_25 = {"type": "move", "move": {"ticker": "TSLA", "sizePct": 25, "funding": {"mode": "pro_rata"}}}


class Crash(BaseException):
    """A worker death: not an Exception, so the workflow cannot record a failure."""


class Clock:
    def __init__(self):
        self.t = 1_794_000_000.0

    def __call__(self):
        return self.t


class CrashingGateway(ScriptedGateway):
    def __init__(self, crash_on=None, **kwargs):
        super().__init__(**kwargs)
        self.crash_on = crash_on

    def generate(self, role, schema, messages, tools, limits):
        if self.crash_on and (role, self.roles.count(role) + 1) == self.crash_on:
            self.crash_on = None
            limits.take("llm_calls")
            raise Crash(role)
        return super().generate(role, schema, messages, tools, limits)


class NoDispatch:
    def __init__(self):
        self.calls = []

    def dispatch(self, run_id, generation):
        self.calls.append((run_id, generation))


def config() -> Settings:
    features = {flag: flag != FeatureFlag.GUARDRAILS for flag in FeatureFlag}
    return Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()), features=features)


class Harness:
    """The real composition with a controllable clock and no background thread."""

    def __init__(self, gateway, dataset: WorldDataset | None = None):
        cfg = config()
        self.clock, store = Clock(), MemoryStore()
        snapshot = SnapshotProvider(cfg)
        self.runs = RunRepository(store, clock=self.clock)
        self.profiles, _ = build_domain_services(ProfileRepository(store), snapshot)
        bundle = dataset or load_bundle()
        self.world = WorldServiceImpl(self.profiles, snapshot, lambda: bundle)
        self.services = build_agent_services(cfg, self.runs, snapshot, self.world, gateway)
        self.services.clock = self.clock
        self.dispatcher = NoDispatch()
        preparer = RunPreparerImpl(self.profiles, snapshot, models_configured=True, world=self.world, clock=self.clock)
        self.coordinator = RunCoordinator(self.runs, self.dispatcher, preparer, clock=self.clock)
        self.session = "s_" + str(uuid.uuid4())

    def create(self, body: dict) -> str:
        self.coordinator.create(self.session, adapter("CreateRunRequest").validate_python(body), None)
        return self.dispatcher.calls[-1][0]

    def drive(self, run_id: str, attempts: int = 4) -> tuple[m.Run, int]:
        """Deliver the worker event until the run is terminal; a crash waits out the lease."""
        crashes = 0
        generation = self.dispatcher.calls[-1][1]
        for _ in range(attempts):
            try:
                execute_run(run_id, generation, self.services)
            except Crash:
                crashes += 1
            run = self.runs.get(self.session, run_id).run
            if run.status in ("succeeded", "failed", "cancelled"):
                return run, crashes
            self.clock.t += 31
        raise AssertionError(f"run still {run.status}")


def decision_body():
    return {"kind": "decision", "profileId": "robert", "lang": "en", "request": TSLA_25}


# 1. Resume around the audit step ----------------------------------------------------------------


@pytest.mark.parametrize("crash_on", [("auditor", 1), ("writer", 1), ("planner", 1)])
def test_a_worker_crash_during_a_model_call_resumes_without_repeating_finished_steps(crash_on):
    gateway = CrashingGateway(crash_on)
    harness = Harness(gateway)
    run, crashes = harness.drive(harness.create(decision_body()))
    assert crashes == 1 and run.status == "succeeded", run.error
    assert [s.type for s in run.steps] == ["plan", "quant", "risk_check", "write", "audit", "sign"]
    assert gateway.roles == ["planner", "writer", "auditor"]          # each role answered exactly once
    assert run.result.decision.brief.model == MODEL_ID   # recorded on the write step, also after a resume


def test_a_crash_while_persisting_the_audit_step_reruns_it_from_the_unfrozen_ledger():
    gateway = ScriptedGateway()
    harness = Harness(gateway)
    run_id = harness.create(decision_body())
    original = harness.runs.checkpoint
    state = {"armed": True}

    def checkpoint(rid, generation, owner, revision, run, private=None):
        done_audit = any(s.type == "audit" and s.status == "done" for s in run.steps)
        if state["armed"] and done_audit:
            state["armed"] = False
            raise Crash("checkpoint")
        return original(rid, generation, owner, revision, run, private)

    harness.runs.checkpoint = checkpoint
    run, crashes = harness.drive(run_id)
    assert crashes == 1 and run.status == "succeeded", run.error
    assert run.result.decision.brief.audit.status == "passed"
    # The auditor model reply is cached, so the retry does not call it again.
    assert gateway.roles == ["planner", "writer", "auditor"]


def test_a_completed_step_is_one_checkpoint_with_its_output():
    harness = Harness(ScriptedGateway())
    run_id = harness.create(decision_body())
    seen = []
    original = harness.runs.checkpoint

    def checkpoint(rid, generation, owner, revision, run, private=None):
        outputs = set((private or {}).get("agents", {}).get("step_outputs", {}))
        done = {f"{s.type}:{s.iteration}" for s in run.steps if s.status == "done"}
        seen.append((outputs, done))
        return original(rid, generation, owner, revision, run, private)

    harness.runs.checkpoint = checkpoint
    run, _ = harness.drive(run_id)
    assert run.status == "succeeded"
    assert all(outputs == done for outputs, done in seen)             # never an output without its done status


# 2. Event brief provenance and information cutoff ------------------------------------------------


def synthetic_dataset(*events) -> WorldDataset:
    real = load_bundle()
    built = [dict(e, importance=0.5, datasetId="world_events", dataVersion=real.version) for e in events]
    manifest = {**real.manifest, "events": {**real.manifest["events"], "count": len(built),
                                            "coverage": {"start": min(e["occurredAt"] for e in built),
                                                         "end": max(e["occurredAt"] for e in built)}}}
    return WorldDataset(real.version, real.built_at, tuple(built), (), manifest)


def official(title, url, occurred, countries=("CAN",), published=None, publisher="Bank of Canada"):
    event = ing._event(url=url, title=title, category="other", occurred=occurred, published=published,
                       location=ing._country_location(countries[0]), origin="official", publisher=publisher,
                       source_type="official")
    event["relatedCountries"] = list(countries)
    return event


def test_event_fact_uses_the_bundle_retrieval_time_when_the_source_states_no_publication_time():
    bundle = load_bundle()
    event = next(e for e in bundle.events if e["sources"][0]["publisher"] == "Statistics Canada")
    assert event["publishedAt"] is None
    harness = Harness(ScriptedGateway())
    run, _ = harness.drive(harness.create({"kind": "event_brief", "profileId": "robert", "lang": "en", "eventId": event["eventId"]}))
    assert run.status == "succeeded", run.error
    record = next(s for s in bundle.manifest["sources"] if s["id"] == "statcan_daily")
    fact = next(f for f in run.facts.values() if f.metric == "count.sources")
    assert fact.available_at == record["retrievedAt"]                 # not an invented end-of-day time
    assert fact.sources[0].retrieved_on == record["retrievedAt"][:10] and fact.sources[0].licence == record["terms"]
    assert fact.method.id == "M_OBSERVED_ROW" and fact.value == 1 and fact.verification.status == "verified"
    assert fact.method.params["publishedAtStated"] is False
    # The run's information cutoff is the day the events were retrieved, later than the price data.
    assert run.as_of == bundle.built_at[:10] > "2026-11-12"
    assert all(f.as_of == run.as_of for f in run.facts.values())


def test_a_measured_price_move_is_cited_without_being_struck_and_only_for_a_named_holding():
    event = official("Royal Bank of Canada announces a financing agreement", "https://example.org/rbc-financing", "2026-06-01")
    assert event["relatedTickers"] == ["RY.TO"]

    def writer(message):
        draft = default_draft(message)
        move = next(fid for fid, fact in message["facts"].items() if fact["method"]["id"] == "M_PRICE_MOVE_AFTER_EVENT")
        draft["sections"][0]["sentences"].append(
            {"id": "S-MOVE", "template": f"The observed price change of the named holding after the event was {{{{fact:{move}}}}}."})
        return draft

    harness = Harness(ScriptedGateway(writer=writer), synthetic_dataset(event))
    run, _ = harness.drive(harness.create({"kind": "event_brief", "profileId": "robert", "lang": "en", "eventId": event["eventId"]}))
    assert run.status == "succeeded", run.error
    result = run.result.event_brief
    by_ticker = {x.ticker: x for x in result.exposures}
    assert by_ticker["RY.TO"].link_type == "named_in_source" and by_ticker["RY.TO"].impact == "measured_price_move"
    move = run.facts[by_ticker["RY.TO"].impact_fact_id]
    assert move.method.id == "M_PRICE_MOVE_AFTER_EVENT" and "LIM_PRICE_MOVE_NOT_CAUSAL" in move.limitations
    assert all(x.impact == "not_established" for t, x in by_ticker.items() if t != "RY.TO")
    assert "observation" in result.impact_statement.en
    sentence = next(s for section in result.brief.sections for s in section.sentences if s.id == "S-MOVE")
    assert sentence.audit.status == "verified", sentence.audit


def test_listing_country_note_names_the_holdings_own_country():
    event = official("Joint statement on cross-border payments", "https://example.org/joint", "2026-06-01", countries=("USA", "CAN"))
    harness = Harness(ScriptedGateway(), synthetic_dataset(event))
    detail = harness.world.event(harness.session, event["eventId"], {"profileId": "robert"}).to_wire()
    notes = {x["ticker"]: x["note"]["en"] for x in detail["exposures"] if x["linkType"] == "listing_country"}
    assert "in Canada" in notes["XIU.TO"] and "in United States" in notes["SPY"]


# 3. Timeless facts and leakage hardening ---------------------------------------------------------


def replay_run(as_of="2023-06-30", request=TSLA_25):
    harness = Harness(ScriptedGateway())
    run, _ = harness.drive(harness.create({"kind": "replay", "profileId": "robert", "lang": "en", "request": request, "asOf": as_of}))
    return harness, run


def test_dataset_derived_figures_of_a_replay_state_their_availability():
    _, run = replay_run()
    assert run.status == "succeeded", run.error
    facts = {k: v for k, v in run.facts.items()}
    timeless = [f for f in facts.values() if f.available_at is None]
    assert timeless and all(is_timeless(f, facts) for f in timeless)
    for fact in timeless:                                             # only stipulated values and arithmetic on them
        assert fact.kind in ("input", "assumption") or fact.method.id in TIMELESS_METHODS, fact.key
        assert not fact.sources
    boundary = next(f for f in facts.values() if f.metric == "size.max_compatible")
    assert boundary.sources and boundary.available_at and boundary.available_at[:10] <= "2023-06-30"
    grouped = [f for f in facts.values() if f.metric in ("weight.sector.max", "weight.growth_assets", "weight.position.max_single")]
    assert grouped and all(f.sources[0].dataset_id == "assets_universe" and f.available_at for f in grouped)
    assert all(f.available_at is None or f.available_at[:10] <= "2023-06-30" for f in facts.values())


def test_a_derived_fact_with_an_unlisted_method_is_never_timeless():
    _, run = replay_run()
    facts = dict(run.facts)
    weight = next(f for f in facts.values() if f.metric == "concentration.hhi")
    assert is_timeless(weight, facts)
    forged = weight.model_copy(update={"method": weight.method.model_copy(update={"id": "M_VOL_STDEV_252"})})
    assert not is_timeless(forged, facts)


def test_replay_refuses_thresholds_that_were_not_derived_at_its_cutoff():
    harness = Harness(ScriptedGateway())
    run_id = harness.create({"kind": "replay", "profileId": "robert", "lang": "en", "request": TSLA_25, "asOf": "2023-06-30"})
    record = harness.runs.get(harness.session, run_id)
    rules = record.private["profile"]["rules"]
    derived = [r for r in rules if r["origin"] == "derived"]
    assert derived and all(r["derivation"]["inputs"]["asOf"] == "2023-06-30" for r in derived)
    # A run whose pinned profile carries a threshold derived from other data cannot open its gate.
    tampered = {**record.private, "profile": {**record.private["profile"], "rules": [
        {**r, "derivation": {**r["derivation"], "inputs": {**r["derivation"]["inputs"], "asOf": "2026-11-12"}}}
        if r["origin"] == "derived" else r for r in rules]}}
    with pytest.raises(RuntimeError, match="not derived at the replay cutoff"):
        harness.services.gate_factory(tampered)


def test_replay_theme_goal_is_refused_at_creation_with_the_reason():
    harness = Harness(ScriptedGateway())
    goal = {"type": "goal", "goal": {"themes": ["ai"], "assetClasses": [], "tickers": [], "targetExposurePct": None,
                                     "maxLossPct": None, "maxVolPct": None, "notes": ""}}
    with pytest.raises(ServiceError) as exc:
        harness.create({"kind": "replay", "profileId": "amira", "lang": "en", "request": goal, "asOf": "2023-06-30"})
    assert exc.value.code == "validation_error" and exc.value.details["themesVisibleAtAsOf"] is False
    assert harness.dispatcher.calls == []                             # no run stored, no model call spent


def test_theme_weight_is_not_enough_evidence_when_no_tag_is_visible():
    from aplomb.quant import LocalLedger, QuantEngine
    from tests.unit.datastore._support import starter_snapshot

    snap = starter_snapshot()
    past = QuantEngine(snap.gate("2023-06-30", "historical"), LocalLedger(), currency="CAD", subject_id="p", created_at="2026-11-14T00:00:00Z")
    measured = past.view({"NVDA": 0.5, "XBB.TO": 0.5}, "before", 1000.0).measure("weight.theme", "ai")
    assert (measured.value, measured.nee_reason) == (None, "not_visible_at_asof")
    now = QuantEngine(snap.gate("2026-11-12", "current"), LocalLedger(), currency="CAD", subject_id="p", created_at="2026-11-14T00:00:00Z")
    assert now.view({"NVDA": 0.5, "XBB.TO": 0.5}, "before", 1000.0).measure("weight.theme", "ai").value == pytest.approx(50.0)


# 4. Portfolio brief plans no research -------------------------------------------------------------


def test_portfolio_brief_ignores_research_questions_from_the_planner():
    plan = {"interpretation": "Brief", "research_questions": [
        {"id": "q1", "subject": "TSLA", "question": "Any controversy?", "preferred_tools": ["web.fetch"]}]}
    gateway = ScriptedGateway(plan=plan)
    harness = Harness(gateway)
    run, _ = harness.drive(harness.create({"kind": "portfolio_brief", "profileId": "robert", "lang": "en"}))
    assert run.status == "succeeded", run.error
    assert [s.type for s in run.steps] == ["plan", "quant", "risk_check", "write", "audit", "sign"]
    assert "researcher" not in gateway.roles
    plan_fit = run.result.portfolio_brief.focus_cards[2]
    assert all(seg.display in ("in conflict", "in tension", "not enough evidence")
               for sentence in plan_fit.body for seg in sentence.segments if seg.t == "status")


# 5. Query validation over HTTP ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    cfg = config()
    return TestClient(create_app(cfg, default_services(cfg)))


def test_a_dateline_crossing_box_is_accepted_and_week_dates_are_rejected(client):
    headers = {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}
    span = {"from": "2025-11-13", "to": "2026-11-12", "limit": 1000}
    crossing = client.get("/v1/world/events", params={**span, "bbox": "170,-60,-170,60"}, headers=headers)
    assert crossing.status_code == 200, crossing.text
    items = crossing.json()["items"]
    assert items and all(e["location"]["lon"] >= 170 or e["location"]["lon"] <= -170 for e in items)
    assert client.get("/v1/world/hazards", params={"bbox": "170,-60,-170,60"}, headers=headers).status_code == 200
    for bad in ("0,0,200,10", "0,50,10,-50", "0,0,nan,10", "1,2,3"):
        assert client.get("/v1/world/events", params={"bbox": bad}, headers=headers).status_code == 422, bad
    for bad in ("2026-W01-1", "20261112", "2026-1-01", "2026-13-01"):
        assert client.get("/v1/world/events", params={"from": bad}, headers=headers).status_code == 422, bad


def test_macro_facts_are_labelled_in_both_languages_and_an_index_is_not_a_ratio(client):
    headers = {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}
    usa = client.get("/v1/world/countries/USA", headers=headers).json()["macro"]
    cpi = next(f for f in usa if f["subject"]["id"] == "CPIAUCSL")
    assert cpi["unit"] == "text" and isinstance(cpi["value"], str) and "1982-84" in cpi["label"]["en"]
    assert all(f["label"]["fr"] != f["label"]["en"] for f in usa)
    canada = client.get("/v1/world/countries/CAN", headers=headers).json()["macro"]
    assert all(f["label"]["fr"] != f["label"]["en"] and f["unit"] == "pct" for f in canada)
