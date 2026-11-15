"""Application composition: frozen inputs cross the API/worker boundary, never clients."""

import hashlib
import json

from aplomb.api.errors import ServiceError
from aplomb.api.services import PreparedRun
from aplomb.contracts import api as a
from aplomb.contracts import models as m


def manifest_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot.manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def runtime_signature(settings):
    context = {"runtime": "2026-11-14.2", "strongModel": settings.model_strong, "fastModel": settings.model_fast,
               "guardrail": [settings.guardrail_id, settings.guardrail_version], "features": settings.features,
               "limits": [settings.run_hard_seconds, settings.max_llm_calls, settings.max_research_calls, settings.max_revise],
               "dataPrefix": settings.data_prefix}
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()


class RunPreparer:
    def __init__(self, settings, profiles, snapshot):
        self.settings, self.profiles, self.snapshot = settings, profiles, snapshot

    def __call__(self, session_id, request):
        if request.kind not in {"decision", "portfolio_brief", "profile_draft"}:
            raise ServiceError("feature_disabled", "This workflow is not enabled")
        snap = self.snapshot()
        private = {"dataVersion": snap.data_version, "asOf": snap.data_as_of,
                   "manifestHash": manifest_hash(snap), "runtimeSignature": runtime_signature(self.settings),
                   "workerFunction": self.settings.worker_function}
        if request.kind == "profile_draft":
            payload = {"kind": request.kind, "text": request.text,
                       "fields": request.fields.to_wire() if request.fields else {}}
            version = None
        else:
            profile = self.profiles.get(session_id, request.profile_id)
            private["profile"] = profile.to_wire()
            version = profile.version
            payload = {"kind": request.kind, "window": (request.window or m.WindowSpec(code="full")).to_wire()}
            if request.kind == "decision":
                payload.update(request=request.request.to_wire(), originalText=request.original_text)
                if request.request.type == "move":
                    snap.gate(snap.data_as_of, "current").universe().get(request.request.move.ticker)
        return PreparedRun(payload, snap.data_as_of, snap.data_version, private, version)


class BriefProfiles:
    """Delegate profile operations; cache only exact pinned user/profile/window/language."""
    def __init__(self, profiles, repository, snapshot, settings=None):
        self.profiles, self.repository, self.snapshot = profiles, repository, snapshot
        self.signature = runtime_signature(settings) if settings else None

    def __getattr__(self, name):
        return getattr(self.profiles, name)

    def cached(self, session_id, request):
        profile = self.profiles.get(session_id, request.profile_id)
        snapshot = self.snapshot()
        version = snapshot.data_version
        key = f"SESSION#{session_id}#PROFILE#{profile.profile_id}#V{profile.version}#portfolio_brief#{version}"
        candidates = self.repository.store.query("runs", key, "byProfile")
        window = (request.window or m.WindowSpec(code="full")).to_wire()
        for item in sorted(candidates, key=lambda x: x["run"]["createdAt"], reverse=True):
            record = self.repository.get(session_id, item["run"]["runId"])
            run = record.run
            if (record.profile_version != profile.version or run.profile_id != profile.profile_id
                    or run.data_version != version or record.private.get("manifestHash") != manifest_hash(snapshot)):
                continue
            if self.signature and record.private.get("runtimeSignature") != self.signature:
                continue
            if (run.status == "succeeded" and run.kind == "portfolio_brief" and run.lang == request.lang
                    and run.input.window.to_wire() == window):
                return run
        return None

    def brief(self, session_id, profile_id, query):
        window = {"code": query.get("window", "full")}
        if window["code"] == "custom":
            window.update(start=query["start"], end=query["end"])
        request = a.CreatePortfolioBriefRunRequest(kind="portfolio_brief", profile_id=profile_id,
                                                  lang=query.get("lang", "en"), window=window)
        return a.CachedBriefResponse(run=self.cached(session_id, request), stale=False)


def make_worker_services(settings, store=None, gateway=None):
    from aplomb.api.composition import create_repositories
    from aplomb.api.domain import SnapshotProvider
    from aplomb.ledger import Ledger
    from aplomb.optimizer.services import DecisionControls

    from .guardrails import BedrockOutputPolicy
    from .models import StrandsBedrockGateway
    from .signing import sign_decision
    from .workflow import AgentServices

    _, repository, _ = create_repositories(settings, store)

    def gate(private):
        pinned = settings.model_copy(update={"data_version": private["dataVersion"], "data_as_of": private["asOf"]})
        snapshot = SnapshotProvider(pinned)()
        if manifest_hash(snapshot) != private["manifestHash"]:
            raise ValueError("Pinned snapshot manifest changed")
        return snapshot.gate(private["asOf"], "current")

    model_gateway = gateway or StrandsBedrockGateway(strong_model=settings.model_strong,
                                                    fast_model=settings.model_fast, region=settings.region)
    policy = BedrockOutputPolicy(settings) if settings.guardrail_id and settings.guardrail_version else None
    return AgentServices(repository, model_gateway, controls=DecisionControls(), ledger_factory=Ledger,
                         signer=sign_decision, gate_factory=gate, guardrail=policy,
                         runtime_signature=runtime_signature(settings), max_llm_calls=settings.max_llm_calls,
                         max_research_calls=settings.max_research_calls, max_revisions=settings.max_revise)


def connect_services(settings, profiles, snapshot, repository, store):
    from aplomb.api.dispatcher import LambdaDispatcher, LocalDispatcher
    from aplomb.api.services import RunCoordinator

    from .models import StrandsBedrockGateway
    from .parser import RequestParser
    from .worker import make_handler

    gateway = StrandsBedrockGateway(strong_model=settings.model_strong, fast_model=settings.model_fast,
                                   region=settings.region)
    if settings.environment == "aws":
        # SDK clients are created on the first dispatch, never during module import.
        class LazyDispatcher:
            def dispatch(self, run_id, generation):
                import boto3
                from botocore.config import Config
                client = boto3.client("lambda", region_name=settings.region,
                                      config=Config(connect_timeout=3, read_timeout=5, retries={"total_max_attempts": 1}))
                LambdaDispatcher(client, settings.worker_function, repository).dispatch(run_id, generation)
        dispatcher = LazyDispatcher()
    else:
        dispatcher = LocalDispatcher(make_handler(make_worker_services(settings, store, gateway)))
    wrapped = BriefProfiles(profiles, repository, snapshot, settings)
    runs = RunCoordinator(repository, dispatcher, RunPreparer(settings, wrapped, snapshot), cached_brief=wrapped.cached)
    return wrapped, runs, RequestParser(gateway, wrapped)
