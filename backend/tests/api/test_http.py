import json
from types import SimpleNamespace

import pytest
from aplomb.api.app import create_app
from aplomb.api.errors import NotFound, ServiceError
from aplomb.api.repositories import RunRepository
from aplomb.api.services import RunCoordinator, Services
from aplomb.api.settings import Settings
from aplomb.api.storage import MemoryStore
from aplomb.contracts.catalog import FeatureFlag
from aplomb.contracts.models import ApiError, Meta, Run
from fastapi.testclient import TestClient
from mangum import Mangum
from pydantic import ValidationError

from .conftest import OTHER_SID, SID

SETTINGS = Settings(data_version="snap-20261113-starter")
HEADERS = {"X-Aplomb-Session": SID}


def assert_error(response, code, status):
    assert response.status_code == status, response.text
    payload = ApiError.model_validate(response.json())
    assert payload.error.code == code
    assert payload.error.request_id == response.headers["X-Request-Id"]
    assert response.headers["X-Aplomb-Data-Version"] == SETTINGS.data_version
    assert response.headers["Cache-Control"] == "no-store"
    return payload


def test_health_meta_and_honest_unavailable_defaults():
    client = TestClient(create_app(SETTINGS))
    assert client.get("/v1/health").json()["status"] == "ok"
    meta = Meta.model_validate(client.get("/v1/meta").json())
    assert meta.universe.total == 0
    assert not any(meta.features.values())
    assert meta.models.strong is None
    assert_error(client.get("/v1/profiles", headers=HEADERS), "upstream_unavailable", 503)
    assert_error(client.get("/v1/world/layers", headers=HEADERS), "feature_disabled", 501)
    unconfigured = TestClient(create_app(Settings()))
    assert unconfigured.get("/v1/health").status_code == 200
    assert unconfigured.get("/v1/meta").status_code == 503


@pytest.mark.parametrize(
    "value",
    [
        None,
        "s_bad",
        "s_00000000-0000-1000-8000-000000000001",
        "s_00000000-0000-4000-7000-000000000001",
    ],
)
def test_session_validation(value):
    client = TestClient(create_app(SETTINGS))
    headers = {"X-Aplomb-Session": value} if value is not None else {}
    assert_error(client.get("/v1/profiles", headers=headers), "validation_error", 422)


