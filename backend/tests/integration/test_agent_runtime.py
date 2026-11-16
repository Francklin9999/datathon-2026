"""Real domain calculations, durable checkpoints and signing; synthetic model text only.

Uses the production composition pieces of ``aplomb.api.runtime`` (preparer, worker services,
gate and brief lookup)."""

import uuid

import pytest
from aplomb.agents.models import AnalysisPlan, Generation
from aplomb.agents.worker import make_handler
from aplomb.api.composition import create_repositories
from aplomb.api.runtime import RunPreparerImpl, brief_lookup, build_agent_services
from aplomb.api.settings import Settings
from aplomb.api.storage import MemoryStore
from aplomb.contracts import api as a
from aplomb.datastore import LocalDataStore
from aplomb.optimizer.services import build_domain_services
from tests.unit.datastore._support import STARTER_VERSION, starter_root


def worker_services(settings, store, gateway, snapshot):
    _, repository = create_repositories(settings, store)
    return build_agent_services(settings, repository, snapshot, None, gateway)


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
    profiles_repo, runs = create_repositories(settings, store)
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
    prepared = RunPreparerImpl(profiles, snapshot, models_configured=True, settings=settings)(sid, body)
    from aplomb.api.services import RunCoordinator
    class Capture:
        def dispatch(self, run_id, generation):
            self.event = {"runId": run_id, "generation": generation}
    dispatch = Capture()
    coordinator = RunCoordinator(runs, dispatch, lambda *_: prepared)
    queued = coordinator.create(sid, body, "same-request")
    worker = make_handler(worker_services(settings, store, SyntheticText(), snapshot))
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
        find = brief_lookup(runs, profiles, snapshot, settings)
        found, stale = find(sid, "robert", "en", {"code": "full"})
        assert found.run_id == run.run_id and stale is False
        assert len(result.focus_cards) == 3
        # A threshold edit changes the effective profile version: the stored brief becomes stale.
        profiles.patch_rule(sid, "robert", "cap.position", 11.0, None)
        assert find(sid, "robert", "en", {"code": "full"})[1] is True


def test_worker_rejects_changed_snapshot_manifest():
    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()))
    def snapshot():
        return LocalDataStore(starter_root()).open(STARTER_VERSION)
    services = worker_services(settings, MemoryStore(), SyntheticText(), snapshot)
    with pytest.raises(RuntimeError, match="manifest changed"):
        services.gate_factory({"dataVersion": STARTER_VERSION, "asOf": "2026-11-12", "mode": "current",
                               "manifestHash": "invalid"})


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


def test_brief_identity_ignores_a_code_only_release():
    """The worker pin (runtime_signature) changes with the build revision; the brief-cache identity
    does not, so a code-only redeploy keeps serving the briefs already written."""
    from aplomb.agents.runtime import brief_runtime_identity, runtime_signature
    settings = Settings(model_strong="model-a", model_fast="writer-a")
    released = settings.model_copy(update={"build_revision": "b" * 40})
    assert runtime_signature(settings) != runtime_signature(released)
    assert brief_runtime_identity(settings) == brief_runtime_identity(released)
    for change in ({"model_strong": "model-b"}, {"model_fast": "writer-b"}, {"guardrail_version": "2"},
                   {"max_llm_calls": 3}, {"run_hard_seconds": 120}, {"data_prefix": "other/"}):
        assert brief_runtime_identity(settings) != brief_runtime_identity(settings.model_copy(update=change)), change


def test_runtime_mismatch_fails_before_any_model_call():
    from aplomb.api.services import RunCoordinator
    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()))
    store = MemoryStore()
    profiles_repo, repo = create_repositories(settings, store)
    def snapshot():
        return LocalDataStore(starter_root()).open(STARTER_VERSION)
    profiles, _ = build_domain_services(profiles_repo, snapshot)
    class Capture:
        def dispatch(self, run_id, generation):
            self.event = {"runId": run_id, "generation": generation}
    dispatch = Capture()
    request = a.CreateProfileDraftRunRequest(kind="profile_draft", text="A fictional librarian.", lang="en")
    sid = "s_" + str(uuid.uuid4())
    prepare = RunPreparerImpl(profiles, snapshot, models_configured=True, settings=settings)
    queued = RunCoordinator(repo, dispatch, prepare).create(sid, request, None)
    changed = settings.model_copy(update={"model_strong": "different-release"})
    make_handler(worker_services(changed, store, SyntheticText(), snapshot))(dispatch.event)
    run = repo.get(sid, queued.run_id).run
    assert run.status == "failed" and run.usage.llm_calls == 0
    assert "runtime configuration" in run.error.message


