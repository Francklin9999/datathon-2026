"""Offline, explicitly synthetic providers; never used by runtime composition."""

import json
import time
from pathlib import Path

import pytest
from aplomb.agents import AgentServices, Generation, ToolContext, ToolRegistry, execute_run
from aplomb.agents.limits import BudgetExceeded, Limits
from aplomb.agents.models import AnalysisPlan
from aplomb.agents.worker import make_handler
from aplomb.api.repositories import RunRepository, timestamp
from aplomb.api.storage import MemoryStore
from aplomb.contracts import models as m
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).parents[3]


class FakeGateway:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.roles = []

    def generate(self, role, schema, messages, tools, limits):
        limits.take("llm_calls")
        self.roles.append(role)
        assert not tools
        return Generation(schema.model_validate(next(self.outputs)), "test-only-model", 11, 7)


def queued(kind="profile_draft"):
    payload = json.loads((ROOT / "contracts/fixtures/run.decision.robert-tsla-25.json").read_text())
    payload.update(
        kind=kind,
        createdAt=timestamp(time.time()),
        updatedAt=timestamp(time.time()),
        status="queued",
        steps=[],
        facts={},
        evidence={},
        result=None,
        error=None,
        question=None,
    )
    if kind == "profile_draft":
        payload.update(
            profileId=None, input={"kind": kind, "text": "I work as a teacher.", "fields": {}}
        )
    return m.Run.model_validate(payload)


def repository(run, private=None):
    repo = RunRepository(MemoryStore())
    record, _ = repo.create(run, private or {}, None, None, {})
    return repo, record


def test_profile_draft_real_lifecycle_and_duplicate_dispatch():
    repo, rec = repository(queued())
    gateway = FakeGateway(
        [
            {
                "profile": {"occupation": "teacher"},
                "explanations": [],
                "unresolved": [
                    {"field": "riskLevel", "question": {"en": "Risk?", "fr": "Risque?"}}
                ],
            }
        ]
    )
    services = AgentServices(repo, gateway)
    execute_run(rec.run.run_id, rec.generation, services)
    run = repo.get(rec.run.session_id, rec.run.run_id).run
    assert run.status == "succeeded", run.error
    assert run.status == "succeeded", run.error
    assert run.result.draft.profile.to_wire() == {"occupation": "teacher"}
    assert run.usage.llm_calls == 1
    assert run.usage.input_tokens == 11
    assert [s.type for s in run.steps] == ["plan", "audit", "sign"]
    assert run.steps[0].model == "test-only-model"
    execute_run(rec.run.run_id, rec.generation, services)
    assert len(gateway.roles) == 1


def test_missing_controls_honest_failure_without_pretend_steps():
    repo, rec = repository(queued("decision"))
    execute_run(rec.run.run_id, rec.generation, AgentServices(repo, FakeGateway([])))
    run = repo.get(rec.run.session_id, rec.run.run_id).run
    assert run.status == "failed"
    assert "controls" in run.error.message
    assert run.steps == []


def test_cancel_during_model_cannot_finish_or_overwrite():
    repo, rec = repository(queued())

    class CancellingGateway(FakeGateway):
        def generate(self, *args):
            repo.cancel(rec.run.session_id, rec.run.run_id)
            return super().generate(*args)

    gateway = CancellingGateway([{"profile": {}, "explanations": [], "unresolved": []}])
    execute_run(rec.run.run_id, rec.generation, AgentServices(repo, gateway))
    assert repo.get(rec.run.session_id, rec.run.run_id).run.status == "cancelled"


def test_registry_role_validation_and_temporal_gates():
    class Args(BaseModel):
        model_config = ConfigDict(extra="forbid")
        query: str

    calls = []
    registry = ToolRegistry()
    registry.register("web.fetch", Args, lambda *a, **k: calls.append(k))
    ctx = ToolContext("test", None, "en", "2025-01-01", object(), None, None, Limits(), None)
    assert not registry.execute("writer", "web.fetch", {"query": "x"}, ctx).ok
    assert not registry.execute("researcher", "web.fetch", {"query": "x", "shell": "rm"}, ctx).ok
    ctx.historical = True
    assert not registry.execute("researcher", "web.fetch", {"query": "x"}, ctx).ok
    assert calls == []


