"""Regressions for the run workflow audit findings (2026-11-15): clarification answers, planner
proposals outside the catalog, typed failures, refusal at creation, parser outage and a worker
crash during batched fact writes. Offline; the model is scripted."""

from __future__ import annotations

import time
import uuid

import pytest
from aplomb.agents.workflow import apply_answer, failure_of
from aplomb.api.app import create_app
from aplomb.api.domain import default_services
from aplomb.api.errors import ServiceError
from aplomb.api.settings import Settings
from aplomb.contracts import models as m
from aplomb.contracts.catalog import FeatureFlag
from fastapi.testclient import TestClient
from tests.integration._scripted import ScriptedGateway
from tests.integration.test_review_regressions import Crash, Harness
from tests.unit.datastore._support import STARTER_VERSION, starter_root

TSLA_25 = {"type": "move", "move": {"ticker": "TSLA", "sizePct": 25, "funding": {"mode": "pro_rata"}}}
DECISION = {"kind": "decision", "profileId": "robert", "lang": "en", "request": TSLA_25}
QUESTION = {"questionId": "q_size", "text": {"en": "Which size?", "fr": "Quelle taille ?"}, "field": "move.sizePct",
            "options": [{"value": "5", "label": {"en": "5", "fr": "5"}}, {"value": "25", "label": {"en": "25", "fr": "25"}}]}


def client(gateway) -> TestClient:
    features = {flag: flag != FeatureFlag.GUARDRAILS for flag in FeatureFlag}
    cfg = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()), features=features)
    return TestClient(create_app(cfg, default_services(cfg, gateway=gateway)), raise_server_exceptions=False)


def session() -> dict:
    return {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}


def wait(c, headers, run_id, until=("succeeded", "failed", "cancelled", "waiting_input")):
    for _ in range(600):
        run = c.get(f"/v1/runs/{run_id}", headers=headers).json()
        if run["status"] in until:
            return run
        time.sleep(0.05)
    raise AssertionError("run did not settle")


def test_a_clarification_answer_changes_the_simulated_size():
    c, headers = client(ScriptedGateway(plan={"interpretation": "Size unclear", "clarification": QUESTION})), session()
    run_id = c.post("/v1/runs", json=DECISION, headers=headers).json()["runId"]
    assert wait(c, headers, run_id)["status"] == "waiting_input"
    assert c.post(f"/v1/runs/{run_id}/answers", json={"questionId": "q_size", "value": "5"}, headers=headers).status_code == 202
    run = wait(c, headers, run_id, until=("succeeded", "failed"))
    assert run["status"] == "succeeded", run["error"]
    decision = run["result"]["decision"]
    assert decision["request"]["move"]["sizePct"] == 5
    assert decision["scenarios"][0]["moves"][0]["sizePct"] == 5
    assert run["input"]["request"] == TSLA_25                          # the confirmed input itself is never rewritten
    assert any(f["metric"] == "size.requested" and f["value"] == 5 for f in run["facts"].values())


def test_a_revise_iteration_keeps_the_answered_request():
    # Audit 2026-11-15: the revise loop re-ran the controls with the original 25-point request,
    # which collided with the facts the answered 5-point request had already registered.
    plan = {"interpretation": "Size unclear", "clarification": QUESTION, "revise": True,
            "scenario_tasks": [{"kind": "alternative", "ticker": "NVDA"}]}
    gateway = ScriptedGateway(plan=plan)
    c, headers = client(gateway), session()
    run_id = c.post("/v1/runs", json=DECISION, headers=headers).json()["runId"]
    assert wait(c, headers, run_id)["status"] == "waiting_input"
    assert c.post(f"/v1/runs/{run_id}/answers", json={"questionId": "q_size", "value": "5"}, headers=headers).status_code == 202
    run = wait(c, headers, run_id, until=("succeeded", "failed"))
    assert run["status"] == "succeeded", run["error"]
    requested = next(s for s in run["result"]["decision"]["scenarios"] if s["scenarioId"] == "sc_requested")
    assert requested["moves"][0]["sizePct"] == 5
    # Review 2026-11-15: the controls ignore the planner's scenarios, so a second revision would see
    # the same checks; the loop stops after one real planner call instead of paying for another.
    revisions = [s for s in run["steps"] if s["type"] == "revise"]
    assert len(revisions) == 1 and revisions[0]["model"]
    assert gateway.roles.count("planner") == 2
    revise_prompts = [p for role, p in gateway.prompts if role == "planner"][1:]
    assert all("iteration" not in p for p in revise_prompts)
    assert all(p["request"]["move"]["sizePct"] == 5 for p in revise_prompts)


