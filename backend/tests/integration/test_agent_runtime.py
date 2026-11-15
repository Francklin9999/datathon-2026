"""Real domain calculations, durable checkpoints and signing; synthetic model text only."""

import uuid

import pytest
from aplomb.agents.models import AnalysisPlan, Generation
from aplomb.agents.runtime import BriefProfiles, RunPreparer, make_worker_services
from aplomb.agents.worker import make_handler
from aplomb.api.composition import create_repositories
from aplomb.api.settings import Settings
from aplomb.api.storage import MemoryStore
from aplomb.contracts import api as a
from aplomb.datastore import LocalDataStore
from aplomb.optimizer.services import build_domain_services
from tests.unit.datastore._support import STARTER_VERSION, starter_root


class SyntheticText:
    def generate(self, role, schema, messages, tools, limits):
        limits.take("llm_calls")
        if role == "planner":
            raw = {"interpretation": "Confirmed hypothetical scenario"}
        elif role == "writer":
            data = messages[0]
            fid = next(k for k, f in data["facts"].items() if f["metric"] == "vol.annualized")
            policy = " ".join("Policy {{rule:" + r["ruleId"] + "}} has status {{status:" + r["ruleId"] + "}}."
                              for r in data["checks"] if r["status"] in {"conflict", "tension"})
            raw = {"sections": [{"id": key, "title": {"en": key, "fr": key},
                                  "sentences": [{"id": key + "-sentence", "template": text}]}
                                 for key, text in [("facts", "Historical volatility is {{fact:" + fid + "}}."),
                                                   ("assumptions", policy or "Policy thresholds are assumptions."),
                                                   ("limits", "Historical evidence is limited.")]]}
        elif role == "auditor":
            raw = {"findings": [], "relations": []}
        else:
            raise AssertionError(role)
        return Generation(schema.model_validate(raw), "synthetic-text-only", 13, 7)


@pytest.mark.parametrize("kind", ["decision", "portfolio_brief"])
def test_runtime_real_controls_signed_and_duplicate_safe(kind):
    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()))
    store = MemoryStore()
    profiles_repo, runs, _ = create_repositories(settings, store)
    def snapshot():
        return LocalDataStore(starter_root()).open(STARTER_VERSION)
    profiles, _ = build_domain_services(profiles_repo, snapshot)
    request = {"kind": kind, "profileId": "robert", "lang": "en"}
    if kind == "decision":
        request["request"] = {"type": "move", "move": {"ticker": "TSLA", "sizePct": 25,
                                                        "funding": {"mode": "pro_rata"}}}
        body = a.CreateDecisionRunRequest.model_validate(request)
    else:
        body = a.CreatePortfolioBriefRunRequest.model_validate(request)
    sid = "s_" + str(uuid.uuid4())
    prepared = RunPreparer(settings, profiles, snapshot)(sid, body)
    from aplomb.api.services import RunCoordinator
    class Capture:
        def dispatch(self, run_id, generation):
            self.event = {"runId": run_id, "generation": generation}
    dispatch = Capture()
    coordinator = RunCoordinator(runs, dispatch, lambda *_: prepared)
    queued = coordinator.create(sid, body, "same-request")
    worker = make_handler(make_worker_services(settings, store, SyntheticText()))
    worker(dispatch.event)
    run = runs.get(sid, queued.run_id).run
    assert run.status == "succeeded", run.error
    result = run.result.decision if kind == "decision" else run.result.portfolio_brief
    assert result.brief.audit.status == "passed"
    assert result.brief.audit.ledger_hash
    assert run.usage.llm_calls == 3
    assert [s.type for s in run.steps] == ["plan", "quant", "risk_check", "write", "audit", "sign"]
    assert all(f.verification.status == "verified" for f in run.facts.values() if f.metric == "vol.annualized")
    worker(dispatch.event)
    assert runs.get(sid, queued.run_id).run == run
    assert coordinator.create(sid, body, "same-request").run_id == run.run_id
    with pytest.raises(Exception) as exc:
        runs.get("s_" + str(uuid.uuid4()), queued.run_id)
    assert "NotFound" in type(exc.value).__name__
    if kind == "portfolio_brief":
        wrapped = BriefProfiles(profiles, runs, snapshot)
        assert wrapped.brief(sid, "robert", {}).run.run_id == run.run_id
        assert len(result.focus_cards) == 3
        # A GSI may still return an old META under a new grouping during propagation.
        stale = store.get("runs", "RUN#" + run.run_id, "META")
        original_query = store.query
        store.query = lambda table, pk, index=None: [stale] if index == "byProfile" else original_query(table, pk, index)
        profiles.patch_rule(sid, "robert", "cap.position", 11.0, None)
        assert wrapped.brief(sid, "robert", {}).run is None


def test_worker_rejects_changed_snapshot_manifest():
    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()))
    services = make_worker_services(settings, MemoryStore(), SyntheticText())
    with pytest.raises(ValueError, match="manifest changed"):
        services.gate_factory({"dataVersion": STARTER_VERSION, "asOf": "2026-11-12", "manifestHash": "invalid"})


def test_planner_cannot_smuggle_an_unknown_computation():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AnalysisPlan.model_validate({"interpretation": "test", "quant_tasks": [{"tool": "shell.execute"}]})


def test_model_or_policy_release_changes_brief_cache_identity():
    from aplomb.agents.runtime import runtime_signature
    settings = Settings(model_strong="model-a", model_fast="writer-a")
    assert runtime_signature(settings) != runtime_signature(settings.model_copy(update={"model_strong": "model-b"}))
    assert runtime_signature(settings) != runtime_signature(settings.model_copy(update={"guardrail_version": "2"}))
    assert runtime_signature(settings) != runtime_signature(settings.model_copy(update={"max_llm_calls": 3}))


def test_runtime_mismatch_fails_before_any_model_call():
    from aplomb.api.services import RunCoordinator
    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()))
    store = MemoryStore()
    profiles_repo, repo, _ = create_repositories(settings, store)
    def snapshot():
        return LocalDataStore(starter_root()).open(STARTER_VERSION)
    profiles, _ = build_domain_services(profiles_repo, snapshot)
    class Capture:
        def dispatch(self, run_id, generation):
            self.event = {"runId": run_id, "generation": generation}
    dispatch = Capture()
    request = a.CreateProfileDraftRunRequest(kind="profile_draft", text="A fictional librarian.", lang="en")
    sid = "s_" + str(uuid.uuid4())
    queued = RunCoordinator(repo, dispatch, RunPreparer(settings, profiles, snapshot)).create(sid, request, None)
    changed = settings.model_copy(update={"model_strong": "different-release"})
    make_handler(make_worker_services(changed, store, SyntheticText()))(dispatch.event)
    run = repo.get(sid, queued.run_id).run
    assert run.status == "failed" and run.usage.llm_calls == 0
    assert "runtime configuration" in run.error.message
