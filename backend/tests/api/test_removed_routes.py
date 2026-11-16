"""Routes for owner-removed or consumer-less sources stay removed (wiring audit).

research#2/#3 (SEC research), intelligence#1 (mempool chain), #2 (DefiLlama protocol),
#5 (live crypto venues), #6 (issuer holdings, Stooq), #10 (security-issuer) and #11
(Golden Copy entity). The routes that still have a web caller keep answering. The World Explorer
keeps the persona modes only: the static airport reference is not served.
"""
import importlib

import pytest
from aplomb.api.app import create_app
from aplomb.api.settings import Settings
from fastapi.testclient import TestClient

from .conftest import SID

HEADERS = {"X-Aplomb-Session": SID}

REMOVED = [
    "/v1/research/sec/concept/0000320193?concept=Assets",
    "/v1/research/sec/frames?concept=Assets&period=CY2024Q4I",
    "/v1/research/sec/latest-filings",
    "/v1/research/sec/ncen/0000320193",
    "/v1/research/company/320193",
    "/v1/intelligence/chains/bitcoin",
    "/v1/intelligence/crypto-markets/compare/BTC",
    "/v1/intelligence/crypto-markets/market/binance/BTCUSDT",
    "/v1/intelligence/defi/protocol/aave?provider_id=1",
    "/v1/intelligence/issuer-holdings/rights",
    "/v1/intelligence/issuer-holdings/ishares/IVV",
    "/v1/intelligence/stooq/daily?symbol=aapl.us&start=2026-01-01&end=2026-02-01",
    "/v1/intelligence/security-issuer?isin=US0378331005&lei=HWUPKR0MPOU8FGXBT394",
    "/v1/intelligence/gleif-golden/entity/HWUPKR0MPOU8FGXBT394",
    "/v1/world/airports",
    "/v1/world/airports?profileId=robert&country=JPN",
]


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(data_version="snap-20261113-starter")))


@pytest.mark.parametrize("path", REMOVED)
def test_removed_route_is_not_registered(client, monkeypatch, path):
    # Even with every former source flag set, nothing answers on these paths.
    for flag in ("APLOMB_SEC_CONTACT", "APLOMB_MEMPOOL_REUSE_CONFIRMED", "APLOMB_DEFILLAMA_WRITTEN_DATA_RIGHTS",
                 "APLOMB_BINANCE_PUBLIC_NONCOMMERCIAL", "APLOMB_BITSTAMP_NONCOMMERCIAL"):
        monkeypatch.setenv(flag, "1")
    assert client.get(path, headers=HEADERS).status_code == 404


@pytest.mark.parametrize("module", [
    "aplomb.research.sec_extra", "aplomb.research.company_routes", "aplomb.intelligence.chain_routes",
    "aplomb.intelligence.chain_public", "aplomb.intelligence.issuer_holdings", "aplomb.intelligence.stooq",
    "aplomb.world.airports", "aplomb.world.providers.ucdp_static", "aplomb.world.providers.transport_extra",
])
def test_removed_module_is_gone(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_routes_with_web_callers_remain(client):
    # Markets still calls these (CryptoHistory, DefiResearch, GoldenCopy); they must stay mounted.
    venues = client.get("/v1/intelligence/crypto-markets/venues", headers=HEADERS)
    assert venues.status_code == 200
    assert [v["venue"] for v in venues.json()["venues"]] == ["binance_vision"]
    assert client.get("/v1/intelligence/defi/sources", headers=HEADERS).status_code == 200
    paths = {getattr(route, "path", "") for route in client.app.routes}
    assert "/v1/intelligence/crypto-markets/vision/{symbol}/{day}" in paths