def test_a_question_whose_answer_cannot_be_applied_is_not_asked():
    # Audit 2026-11-15: an answer about anything but a move's size or funding was accepted and ignored.
    question = {**QUESTION, "questionId": "q_goal", "field": "objective", "options": None}
    gateway = ScriptedGateway(plan={"interpretation": "Objective unclear", "clarification": question})
    c, headers = client(gateway), session()
    run = wait(c, headers, c.post("/v1/runs", json=DECISION, headers=headers).json()["runId"], until=("succeeded", "failed"))
    assert run["status"] == "succeeded", run["error"]
    assert run["question"] is None
    assert run["steps"][0]["summary"]["en"].startswith("Planned ")
    writer = next(p for role, p in gateway.prompts if role == "writer")
    assert any("objective" in note for note in writer["execution_limitations"])


def test_answer_parsing():
    request = m.MoveRequest.model_validate(TSLA_25) if hasattr(m, "MoveRequest") else None
    if request is None:
        from aplomb.contracts.registry import adapter

        request = adapter("DecisionRequest").validate_python(TSLA_25)
    question = m.ClarifyingQuestion.model_validate(QUESTION)
    assert apply_answer(request, question, {"questionId": "q_size", "value": "7,5 %"}).move.size_pct == 7.5
    assert apply_answer(request, question, {"questionId": "other", "value": "7"}) is None
    with pytest.raises(ServiceError):
        apply_answer(request, question, {"questionId": "q_size", "value": "a lot"})
    funding = m.ClarifyingQuestion.model_validate({**QUESTION, "field": "move.funding.mode"})
    assert apply_answer(request, funding, {"questionId": "q_size", "value": "new_money"}).move.funding.mode == "new_money"
    assert apply_answer(request, funding, {"questionId": "q_size", "value": "Cash"}).move.funding.mode == "from_cash"
    with pytest.raises(ServiceError):
        apply_answer(request, funding, {"questionId": "q_size", "value": "borrowed"})
    other = m.ClarifyingQuestion.model_validate({**QUESTION, "field": "preferences.notes"})
    assert apply_answer(request, other, {"questionId": "q_size", "value": "x"}) is None


def test_planner_proposals_outside_the_catalog_are_dropped_and_disclosed():
    # Tool names are an enumeration in the plan schema, so an unknown tool is a schema failure the
    # gateway repairs; a ticker outside the universe is schema-valid and must be dropped here.
    plan = {"interpretation": "x", "scenario_tasks": [{"kind": "alternative", "ticker": "ZZZZ"}]}
    gateway = ScriptedGateway(plan=plan)
    c, headers = client(gateway), session()
    run = wait(c, headers, c.post("/v1/runs", json=DECISION, headers=headers).json()["runId"], until=("succeeded", "failed"))
    assert run["status"] == "succeeded", run["error"]
    writer = next(p for role, p in gateway.prompts if role == "writer")
    notes = " ".join(writer["execution_limitations"])
    assert "ZZZZ" in notes
    planner = next(p for role, p in gateway.prompts if role == "planner")
    assert "quant.portfolio_metrics" in planner["allowed_computation_tools"] and "TSLA" in planner["universe_tickers"]


def test_failed_runs_carry_a_catalog_code_and_a_fixed_message():
    c, headers = client(ScriptedGateway(fail_role="writer")), session()
    run = wait(c, headers, c.post("/v1/runs", json=DECISION, headers=headers).json()["runId"], until=("succeeded", "failed"))
    assert run["status"] == "failed"
    assert run["error"]["code"] == "upstream_unavailable"
    assert "scripted failure" not in run["error"]["message"] and "is unavailable" not in run["error"]["message"]

    class AccessDenied(Exception):
        __module__ = "botocore.exceptions"

    code, message = failure_of(AccessDenied("arn:aws:sts::123456789012:assumed-role/x/y is not authorized"))
    assert code == "upstream_unavailable" and "123456789012" not in message
    assert failure_of(ServiceError("insufficient_data", "TSLA has no price on 2021-01-04")) == (
        "insufficient_data", "TSLA has no price on 2021-01-04")


