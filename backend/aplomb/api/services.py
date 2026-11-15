"""Composition interfaces for domain tracks; no network/model calls on import.

T04: DataService. T05/T06: CheckService/ProfileService. T08: ParserService,
RunPreparer and a worker using RunRepository.claim/checkpoint/heartbeat.
T11/T12: WorldService/ReplayService. Domain services must authorize every
session resource they dereference, including nested draft/parent run IDs.
"""

import secrets
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

from aplomb.contracts import api as a
from aplomb.contracts import models as m

from .dispatcher import Dispatcher
from .errors import Conflict, NotFound, unavailable
from .repositories import RunRepository, timestamp


class ProfileService(Protocol):
    def list(self, session_id: str) -> list[m.Profile]: ...
    def get(self, session_id: str, profile_id: str) -> m.Profile: ...
    def create(self, session_id: str, request: a.CreateProfileRequest) -> m.Profile: ...
    def replace(
        self, session_id: str, profile_id: str, request: a.UpdateProfileRequest, version: int
    ) -> m.Profile: ...
    def delete(self, session_id: str, profile_id: str) -> None: ...
    def patch_rule(
        self,
        session_id: str,
        profile_id: str,
        rule_id: str,
        threshold: float | None,
        enabled: bool | None,
    ) -> m.Profile: ...
    def rederive_rules(
        self, session_id: str, profile_id: str, reset: bool, window: m.WindowSpec | None
    ) -> tuple[m.Profile, dict[str, m.Fact]]: ...
    def set_portfolio(
        self, session_id: str, profile_id: str, portfolio: a.UpdatePortfolioRequest, version: int
    ) -> m.Profile: ...
    def risk_diagnostics(self, session_id: str, profile_id: str, query: dict) -> a.RiskDiagnosticsResponse: ...
    def overview(self, session_id: str, profile_id: str, query: dict) -> a.OverviewResponse: ...
    def performance(
        self, session_id: str, profile_id: str, query: dict
    ) -> a.PerformanceResponse: ...
    def frontier(self, session_id: str, profile_id: str, query: dict) -> a.FrontierResponse: ...
    def brief(self, session_id: str, profile_id: str, query: dict) -> a.CachedBriefResponse: ...


class CheckService(Protocol):
    def check(self, session_id: str, request: a.CheckRequest) -> m.CheckResult: ...


class ParserService(Protocol):
    def parse(self, session_id: str, request: a.ParseRequest) -> m.ParsedRequest: ...


class DataService(Protocol):
    def assets(self, session_id: str, query: dict) -> a.AssetsResponse: ...
    def asset(self, session_id: str, ticker: str) -> m.Asset: ...
    def analytics(self, session_id: str, ticker: str, query: dict) -> a.AssetAnalyticsResponse: ...
    def fetch(self, session_id: str, ticker: str) -> a.FetchAssetResponse: ...
    def attention(self, session_id: str, ticker: str) -> a.AttentionResponse: ...
    def datasets(self, session_id: str) -> a.DatasetsResponse: ...
    def dataset(self, session_id: str, dataset_id: str) -> m.DatasetPassport: ...
    def universe_summary(self) -> m.UniverseSummary: ...


class WorldService(Protocol):
    def layers(self, session_id: str, query: dict) -> a.WorldLayersResponse: ...
    def events(self, session_id: str, query: dict) -> a.WorldEventsResponse: ...
    def event(self, session_id: str, event_id: str, query: dict) -> a.WorldEventResponse: ...
    def exposure(self, session_id: str, query: dict) -> a.WorldExposureResponse: ...
    def country(self, session_id: str, iso3: str, query: dict) -> a.WorldCountryResponse: ...
    def facilities(self, session_id: str, query: dict) -> a.FacilitiesResponse: ...
    def hazards(self, session_id: str, query: dict) -> a.HazardsResponse: ...


class ReplayService(Protocol):
    def presets(self, session_id: str) -> a.ReplayPresetsResponse: ...
    def reveal(self, session_id: str, run: m.Run, request: a.RevealRequest) -> object: ...


@dataclass(frozen=True)
class PreparedRun:
    """Validated, authorized immutable inputs from the domain composition.

    `private` must contain pinned profile/manifest/context and worker resume state.
    `input` is a shared RunInput wire payload (including resolved window/fields).
    Preparation must not invoke models or dispatch work. The caller's body is
    the idempotency digest; effective context is frozen from the first creation.
    """

    input: dict
    as_of: str
    data_version: str
    private: dict
    profile_version: int | None


