"""Run composition for the exported application: preparer, worker services and dispatch.

Connects the tracks that were built against protocols: T03 repositories/dispatcher, T08 workflow,
T05–T07 code controls, T10 ledger/signing, T09 research tools, T11 world events and T12 replay
metadata. Nothing here calls a model, AWS or a public source at import or at app creation.

A run pins its inputs at creation (``PreparedRun.private``): the effective profile, the snapshot
version, the as-of date and the gate mode. The worker reopens exactly that context.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.contracts.catalog import FeatureFlag
from aplomb.datastore import Snapshot

from .dispatcher import LambdaDispatcher, LocalDispatcher
from .errors import NotFound, ServiceError, unavailable
from .repositories import RunRepository
from .services import PreparedRun, RunCoordinator
from .settings import Settings

log = logging.getLogger(__name__)
FULL_WINDOW = {"code": "full"}


def _stamp(clock: Callable[[], float]) -> str:
    return datetime.fromtimestamp(clock(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class UnconfiguredGateway:
    """Stands in when no Bedrock model ID is configured: every call fails with the reason."""

    def generate(self, role, schema, messages, tools, limits):
        raise RuntimeError("No model is configured (APLOMB_MODEL_STRONG / APLOMB_MODEL_FAST)")


def model_gateway(settings: Settings):
    if not (settings.model_strong and settings.model_fast):
        return None
    from aplomb.agents.models import StrandsBedrockGateway

    return StrandsBedrockGateway(strong_model=settings.model_strong, fast_model=settings.model_fast, region=settings.region)


class RunPreparerImpl:
    """``RunPreparer``: authorizes and pins the inputs of a run. No model call, no dispatch."""

    def __init__(self, profiles, snapshot: Callable[[], Snapshot], *, models_configured: bool, world=None,
                 clock: Callable[[], float] = time.time, settings: Settings | None = None) -> None:
        self.profiles, self.snapshot, self.world = profiles, snapshot, world
        self.models_configured = models_configured
        self.clock = clock
        self.settings = settings

    def _pins(self, snap: Snapshot) -> dict:
        """What a worker must find again before it runs: the exact manifest, the runtime
        configuration (models, guardrail, limits, flags) and, in AWS, the worker version."""
        from aplomb.agents.runtime import manifest_hash, runtime_signature

        pins = {"manifestHash": manifest_hash(snap)}
        if self.settings is not None:
            pins["runtimeSignature"] = runtime_signature(self.settings)
            pins["workerFunction"] = self.settings.worker_function
        return pins

    def __call__(self, session_id: str, request: a.CreateRunRequest) -> PreparedRun:
        if not self.models_configured:
            # Every run kind needs at least one model call; refuse before persisting a run that cannot start.
            raise unavailable("Model configuration (APLOMB_MODEL_STRONG and APLOMB_MODEL_FAST)")
        snap = self.snapshot()
        base = {"dataVersion": snap.data_version, "asOf": snap.data_as_of, "mode": "current", **self._pins(snap)}
        if request.kind == "profile_draft":
            fields = request.fields.to_wire() if request.fields is not None else {}
            return PreparedRun({"kind": "profile_draft", "text": request.text, "fields": fields}, snap.data_as_of,
                               snap.data_version, base, None)
        profile = self.profiles.get(session_id, request.profile_id)
        window = request.window.to_wire() if getattr(request, "window", None) is not None else dict(FULL_WINDOW)
        if request.kind == "decision":
            self._check_request(snap, request.request)
            self._check_move(snap, profile, request.request, snap.data_as_of, "current", window)
            payload = {"kind": "decision", "request": request.request.to_wire(), "originalText": request.original_text,
                       "window": window}
            return PreparedRun(payload, snap.data_as_of, snap.data_version, {**base, "profile": profile.to_wire()},
                               profile.version)
        if request.kind == "replay":
            from aplomb.timemachine import validate_asof

            self._check_request(snap, request.request)
            ctx = validate_asof(request.as_of, profile, snap, request.request, _stamp(self.clock))
            self._check_move(snap, ctx.profile, request.request, ctx.as_of, "historical", window)
            payload = {"kind": "replay", "request": request.request.to_wire(), "asOf": ctx.as_of, "window": window}
            private = {"dataVersion": snap.data_version, "asOf": ctx.as_of, "mode": "historical", **self._pins(snap),
                       "profile": ctx.profile.to_wire(), "revealAvailableUntil": ctx.reveal_available_until}
            return PreparedRun(payload, ctx.as_of, snap.data_version, private, profile.version)
        if request.kind == "portfolio_brief":
            return PreparedRun({"kind": "portfolio_brief", "window": window}, snap.data_as_of, snap.data_version,
                               {**base, "profile": profile.to_wire()}, profile.version)
        if request.kind == "event_brief":
            if self.world is None:
                raise unavailable("World events dataset")
            detail = self.world.event(session_id, request.event_id, {"profileId": request.profile_id})
            source = self.world.provenance(detail.event.to_wire())
            # The information cutoff of an event brief is the later of the price data date and the
            # day the events were retrieved: the event row is not older information than that.
            as_of = max(snap.data_as_of, source["builtAt"][:10])
            private = {**base, "asOf": as_of, "profile": profile.to_wire(), "event": detail.event.to_wire(),
                       "exposures": [x.to_wire() for x in detail.exposures], "eventSource": source}
            return PreparedRun({"kind": "event_brief", "eventId": request.event_id}, as_of, snap.data_version,
                               private, profile.version)
        raise ServiceError("validation_error", f"Unsupported run kind {request.kind}")

    def _check_move(self, snap: Snapshot, profile: m.Profile, request: m.DecisionRequest, as_of: str, mode: str,
                    window: dict) -> None:
        """The same deterministic preparation /check performs: a move or a window that /check
        refuses is refused here with the same typed error, before a run is stored."""
        from aplomb.optimizer.check import prepare
        from aplomb.quant import LocalLedger, QuantEngine, Unavailable

        engine = QuantEngine(snap.gate(as_of, mode), LocalLedger(), currency=profile.reporting_currency,
                             subject_id=profile.profile_id, created_at=_stamp(self.clock), window=window)
        try:
            engine.window(window)
        except Unavailable as exc:
            raise ServiceError("validation_error", f"The window cannot be computed at {as_of}: {exc.detail}",
                               {"fields": [{"path": "window", "problem": exc.detail}]}) from exc
        if request.type == "move":
            prepare(engine, profile, profile.rules, request.move, False)

    @staticmethod
    def _check_request(snap: Snapshot, request: m.DecisionRequest) -> None:
        universe = snap.gate(snap.data_as_of, "current").universe()
        tickers = []
        if request.type == "move":
            tickers = [request.move.ticker, *(request.move.funding.from_tickers or [])]
            if request.move.funding.mode == "from_holdings" and not request.move.funding.from_tickers:
                raise ServiceError("validation_error", "from_holdings funding needs fromTickers",
                                   {"fields": [{"path": "request.move.funding.fromTickers", "problem": "required"}]})
        elif request.type == "goal":
            tickers = list(request.goal.tickers)
            if not (request.goal.themes or request.goal.asset_classes or request.goal.tickers):
                raise ServiceError("validation_error", "A goal needs at least one theme, asset class or ticker",
                                   {"fields": [{"path": "request.goal", "problem": "empty goal"}]})
        for ticker in tickers:
            if ticker not in universe:
                raise NotFound(f"Unknown ticker {ticker}")


def gate_factory(snapshot: Callable[[], Snapshot], settings: Settings | None = None):
    def open_gate(private: dict):
        from aplomb.agents.runtime import manifest_hash

        snap = snapshot()
        if private.get("dataVersion") != snap.data_version:
            if settings is None:
                raise RuntimeError(f"Run is pinned to {private.get('dataVersion')}; loaded snapshot is {snap.data_version}")
            from .domain import SnapshotProvider

            pinned = settings.model_copy(update={"data_version": private["dataVersion"], "data_as_of": private.get("dataAsOf", snap.data_as_of)})
            snap = SnapshotProvider(pinned)()
        if "manifestHash" in private and manifest_hash(snap) != private["manifestHash"]:
            raise RuntimeError("Pinned snapshot manifest changed")
        if private["mode"] == "historical":
            for rule in private["profile"]["rules"]:
                derivation = rule.get("derivation") or {}
                if rule["origin"] == "derived" and derivation.get("inputs", {}).get("asOf") != private["asOf"]:
                    raise RuntimeError(f"Rule {rule['ruleId']} was not derived at the replay cutoff {private['asOf']}")
        return snap.gate(private["asOf"], private["mode"])

    return open_gate


def build_registry(settings: Settings, world=None):
    """Catalog tools with real implementations: T04–T07 lookups/quant/rules, T09 research, T11 events."""
    from pydantic import BaseModel, ConfigDict, Field

    from aplomb.agents.registry import ToolRegistry, ToolResult
    from aplomb.optimizer.tools import register_domain_tools

    registry = ToolRegistry()
    register_domain_tools(registry)
    if settings.source_user_agent:
        from aplomb.research import PublicHTTP, ResearchService, research_tool_handlers

        try:
            transport = PublicHTTP(settings.source_user_agent)
        except ValueError:
            # Public sources require a contact in the user agent. Without one the research tools are
            # simply absent (evidence gaps stay visible); the API itself must still start.
            log.warning("Research tools disabled: APLOMB_SOURCE_USER_AGENT needs a contact URL or email")
        else:
            service = ResearchService(transport, lambda: datetime.now(timezone.utc))
            browser = None
            if settings.features[FeatureFlag.RESEARCH_OPEN_WEB]:
                # web.browse through AgentCore Browser; without the flag the tool does not exist.
                from aplomb.research.browser import AgentCoreBrowser

                browser = AgentCoreBrowser(settings.region)
            for name, (args, function) in research_tool_handlers(service, browser=browser).items():
                registry.register(name, args, function)
    if world is not None:
        class SearchEventsArgs(BaseModel):
            model_config = ConfigDict(extra="forbid")
            q: str | None = Field(default=None, max_length=200)
            country: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
            ticker: str | None = Field(default=None, max_length=20)
            start: str | None = None
            end: str | None = None
            limit: int = Field(default=20, ge=1, le=50)

        def search_events(ctx, **args):
            found = world.search_events(as_of=str(ctx.as_of), **args)
            data = {"events": [{"eventId": e["eventId"], "title": e["title"], "occurredAt": e["occurredAt"],
                                "category": e["category"], "countries": e["relatedCountries"], "tickers": e["relatedTickers"],
                                "sources": [{"publisher": s["publisher"], "url": s["url"]} for s in e["sources"]]}
                               for e in found],
                    "note": "Events from the cached dataset; a listed event is not evidence of a financial effect."}
            return ToolResult(True, f"{len(found)} cached event(s)", data=data)

        registry.register("world.search_events", SearchEventsArgs, search_events)
    return registry


def build_agent_services(settings: Settings, repository: RunRepository, snapshot: Callable[[], Snapshot], world=None,
                         gateway=None):
    """``AgentServices`` with every implemented provider; used by the local worker and by Lambda."""
    from aplomb.agents import AgentServices
    from aplomb.agents.guardrails import BedrockOutputPolicy
    from aplomb.agents.runtime import runtime_signature
    from aplomb.agents.signing import sign_decision
    from aplomb.ledger import Ledger
    from aplomb.optimizer.services import DecisionControls
    from aplomb.timemachine import replay_result

    policy = BedrockOutputPolicy(settings) if settings.guardrail_id and settings.guardrail_version else None
    return AgentServices(
        repository=repository,
        gateway=gateway or model_gateway(settings) or UnconfiguredGateway(),
        registry=build_registry(settings, world),
        controls=DecisionControls(),
        ledger_factory=Ledger,
        signer=sign_decision,
        gate_factory=gate_factory(snapshot, settings),
        logger=log,
        replay_result_factory=replay_result,
        guardrail=policy,
        runtime_signature=runtime_signature(settings),
        max_llm_calls=settings.max_llm_calls,
        max_research_calls=settings.max_research_calls,
        max_revisions=settings.max_revise,
    )


class _LazyLambda:
    def __init__(self, region: str) -> None:
        self.region, self._client, self._lock = region, None, threading.Lock()

    def invoke(self, **kwargs):
        with self._lock:
            if self._client is None:
                import boto3
                from botocore.config import Config

                self._client = boto3.Session(region_name=self.region).client(
                    "lambda", config=Config(connect_timeout=3, read_timeout=5, retries={"total_max_attempts": 1}))
        return self._client.invoke(**kwargs)


def brief_lookup(repository: RunRepository, profiles, snapshot: Callable[[], Snapshot]):
    """Latest succeeded ``portfolio_brief`` of this session and profile (api.md §3.12, D-37).

    Returns ``(run, stale)``: stale when the profile version or the data version changed since."""

    def find(session_id: str, profile_id: str, lang: str, window: dict | None = None):
        profile = profiles.get(session_id, profile_id)
        data_version = snapshot().data_version
        for run in repository.list(session_id):
            if run.kind != "portfolio_brief" or run.status != "succeeded" or run.profile_id != profile_id or run.lang != lang:
                continue
            if window is not None and run.input.window.to_wire() != window:
                continue
            record = repository.get(session_id, run.run_id)
            stale = record.profile_version != profile.version or run.data_version != data_version
            return record.run, stale
        return None, False

    return find


def build_run_services(settings: Settings, repository: RunRepository, profiles, snapshot: Callable[[], Snapshot], world=None,
                       gateway=None):
    """``(RunCoordinator, parser, brief finder)`` for ``Services``. ``gateway`` overrides the Bedrock
    gateway (tests inject a scripted one; production leaves it unset)."""
    from aplomb.agents.worker import make_handler

    gateway = gateway or model_gateway(settings)
    agent_services = build_agent_services(settings, repository, snapshot, world, gateway)
    if settings.environment == "aws":
        dispatcher = LambdaDispatcher(_LazyLambda(settings.region), settings.worker_function, repository)
    else:
        dispatcher = LocalDispatcher(make_handler(agent_services))
    find_brief = brief_lookup(repository, profiles, snapshot)

    def cached_brief(session_id: str, request: a.CreatePortfolioBriefRunRequest):
        window = request.window.to_wire() if request.window is not None else dict(FULL_WINDOW)
        run, stale = find_brief(session_id, request.profile_id, request.lang, window)
        return None if run is None or stale else run

    coordinator = RunCoordinator(
        repository, dispatcher,
        RunPreparerImpl(profiles, snapshot, models_configured=gateway is not None, world=world, settings=settings),
        cached_brief=cached_brief)
    parser = None
    if gateway is not None:
        from aplomb.agents.parser import RequestParser

        parser = RequestParser(gateway, profiles)
    return coordinator, parser, find_brief


def default_agent_services():
    """Lambda worker composition from the process environment (``aplomb.agents.worker.handler``)."""
    from .composition import create_repositories
    from .domain import SnapshotProvider, world_provider

    settings = Settings.from_env()
    snapshot = SnapshotProvider(settings)
    profile_repo, run_repo, _ = create_repositories(settings)
    world = world_provider(profile_repo, snapshot)
    return build_agent_services(settings, run_repo, snapshot, world)
