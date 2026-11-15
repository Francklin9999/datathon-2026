"""FastAPI HTTP boundary. Domain calculations are supplied through Services."""

import base64
import json
import logging
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError
from starlette.exceptions import HTTPException

from aplomb.contracts import CONTRACT_VERSION
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.contracts.base import FactId, ProfileId, RunId, SessionId
from aplomb.contracts.catalog import FeatureFlag

from .composition import create_store
from .errors import Conflict, NotFound, ServiceError, unavailable
from .limiter import SessionLimiter
from .queries import parameters
from .repositories import timestamp
from .services import Services
from .settings import Settings

log = logging.getLogger(__name__)


def run_verdict(run: m.Run):
    result = run.result
    if result is None:
        return None
    if result.kind == "decision":
        return result.decision.verdict
    if result.kind == "portfolio_brief":
        return result.portfolio_brief.verdict
    if result.kind == "replay":
        return result.replay.decision.verdict
    return None


def run_title(run: m.Run) -> m.I18nText:
    """Bilingual link text for a run, built by code from its pinned input (never model text)."""
    data = run.input
    if run.kind in {"decision", "replay"}:
        if data.request.type == "move":
            move = data.request.move
            en = fr = f"{move.ticker} +{move.size_pct:g} pts"
        else:
            goal = data.request.goal
            what = ", ".join([*goal.themes, *goal.asset_classes, *goal.tickers]) or "exposure"
            en, fr = f"Goal: {what}", f"Objectif : {what}"
        if run.kind == "replay":
            en, fr = f"{en}, as of {run.as_of}", f"{fr}, en date du {run.as_of}"
        return m.I18nText(en=en, fr=fr)
    if run.kind == "event_brief":
        result = run.result
        if result is not None and result.kind == "event_brief":
            title = result.event_brief.event.title
            return m.I18nText(en=f"Event brief: {title}", fr=f"Note d'événement : {title}")
        return m.I18nText(en="Event brief", fr="Note d'événement")
    labels = {
        "portfolio_brief": ("Portfolio brief", "Note de portefeuille"),
        "profile_draft": ("Profile draft", "Ébauche de profil"),
        "sabotage": ("Audit demonstration", "Démonstration d'audit"),
    }
    en, fr = labels.get(run.kind, (run.kind, run.kind))
    return m.I18nText(en=en, fr=fr)


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_env()
    services = services if services is not None else Services()
    app = FastAPI(
        title="Aplomb API",
        version=CONTRACT_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings, app.state.services = settings, services
    store = services.runs.repository.store if services.runs else create_store(settings)
    limiter = SessionLimiter(store)
    app.state.limiter = limiter

    def feature_enabled(flag: str) -> bool:
        return settings.features[FeatureFlag(flag)] and flag in services.capabilities

    def feature(flag: str) -> None:
        if not feature_enabled(flag):
            raise ServiceError("feature_disabled", f"Feature {flag} is disabled")

    def require(provider, name: str):
        if provider is None:
            raise unavailable(name)
        return provider

    def error_response(request: Request, error: ServiceError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_" + uuid.uuid4().hex)
        response = JSONResponse(error.envelope(request_id).to_wire(), status_code=error.status)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Aplomb-Data-Version"] = getattr(
            request.state, "data_version", settings.data_version
        )
        if error.code == "rate_limited":
            response.headers["Retry-After"] = str((error.details or {}).get("retryAfterSeconds", 1))
        return response

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError):
        return error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        fields = [
            {"path": ".".join(str(s) for s in item["loc"]), "problem": item["msg"]}
            for item in error.errors()
        ]
        return error_response(
            request,
            ServiceError("validation_error", "Request validation failed", {"fields": fields}),
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        if error.status_code == 404:
            mapped = NotFound()
        elif error.status_code in {400, 405, 413, 415, 422}:
            mapped = ServiceError("validation_error", "Unsupported request")
        else:
            mapped = ServiceError("internal", "The request could not be completed")
        return error_response(request, mapped)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Aplomb-Session", "Idempotency-Key", "Accept-Language"],
        expose_headers=["X-Request-Id", "X-Aplomb-Data-Version", "Retry-After"],
    )

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        request.state.request_id = "req_" + uuid.uuid4().hex
        try:
            total, chunks = 0, []
            async for chunk in request.stream():
                total += len(chunk)
                if total > settings.max_body_bytes:
                    raise ServiceError("validation_error", "Request body exceeds the size limit")
                chunks.append(chunk)
            request._body = b"".join(chunks)
            if (
                request._body
                and request.headers.get("content-type", "").split(";")[0] != "application/json"
            ):
                raise ServiceError("validation_error", "Content-Type must be application/json")
            response = await call_next(request)
            if request.method == "OPTIONS" and response.status_code >= 400:
                response = error_response(
                    request, ServiceError("validation_error", "CORS preflight rejected")
                )
        except ServiceError as exc:
            response = error_response(request, exc)
        except Exception as exc:
            log.error(
                "API request failed",
                extra={
                    "request_id": request.state.request_id,
                    "exception_type": type(exc).__name__,
                },
            )
            response = error_response(request, ServiceError("internal", "Internal service error"))
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers.setdefault(
            "X-Aplomb-Data-Version", getattr(request.state, "data_version", settings.data_version)
        )
        response.headers["Cache-Control"] = "no-store"
        # Boundary errors also need readable CORS headers for explicitly allowed callers.
        origin = request.headers.get("origin")
        if origin in settings.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Expose-Headers"] = (
                "X-Request-Id, X-Aplomb-Data-Version, Retry-After"
            )
            response.headers.append("Vary", "Origin")
        return response

    def session(x_aplomb_session: Annotated[str | None, Header()] = None) -> str:
        try:
            value = TypeAdapter(SessionId).validate_python(x_aplomb_session)
        except ValidationError as exc:
            raise ServiceError(
                "validation_error", "X-Aplomb-Session must be s_ plus a UUIDv4"
            ) from exc
        limiter.take(value, "requests", 30, 1)
        return value

    Session = Annotated[str, Depends(session)]

    @app.get("/v1/health", response_model=a.HealthResponse)
    def health():
        import time

        return a.HealthResponse(status="ok", time=timestamp(time.time()))

    @app.get("/v1/meta", response_model=m.Meta, response_model_exclude_unset=True)
    def meta():
        if settings.data_version == "unconfigured":
            raise unavailable("Pinned data snapshot configuration")
        universe = (
            services.datastore.universe_summary()
            if services.datastore
            else m.UniverseSummary(total=0, by_tier={"starter": 0, "extended": 0, "on_demand": 0})
        )
        return m.Meta(
            contract_version=CONTRACT_VERSION,
            data_version=settings.data_version,
            data_as_of=settings.data_as_of,
            environment=settings.environment,
            languages=["en", "fr"] if feature_enabled("bilingual") else ["en"],
            features={flag: feature_enabled(flag) for flag in FeatureFlag},
            models=m.ModelIds(strong=settings.model_strong, fast=settings.model_fast),
            universe=universe,
            disclaimer=m.I18nText(
                en="Simulation only. Fictional profiles. Not financial advice.",
                fr="Simulation uniquement. Profils fictifs. Ceci n'est pas un conseil financier.",
            ),
        )

    @app.get("/v1/assets", response_model=a.AssetsResponse, response_model_exclude_unset=True)
    def assets(request: Request, sid: Session, limit: int = Query(50, ge=1, le=500)):
        return require(services.datastore, "Asset datastore").assets(
            sid, parameters(request, "assets")
        )

    @app.get("/v1/assets/{ticker}", response_model=m.Asset, response_model_exclude_unset=True)
    def asset(ticker: str, sid: Session):
        return require(services.datastore, "Asset datastore").asset(sid, ticker)

    @app.post(
        "/v1/assets/{ticker}/fetch",
        response_model=a.FetchAssetResponse,
        response_model_exclude_unset=True,
    )
    def fetch(ticker: str, body: a.EmptyRequest, sid: Session):
        feature("on_demand_tickers")
        return require(services.datastore, "Asset ingestion").fetch(sid, ticker)

    @app.get(
        "/v1/assets/{ticker}/attention",
        response_model=a.AttentionResponse,
        response_model_exclude_unset=True,
    )
    def attention(ticker: str, sid: Session):
        return require(services.datastore, "Attention research").attention(sid, ticker)

    @app.get("/v1/profiles", response_model=a.ProfilesResponse, response_model_exclude_unset=True)
    def profiles(sid: Session):
        return a.ProfilesResponse(items=require(services.profiles, "Profile service").list(sid))

    @app.get(
        "/v1/profiles/{profile_id}", response_model=m.Profile, response_model_exclude_unset=True
    )
    def profile(profile_id: ProfileId, sid: Session):
        return require(services.profiles, "Profile service").get(sid, profile_id)

    @app.post(
        "/v1/profiles", status_code=201, response_model=m.Profile, response_model_exclude_unset=True
    )
    def create_profile(body: a.CreateProfileRequest, sid: Session):
        feature("profile_creator")
        if body.from_draft_run_id:
            require(services.runs, "Run service").get(sid, body.from_draft_run_id)
        return require(services.profiles, "Profile service").create(sid, body)

    @app.put(
        "/v1/profiles/{profile_id}", response_model=m.Profile, response_model_exclude_unset=True
    )
    def replace_profile(profile_id: ProfileId, body: a.UpdateProfileRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        provider.get(sid, profile_id)
        if body.from_draft_run_id:
            require(services.runs, "Run service").get(sid, body.from_draft_run_id)
        return provider.replace(sid, profile_id, body, body.version)

    @app.delete("/v1/profiles/{profile_id}", status_code=204)
    def delete_profile(profile_id: ProfileId, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        provider.get(sid, profile_id)
        provider.delete(sid, profile_id)
        return Response(status_code=204)

    @app.patch(
        "/v1/profiles/{profile_id}/rules/{rule_id}",
        response_model=a.RulePatchResponse,
        response_model_exclude_unset=True,
    )
    def patch_rule(
        profile_id: ProfileId, rule_id: m.RuleId, body: a.RulePatchRequest, sid: Session
    ):
        provider = require(services.profiles, "Profile service")
        provider.get(sid, profile_id)
        updated = provider.patch_rule(sid, profile_id, rule_id, body.threshold, body.enabled)
        rule = next((rule for rule in updated.rules if rule.rule_id == rule_id), None)
        if rule is None:
            raise NotFound()
        return a.RulePatchResponse(rule=rule, profile_version=updated.version)

    @app.post(
        "/v1/profiles/{profile_id}/rules/derive",
        response_model=a.DeriveRulesResponse,
        response_model_exclude_unset=True,
    )
    def derive(profile_id: ProfileId, body: a.DeriveRulesRequest, sid: Session):
        provider = require(services.profiles, "Profile service")
        provider.get(sid, profile_id)
        updated, facts = provider.rederive_rules(sid, profile_id, body.reset, body.window)
        return a.DeriveRulesResponse(
            rules=updated.rules, facts=facts, profile_version=updated.version
        )

    @app.put(
        "/v1/profiles/{profile_id}/portfolio",
        response_model=m.Profile,
        response_model_exclude_unset=True,
    )
    def portfolio(profile_id: ProfileId, body: a.UpdatePortfolioRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        provider.get(sid, profile_id)
        return provider.set_portfolio(sid, profile_id, body, body.version)

    def register_profile_read(path: str, method: str, response_model, flag: str | None = None):
        def read(profile_id: ProfileId, request: Request, sid: Session):
            if flag:
                feature(flag)
            provider = require(services.profiles, "Profile service")
            provider.get(sid, profile_id)
            return getattr(provider, method)(sid, profile_id, parameters(request, method))

        app.add_api_route(
            "/v1/profiles/{profile_id}/" + path,
            read,
            methods=["GET"],
            response_model=response_model,
            response_model_exclude_unset=True,
            name=f"profile_{method}",
        )

    register_profile_read("overview", "overview", a.OverviewResponse)
    register_profile_read("performance", "performance", a.PerformanceResponse)
    register_profile_read("frontier", "frontier", a.FrontierResponse, "frontier_chart")
    register_profile_read("brief", "brief", a.CachedBriefResponse)

    @app.post(
        "/v1/requests/parse", response_model=m.ParsedRequest, response_model_exclude_unset=True
    )
    def parse(body: a.ParseRequest, sid: Session):
        require(services.profiles, "Profile service").get(sid, body.profile_id)
        return require(services.parser, "Request parser").parse(sid, body)

    @app.post("/v1/check", response_model=m.CheckResult, response_model_exclude_unset=True)
    def check(body: a.CheckRequest, sid: Session):
        require(services.profiles, "Profile service").get(sid, body.profile_id)
        return require(services.checks, "Deterministic check service").check(sid, body)

    @app.post(
        "/v1/check/batch", response_model=a.BatchCheckResponse, response_model_exclude_unset=True
    )
    def batch(body: a.BatchCheckRequest, request: Request, sid: Session):
        results = []
        for item in body.items:
            try:
                require(services.profiles, "Profile service").get(sid, item.profile_id)
                result = require(services.checks, "Deterministic check service").check(sid, item)
                results.append(m.CheckResult.model_validate(result))
            except ServiceError as exc:
                results.append(exc.envelope(request.state.request_id))
            except Exception as exc:
                log.error(
                    "Batch item failed",
                    extra={
                        "exception_type": type(exc).__name__,
                        "request_id": request.state.request_id,
                    },
                )
                results.append(
                    ServiceError("internal", "Internal service error").envelope(
                        request.state.request_id
                    )
                )
        return a.BatchCheckResponse(results=results)

    @app.post(
        "/v1/runs",
        status_code=202,
        response_model=a.QueuedRunResponse | a.CachedRunResponse,
        response_model_exclude_unset=True,
    )
    def create_run(
        body: a.CreateRunRequest,
        response: Response,
        request: Request,
        sid: Session,
        idempotency_key: Annotated[str | None, Header()] = None,
    ):
        flags = {
            "replay": "time_machine",
            "profile_draft": "profile_creator",
            "event_brief": "world_explorer",
        }
        if body.kind in flags:
            feature(flags[body.kind])
        if body.kind in {"decision", "replay"} and body.request.type == "goal":
            feature("goal_requests")
        if body.lang == "fr":
            feature("bilingual")
        limiter.take(sid, "run-creations", 6, 60)
        result = require(services.runs, "Run workflow").create(sid, body, idempotency_key)
        request.state.data_version = services.runs.get(sid, result.run_id).data_version
        if result.status == "succeeded":
            response.status_code = 200
        return result

    @app.get("/v1/runs/{run_id}", response_model=m.Run, response_model_exclude_unset=True)
    def get_run(
        run_id: RunId, request: Request, sid: Session, since: int | None = Query(None, ge=0)
    ):
        run = require(services.runs, "Run workflow").get(sid, run_id, since)
        request.state.data_version = run.data_version
        return run

    @app.get("/v1/runs", response_model=a.RunsResponse, response_model_exclude_unset=True)
    def list_runs(
        sid: Session,
        profileId: ProfileId | None = None,
        kind: m.RunKind | None = None,
        limit: int = Query(20, ge=1, le=100),
        cursor: str | None = None,
    ):
        runs = require(services.runs, "Run workflow").repository.list(sid)
        runs = [
            run
            for run in runs
            if (profileId is None or run.profile_id == profileId)
            and (kind is None or run.kind == kind)
        ]
        if cursor:
            try:
                after = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if (
                    not isinstance(after, list)
                    or len(after) != 2
                    or not all(isinstance(x, str) for x in after)
                ):
                    raise ValueError()
                runs = [run for run in runs if (run.created_at, run.run_id) < tuple(after)]
            except Exception as exc:
                raise ServiceError("validation_error", "Invalid cursor") from exc
        page = runs[:limit]
        next_cursor = (
            base64.urlsafe_b64encode(
                json.dumps([page[-1].created_at, page[-1].run_id]).encode()
            ).decode()
            if len(runs) > limit
            else None
        )
        items = [
            a.RunSummary(
                run_id=run.run_id,
                kind=run.kind,
                status=run.status,
                profile_id=run.profile_id,
                created_at=run.created_at,
                title=run_title(run),
                verdict=run_verdict(run),
                duration_ms=run.usage.duration_ms
                if run.status in {"succeeded", "failed", "cancelled"}
                else None,
            )
            for run in page
        ]
        return a.RunsResponse(items=items, next_cursor=next_cursor)

    @app.post(
        "/v1/runs/{run_id}/answers",
        status_code=202,
        response_model=a.AnswerResponse,
        response_model_exclude_unset=True,
    )
    def answer(run_id: RunId, body: a.AnswerRequest, request: Request, sid: Session):
        request.state.data_version = (
            require(services.runs, "Run workflow").get(sid, run_id).data_version
        )
        return require(services.runs, "Run workflow").answer(sid, run_id, body)

    @app.post(
        "/v1/runs/{run_id}/cancel",
        response_model=a.CancelResponse,
        response_model_exclude_unset=True,
    )
    def cancel(run_id: RunId, request: Request, sid: Session):
        request.state.data_version = (
            require(services.runs, "Run workflow").get(sid, run_id).data_version
        )
        return require(services.runs, "Run workflow").cancel(sid, run_id)

    @app.get(
        "/v1/runs/{run_id}/facts/{fact_id}",
        response_model=a.FactResponse,
        response_model_exclude_unset=True,
    )
    def fact(run_id: RunId, fact_id: FactId, request: Request, sid: Session):
        run = require(services.runs, "Run workflow").get(sid, run_id)
        request.state.data_version = run.data_version
        if fact_id not in run.facts:
            raise NotFound()
        return require(services.fact_resolver, "Ledger fact usage resolver")(sid, run, fact_id)

    @app.post(
        "/v1/runs/{run_id}/sabotage",
        status_code=202,
        response_model=a.QueuedRunResponse,
        response_model_exclude_unset=True,
    )
    def sabotage(run_id: RunId, body: a.SabotageRequest, request: Request, sid: Session):
        run = require(services.runs, "Run workflow").get(sid, run_id)
        request.state.data_version = run.data_version
        feature("sabotage_demo")
        if run.kind != "decision" or run.status != "succeeded":
            raise Conflict("Sabotage requires a succeeded decision")
        return require(services.sabotage, "Sabotage workflow")(sid, run, body)

    @app.post(
        "/v1/runs/{run_id}/reveal", response_model=m.RevealResult, response_model_exclude_unset=True
    )
    def reveal(run_id: RunId, body: a.RevealRequest, request: Request, sid: Session):
        run = require(services.runs, "Run workflow").get(sid, run_id)
        request.state.data_version = run.data_version
        feature("time_machine")
        if run.kind != "replay" or run.status != "succeeded":
            raise Conflict("Reveal requires a succeeded replay")
        return require(services.replay, "Historical replay").reveal(sid, run, body)

    def register_world(path: str, method: str, response_model, flag: str = "world_explorer"):
        def read(request: Request, sid: Session):
            feature("world_explorer")
            feature(flag)
            query = parameters(request, f"world_{method}")
            if "profileId" in query:
                require(services.profiles, "Profile service").get(sid, query["profileId"])
            return getattr(require(services.world, "World service"), method)(sid, query)

        app.add_api_route(
            "/v1/world/" + path,
            read,
            methods=["GET"],
            response_model=response_model,
            response_model_exclude_unset=True,
            name=f"world_{method}",
        )

    register_world("layers", "layers", a.WorldLayersResponse)
    register_world("events", "events", a.WorldEventsResponse)
    register_world("exposure", "exposure", a.WorldExposureResponse)
    register_world("facilities", "facilities", a.FacilitiesResponse, "world_layer_facilities")
    register_world("hazards", "hazards", a.HazardsResponse, "world_layer_hazards")

    @app.get(
        "/v1/world/events/{event_id}",
        response_model=a.WorldEventResponse,
        response_model_exclude_unset=True,
    )
    def world_event(event_id: str, request: Request, sid: Session):
        feature("world_explorer")
        query = parameters(request, "world_event")
        if "profileId" in query:
            require(services.profiles, "Profile service").get(sid, query["profileId"])
        return require(services.world, "World service").event(sid, event_id, query)

    @app.get(
        "/v1/world/countries/{iso3}",
        response_model=a.WorldCountryResponse,
        response_model_exclude_unset=True,
    )
    def country(iso3: str, request: Request, sid: Session):
        feature("world_explorer")
        query = parameters(request, "world_country")
        if "profileId" in query:
            require(services.profiles, "Profile service").get(sid, query["profileId"])
        return require(services.world, "World service").country(sid, iso3, query)

    @app.get(
        "/v1/replay/presets",
        response_model=a.ReplayPresetsResponse,
        response_model_exclude_unset=True,
    )
    def presets(sid: Session):
        feature("time_machine")
        return require(services.replay, "Historical replay").presets(sid)

    @app.get("/v1/datasets", response_model=a.DatasetsResponse, response_model_exclude_unset=True)
    def datasets(sid: Session):
        return require(services.datastore, "Dataset passports").datasets(sid)

    @app.get(
        "/v1/datasets/{dataset_id}",
        response_model=m.DatasetPassport,
        response_model_exclude_unset=True,
    )
    def dataset(dataset_id: str, sid: Session):
        return require(services.datastore, "Dataset passports").dataset(sid, dataset_id)

    return app


def create_default_app(settings: Settings | None = None) -> FastAPI:
    """The exported application: configured snapshot plus the implemented domain providers."""
    from .domain import default_services

    settings = settings if settings is not None else Settings.from_env()
    return create_app(settings, default_services(settings))


app = create_default_app()