class RunPreparer(Protocol):
    def __call__(self, session_id: str, request: a.CreateRunRequest) -> PreparedRun: ...


def new_run_id(epoch: float) -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    value = (int(epoch * 1000) << 80) | secrets.randbits(80)
    return "run_" + "".join(alphabet[(value >> shift) & 31] for shift in range(125, -1, -5))


class RunCoordinator:
    def __init__(
        self,
        repository: RunRepository,
        dispatcher: Dispatcher,
        prepare: RunPreparer,
        clock: Callable[[], float] = time.time,
        cached_brief: Callable[[str, a.CreatePortfolioBriefRunRequest], m.Run | None] | None = None,
    ):
        self.repository, self.dispatcher, self.prepare = repository, dispatcher, prepare
        self.clock = clock
        self.cached_brief = cached_brief

    def create(
        self, session_id: str, request: a.CreateRunRequest, idempotency_key: str | None
    ) -> a.QueuedRunResponse | a.CachedRunResponse:
        prior = self.repository.idempotent(session_id, idempotency_key, request.to_wire())
        if prior is not None:
            return self._accepted(prior.run)
        if request.kind == "portfolio_brief" and not request.force and self.cached_brief:
            cached = self.cached_brief(session_id, request)
            if cached is not None:
                if (
                    cached.session_id != session_id
                    or cached.profile_id != request.profile_id
                    or cached.kind != "portfolio_brief"
                    or cached.status != "succeeded"
                ):
                    raise ValueError("Invalid brief cache ownership or state")
                reserved = self.repository.reserve_existing(
                    session_id, cached.run_id, idempotency_key, request.to_wire()
                )
                return self._accepted(reserved.run)
        prepared = self.prepare(session_id, request)
        now = timestamp(self.clock())
        run = m.Run.model_validate(
            {
                "runId": new_run_id(self.clock()),
                "kind": request.kind,
                "status": "queued",
                "sessionId": session_id,
                "profileId": getattr(request, "profile_id", None),
                "parentRunId": None,
                "lang": request.lang,
                "asOf": prepared.as_of,
                "dataVersion": prepared.data_version,
                "input": prepared.input,
                "steps": [],
                "facts": {},
                "evidence": {},
                "question": None,
                "result": None,
                "error": None,
                "flags": {
                    "sabotage": None,
                    "fixture": False,
                    "timeMachine": request.kind == "replay",
                },
                "usage": {
                    "inputTokens": 0,
                    "outputTokens": 0,
                    "llmCalls": 0,
                    "toolCalls": 0,
                    "durationMs": 0,
                },
                "createdAt": now,
                "updatedAt": now,
            }
        )
        record, created = self.repository.create(
            run, prepared.private, prepared.profile_version, idempotency_key, request.to_wire()
        )
        if created:
            try:
                self.dispatcher.dispatch(run.run_id, record.generation)
            except Exception as exc:
                self.repository.dispatch_failed(session_id, run.run_id, record.generation)
                raise unavailable("Worker dispatch") from exc
        return self._accepted(record.run)

    def sabotage(self, session_id: str, parent: m.Run, request: a.SabotageRequest) -> a.QueuedRunResponse:
        record = self.repository.get(session_id, parent.run_id)
        parent = record.run
        if parent.kind != "decision" or parent.status != "succeeded" or parent.result is None:
            raise Conflict("Sabotage requires a succeeded decision")
        if request.lang != parent.lang:
            raise Conflict("Sabotage language must match the parent decision")
        checkpoint = record.private.get("agents", {}).get("ledger")
        if not checkpoint or not checkpoint.get("frozen"):
            raise Conflict("Signed parent ledger checkpoint is unavailable")
        now = timestamp(self.clock())
        payload = parent.to_wire()
        payload.update(runId=new_run_id(self.clock()), kind="sabotage", status="queued", parentRunId=parent.run_id,
                       lang=request.lang, input={"kind": "sabotage", "mode": request.mode}, steps=[], facts={}, evidence={},
                       result=None, error=None, question=None, flags={"sabotage": request.mode, "fixture": False, "timeMachine": False},
                       usage={"inputTokens": 0, "outputTokens": 0, "llmCalls": 0, "toolCalls": 0, "durationMs": 0},
                       createdAt=now, updatedAt=now)
        child = m.Run.model_validate(payload)
        private = {k: v for k, v in record.private.items() if k != "agents"}
        private.update(sabotageParent=parent.to_wire(), sabotageLedger=checkpoint)
        child_record, _ = self.repository.create(child, private, record.profile_version)
        try:
            self.dispatcher.dispatch(child.run_id, child_record.generation)
        except Exception as exc:
            self.repository.dispatch_failed(session_id, child.run_id, child_record.generation)
            raise unavailable("Worker dispatch") from exc
        return a.QueuedRunResponse(run_id=child.run_id, status="queued", poll_after_ms=1000)

    @staticmethod
    def _accepted(run: m.Run) -> a.QueuedRunResponse | a.CachedRunResponse:
        # A failed or cancelled prior run replays its acceptance: the poll shows the stored outcome.
        if run.status == "succeeded":
            return a.CachedRunResponse(run_id=run.run_id, status="succeeded")
        return a.QueuedRunResponse(run_id=run.run_id, status="queued", poll_after_ms=1000)

    def get(self, session_id: str, run_id: str, since: int | None = None) -> m.Run:
        run = self.repository.get(session_id, run_id).run
        if since is None:
            return run
        payload = run.to_wire()
        steps = [step for step in run.steps if step.seq > since]
        fact_ids = {fact_id for step in steps for fact_id in step.fact_ids}
        evidence_ids = {eid for step in steps for eid in step.evidence_ids}
        for step in steps:
            for tool in step.tool_calls:
                fact_ids.update(tool.fact_ids)
                evidence_ids.update(tool.evidence_ids)
        # Include transitive input facts and their evidence, not unrelated ledger data.
        pending = list(fact_ids)
        while pending:
            fact_id = pending.pop()
            if fact_id not in run.facts:
                continue
            fact = run.facts[fact_id]
            for child in fact.inputs:
                if child not in fact_ids:
                    pending.append(child)
                    fact_ids.add(child)
        payload.update(
            steps=[step.to_wire() for step in steps],
            facts={key: fact.to_wire() for key, fact in run.facts.items() if key in fact_ids},
            evidence={key: ev.to_wire() for key, ev in run.evidence.items() if key in evidence_ids},
        )
        # Result references may require the full ledger: terminal consumers fetch without since.
        return m.Run.model_validate(payload)

    def answer(self, session_id: str, run_id: str, answer: a.AnswerRequest) -> a.AnswerResponse:
        record = self.repository.answer(session_id, run_id, answer.question_id, answer.value)
        try:
            self.dispatcher.dispatch(run_id, record.generation)
        except Exception as exc:
            self.repository.dispatch_failed(session_id, run_id, record.generation)
            raise unavailable("Worker dispatch") from exc
        return a.AnswerResponse(run_id=run_id, status="running")

    def cancel(self, session_id: str, run_id: str) -> a.CancelResponse:
        self.repository.cancel(session_id, run_id)
        return a.CancelResponse(run_id=run_id, status="cancelled")

    def fact(self, session_id: str, run_id: str, fact_id: str) -> a.FactResponse:
        run = self.get(session_id, run_id)
        return resolve_fact(session_id, run, fact_id)


