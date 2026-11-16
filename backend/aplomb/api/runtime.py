"""Run composition for the exported application: preparer, worker services and dispatch.

Connects the tracks that were built against protocols: T03 repositories/dispatcher, T08 workflow,
T05–T07 code controls, T10 ledger/signing, T09 research tools, T11 world events and T12 replay
metadata. Nothing here calls a model, AWS or a public source at import or at app creation.

A run pins its inputs at creation (``PreparedRun.private``): the effective profile, the snapshot
version, the as-of date and the gate mode. The worker reopens exactly that context.
"""

from __future__ import annotations

import json
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
        # ``dataAsOf`` is the pinned snapshot's own end date (the worker reopens that version with
        # it); ``asOf`` is the information cutoff of the run, which can differ (replay, event brief).
        base = {"dataVersion": snap.data_version, "dataAsOf": snap.data_as_of, "asOf": snap.data_as_of,
                "mode": "current", **self._pins(snap)}
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
        if request.kind == "rebalance":
            from aplomb.optimizer.check import CheckServiceImpl

            target = a.RebalanceRequest(profile_id=request.profile_id, profile_version=request.profile_version,
                                        positions=request.positions, window=request.window)
            started = _stamp(self.clock)
            started_mono = time.monotonic()
            comparison = CheckServiceImpl(self.profiles, lambda: snap).rebalance(session_id, target)
            receipt = {"startedAt": started, "durationMs": max(0, (time.monotonic() - started_mono) * 1000)}
            payload = {"kind": "rebalance", "profileVersion": request.profile_version,
                       "positions": [position.to_wire() for position in request.positions], "window": window}
            return PreparedRun(payload, snap.data_as_of, snap.data_version,
                               {**base, "profile": profile.to_wire(), "rebalance": comparison.to_wire(),
                                "rebalanceReceipt": receipt}, profile.version)
        if request.kind == "replay":
            from aplomb.timemachine import validate_asof

            self._check_request(snap, request.request)
            ctx = validate_asof(request.as_of, profile, snap, request.request, _stamp(self.clock))
            self._check_move(snap, ctx.profile, request.request, ctx.as_of, "historical", window)
            payload = {"kind": "replay", "request": request.request.to_wire(), "asOf": ctx.as_of, "window": window}
            private = {"dataVersion": snap.data_version, "dataAsOf": snap.data_as_of, "asOf": ctx.as_of,
                       "mode": "historical", **self._pins(snap),
                       "profile": ctx.profile.to_wire(), "revealAvailableUntil": ctx.reveal_available_until}
            return PreparedRun(payload, ctx.as_of, snap.data_version, private, profile.version)
        if request.kind == "portfolio_brief":
            private = {**base, "profile": profile.to_wire()}
            if self.settings is not None:
                from aplomb.agents.runtime import brief_runtime_identity

                # The brief cache compares this, not the full signature: a code-only release keeps briefs.
                private["briefIdentity"] = brief_runtime_identity(self.settings)
            return PreparedRun({"kind": "portfolio_brief", "window": window}, snap.data_as_of, snap.data_version,
                               private, profile.version)
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
                             subject_id=profile.profile_id, created_at=_stamp(self.clock), window=window, custom_themes=profile.investor_context.custom_theme_definitions if profile.investor_context else ())
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
            for name, (args, function) in research_tool_handlers(service).items():
                registry.register(name, args, function)
    if world is not None:
        class SearchEventsArgs(BaseModel):
            """Events from Aplomb's own cached world dataset up to the run cutoff, most important first: title,
            date, category, related countries (ISO3) and tickers, and source links. A listed event is not
            evidence of a financial effect."""

            model_config = ConfigDict(extra="forbid")
            q: str | None = Field(default=None, max_length=200)
            country: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
            ticker: str | None = Field(default=None, max_length=20)
            start: str | None = None
            end: str | None = None
            limit: int = Field(default=20, ge=1, le=50)

        def search_events(ctx, **args):
            # The registry already refuses research tools in a historical run; the service's own capture
            # gate is the second safeguard (current-only bundled events are not known at an earlier date).
            found = world.search_events(as_of=str(ctx.as_of), historical=ctx.historical, **args)
            data = {"events": [{"eventId": e["eventId"], "title": e["title"], "occurredAt": e["occurredAt"],
                                "category": e["category"], "countries": e["relatedCountries"], "tickers": e["relatedTickers"],
                                "sources": [{"publisher": s["publisher"], "url": s["url"]} for s in e["sources"]]}
                               for e in found],
                    "note": "Events from the cached dataset; a listed event is not evidence of a financial effect."}
            return ToolResult(True, f"{len(found)} cached event(s)", data=data)

        registry.register("world.search_events", SearchEventsArgs, search_events)
        if settings.features[FeatureFlag.WORLD_LAYER_FACILITIES] and hasattr(world, "facilities"):
            # contracts/tools.md §5: offered only with the world dataset and the world_layer_facilities flag,
            # and only in a run whose cutoff is on or after the capture day: before it the tool could only
            # answer an evidence gap, so it is not offered and no research call is spent on it.
            registry.register("emissions.facilities", *facilities_tool(world), available=facility_capture_known)
    return registry