@pytest.mark.parametrize("body", [
    {**DECISION, "request": {"type": "move", "move": {"ticker": "TSLA", "sizePct": 100.5, "funding": {"mode": "pro_rata"}}}},
    {**DECISION, "request": {"type": "move", "move": {"ticker": "TSLA", "sizePct": 25, "funding": {"mode": "from_cash"}}}},
    {"kind": "replay", "profileId": "robert", "lang": "en", "request": TSLA_25, "asOf": "2025-02-19", "window": {"code": "5y"}},
])
def test_what_check_refuses_is_refused_at_run_creation(body):
    c, headers = client(ScriptedGateway()), session()
    response = c.post("/v1/runs", json=body, headers=headers)
    assert response.status_code == 422 and response.json()["error"]["code"] == "validation_error", response.text
    assert c.get("/v1/runs", headers=headers).json()["items"] == []


def test_parser_outage_is_503():
    class Broken(ScriptedGateway):
        def generate(self, *args, **kwargs):
            raise ValueError("model returned invalid JSON twice")

    response = client(Broken()).post("/v1/requests/parse", json={"profileId": "robert", "text": "25% into Tesla", "lang": "en"},
                                     headers=session())
    assert response.status_code == 503 and response.json()["error"]["code"] == "upstream_unavailable"


def test_a_crash_between_batched_fact_writes_resumes_to_the_same_facts():
    harness = Harness(ScriptedGateway())
    run_id = harness.create(DECISION)
    original = harness.runs.checkpoint
    state = {"batches": 0, "armed": True}

    def checkpoint(rid, generation, owner, revision, run, private=None):
        steps = run.steps
        mid_step = steps and steps[-1].status == "running" and len(run.facts) > 40
        if state["armed"] and mid_step:
            state["batches"] += 1
            if state["batches"] == 2:           # after the first batch of a large step is stored
                state["armed"] = False
                raise Crash("between batches")
        return original(rid, generation, owner, revision, run, private)

    harness.runs.checkpoint = checkpoint
    run, crashes = harness.drive(run_id)
    assert crashes == 1 and run.status == "succeeded", run.error
    assert all(f.verification.status == "verified" for f in run.facts.values())
    assert [s.type for s in run.steps] == ["plan", "quant", "risk_check", "write", "audit", "sign"]


def test_ledger_display_keeps_the_precision_of_the_unit():
    from aplomb.ledger.core import format_value

    assert format_value(0.25, "pct").en == "0.25%" and format_value(0.25, "pct").fr == "0,25 %"
    assert format_value(16.9567, "pct").en == "16.96%"
    assert format_value(1, "count").en == "1 count" and format_value(600000.4, "cad").en == "600,000 CAD"
    assert format_value(6.0, "pts").en == "6.0 pts"


def test_event_brief_without_a_linked_holding_says_so():
    c, headers = client(ScriptedGateway()), session()
    events = c.get("/v1/world/events", params={"origin": "usgs", "limit": 200, "from": "2026-01-01", "to": "2026-11-12"},
                   headers=headers).json()["items"]
    event = next(e for e in events if not e["relatedCountries"])
    run_id = c.post("/v1/runs", json={"kind": "event_brief", "profileId": "robert", "lang": "en", "eventId": event["eventId"]},
                    headers=headers).json()["runId"]
    run = wait(c, headers, run_id, until=("succeeded", "failed"))
    assert run["status"] == "succeeded", run["error"]
    result = run["result"]["eventBrief"]
    assert result["exposures"] == []
    assert result["impactStatement"]["en"].startswith("No holding of this portfolio is linked")


