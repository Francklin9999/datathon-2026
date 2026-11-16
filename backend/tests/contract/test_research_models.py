"""research#7: the research route models describe the payloads exactly (contract 1.6.0).

Every handler result below comes from the real normalizers with synthetic provider bodies. Each one
must validate against its model and serialize back to the same JSON FastAPI produced before the
route had a response model: no key dropped, renamed or retyped. No network access.
"""
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from aplomb.api.storage import MemoryStore
from aplomb.contracts import api as a
from fastapi.encoders import jsonable_encoder

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)
SID = "s_6f1c2d3e-4a5b-4c6d-8e7f-0123456789ab"


def same_wire(model, payload):
    validated = model.model_validate(payload)
    assert validated.model_dump(mode="json", by_alias=True, exclude_unset=True) == json.loads(json.dumps(jsonable_encoder(payload)))
    return validated


def encode(value):
    return json.dumps(value).encode()


# --- keyed markets ---------------------------------------------------------------------------------


def test_connection_rows(monkeypatch):
    from aplomb.research.keyed_markets import connection_status

    monkeypatch.setenv("APLOMB_FINNHUB_KEY", "k")
    same_wire(a.MarketConnectionsResponse, connection_status())
    # A 1.4.0 API sent chain rows without signup_url/credential_variable and tiingo without documentation_url.
    same_wire(a.MarketConnectionsResponse, {"providers": [
        {"id": "alchemy", "credential_present": False, "rights_confirmed": False, "supported_operation": "x", "documentation_url": "https://d"},
        {"id": "tiingo", "signup_url": "https://s", "credential_variable": "T", "credential_present": True, "rights_confirmed": True,
         "supported_operation": "y"}]})