def facility_capture_known(ctx) -> bool:
    """Whether the packaged facility capture is known at the run's cutoff (capture day <= asOf).
    Reads only the small manifest; the handler still checks the capture's integrity."""
    from aplomb.world.facilities import DIRECTORY

    try:
        captured = json.loads((DIRECTORY / "facilities_manifest.json").read_text(encoding="utf-8")).get("capturedAt")
    except (ValueError, OSError, AttributeError):
        return True  # the handler reports the unreadable capture as an evidence gap
    return isinstance(captured, str) and captured[:10] <= str(ctx.as_of)


# Fixed by the facility capture (world/facilities.py normalize, world/bundle/facilities_manifest.json).
FACILITY_SOURCE = "Environment and Climate Change Canada, Greenhouse Gas Reporting Program"
FACILITY_LICENCE = "Open Government Licence – Canada"
FACILITY_TOOL_ROWS = 10


def facilities_tool(world):
    """``(Args, handler)`` for ``emissions.facilities`` over the world service's facility capture.

    Each reported emission becomes an observed ledger fact (``emissions.facility_total``, tonnes CO2e,
    subject the facility's country with the facility ID as variant, available from the capture time),
    so the model only sees figures with fact IDs (tools.md §1 rule 4). The capture has no historical
    vintages: a run whose cutoff is before the capture day gets an evidence gap, not a figure that the
    audit's availability check (A11) would reject."""
    from pydantic import BaseModel, ConfigDict, Field

    from aplomb.agents.registry import ToolResult

    class FacilitiesArgs(BaseModel):
        """Facilities in Aplomb's cached Canadian greenhouse-gas registry capture (ECCC GHGRP, latest
        completed reporting year) whose facility or reporting-company name contains the given words,
        largest emitters first: facility name, reporting company, country, reporting year and reported
        emissions in tonnes CO2e, each figure registered as a fact. No listed security is linked to any
        facility, so pass a company name, not a ticker. A reporting-company name is not an issuer, owner or
        operator link. A run whose cutoff is before the capture day gets no figures."""

        model_config = ConfigDict(extra="forbid")
        ticker_or_operator: str = Field(min_length=1, max_length=200,
                                        description="Words of a facility or reporting-company name.")
        country: str | None = Field(default=None, pattern=r"^[A-Z]{3}$",
                                    description="ISO3 country code; the capture covers CAN only.")

    def facilities(ctx, ticker_or_operator, country=None):
        try:
            found = world.facilities(ctx.run_id, {"q": ticker_or_operator, "country": [country] if country else None,
                                                  "limit": FACILITY_TOOL_ROWS})
        except ServiceError as exc:
            return ToolResult(False, "Facility emissions are unavailable; evidence gap remains",
                              error=f"facility_dataset_unavailable: {exc.message}"[:300])
        captured = found.captured_at
        if captured is None or found.data_version is None or captured[:10] > str(ctx.as_of):
            # Same rule as the world service's current-only captures: not known at an earlier cutoff.
            return ToolResult(False, "Facility capture is later than the run cutoff; evidence gap remains",
                              error="facility_capture_after_cutoff")
        rows = []
        # All of a call's facts or none (the research tools register the same way).
        with ctx.ledger.transaction():
            for item in found.items:
                rows.append(_facility_row(ctx, item, captured, found.data_version))
        data = {"facilities": rows, "matched": found.total, "shown": len(rows), "capturedAt": captured,
                "note": "Facility-reported annual emissions, Canada only (ECCC GHGRP). A reporting-company name "
                        "does not establish operator or owner status, a listed security or a financial effect."}
        return ToolResult(True, f"{found.total} matching facilit{'y' if found.total == 1 else 'ies'}; "
                                f"{len(rows)} shown", fact_ids=[r["emissionsTco2e"]["factId"] for r in rows], data=data)

    return FacilitiesArgs, facilities


