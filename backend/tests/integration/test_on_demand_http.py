"""POST /v1/assets/{ticker}/fetch end to end with a fake live provider (no network)."""

from __future__ import annotations

import uuid

import pytest
from aplomb.api.app import create_app
from aplomb.api.domain import default_services
from aplomb.api.settings import Settings
from aplomb.contracts.catalog import FeatureFlag
from aplomb.contracts.registry import adapter
from aplomb.datastore import LocalDataStore
from aplomb.datastore.ingest import ingest_starter
from aplomb.datastore.ondemand import FetchedAsset
from aplomb.datastore.providers import ProviderError
from fastapi.testclient import TestClient
from tests.unit.datastore._support import (
    METADATA_DIR,
    STARTER_DIR,
    STARTER_VERSION,
    fixed_clock,
    temp_root,
)

H = {"X-Aplomb-Session": "s_" + str(uuid.uuid4())}


class FakeProvider:
    def __init__(self, data_root):
        snap = LocalDataStore(data_root).open(STARTER_VERSION)
        self.dates = snap.gate(snap.data_as_of).master_calendar().dates

    def fetch(self, ticker, start, end):
        if ticker == "FUNDY":
            raise ProviderError("unsupported", "Funds are not accepted on demand.", "Les fonds ne sont pas acceptés à la demande.")
        if ticker == "DOWN":
            raise ProviderError("unavailable", "Provider unreachable.", "Fournisseur injoignable.")
        days = self.dates if ticker != "TINY" else self.dates[-20:]
        rows = tuple({"date": d, "open": 50 + i * 0.01, "high": 51 + i * 0.01, "low": 49 + i * 0.01, "close": 50 + i * 0.01,
                      "adj_close": 50 + i * 0.01 + (i % 7) * 0.05, "volume": 1000} for i, d in enumerate(days))
        return FetchedAsset(ticker=ticker, name=f"{ticker} Inc", asset_class="equity", market="NASDAQ", currency="USD", sector=None,
                            rows=rows, provider="fake provider", retrieved_at="2026-11-14T23:00:00Z", source_url=None, terms=None)


@pytest.fixture()
def client():
    root = temp_root()
    ingest_starter(STARTER_DIR, root, STARTER_VERSION, metadata_dir=METADATA_DIR, clock=fixed_clock)
    features = {flag: False for flag in FeatureFlag}
    features[FeatureFlag.ON_DEMAND_TICKERS] = True
    settings = Settings(data_version=STARTER_VERSION, data_dir=str(root), features=features)
    return TestClient(create_app(settings, default_services(settings, price_provider=FakeProvider(root)))), root


def test_accepted_fetch_publishes_and_serves_new_version(client):
    c, root = client
    body = adapter("FetchAssetResponse").validate_json(c.post("/v1/assets/NEWCO/fetch", json={}, headers=H).content).to_wire()
    assert body["accepted"] is True
    assert body["asset"]["tier"] == "on_demand" and "short_history" not in body["asset"]["flags"]
    new_version = body["asset"]["dataVersion"]
    assert new_version.startswith("snap-") and "-od-newco-" in new_version
    meta = c.get("/v1/meta").json()
    assert meta["dataVersion"] == new_version
    assert meta["features"]["on_demand_tickers"] is True
    assert meta["universe"]["byTier"]["on_demand"] == 1
    assert c.get("/v1/assets/NEWCO", headers=H).status_code == 200
    check = c.post("/v1/check", json={"profileId": "robert", "move": {"ticker": "NEWCO", "sizePct": 2, "funding": {"mode": "pro_rata"}}},
                   headers=H)
    assert check.status_code == 200 and check.json()["dataVersion"] == new_version
    assert LocalDataStore(root).open(STARTER_VERSION).gate("2026-11-12").universe().counts()["total"] == 31  # parent untouched


def test_short_history_and_rejections(client):
    c, _ = client
    tiny = c.post("/v1/assets/TINY/fetch", json={}, headers=H)
    body = adapter("FetchAssetResponse").validate_json(tiny.content).to_wire()
    assert body["accepted"] is False and "at least 30" in body["rejectedReason"]["en"]
    assert body["asset"]["dataVersion"] == STARTER_VERSION  # provisional, nothing published
    assert c.get("/v1/meta").json()["dataVersion"] == STARTER_VERSION
    assert c.post("/v1/assets/FUNDY/fetch", json={}, headers=H).status_code == 422
    assert c.post("/v1/assets/DOWN/fetch", json={}, headers=H).status_code == 503
    existing = c.post("/v1/assets/SPY/fetch", json={}, headers=H).json()
    assert existing["accepted"] is True and existing["asset"]["tier"] == "starter"


def test_without_provider_the_endpoint_is_disabled():
    features = {flag: False for flag in FeatureFlag}
    features[FeatureFlag.ON_DEMAND_TICKERS] = True
    settings = Settings(data_version=STARTER_VERSION, data_dir=str(temp_root()), features=features)
    c = TestClient(create_app(settings, default_services(settings)))
    assert c.post("/v1/assets/NEWCO/fetch", json={}, headers=H).status_code == 501  # capability not advertised
