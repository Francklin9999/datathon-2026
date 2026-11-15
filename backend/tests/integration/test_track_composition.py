"""Independent checks where the written API, ASGI app and Lambda adapter meet."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

from aplomb.api.app import create_app
from aplomb.api.settings import Settings
from aplomb.contracts.registry import adapter
from mangum import Mangum

ROOT = Path(__file__).resolve().parents[3]


def normalized(path):
    return re.sub(r"\{[^}]+\}", "{}", path.removeprefix("/v1"))


def test_every_documented_endpoint_has_one_registered_method_and_path():
    text = (ROOT / "contracts/api.md").read_text()
    expected = {
        (method, normalized(path))
        for method, path in re.findall(r"\| (GET|POST|PUT|PATCH|DELETE) `([^`]+)`", text)
    }
    app = create_app(Settings(data_version="snap-20261113-starter"))
    actual = {
        (method, normalized(route.path))
        for item in app.routes
        for route in (item.effective_route_contexts() if hasattr(item, "effective_route_contexts") else [item])
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }
    assert expected
    assert actual == expected


def test_api_gateway_v2_preserves_wire_errors_and_correlation_headers():
    app = create_app(Settings(data_version="snap-20261113-starter"))
    handler = Mangum(app, lifespan="off")
    for path, expected_status, contract in [
        ("/v1/health", 200, "HealthResponse"),
        ("/v1/meta", 200, "Meta"),
        ("/v1/profiles", 422, "ApiError"),
    ]:
        event = {
            "version": "2.0", "routeKey": "$default", "rawPath": path,
            "rawQueryString": "", "headers": {"host": "example.execute-api.us-east-1.amazonaws.com"},
            "requestContext": {
                "http": {"method": "GET", "path": path, "protocol": "HTTP/1.1",
                         "sourceIp": "127.0.0.1", "userAgent": "aplomb-integration-test"},
                "stage": "$default", "requestId": "gateway-test",
            },
            "isBase64Encoded": False,
        }
        response = handler(event, SimpleNamespace())
        assert response["statusCode"] == expected_status
        payload = adapter(contract).validate_json(response["body"])
        headers = {key.lower(): value for key, value in response["headers"].items()}
        assert headers["x-aplomb-data-version"] == "snap-20261113-starter"
        assert headers["x-request-id"].startswith("req_")
        if contract == "ApiError":
            assert payload.error.request_id == headers["x-request-id"]
        assert json.loads(response["body"])