def _facility_row(ctx, item, captured: str, data_version: str) -> dict:
    """One facility as the model sees it, its reported emissions registered as a fact first."""
    year = item.reporting_year
    fact_id = ctx.ledger.add_fact({
        "kind": "observed", "metric": "emissions.facility_total",
        "label": {"en": f"Reported emissions in {year}, tonnes CO2e: {item.name}",
                  "fr": f"Émissions déclarées en {year}, tonnes éq. CO2 : {item.name}"},
        "value": item.emissions_tco2e, "unit": "count", "currency": None,
        # FactSubject has no facility type: the facility's country, the facility ID as variant.
        "subject": {"type": "country", "id": item.country_iso3, "variant": item.facility_id},
        "period": {"start": f"{year}-01-01", "end": f"{year}-12-31"},
        "window": None, "asOf": str(ctx.as_of), "availableAt": captured,
        "method": {"id": "M_OBSERVED_ROW",
                   "description": {"en": "Value read from one dataset row.",
                                   "fr": "Valeur lue dans une ligne d'un jeu de données."},
                   "params": {"facilityId": item.facility_id, "registry": item.registry,
                              "availabilityBasis": "first captured; original vintage unknown"}},
        "inputs": [], "nObs": 1,
        "sources": [{"datasetId": "emissions_facilities", "dataVersion": data_version,
                     "sourceName": FACILITY_SOURCE, "sourceUrl": item.source_url,
                     "retrievedOn": captured[:10], "licence": FACILITY_LICENCE, "rowsRead": 1}],
        "limitations": ["LIM_IMPACT_NOT_ESTABLISHED"],
        "createdBy": "world",
    })
    return {"facilityId": item.facility_id, "name": item.name, "reportingCompany": item.operator,
            "countryIso3": item.country_iso3, "reportingYear": year,
            "emissionsTco2e": {"value": item.emissions_tco2e, "unit": "count", "factId": fact_id}}


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

    # The Guardrail applies only when its flag is on (the Settings validator then requires the ID and
    # version): a configured ID with the flag off is reported as not applied, like /meta reports it.
    guardrails_on = settings.features[FeatureFlag.GUARDRAILS] and settings.guardrail_id and settings.guardrail_version
    policy = BedrockOutputPolicy(settings) if guardrails_on else None
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


def brief_lookup(repository: RunRepository, profiles, snapshot: Callable[[], Snapshot], settings: Settings | None = None):
    """Latest succeeded ``portfolio_brief`` of this session and profile (api.md §3.12, D-37).

    Returns ``(run, stale)``: stale when the profile version, the data version or the pinned
    manifest digest changed since, or (with ``settings``) when the brief was prepared under another
    runtime configuration (models, fallback, Guardrail, limits, flags, data prefix). The build
    revision alone never makes a brief stale: a code-only redeploy keeps the briefs already written.
    A record written before ``briefIdentity`` was pinned is not compared on runtime, as that release
    did not: its full runtime signature carries the build revision, so it could never match a new
    release and every existing brief would turn stale on the first redeploy."""
    from aplomb.agents.runtime import brief_runtime_identity, manifest_hash

    identity = brief_runtime_identity(settings) if settings is not None else None

    def other_runtime(private: dict) -> bool:
        if identity is None or "briefIdentity" not in private:
            return False
        return private["briefIdentity"] != identity

    def find(session_id: str, profile_id: str, lang: str, window: dict | None = None):
        profile = profiles.get(session_id, profile_id)
        snap = snapshot()
        data_version = snap.data_version
        for run in repository.list(session_id):
            if run.kind != "portfolio_brief" or run.status != "succeeded" or run.profile_id != profile_id or run.lang != lang:
                continue
            if window is not None and run.input.window.to_wire() != window:
                continue
            record = repository.get(session_id, run.run_id)
            stale = (record.profile_version != profile.version or run.data_version != data_version
                     or record.private.get("manifestHash") != manifest_hash(snap)
                     or other_runtime(record.private))
            return record.run, stale
        return None, False

    return find


def build_run_services(settings: Settings, repository: RunRepository, profiles, snapshot: Callable[[], Snapshot], world=None,
                       gateway=None):
    """``(RunCoordinator, parser, brief finder)`` for ``Services``. ``gateway`` overrides the Bedrock
    gateway (tests inject a scripted one; production leaves it unset)."""
    from aplomb.agents.worker import make_handler

    gateway = gateway or model_gateway(settings)
    if settings.environment == "aws":
        # The worker Lambda builds its own AgentServices (default_agent_services); the API never runs one.
        dispatcher = LambdaDispatcher(_LazyLambda(settings.region), settings.worker_function, repository)
    else:
        dispatcher = LocalDispatcher(make_handler(build_agent_services(settings, repository, snapshot, world, gateway)))
    find_brief = brief_lookup(repository, profiles, snapshot, settings)

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
    profile_repo, run_repo = create_repositories(settings)
    world = world_provider(profile_repo, snapshot)
    return build_agent_services(settings, run_repo, snapshot, world)