def test_validation_notfound_internal_cors_and_input_limits():
    class BrokenData:
        def assets(self, session, query):
            raise RuntimeError("secret-provider-diagnostic")

    client = TestClient(create_app(SETTINGS, Services(datastore=BrokenData())))
    assert_error(client.get("/missing"), "not_found", 404)
    assert_error(client.get("/v1/openapi.json"), "not_found", 404)
    assert_error(client.get("/v1/assets?limit=501", headers=HEADERS), "validation_error", 422)
    malformed = client.post(
        "/v1/check", headers={**HEADERS, "Content-Type": "application/json"}, content="{"
    )
    assert_error(malformed, "validation_error", 422)
    failure = client.get("/v1/assets", headers={**HEADERS, "Origin": "http://localhost:3000"})
    assert_error(failure, "internal", 500)
    assert "secret-provider-diagnostic" not in failure.text
    assert failure.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    denied = client.get("/v1/assets", headers={**HEADERS, "Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in denied.headers
    preflight = client.options(
        "/v1/assets",
        headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"},
    )
    assert_error(preflight, "validation_error", 422)
    oversized = client.post("/v1/check", headers=HEADERS, json={"text": "x" * 270000})
    assert_error(oversized, "validation_error", 422)


def test_batch_preserves_order_and_converts_independent_failures(fixture_payload):
    class Profiles:
        def get(self, sid, pid):
            if pid == "mateo":
                raise NotFound()

    class Checks:
        def check(self, sid, request):
            if request.profile_id == "amira":
                raise RuntimeError("synthetic failure")
            raise ServiceError("insufficient_data", "Missing snapshot")

    client = TestClient(create_app(SETTINGS, Services(profiles=Profiles(), checks=Checks())))
    body = {"items": [{"profileId": p, "move": None} for p in ["robert", "mateo", "amira"]]}
    response = client.post("/v1/check/batch", headers=HEADERS, json=body)
    assert response.status_code == 200
    assert [item["error"]["code"] for item in response.json()["results"]] == [
        "insufficient_data",
        "not_found",
        "internal",
    ]
    assert all(
        item["error"]["requestId"] == response.headers["X-Request-Id"]
        for item in response.json()["results"]
    )
    assert_error(
        client.post("/v1/check/batch", headers=HEADERS, json={"items": body["items"] * 2}),
        "validation_error",
        422,
    )


def test_nested_run_routes_hide_cross_session_resources(queued_run, clock):
    repo = RunRepository(MemoryStore(), clock)
    repo.create(queued_run, {}, 1)
    services = Services(runs=RunCoordinator(repo, None, None, clock))
    client = TestClient(create_app(SETTINGS, services))
    headers = {"X-Aplomb-Session": OTHER_SID}
    rid = queued_run.run_id
    requests = [
        ("GET", f"/v1/runs/{rid}", None),
        ("GET", f"/v1/runs/{rid}/facts/F-001", None),
        ("POST", f"/v1/runs/{rid}/cancel", None),
        ("POST", f"/v1/runs/{rid}/answers", {"questionId": "q", "value": "v"}),
        ("POST", f"/v1/runs/{rid}/sabotage", {"lang": "en"}),
        ("POST", f"/v1/runs/{rid}/reveal", {}),
    ]
    for method, path, body in requests:
        assert_error(client.request(method, path, headers=headers, json=body), "not_found", 404)
    assert client.get("/v1/runs", headers=headers).json()["items"] == []


def test_session_rate_limits_are_atomic_and_independent(clock):
    app = create_app(SETTINGS)
    app.state.limiter.clock = clock
    client = TestClient(app)
    for _ in range(30):
        assert client.get("/v1/profiles", headers=HEADERS).status_code == 503
    response = client.get("/v1/profiles", headers=HEADERS)
    assert_error(response, "rate_limited", 429)
    assert int(response.headers["Retry-After"]) >= 1
    assert client.get("/v1/profiles", headers={"X-Aplomb-Session": OTHER_SID}).status_code == 503
    clock.advance(1.001)
    assert client.get("/v1/profiles", headers=HEADERS).status_code == 503


def test_world_repeatable_filters_required_profile_and_date_bounds():
    captured = []

    class World:
        def events(self, sid, query):
            captured.append(query)
            raise ServiceError("upstream_unavailable", "Synthetic provider")

    settings = SETTINGS.model_copy(update={"features": {f: True for f in FeatureFlag}})
    services = Services(world=World(), capabilities={"world_explorer"})
    client = TestClient(create_app(settings, services))
    response = client.get(
        "/v1/world/events?category=macro_release&category=corporate&country=CAN"
        "&country=USA&origin=curated&origin=gdelt&limit=2",
        headers=HEADERS,
    )
    assert response.status_code == 503
    assert captured[0]["category"] == ["macro_release", "corporate"]
    assert captured[0]["country"] == ["CAN", "USA"]
    assert captured[0]["origin"] == ["curated", "gdelt"]
    assert captured[0]["limit"] == 2
    for path in [
        "/v1/world/exposure",
        "/v1/world/events?limit=1001",
        "/v1/world/events?from=2024-01-01&to=2026-01-01",
        "/v1/world/events?bbox=0,0,nan,50",
    ]:
        assert_error(client.get(path, headers=HEADERS), "validation_error", 422)


def test_world_layers_require_parent_flag():
    flags = {flag: False for flag in FeatureFlag}
    flags[FeatureFlag.WORLD_LAYER_FACILITIES] = True
    flags[FeatureFlag.WORLD_LAYER_HAZARDS] = True
    settings = SETTINGS.model_copy(update={"features": flags})
    services = Services(capabilities={"world_layer_facilities", "world_layer_hazards"})
    client = TestClient(create_app(settings, services))
    for path in ["/v1/world/facilities", "/v1/world/hazards"]:
        assert_error(client.get(path, headers=HEADERS), "feature_disabled", 501)


def test_run_summary_reads_wrapped_verdict(fixture_payload, clock):
    # A committed synthetic fixture is explicit test data; not an API default.
    run = Run.model_validate(fixture_payload)
    repo = RunRepository(MemoryStore(), clock)
    repo.create(run, {}, 1)
    client = TestClient(
        create_app(SETTINGS, Services(runs=RunCoordinator(repo, None, None, clock)))
    )
    response = client.get("/v1/runs", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["items"][0]["verdict"] == "conflict"


def test_pinned_run_and_fact_headers_survive_current_snapshot_change(fixture_payload, clock):
    run = Run.model_validate(fixture_payload)
    repository = RunRepository(MemoryStore(), clock)
    repository.create(run, {}, 1)
    current = Settings(data_version="snap-20261114-new")
    client = TestClient(
        create_app(current, Services(runs=RunCoordinator(repository, None, None, clock)))
    )
    for path in [f"/v1/runs/{run.run_id}", f"/v1/runs/{run.run_id}/facts/F-001"]:
        response = client.get(path, headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.headers["X-Aplomb-Data-Version"] == run.data_version


def test_lambda_http_api_v2_adapter():
    handler = Mangum(create_app(SETTINGS), lifespan="off")
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/v1/health",
        "rawQueryString": "",
        "headers": {"host": "api.example", "x-forwarded-proto": "https"},
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/v1/health",
                "sourceIp": "127.0.0.1",
                "protocol": "HTTP/1.1",
            }
        },
        "isBase64Encoded": False,
    }
    response = handler(event, SimpleNamespace())
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "ok"
    event["rawPath"] = event["requestContext"]["http"]["path"] = "/v1/profiles"
    error = handler(event, SimpleNamespace())
    assert error["statusCode"] == 422
    assert ApiError.model_validate_json(error["body"]).error.code == "validation_error"


def test_settings_validate_dates_snapshots_flags_and_cloud_requirements():
    for values in [
        {"data_version": "garbage"},
        {"data_as_of": "2026-02-30"},
        {"environment": "aws"},
        {"allowed_origins": ["*"]},
    ]:
        with pytest.raises(ValidationError):
            Settings(**values)
    with pytest.raises(ValueError):
        Settings.from_env({"APLOMB_FEATURE_TIME_MACHINE": "maybe"})
    settings = Settings.from_env(
        {
            "APLOMB_ALLOWED_ORIGINS": "https://a.example,http://localhost:3000",
            "APLOMB_MODEL_STRONG": "verified-model",
        }
    )
    assert len(settings.allowed_origins) == 2
    assert not any(settings.features.values())


def test_public_build_identity_is_validated_and_exposed_on_success_and_errors():
    revision = "a" * 40
    settings = Settings(data_version=SETTINGS.data_version, build_revision=revision)
    client = TestClient(create_app(settings))
    for route in ("/v1/health", "/v1/missing"):
        response = client.get(route, headers={"Origin": "http://localhost:3000"})
        assert response.headers["X-Aplomb-Build"] == revision
        assert "X-Aplomb-Build" in response.headers["Access-Control-Expose-Headers"]
    assert "X-Aplomb-Build" not in TestClient(create_app(SETTINGS)).get("/v1/health").headers
    with pytest.raises(ValidationError):
        Settings(build_revision="arbitrary-provider-text")