def resolve_fact(session_id: str, run: m.Run, fact_id: str) -> a.FactResponse:
    """Project actual stored references; no numbers or usage are synthesized."""
    if run.session_id != session_id:
        raise NotFound()
    if fact_id not in run.facts:
        raise NotFound()
    fact = run.facts[fact_id]
    sentence_ids, rule_ids = set(), set()

    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            if "segments" in node and any(
                s.get("t") == "fact" and s.get("factId") == fact_id for s in node["segments"]
            ):
                sentence_ids.add(node["id"])
            if "ruleId" in node and fact_id in {
                node.get("valueFactId"),
                node.get("thresholdFactId"),
            }:
                rule_ids.add(node["ruleId"])
            for value in node.values():
                visit(value)

    visit(run.result.to_wire() if run.result is not None else {})
    return a.FactResponse(
        fact=fact,
        inputs=[run.facts[key] for key in fact.inputs],
        used_by=a.FactUsage(sentence_ids=sorted(sentence_ids), rule_ids=sorted(rule_ids)),
    )


@dataclass
class Services:
    profiles: ProfileService | None = None
    checks: CheckService | None = None
    runs: RunCoordinator | None = None
    datastore: DataService | None = None
    parser: ParserService | None = None
    world: WorldService | None = None
    replay: ReplayService | None = None
    fact_resolver: Callable[[str, m.Run, str], a.FactResponse] | None = resolve_fact
    sabotage: Callable[[str, m.Run, a.SabotageRequest], a.QueuedRunResponse] | None = None
    # A configured flag is advertised only when a verified provider explicitly supports it.
    capabilities: set[str] = field(default_factory=set)
