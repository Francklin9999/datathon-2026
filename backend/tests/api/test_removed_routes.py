"""Routes for owner-removed or consumer-less sources stay removed (wiring audit).

research#2/#3 (SEC research), intelligence#1 (mempool chain), #2 (DefiLlama protocol),
#5 (live crypto venues), #6 (issuer holdings, Stooq), #10 (security-issuer) and #11
(Golden Copy entity). Then the whole Markets research surface, which had no role in the persona
decision flow: every /v1/intelligence/* route except the source-capabilities shim, every
/v1/research/* route and /v1/timemachine/vintages/status.
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
    "/v1/timemachine/point-in-time/0000320193?cutoff=2020-01-01",
    "/v1/timemachine/point-in-time/0000320193/published-later?cutoff=2020-01-01&until=2021-01-01",
    "/v1/timemachine/sec-ticker-candidates?ticker=AAPL",
    # Markets research surface
    "/v1/intelligence/entities?q=Apple",
    "/v1/intelligence/listings?as_of=2026-11-15",
    "/v1/intelligence/listings/lst_1?as_of=2026-11-15",
    "/v1/intelligence/sec-structured",
    "/v1/intelligence/sec-data-library",
    "/v1/intelligence/coinmetrics/btc",
    "/v1/intelligence/crypto-markets/venues",
    "/v1/intelligence/crypto-markets/vision/BTCUSDT/2026-11-01",
    "/v1/intelligence/disclosures/aapu?as_of=2026-11-12",
    "/v1/intelligence/funds",
    "/v1/intelligence/funds/fund_1?as_of=2026-11-12",
    "/v1/intelligence/relationships?lei=HWUPKR0MPOU8FGXBT394",
    "/v1/intelligence/relationships/captures/" + "0" * 64,
    "/v1/intelligence/regional?region=JP&identifier=86970&start=2026-10-01&end=2026-11-01",
    "/v1/intelligence/bitcoin-sentiment",
    "/v1/intelligence/company-registry/ca/1234567",
    "/v1/intelligence/defi/sources",
    "/v1/intelligence/defi/pair/ethereum/0xabc",
    "/v1/intelligence/eu/esma-entity/HWUPKR0MPOU8FGXBT394",
    "/v1/intelligence/eu/eba-market-risk/HWUPKR0MPOU8FGXBT394",
    "/v1/intelligence/gleif-golden/metadata",
    "/v1/intelligence/master/coverage",
    "/v1/intelligence/master/crosswalk?isin=US0378331005&as_of=2026-11-15",
    "/v1/intelligence/openfigi?isin=US0378331005",
    "/v1/intelligence/wikidata-candidates?isin=US0378331005",
    "/v1/research/market-connections",
    "/v1/research/market-provider/finnhub?symbol=AAPL",
    "/v1/research/tiingo/AAPL?start=2026-10-01&end=2026-11-01",
    "/v1/timemachine/vintages/status",
]

REMOVED_POST = [
    "/v1/intelligence/funds/S000000001",
    "/v1/intelligence/gleif-golden/delta/HWUPKR0MPOU8FGXBT394",
    "/v1/intelligence/master/adapters/coinmetrics/btc",
    "/v1/intelligence/master/adapters/gleif-pair?isin=US0378331005&lei=HWUPKR0MPOU8FGXBT394",
    "/v1/intelligence/master/adapters/wikidata?isin=US0378331005",
]


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(data_version="snap-20261113-starter")))


@pytest.mark.parametrize("path", REMOVED)
def test_removed_route_is_not_registered(client, monkeypatch, path):
    # Even with every former source flag set, nothing answers on these paths.
    for flag in ("APLOMB_SEC_CONTACT", "APLOMB_MEMPOOL_REUSE_CONFIRMED", "APLOMB_DEFILLAMA_WRITTEN_DATA_RIGHTS",
                 "APLOMB_BINANCE_PUBLIC_NONCOMMERCIAL", "APLOMB_BITSTAMP_NONCOMMERCIAL",
                 "APLOMB_COINMETRICS_NONCOMMERCIAL", "APLOMB_BINANCE_VISION_NONCOMMERCIAL",
                 "APLOMB_DEXSCREENER_RIGHTS_CONFIRMED", "APLOMB_ALFRED_RIGHTS_CONFIRMED"):
        monkeypatch.setenv(flag, "1")
    assert client.get(path, headers=HEADERS).status_code == 404


@pytest.mark.parametrize("path", REMOVED_POST)
def test_removed_post_route_is_not_registered(client, path):
    assert client.post(path, headers=HEADERS).status_code == 404


@pytest.mark.parametrize("module", [
    "aplomb.research.sec_extra", "aplomb.research.company_routes", "aplomb.intelligence.chain_routes",
    "aplomb.intelligence.chain_public", "aplomb.intelligence.issuer_holdings", "aplomb.intelligence.stooq",
    *(f"aplomb.intelligence.{name}" for name in (
        "coinmetrics", "crypto_markets", "defi_routes", "defi_sources", "disclosure_examples", "discovery",
        "eu_registers", "eu_routes", "exact", "fund_pipeline", "gleif_relations", "golden_copy", "golden_routes",
        "holdings_ingest", "master", "master_adapters", "master_repository", "master_routes", "openfigi",
        "overlap", "registries", "registry_routes", "relationship_graph", "sec_structured", "sentiment",
        "sentiment_routes", "wikidata", "wikidata_routes")),
    *(f"aplomb.research.{name}" for name in (
        "keyed_markets", "stock_accounts", "chain_accounts", "regional", "company_detail", "disclosures")),
    "aplomb.timemachine.pit_routes", "aplomb.timemachine.vintages",
])
def test_removed_module_is_gone(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_source_capabilities_shim_reports_no_family(client):
    # The current Markets page shows a research panel only for an available family: none is left.
    response = client.get("/v1/intelligence/source-capabilities", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["families"] == [] and body["catalogue"] == {"rows": [], "source_count": 0}
    assert client.get("/v1/intelligence/source-capabilities").status_code == 422  # session still required