def test_verified_run_evidence_reaches_the_controversy_rule():
    from aplomb.ledger import DocumentRef, Ledger
    from aplomb.optimizer.services import DecisionControls

    harness = Harness(ScriptedGateway())
    profile = harness.profiles.get(harness.session, "mateo")
    snap = harness.world.snapshot()
    ledger = Ledger("run_EVIDENCE", "2026-11-12", clock=lambda: "2026-11-14T00:00:00Z")
    text = "Canadian Natural Resources faces a regulatory investigation into tailings releases."
    ledger.register_document(DocumentRef("doc-1", text, "https://www.sec.gov/example", "run_EVIDENCE"))
    ledger.add_evidence({"type": "filing", "tier": 1, "title": "Filing", "publisher": "SEC", "url": "https://www.sec.gov/example",
                         "publishedAt": "2026-01-05", "retrievedAt": "2026-11-14T00:00:00Z", "lang": "en",
                         "quote": "faces a regulatory investigation into tailings releases", "claim": {"en": "Controversy", "fr": "Controverse"},
                         "subject": {"type": "asset", "id": "CNQ.TO"}, "tool": "research.save_evidence", "documentRef": "doc-1",
                         "licence": "public domain (US gov)"})

    class Ctx:
        pass

    ctx = Ctx()
    ctx.gate, ctx.ledger, ctx.profile, ctx.as_of = snap.gate("2026-11-12", "current"), ledger, profile, "2026-11-12"
    move = {"type": "move", "move": {"ticker": "CNQ.TO", "sizePct": 10, "funding": {"mode": "pro_rata"}}}
    controls = DecisionControls()
    outcome = controls.risk(ctx, controls.quant(ctx, move, {"code": "full"}, [], []))
    rule = next(c for c in outcome.check.rule_checks if c.rule_id == "evidence.controversy")
    assert ledger.export().evidence["E-001"].verification.status == "verified"
    assert rule.status == "tension" and rule.evidence_ids == ["E-001"]


def test_verified_run_evidence_reaches_every_scenario_of_the_run():
    # Audit 2026-11-15: only sc_requested saw the run's evidence; the largest-size scenario and the
    # alternatives built in the same run reported "not enough evidence" for the same sources.
    from aplomb.ledger import DocumentRef, Ledger
    from aplomb.optimizer.services import DecisionControls

    harness = Harness(ScriptedGateway())
    mateo = harness.profiles.get(harness.session, "mateo")
    rules = [r.model_copy(update={"enabled": False}) if r.rule_id == "exclude.sector.energy" else r for r in mateo.rules]
    profile = mateo.model_copy(update={"rules": rules})
    ledger = Ledger("run_EVIDENCE", "2026-11-12", clock=lambda: "2026-11-14T00:00:00Z")
    for n, (ticker, name) in enumerate([("CNQ.TO", "Canadian Natural Resources"), ("XOM", "Exxon Mobil")], 1):
        url = f"https://www.sec.gov/example-{n}"
        ledger.register_document(DocumentRef(f"doc-{n}", f"{name} faces a regulatory investigation into tailings releases.",
                                             url, "run_EVIDENCE"))
        ledger.add_evidence({"type": "filing", "tier": 1, "title": "Filing", "publisher": "SEC", "url": url,
                             "publishedAt": "2026-01-05", "retrievedAt": "2026-11-14T00:00:00Z", "lang": "en",
                             "quote": "faces a regulatory investigation into tailings releases",
                             "claim": {"en": "Controversy", "fr": "Controverse"}, "subject": {"type": "asset", "id": ticker},
                             "tool": "research.save_evidence", "documentRef": f"doc-{n}", "licence": "public domain (US gov)"})

    class Ctx:
        pass

    ctx = Ctx()
    ctx.gate, ctx.ledger, ctx.profile, ctx.as_of = harness.world.snapshot().gate("2026-11-12", "current"), ledger, profile, "2026-11-12"
    move = {"type": "move", "move": {"ticker": "CNQ.TO", "sizePct": 20, "funding": {"mode": "pro_rata"}}}
    controls = DecisionControls()
    outcome = controls.risk(ctx, controls.quant(ctx, move, {"code": "full"}, [], []))

    def status(scenario_id):
        scenario = next(s for s in outcome.scenarios if s.scenario_id == scenario_id)
        return next((c.status, c.evidence_ids) for c in scenario.rule_checks if c.rule_id == "evidence.controversy")

    assert status("sc_requested") == ("tension", ["E-001"])
    assert status("sc_max_compatible") == ("tension", ["E-001"])
    assert status("sc_alt_xom") == ("tension", ["E-002"])