def test_reviewed_rebalance_owns_all_local_facts_and_preserves_targets():
    from aplomb.api.services import RunCoordinator

    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()))
    store = MemoryStore()
    profiles_repo, runs = create_repositories(settings, store)

    def snapshot():
        return LocalDataStore(starter_root()).open(STARTER_VERSION)

    profiles, checks = build_domain_services(profiles_repo, snapshot)
    sid = "s_" + str(uuid.uuid4())
    profile = profiles.get(sid, "robert")
    positions = profile.portfolio.positions
    body = a.CreateRebalanceRunRequest(kind="rebalance", profile_id="robert", profile_version=profile.version,
                                       positions=positions, lang="en")
    request = a.RebalanceRequest(profile_id="robert", profile_version=profile.version, positions=positions)
    deterministic = checks.rebalance(sid, request)

    class Capture:
        def dispatch(self, run_id, generation):
            self.event = {"runId": run_id, "generation": generation}

    dispatch = Capture()
    prepare = RunPreparerImpl(profiles, snapshot, models_configured=True, settings=settings)
    queued = RunCoordinator(runs, dispatch, prepare).create(sid, body, "target-once")
    make_handler(worker_services(settings, store, SyntheticText(), snapshot))(dispatch.event)
    run = runs.get(sid, queued.run_id).run
    assert run.status == "succeeded", run.error
    result = run.result.rebalance
    assert result.brief.audit.status == "passed"
    assert result.verdict_after == deterministic.verdict_after
    assert result.portfolio_after.total_value == deterministic.portfolio_after.total_value
    assert [s.type for s in run.steps] == ["plan", "quant", "risk_check", "write", "audit", "sign"]
    quant = next(step for step in run.steps if step.type == "quant")
    assert run.usage.tool_calls == 1 and quant.tool_calls[0].tool == "check.rebalance"
    assert quant.tool_calls[0].fact_ids and all(fid in run.facts for fid in quant.tool_calls[0].fact_ids)
    for check in result.rule_checks_after:
        assert all(fid in run.facts for fid in (check.value_fact_id, check.threshold_fact_id) if fid)
    for fact in run.facts.values():
        assert all(fid in run.facts for fid in fact.inputs)
    with pytest.raises(Exception):
        runs.get("s_" + str(uuid.uuid4()), queued.run_id)


def test_rebalance_local_ids_are_remapped_when_run_already_has_facts():
    from types import SimpleNamespace

    from aplomb.agents.workflow import _register_rebalance
    from aplomb.ledger import Ledger

    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()))
    profiles_repo, _ = create_repositories(settings, MemoryStore())

    def snapshot():
        return LocalDataStore(starter_root()).open(STARTER_VERSION)

    profiles, checks = build_domain_services(profiles_repo, snapshot)
    sid = "s_" + str(uuid.uuid4())
    profile = profiles.get(sid, "robert")
    result = checks.rebalance(sid, a.RebalanceRequest(profile_id="robert", profile_version=profile.version,
                                                       positions=profile.portfolio.positions))
    ledger = Ledger("run_00000000000000000000000000", as_of=result.as_of)
    first = next(f.to_wire() for f in result.facts.values() if not f.inputs)
    first.pop("id")
    first["subject"]["id"] = "preexisting"
    assert ledger.add_fact(first) == "F-001"
    comparison = _register_rebalance(SimpleNamespace(ledger=ledger), result.to_wire())
    assert len(ledger.export().facts) > len(result.facts)
    for check in comparison["ruleChecksAfter"]:
        for key in ("valueFactId", "thresholdFactId"):
            if check.get(key):
                assert check[key] != "F-001"
                assert check[key] in ledger.export().facts
    assert all(item in ledger.export().facts for fact in ledger.export().facts.values() for item in fact.inputs)


def test_rebalance_model_failure_keeps_standalone_comparison_available():
    from aplomb.api.services import RunCoordinator

    class UnavailableModel:
        def generate(self, role, schema, messages, tools, limits):
            limits.take("llm_calls")
            raise RuntimeError("provider credential SECRET is intentionally not exposed")

    class Capture:
        def dispatch(self, run_id, generation):
            self.event = {"runId": run_id, "generation": generation}

    settings = Settings(data_version=STARTER_VERSION, data_dir=str(starter_root()))
    store = MemoryStore()
    profiles_repo, runs = create_repositories(settings, store)

    def snapshot():
        return LocalDataStore(starter_root()).open(STARTER_VERSION)

    profiles, checks = build_domain_services(profiles_repo, snapshot)
    sid = "s_" + str(uuid.uuid4())
    profile = profiles.get(sid, "robert")
    body = a.CreateRebalanceRunRequest(kind="rebalance", profile_id="robert", profile_version=profile.version,
                                       positions=profile.portfolio.positions, lang="en")
    dispatch = Capture()
    queued = RunCoordinator(runs, dispatch, RunPreparerImpl(profiles, snapshot, models_configured=True,
                                                            settings=settings)).create(sid, body, None)
    make_handler(worker_services(settings, store, UnavailableModel(), snapshot))(dispatch.event)
    run = runs.get(sid, queued.run_id).run
    assert run.status == "failed" and "SECRET" not in str(run.to_wire())
    comparison = checks.rebalance(sid, a.RebalanceRequest(profile_id="robert", profile_version=profile.version,
                                                           positions=profile.portfolio.positions))
    assert comparison.portfolio_after.total_value == profile.portfolio.total_value