def test_budget_caps_and_worker_validation():
    limits = Limits()
    for _ in range(12):
        limits.take("llm_calls")
    with pytest.raises(BudgetExceeded):
        limits.take("llm_calls")
    repo, _ = repository(queued())
    handler = make_handler(AgentServices(repo, FakeGateway([])))
    with pytest.raises(ValueError):
        handler({"runId": "x", "generation": True})


def test_waiting_resume_does_not_repeat_planner():
    run = queued("decision")
    profile = json.loads((ROOT / "contracts/fixtures/profiles.json").read_text())["items"][0]
    repo, rec = repository(run, {"profile": profile})
    plan = AnalysisPlan(
        interpretation="Confirm funding",
        clarification=m.ClarifyingQuestion(
            question_id="funding",
            text={"en": "Funding?", "fr": "Financement?"},
            field="funding",
            options=None,
        ),
    )
    gateway = FakeGateway([plan.model_dump()])

    class StopControls:
        def quant(self, *args):
            raise RuntimeError("Stopped at actual mandatory code call")

    from aplomb.ledger import Ledger

    services = AgentServices(
        repo,
        gateway,
        controls=StopControls(),
        ledger_factory=Ledger,
        signer=lambda **kwargs: None,
        gate_factory=lambda private: object(),
    )
    execute_run(run.run_id, rec.generation, services)
    waiting = repo.get(run.session_id, run.run_id).run
    assert waiting.status == "waiting_input", waiting.error
    rec = repo.answer(run.session_id, run.run_id, "funding", "cash")
    execute_run(run.run_id, rec.generation, services)
    done = repo.get(run.session_id, run.run_id).run
    assert done.status == "failed"
    assert gateway.roles == ["planner"]
    assert [s.type for s in done.steps] == ["plan", "quant"]


