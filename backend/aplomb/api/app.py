"""FastAPI HTTP boundary. Domain calculations are supplied through Services."""

import base64
import json
import logging
import time
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
    if result.kind == "rebalance":
        return result.rebalance.verdict_after
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
    if run.kind == "rebalance":
        return m.I18nText(en="Target allocation review", fr="Examen de la répartition cible")
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
    app.state.services = services
    store = services.runs.repository.store if services.runs else create_store(settings)
    from aplomb.intelligence.discovery import EntityDiscovery
    entity_discovery = EntityDiscovery(store)
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
            mapped = ServiceError("validation_error", str(error.detail)[:1000] if error.status_code == 422 and isinstance(error.detail, str) else "Unsupported request")
        else:
            mapped = ServiceError("internal", "The request could not be completed")
        return error_response(request, mapped)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Aplomb-Session", "Idempotency-Key", "Accept-Language"],
        expose_headers=["X-Request-Id", "X-Aplomb-Data-Version", "X-Aplomb-Build", "Retry-After"],
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
        if settings.build_revision:
            response.headers["X-Aplomb-Build"] = settings.build_revision
        response.headers["Cache-Control"] = "no-store"
        # Boundary errors also need readable CORS headers for explicitly allowed callers.
        origin = request.headers.get("origin")
        if origin in settings.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Expose-Headers"] = (
                "X-Request-Id, X-Aplomb-Data-Version, X-Aplomb-Build, Retry-After"
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
    from aplomb.quant.scenario_api import router as scenario_router
    app.include_router(scenario_router, dependencies=[Depends(session)])
    from aplomb.datastore.financial_inputs_api import router as financial_inputs_router
    app.include_router(financial_inputs_router, dependencies=[Depends(session)])
    from aplomb.datastore.financial_provider_api import make_router as financial_provider_router
    app.include_router(financial_provider_router(store, session))
    app.state.financial_capture_store = store
    from aplomb.quant.joint_plan_api import router as joint_plan_router
    app.include_router(joint_plan_router, dependencies=[Depends(session)])
    from aplomb.quant.expanded_api import make_router as expanded_quant_router
    app.include_router(expanded_quant_router(session))

    from aplomb.intelligence.golden_routes import golden_router
    app.include_router(golden_router(store, session))

    from aplomb.research.keyed_markets import keyed_market_router
    app.include_router(keyed_market_router(store, session))
    from aplomb.intelligence.sentiment_routes import sentiment_router
    app.include_router(sentiment_router(store, session))
    from aplomb.intelligence.capability_routes import capability_router
    app.include_router(capability_router(settings, session))
    from aplomb.intelligence.registry_routes import registry_router
    app.include_router(registry_router(store, session))
    from aplomb.intelligence.wikidata_routes import wikidata_router
    app.include_router(wikidata_router(settings, store, session))
    from aplomb.intelligence.master_routes import master_router
    app.include_router(master_router(settings, store, session))
    from aplomb.intelligence.openfigi import openfigi_router
    app.include_router(openfigi_router(store, session))
    from aplomb.timemachine.pit_routes import point_in_time_router
    app.include_router(point_in_time_router(session, feature))
    from aplomb.intelligence.defi_routes import defi_router
    app.include_router(defi_router(store, session))
    from aplomb.intelligence.eu_routes import eu_router
    app.include_router(eu_router(store, session))

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
        served = getattr(services.datastore, "current_version", None) if services.datastore else None
        data_version, data_as_of = served() if served else (settings.data_version, settings.data_as_of)
        return m.Meta(
            contract_version=CONTRACT_VERSION,
            reporting_currencies=services.datastore.reporting_currencies() if services.datastore and hasattr(services.datastore, "reporting_currencies") else ["CAD", "USD"],
            data_version=data_version,
            data_as_of=data_as_of,
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

    @app.get("/v1/intelligence/entities", response_model=a.EntitySearchResponse, response_model_exclude_unset=True)
    def entity_candidates(sid: Session, q: str = Query(min_length=2, max_length=120), limit: int = Query(10, ge=1, le=20)):
        from aplomb.intelligence import GLEIFError
        from aplomb.intelligence.discovery import DiscoveryStorageError
        try:
            return entity_discovery.search(sid, q, limit=limit)
        except (GLEIFError, DiscoveryStorageError, ValidationError) as exc:
            raise unavailable("GLEIF entity discovery") from exc
        except ValueError as exc:
            raise ServiceError("validation_error", str(exc)) from exc

    @app.get("/v1/intelligence/listings")
    def instrument_listings(sid: Session, as_of: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
                            ticker: str | None = None, mic: str | None = None, isin: str | None = None,
                            provider: str | None = None, provider_asset_id: str | None = None):
        from datetime import date

        from aplomb.intelligence.master import listing_wire
        from aplomb.intelligence.master_repository import InstrumentRepository
        try:
            cutoff = date.fromisoformat(as_of)
            rows = InstrumentRepository(store, sid).snapshot(cutoff).discover(
                as_of=cutoff, ticker=ticker, mic=mic, isin=isin, provider=provider,
                provider_asset_id=provider_asset_id)
            return {"items": [listing_wire(row) for row in rows], "total": len(rows)}
        except ValueError as exc:
            raise ServiceError("validation_error", str(exc)) from exc

    @app.get("/v1/intelligence/listings/{listing_id}")
    def instrument_detail(listing_id: str, sid: Session, as_of: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$")):
        from datetime import date

        from aplomb.intelligence.master import listing_wire
        from aplomb.intelligence.master_repository import InstrumentRepository
        try:
            cutoff = date.fromisoformat(as_of)
            record = InstrumentRepository(store, sid).snapshot(cutoff).detail(listing_id, as_of=cutoff)
        except ValueError as exc:
            raise ServiceError("validation_error", "Invalid as-of date") from exc
        if record is None:
            raise NotFound("Listing not found or unavailable at cutoff")
        return listing_wire(record)

    @app.get("/v1/intelligence/sec-data-library")
    def sec_data_library(sid: Session):
        from aplomb.intelligence.sec_structured import SecFeedError, capture_data_library
        try:
            return capture_data_library(store, sid)
        except SecFeedError as exc:
            raise unavailable("SEC DERA data library") from exc

    @app.get("/v1/intelligence/sec-structured")
    def sec_structured(sid: Session):
        from aplomb.intelligence.sec_structured import SecFeedError, capture
        try:
            return capture(store, sid)
        except SecFeedError as exc:
            raise unavailable("SEC structured disclosure feed") from exc

    @app.get("/v1/intelligence/coinmetrics/{asset}")
    def coinmetrics_observation(asset: str, sid: Session):
        from aplomb.intelligence.coinmetrics import CoinMetricsError, capture
        try:
            return capture(store, sid, asset)
        except CoinMetricsError as exc:
            raise unavailable("Coin Metrics Community or permitted noncommercial use") from exc
        except ValueError as exc:
            raise ServiceError("validation_error", str(exc)) from exc

    # crypto-exchanges stream: Binance Vision daily history only, rights-gated (the owner
    # excluded the live venues, so their compare/market routes were removed).
    def crypto_unavailable(exc):
        # Stable reason codes from crypto_markets only; never upstream text.
        return ServiceError("upstream_unavailable", "Crypto venue data is unavailable", {"reason": str(exc)})

    @app.get("/v1/intelligence/crypto-markets/venues")
    def crypto_market_venues(sid: Session):
        from aplomb.intelligence.crypto_markets import venue_catalog
        return venue_catalog()

    @app.get("/v1/intelligence/crypto-markets/vision/{symbol}/{day}")
    def crypto_market_vision(symbol: str, day: str, sid: Session, interval: str = "1d"):
        from datetime import date

        from aplomb.intelligence.crypto_markets import CryptoMarketError, vision_daily
        try:
            return vision_daily(store, sid, symbol, date.fromisoformat(day), interval=interval)
        except CryptoMarketError as exc:
            raise crypto_unavailable(exc) from exc
        except ValueError as exc:
            raise ServiceError("validation_error", str(exc)) from exc

    @app.get("/v1/intelligence/disclosures/aapu")
    def disclosure_aapu(sid: Session, as_of: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$")):
        from datetime import date

        from aplomb.intelligence.disclosure_examples import aapu_partial_lookthrough
        try:
            return aapu_partial_lookthrough(date.fromisoformat(as_of), historical=True)
        except ValueError as exc:
            raise ServiceError("validation_error", "Invalid as-of date") from exc

    def fund_pipeline_error(exc):
        # Stable reason codes only; never upstream text.
        reason = str(exc)
        if reason == "no_filing_found":
            return ServiceError("not_found", "No N-PORT-P filing found for this series", {"reason": reason})
        if reason == "capture_conflict":
            return Conflict("Stored capture differs from source")
        if reason.startswith(("invalid_series", "invalid_cik", "invalid_accession", "invalid_fund", "fund_isin", "invalid_session")):
            return ServiceError("validation_error", "Invalid fund identifier", {"reason": reason})
        return ServiceError("upstream_unavailable", "SEC EDGAR N-PORT is unavailable", {"reason": reason})

    @app.get("/v1/intelligence/funds")
    def fund_captures(sid: Session):
        from aplomb.intelligence.fund_pipeline import documented_mappings, list_funds
        return {"items": list_funds(store, sid),
                "documented_isin_mappings": [{k: x[k] for k in ("series_id", "class_id", "fund_isin", "sources")} for x in documented_mappings()]}

    @app.post("/v1/intelligence/funds/{series_id}", status_code=201)
    def fund_ingest(series_id: str, sid: Session, cik: str | None = Query(None, pattern=r"^\d{1,10}$"),
                    accession: str | None = Query(None, pattern=r"^\d{10}-\d{2}-\d{6}$")):
        from aplomb.intelligence.fund_pipeline import FundPipelineError, compute_lookthrough, ingest
        limiter.take(sid, "fund-ingest", 6, 60)
        try:
            record = ingest(store, sid, series_id, cik=cik, accession=accession)
        except FundPipelineError as exc:
            raise fund_pipeline_error(exc) from None
        summary = compute_lookthrough(record["positions"])
        summary["constituents"] = summary["constituents"][:25]
        return {"filing": {k: v for k, v in record.items() if k != "positions"}, **summary}

    @app.get("/v1/intelligence/funds/{fund_id}")
    def fund_lookthrough(fund_id: str, sid: Session, as_of: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
                         historical: bool = False, limit: int = Query(50, ge=1, le=500)):
        from datetime import date

        from aplomb.intelligence.fund_pipeline import FundPipelineError, look_through
        try:
            day = date.fromisoformat(as_of)
        except ValueError as exc:
            raise ServiceError("validation_error", "Invalid as-of date") from exc
        try:
            return look_through(store, sid, fund_id, day, historical=historical, limit=limit)
        except FundPipelineError as exc:
            raise fund_pipeline_error(exc) from None

    @app.get("/v1/intelligence/relationships")
    def relationship_graph_view(sid: Session, lei: str | None = Query(None, min_length=20, max_length=20),
                                isin: str | None = Query(None, min_length=12, max_length=12),
                                as_of: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
                                knowledge: str = Query("as_of", pattern=r"^(as_of|latest)$"),
                                include_unverified: bool = False,
                                max_pages: int = Query(1, ge=1, le=3)):
        from datetime import date

        from aplomb.intelligence.gleif import GLEIFError
        from aplomb.intelligence.relationship_graph import relationship_view
        try:
            return relationship_view(store, sid, lei=lei, isin=isin,
                                     as_of=date.fromisoformat(as_of) if as_of else None,
                                     knowledge=knowledge, include_unverified=include_unverified,
                                     max_pages=max_pages)
        except GLEIFError as exc:
            raise unavailable("GLEIF relationship capture") from exc
        except ValueError as exc:
            raise ServiceError("validation_error", str(exc)) from exc

    @app.get("/v1/intelligence/relationships/captures/{sha256}")
    def relationship_capture(sha256: str, sid: Session):
        from aplomb.intelligence.gleif_relations import stored_payload
        raw = stored_payload(store, sid, sha256)
        if raw is None:
            raise NotFound("Capture not held by this session")
        return Response(raw, media_type="application/json")

    @app.get("/v1/intelligence/regional", response_model=a.RegionalResearchResponse,
             response_model_exclude_unset=True)
    def regional_research(sid: Session, region: str = Query(min_length=2, max_length=2),
                          identifier: str = Query(min_length=1, max_length=8),
                          start: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
                          end: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
                          kind: str = Query(default='overview', pattern=r'^(overview|prices|company|filings|financials|ownership)$'),
                          fiscal_year: str | None = Query(default=None, pattern=r'^\d{4}$'),
                          report_code: str = Query(default='11011', pattern=r'^1101[1234]$'),
                          statement_type: str = Query(default='CFS', pattern=r'^(CFS|OFS)$')):
        from aplomb.research.regional import RegionalError, RegionalResearch
        try:
            return RegionalResearch(store=store, session_id=sid).query(
                region, identifier, start, end, kind=kind, fiscal_year=fiscal_year,
                report_code=report_code, statement_type=statement_type)
        except RegionalError as exc:
            if str(exc).startswith('provider_'):
                raise unavailable("Regional source") from None
            raise ServiceError("validation_error", str(exc)) from None

    @app.get("/v1/assets", response_model=a.AssetsResponse, response_model_exclude_unset=True)
    def assets(request: Request, sid: Session, limit: int = Query(50, ge=1, le=500)):
        return require(services.datastore, "Asset datastore").assets(
            sid, parameters(request, "assets")
        )

    @app.get("/v1/assets/{ticker}", response_model=m.Asset, response_model_exclude_unset=True)
    def asset(ticker: str, sid: Session):
        return require(services.datastore, "Asset datastore").asset(sid, ticker)

    @app.get("/v1/assets/{ticker}/analytics", response_model=a.AssetAnalyticsResponse, response_model_exclude_unset=True)
    def asset_analytics(ticker: str, request: Request, sid: Session):
        provider = require(services.datastore, "Asset datastore")
        return require(getattr(provider, "analytics", None), "Asset analytics")(sid, ticker, parameters(request, "asset_analytics"))

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

    @app.post("/v1/profiles/{profile_id}/duplicate", response_model=m.Profile, response_model_exclude_unset=True, status_code=201)
    def duplicate_profile(profile_id: ProfileId, body: a.DuplicateProfileRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "duplicate", None), "Profile duplication")(sid, profile_id, body.name)

    @app.post("/v1/profiles/{profile_id}/exposure-limits", response_model=m.Profile, response_model_exclude_unset=True)
    def add_exposure_limit(profile_id: ProfileId, body: a.AddExposureLimitRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "add_exposure_limit", None), "Exposure policy")(sid, profile_id, body)

    @app.get("/v1/profiles/{profile_id}/goals", response_model=a.GoalFundingResponse, response_model_exclude_unset=True)
    def profile_goals(profile_id: ProfileId, sid: Session):
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "goal_funding", None), "Goal funding scenarios")(sid, profile_id)

    @app.get("/v1/profiles/archived", response_model=a.ProfilesResponse, response_model_exclude_unset=True)
    def archived_profiles(sid: Session):
        provider = require(services.profiles, "Profile service")
        return a.ProfilesResponse(items=require(getattr(provider, "archived", None), "Profile archive")(sid))

    @app.patch("/v1/profiles/{profile_id}/archive", response_model=m.Profile, response_model_exclude_unset=True)
    def archive_profile(profile_id: ProfileId, body: a.ArchiveProfileRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "archive", None), "Profile archive")(sid, profile_id, body.archived, body.version)

    @app.post("/v1/profiles/{profile_id}/accounts", response_model=m.Profile, response_model_exclude_unset=True, status_code=201)
    def create_account(profile_id: ProfileId, body: a.CreateAccountRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "create_account", None), "Portfolio accounts")(sid, profile_id, body)

    @app.get("/v1/profiles/{profile_id}/account-valuations")
    def account_valuations(profile_id: ProfileId, sid: Session):
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "account_valuation_summary", None), "Account valuations")(sid, profile_id)

    @app.post("/v1/profiles/{profile_id}/accounts/{account_id}/private-assets", response_model=m.Profile, response_model_exclude_unset=True)
    def value_private_asset(profile_id: ProfileId, account_id: str, body: a.PrivateAssetRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "value_private_asset", None), "Private asset valuations")(sid, profile_id, account_id, body)

    @app.post("/v1/profiles/{profile_id}/custom-rules", response_model=m.Profile, response_model_exclude_unset=True)
    def add_custom_rule(profile_id: ProfileId, body: a.AddCustomRuleRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "add_custom_rule", None), "Custom policy conditions")(sid, profile_id, body)

    @app.post("/v1/profiles/{profile_id}/condition-rules", response_model=m.Profile, response_model_exclude_unset=True)
    def add_condition_rule(profile_id: ProfileId, body: a.AddConditionalRuleRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "add_conditional_rule", None), "Conditional policies")(sid, profile_id, body)

    @app.delete("/v1/profiles/{profile_id}/condition-rules/{rule_id}", response_model=m.Profile, response_model_exclude_unset=True)
    def remove_condition_rule(profile_id: ProfileId, rule_id: str, sid: Session, version: Annotated[int, Query(ge=1)]):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "remove_conditional_rule", None), "Conditional policies")(sid, profile_id, rule_id, version)

    @app.put("/v1/profiles/{profile_id}/accounts/{account_id}", response_model=m.Profile, response_model_exclude_unset=True)
    def edit_account(profile_id: ProfileId, account_id: str, body: a.EditAccountRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "edit_account", None), "Account editing")(sid, profile_id, account_id, body)

    @app.get("/v1/profiles/{profile_id}/strategic-candidates")
    def strategic_candidates(profile_id: ProfileId, sid: Session):
        from aplomb.quant.candidates import strategic_brief
        provider = require(services.profiles, "Profile service")
        return strategic_brief(provider.get(sid, profile_id), provider.snapshot(), timestamp(time.time()))

    @app.get("/v1/profiles/{profile_id}/allocation-targets")
    def allocation_targets(profile_id: ProfileId, sid: Session):
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "allocation_targets", None), "Allocation target comparison")(sid, profile_id)

    @app.post("/v1/profiles/{profile_id}/accounts/{account_id}/select", response_model=m.Profile, response_model_exclude_unset=True)
    def select_account(profile_id: ProfileId, account_id: str, body: a.SelectAccountRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "select_account", None), "Portfolio accounts")(sid, profile_id, account_id, body.version)

    @app.post("/v1/profiles/{profile_id}/accounts/{account_id}/refresh", response_model=m.Profile, response_model_exclude_unset=True)
    def refresh_account(profile_id: ProfileId, account_id: str, body: a.RefreshAccountRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "refresh_account", None), "Account valuation refresh")(sid, profile_id, account_id, body.version, body.as_of)

    @app.post("/v1/profiles/{profile_id}/accounts/{account_id}/transfer", response_model=m.Profile, response_model_exclude_unset=True)
    def transfer_account(profile_id: ProfileId, account_id: str, body: a.TransferAccountRequest, sid: Session):
        feature("profile_creator")
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "transfer_account", None), "Account transfer")(sid, profile_id, account_id, body.destination_account_id, body.amount_reporting, body.version)

    @app.get("/v1/profiles/{profile_id}/risk", response_model=a.RiskDiagnosticsResponse, response_model_exclude_unset=True)
    def risk_diagnostics(profile_id: ProfileId, request: Request, sid: Session):
        provider = require(services.profiles, "Profile service")
        return require(getattr(provider, "risk_diagnostics", None), "Risk diagnostics")(sid, profile_id, parameters(request, "risk"))

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
        "/v1/profiles/{profile_id}/strategies/simulate",
        response_model=a.StrategySimulation,
        response_model_exclude_unset=True,
    )
    def simulate_strategy(profile_id: ProfileId, body: a.StrategySimulateRequest, sid: Session):
        provider = require(services.profiles, "Profile service")
        provider.get(sid, profile_id)
        return provider.simulate_strategy(sid, profile_id, body)

    @app.post(
        "/v1/requests/parse", response_model=m.ParsedRequest, response_model_exclude_unset=True
    )
    def parse(body: a.ParseRequest, sid: Session):
        require(services.profiles, "Profile service").get(sid, body.profile_id)
        parsed = m.ParsedRequest.model_validate(require(services.parser, "Request parser").parse(sid, body))
        request = parsed.request
        # api.md §4.1: with goal_requests off, a goal is not returned; `missing` asks for an asset.
        if request is not None and request.type == "goal" and not feature_enabled("goal_requests"):
            missing = [item for item in parsed.missing if item.field != "move.ticker"]
            missing.append(m.MissingField(field="move.ticker", question=m.I18nText(
                en="Goal requests are turned off. Which specific asset should be tested?",
                fr="Les objectifs sont désactivés. Quel actif précis faut-il tester ?",
            )))
            return parsed.model_copy(update={"request": None, "missing": missing})
        # api.md §4.1: an unknown ticker is fetched on demand, when that feature is on.
        if request is not None and request.type == "move" and feature_enabled("on_demand_tickers"):
            try:
                require(services.datastore, "Asset datastore").asset(sid, request.move.ticker)
            except NotFound:
                ticker = request.move.ticker
                warning = m.I18nText(
                    en=f"{ticker} is not in the dataset yet; it can be fetched on demand from the form.",
                    fr=f"{ticker} n’est pas encore dans les données ; il peut être récupéré à la demande depuis le formulaire.",
                )
                return parsed.model_copy(update={"warnings": [*parsed.warnings, warning]})
        return parsed

    @app.post("/v1/rebalance/check", response_model=a.RebalanceResponse, response_model_exclude_unset=True)
    def rebalance_check(body: a.RebalanceRequest, sid: Session):
        return require(services.checks, "Deterministic checks").rebalance(sid, body)

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
        # api.md §4.2b: two checked profiles get the rule-by-rule alignment (rules SPEC §6).
        if len(results) == 2 and all(isinstance(r, m.CheckResult) for r in results):
            from aplomb.rules.engine import explain_difference

            differences = explain_difference(results[0].rule_checks, results[1].rule_checks)
            return a.BatchCheckResponse(results=results, differences=differences)
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

    @app.get("/v1/runs/{run_id}/trace")
    def run_trace(run_id: RunId, request: Request, sid: Session):
        # Session-owned, read-only view of recorded execution and per-claim audit (Agents 2).
        from aplomb.agents.trace import build_trace

        record = require(services.runs, "Run workflow").repository.get(sid, run_id)
        request.state.data_version = record.run.data_version
        return build_trace(record, {
            "max_llm_calls": settings.max_llm_calls, "max_research_calls": settings.max_research_calls,
            "max_revisions": settings.max_revise, "hard_seconds": settings.run_hard_seconds,
        })

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
    register_world("observations", "observations", a.WorldObservationsResponse)
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
