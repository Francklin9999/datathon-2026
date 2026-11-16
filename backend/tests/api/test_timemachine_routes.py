"""Time Machine side routes: the ALFRED rights status stays; the removed SEC point-in-time routes are gone."""
import pytest
from aplomb.api.app import create_app
from aplomb.api.services import Services
from aplomb.api.settings import Settings
from aplomb.contracts.catalog import FeatureFlag
from fastapi.testclient import TestClient

from .conftest import SID

HEADERS = {"X-Aplomb-Session": SID}


def client(enabled: bool) -> TestClient:
    settings = Settings(data_version="snap-20261113-starter", features={FeatureFlag.TIME_MACHINE: enabled})
    return TestClient(create_app(settings, Services(capabilities={"time_machine"})))


def test_vintage_status_reports_rights_gate_without_secrets(monkeypatch):
    monkeypatch.delenv("APLOMB_ALFRED_RIGHTS_CONFIRMED", raising=False)
    monkeypatch.setenv("APLOMB_FRED_KEY", "secret-key-value")
    response = client(True).get("/v1/timemachine/vintages/status", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable" and body["missing"] == ["APLOMB_ALFRED_RIGHTS_CONFIRMED"]
    assert body["ingested"] is False and body["used_in_replay"] is False
    assert "secret-key-value" not in response.text


def test_vintage_status_requires_session_and_feature():
    missing = client(True).get("/v1/timemachine/vintages/status")
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "validation_error"
    disabled = client(False).get("/v1/timemachine/vintages/status", headers=HEADERS)
    assert disabled.status_code == 501 and disabled.json()["error"]["code"] == "feature_disabled"


@pytest.mark.parametrize("path", [
    "/v1/timemachine/point-in-time/0000320193?cutoff=2020-01-01",
    "/v1/timemachine/point-in-time/0000320193/published-later?cutoff=2020-01-01&until=2021-01-01",
    "/v1/timemachine/sec-ticker-candidates?ticker=AAPL",
])
def test_removed_sec_point_in_time_routes_are_not_registered(monkeypatch, path):
    # The owner removed the SEC sources; the routes and their contracts/api.md rows are gone.
    monkeypatch.setenv("APLOMB_SEC_CONTACT", "Example ops@example.com")
    response = client(True).get(path, headers=HEADERS)
    assert response.status_code == 404