def test_fake_decision_revision_mandatory_controls_and_real_audit():
    """Schema fixtures describe synthetic controls only; all review/sign steps execute."""
    from aplomb.agents import ControlOutcome
    from aplomb.agents.signing import sign_decision
    from aplomb.ledger import Ledger

    def draft():
        return {
            "sections": [
                {
                    "id": name,
                    "title": {"en": name, "fr": name},
                    "sentences": [{"id": f"sentence-{name}", "template": text}],
                }
                for name, text in [
                    ("facts", "Synthetic value {{fact:F-001}}."),
                    ("assumptions", "Threshold is assumed."),
                    ("limits", "Simulation remains limited."),
                ]
            ]
        }

    def fact(**extra):
        return {
            "kind": "assumption",
            "metric": "vol.annualized",
            "label": {"en": "Risk", "fr": "Risque"},
            "value": 12.0,
            "unit": "pct",
            "currency": None,
            "subject": {"type": "portfolio", "id": "robert", "variant": "before"},
            "period": None,
            "window": {"code": "full"},
            "asOf": run.as_of,
            "availableAt": None,
            "method": {
                "id": "M_PROFILE_ASSUMPTION",
                "description": {"en": "Synthetic test threshold", "fr": "Seuil test"},
                "params": {},
            },
            "inputs": [],
            "nObs": None,
            "sources": [],
            "limitations": ["LIM_THRESHOLDS_ASSUMED"],
            "createdBy": "user",
            **extra,
        }

    run = queued("decision")
    raw = json.loads((ROOT / "contracts/fixtures/run.decision.robert-tsla-25.json").read_text())
    result = raw["result"]["decision"]
    profile = json.loads((ROOT / "contracts/fixtures/profiles.json").read_text())["items"][0]
    repo, rec = repository(run, {"profile": profile})
    calls = []

    class SyntheticControls:
        def quant(self, ctx, request, window, tasks, scenarios):
            calls.append("quant")
            if not ctx.ledger.export().facts:
                ctx.ledger.add_fact(fact(asOf=run.as_of))
            return {"synthetic": True}

        def risk(self, ctx, computed):
            calls.append("risk")
            assert computed == {"synthetic": True}
            counts = {"pass": 0, "tension": 0, "conflict": 0, "nee": 0, "info": 0}
            scenario = dict(result["scenarios"][0])
            scenario.update(
                ruleChecks=[], counts=counts, verdict="compatible", keyFactIds=["F-001"]
            )
            check = m.CheckResult.model_validate(
                {
                    "verdict": "compatible",
                    "counts": counts,
                    "ruleChecks": [],
                    "portfolioBefore": result["portfolioBefore"],
                    "portfolioAfter": scenario["portfolioAfter"],
                    "fundingUsed": scenario["moves"][0]["funding"],
                    "fundingOptions": [],
                    "maxCompatibleSizePct": 5.0,
                    "baselineConflict": False,
                    "facts": {k: v.to_wire() for k, v in ctx.ledger.export().facts.items()},
                    "asOf": run.as_of,
                    "dataVersion": run.data_version,
                    "window": {"code": "full"},
                    "computeMs": 1.0,
                }
            )
            return ControlOutcome(
                check, [m.Scenario.model_validate(scenario)], scenario["scenarioId"]
            )

    first = AnalysisPlan(interpretation="Synthetic initial", revise=True)
    revision = AnalysisPlan(
        interpretation="Synthetic revised",
        scenario_tasks=[{"kind": "alternative", "ticker": "TSLA", "funding": None}],
        revise=False,
    )
    gateway = FakeGateway(
        [first.model_dump(), revision.model_dump(), draft(), {"findings": [], "relations": []}]
    )
    services = AgentServices(
        repo,
        gateway,
        controls=SyntheticControls(),
        ledger_factory=Ledger,
        signer=sign_decision,
        gate_factory=lambda private: object(),
    )
    execute_run(run.run_id, rec.generation, services)
    stored = repo.get(run.session_id, run.run_id).run
    assert stored.status == "succeeded", stored.error
    assert calls == ["quant", "risk", "quant", "risk"]
    assert gateway.roles == ["planner", "planner", "writer", "auditor"]
    assert stored.result.decision.brief.audit.status == "passed"
    assert stored.result.decision.brief.audit.guardrail.applied is False
    assert stored.steps[1].fact_ids == ["F-001"]
    assert stored.usage.llm_calls == 4
    assert [s.type for s in stored.steps] == [
        "plan",
        "quant",
        "risk_check",
        "revise",
        "quant",
        "risk_check",
        "write",
        "audit",
        "sign",
    ]


def test_strands_gateway_constructor_usage_and_bounded_repair(monkeypatch):
    from types import SimpleNamespace

    import strands
    import strands.models
    from aplomb.agents import StrandsBedrockGateway

    captured = []
    replies = iter(["not JSON", '{"profile":{},"explanations":[],"unresolved":[]}'])

    def model(**kwargs):
        captured.append(kwargs)
        assert "temperature" not in kwargs
        assert kwargs["streaming"] is False
        assert kwargs["boto_client_config"].retries == {"total_max_attempts": 1}
        return object()

    class Agent:
        def __init__(self, **kwargs):
            assert kwargs["tools"] == []
            assert kwargs["retry_strategy"] is None

        def __call__(self, prompt, limits):
            assert limits == {"turns": 1}
            return SimpleNamespace(
                metrics=SimpleNamespace(accumulated_usage={"inputTokens": 5, "outputTokens": 9}),
                message={"content": [{"text": next(replies)}]},
            )

    monkeypatch.setattr(strands.models, "BedrockModel", model)
    monkeypatch.setattr(strands, "Agent", Agent)
    limits = Limits()
    result = StrandsBedrockGateway(
        strong_model="actual-strong-id", fast_model="actual-fast-id"
    ).generate("profile_draft", m.ProfileDraftResult, [{"text": "teacher"}], [], limits)
    assert result.model_id == "actual-fast-id"
    assert (result.calls, limits.llm_calls, result.input_tokens, result.output_tokens) == (
        2,
        2,
        10,
        18,
    )
    assert len(captured) == 2