def test_keyed_stock_and_chain_captures(monkeypatch):
    from aplomb.research import chain_accounts, keyed_markets, stock_accounts

    keys = [keyed_markets.PROVIDERS[p]["key"] for p in ("finnhub", "alpha-vantage", "twelve-data")]
    keys += [stock_accounts.PROVIDERS["fmp"]["key"], chain_accounts.PROVIDERS["alchemy"]["key"]]
    for key in keys:
        monkeypatch.setenv(key, "private-test-secret")
        monkeypatch.setenv(key.removesuffix("_KEY") + "_RIGHTS_CONFIRMED", "true")
    store = MemoryStore()
    bodies = {
        "finnhub": {"ticker": "AAPL", "name": "Apple", "currency": "USD", "marketCapitalization": 3000000.5},
        "alpha-vantage": {"Global Quote": {"01. symbol": "IBM", "05. price": "250.10", "06. volume": "1000",
                                           "07. latest trading day": "2026-11-13"}},
        "twelve-data": {"meta": {"symbol": "AAPL", "mic_code": "XNGS", "interval": "1day", "currency": "USD", "exchange": "NASDAQ",
                                 "exchange_timezone": "America/New_York"},
                        "values": [{"datetime": "2026-11-13", "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "10"}]},
    }
    results = [
        keyed_markets.capture(store, SID, "finnhub", "AAPL", get=lambda p, q, s: ("https://finnhub.io/x", encode(bodies["finnhub"])), now=NOW),
        keyed_markets.capture(store, SID, "alpha-vantage", "IBM", get=lambda p, q, s: ("https://www.alphavantage.co/x", encode(bodies["alpha-vantage"])),
                              now=NOW),
        keyed_markets.capture(store, SID, "twelve-data", "AAPL", "XNGS",
                              get=lambda p, q, s: ("https://api.twelvedata.com/x", encode(bodies["twelve-data"])), now=NOW),
        stock_accounts.capture(store, SID, "fmp", "AAPL", get=lambda *_: ("https://financialmodelingprep.com/stable/quote?symbol=AAPL",
                                                                          b'[{"symbol":"AAPL","price":1}]'), now=NOW),
        chain_accounts.capture(store, SID, "alchemy", "ethereum", get=lambda *_: b'{"jsonrpc":"2.0","id":1,"result":"0x20"}', now=NOW),
    ]
    for result in results:
        same_wire(a.MarketObservationResponse, result)
    assert results[-1]["source_request"]["method"] == "POST"  # the chain capture's typed request


def test_tiingo_capture(monkeypatch):
    from aplomb.datastore import providers
    from aplomb.research.keyed_markets import tiingo_capture

    def fake_get(url, headers):
        if url.endswith("/prices?startDate=2026-10-01&endDate=2026-11-01"):
            return 200, encode([{"date": "2026-10-02T00:00:00.000Z", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "adjClose": 1.4,
                                 "volume": 100}])
        return 200, encode({"ticker": "aapl", "name": "Apple Inc", "exchangeCode": "NASDAQ", "description": "Phones"})

    monkeypatch.setattr(providers, "urllib_get", fake_get)
    result = tiingo_capture(MemoryStore(), SID, "token", "AAPL", "2026-10-01", "2026-11-01")
    validated = same_wire(a.MarketObservationResponse, result)
    assert validated.sources and validated.source_url is None


# --- regional research -----------------------------------------------------------------------------


def regional(fetch, provider, store=None):
    from aplomb.research.regional import RegionalResearch

    env = {f"APLOMB_{provider}_KEY": "private", f"APLOMB_{provider}_RIGHTS_CONFIRMED": "true"}
    return RegionalResearch(fetch=fetch, env=env, clock=lambda: NOW, store=store, session_id=SID if store else None)


def japan(url, headers):
    path = urlparse(url).path
    if path.endswith("/bars/daily"):
        return encode({"data": [{"Date": "2026-10-02", "Code": "86970", "C": 102, "AdjC": 100.5}]})
    if path.endswith("/master"):
        return encode({"data": [{"Date": "2026-11-02", "Code": "86970", "CoName": "日本取引所", "CoNameEn": "JPX", "S17": "16",
                                 "S17Nm": "金融", "S33": "7200", "S33Nm": "その他金融業", "ScaleCat": "TOPIX Large70", "Mkt": "0111",
                                 "MktNm": "プライム", "Mrgn": "1", "MrgnNm": "信用", "ProdCat": "011"}]})
    return encode({"data": [{"Code": "86970", "DiscDate": "2026-10-28", "DiscTime": "15:00:00", "DiscNo": "20261028000001",
                             "DocType": "2QFinancialStatements_Consolidated_IFRS", "CurPerType": "2Q", "CurPerSt": "2026-04-01",
                             "CurPerEn": "2026-09-30", "CurFYSt": "2026-04-01", "CurFYEn": "2027-03-31", "NxtFYSt": "", "NxtFYEn": "",
                             "Sales": "80000000000", "EPS": "45.67", "FSales": "160000000000", "OP": "bad", "NP": ""}]})


def korea(url, headers):
    path, q = urlparse(url).path, parse_qs(urlparse(url).query)
    if path.endswith("company.json"):
        return encode({"status": "000", "corp_name": "예시", "corp_name_eng": "Example Ltd", "stock_code": "000001"})
    if path.endswith("list.json"):
        return encode({"status": "000", "total_page": 1, "total_count": 1, "list": [
            {"corp_code": "00126380", "rcept_no": "20261003000001", "rcept_dt": "20261003", "report_nm": "Annual report"}]})
    if path.endswith("fnlttSinglAcntAll.json"):
        assert q["bsns_year"] == ["2025"]
        return encode({"status": "000", "list": [
            {"corp_code": "00126380", "bsns_year": "2025", "reprt_code": "11011", "rcept_no": "20260310000001", "thstrm_nm": "제 57 기",
             "sj_div": "IS", "sj_nm": "손익계산서", "account_id": "ifrs-full_Revenue", "account_nm": "매출액", "account_detail": "-",
             "thstrm_amount": "300,000,000", "thstrm_add_amount": "", "frmtrm_nm": "제 56 기", "frmtrm_amount": "-1,000",
             "ord": "1", "currency": "KRW"}]})
    if path.endswith("majorstock.json"):
        return encode({"status": "000", "list": [
            {"corp_code": "00126380", "rcept_no": "20261005000001", "rcept_dt": "20261005", "repror": "Holder A", "report_tp": "일반",
             "report_resn": "보유비율 변동", "stkqy": "1,000", "stkqy_irds": "-10", "stkrt": "5.01", "stkrt_irds": "0.10",
             "ctr_stkqy": "0", "ctr_stkrt": "0.00"}]})
    return encode({"status": "013"})  # elestock: no rows


@pytest.mark.parametrize(("region", "identifier", "kind", "provider", "fetch"), [
    ("JP", "86970", "prices", "JQUANTS", japan),
    ("JP", "86970", "company", "JQUANTS", japan),
    ("JP", "86970", "financials", "JQUANTS", japan),
    ("KR", "00126380", "filings", "OPENDART", korea),
    ("KR", "00126380", "financials", "OPENDART", korea),
    ("KR", "00126380", "ownership", "OPENDART", korea),
])
@pytest.mark.parametrize("stored", [False, True])
def test_regional_kinds(region, identifier, kind, provider, fetch, stored):
    service = regional(fetch, provider, MemoryStore() if stored else None)
    result = service.query(region, identifier, "2026-10-01", "2026-11-01", kind=kind, fiscal_year="2025")
    assert result["status"] == "ok"
    validated = same_wire(a.RegionalResearchResponse, result)
    rows = {"prices": validated.prices, "company": [validated.company] if validated.company else [], "filings": validated.filings,
            "financials": validated.financials, "ownership": validated.ownership}[kind]
    assert rows, kind  # the synthetic body produced rows of that kind
    assert (validated.capture_id is not None) == stored


def test_regional_unavailable_without_an_account():
    from aplomb.research.regional import RegionalResearch

    for region, identifier, kind in (("JP", "86970", "company"), ("KR", "00126380", "financials")):
        result = RegionalResearch(fetch=None, env={}, clock=lambda: NOW).query(region, identifier, "2026-10-01", "2026-11-01", kind=kind)
        assert same_wire(a.RegionalResearchResponse, result).status == "unavailable"


def test_routes_declare_the_models():
    from aplomb.api.app import create_app
    from aplomb.api.settings import Settings

    app = create_app(Settings(local_state_file="/tmp/aplomb-research-models-test-state.json"))
    def flat(routes):  # included routers (FastAPI 0.163) keep their routes on original_router
        for route in routes:
            if hasattr(route, "original_router"):
                yield from flat(route.original_router.routes)
            else:
                yield route

    models = {getattr(route, "path", None): getattr(route, "response_model", None) for route in flat(app.routes)}
    assert models["/v1/research/market-connections"] is a.MarketConnectionsResponse
    assert models["/v1/research/market-provider/{provider}"] is a.MarketObservationResponse
    assert models["/v1/research/tiingo/{symbol}"] is a.MarketObservationResponse
    assert models["/v1/intelligence/regional"] is a.RegionalResearchResponse
    from aplomb.research.keyed_markets import connection_status
    from fastapi.testclient import TestClient

    served = TestClient(app).get("/v1/research/market-connections", headers={"X-Aplomb-Session": SID})
    assert served.status_code == 200 and served.json() == connection_status()  # snake_case keys unchanged on the wire