def test_draft_drops_unsupported_risk_and_thresholds():
    repo, rec = repository(queued())
    gateway = FakeGateway(
        [
            {
                "profile": {
                    "occupation": "teacher",
                    "riskLevel": "high",
                    "horizonYears": {"min": 20, "max": 20},
                },
                "explanations": [],
                "unresolved": [],
            }
        ]
    )
    execute_run(rec.run.run_id, rec.generation, AgentServices(repo, gateway))
    run = repo.get(rec.run.session_id, rec.run.run_id).run
    assert run.status == "succeeded", run.error
    assert run.result.draft.profile.to_wire() == {"occupation": "teacher"}
    assert {x.field for x in run.result.draft.unresolved} >= {"riskLevel", "horizonYears"}
    assert [s.actor for s in run.steps] == ["llm", "code", "code"]
    assert "profile_draft_integrity" in repo.get(run.session_id, run.run_id).private["agents"]


def test_parser_ambiguity_and_refusal_preserve_manual_fallback():
    from aplomb.agents import RequestParser

    output = {
        "request": queued("decision").input.request.to_wire(),
        "interpretation": {"en": "Ambiguous", "fr": "Ambigu"},
        "confidence": "low",
        "missing": [{"field": "funding", "question": {"en": "Funding?", "fr": "Financement?"}}],
        "warnings": [],
        "refused": None,
    }
    gateway = FakeGateway([output])
    parsed = RequestParser(gateway).parse_request(None, "Maybe add some Tesla", "en")
    assert parsed.request is None and parsed.missing
    output.update(
        confidence="high",
        missing=[],
        refused={
            "reason": "trade_execution",
            "message": {"en": "Simulation only", "fr": "Simulation seulement"},
        },
    )
    parsed = RequestParser(FakeGateway([output])).parse_request(None, "Place order", "en")
    assert parsed.request is None and parsed.refused.reason == "trade_execution"


def test_stale_lease_resumes_completed_model_without_new_step():
    from aplomb.ledger import Ledger

    class SimulatedCrash(BaseException):
        pass

    now = [1_800_000_000.0]
    run = queued("decision")
    run = run.model_copy(update={"created_at": timestamp(now[0]), "updated_at": timestamp(now[0])})
    profile = json.loads((ROOT / "contracts/fixtures/profiles.json").read_text())["items"][0]
    repo = RunRepository(MemoryStore(), clock=lambda: now[0])
    rec, _ = repo.create(run, {"profile": profile}, None, None, {})

    class Controls:
        calls = 0

        def quant(self, *args):
            self.calls += 1
            if self.calls == 1:
                raise SimulatedCrash()
            raise RuntimeError("Expected synthetic stop after resumed code")

    controls = Controls()
    gateway = FakeGateway([AnalysisPlan(interpretation="Confirmed input").model_dump()])
    services = AgentServices(
        repo,
        gateway,
        controls=controls,
        ledger_factory=Ledger,
        signer=lambda **kwargs: None,
        gate_factory=lambda private: object(),
        clock=lambda: now[0],
    )
    with pytest.raises(SimulatedCrash):
        execute_run(run.run_id, rec.generation, services)
    now[0] += 31
    execute_run(run.run_id, rec.generation, services)
    stored = repo.get(run.session_id, run.run_id).run
    assert stored.status == "failed"
    assert gateway.roles == ["planner"]
    assert [s.type for s in stored.steps] == ["plan", "quant"]
    assert controls.calls == 2


def test_timed_out_context_cannot_mutate_live_ledger():
    import threading

    from aplomb.agents.workflow import Execution
    from aplomb.ledger import Ledger

    repo, rec = repository(queued())
    rec = repo.claim(rec.run.run_id, rec.generation)
    execution = Execution(rec, AgentServices(repo, FakeGateway([])))
    ledger = Ledger(rec.run.run_id, rec.run.as_of)
    ctx = ToolContext(
        rec.run.run_id, None, "en", rec.run.as_of, object(), ledger, None, Limits(), None
    )
    gate = threading.Event()
    finished = threading.Event()

    def late(isolated):
        gate.wait(timeout=1)
        isolated.ledger.freeze()
        finished.set()

    with pytest.raises(TimeoutError):
        execution.context_call(ctx, late, 0.01)
    gate.set()
    assert finished.wait(timeout=1)
    # Freezing a discarded late copy does not freeze the run's live ledger.
    assert ledger.checkpoint()["frozen"] is False
