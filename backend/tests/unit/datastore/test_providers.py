"""Tiingo adapter against responses shaped like its documentation (no network access)."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from aplomb.datastore.providers import ProviderError, TiingoProvider

META = {"ticker": "newco", "name": "New Company Inc", "exchangeCode": "NASDAQ", "description": "Makes things.",
        "startDate": "2015-01-02", "endDate": "2026-11-12"}


def rows(n=40):
    return [{"date": f"2026-0{1 + i // 28}-{1 + i % 28:02d}T00:00:00.000Z", "open": 10.0 + i, "high": 11.0 + i, "low": 9.0 + i,
             "close": 10.0 + i, "volume": 1000, "adjOpen": 9.5 + i, "adjHigh": 10.5 + i, "adjLow": 8.5 + i, "adjClose": 9.8 + i,
             "adjVolume": 1000, "divCash": 0.0, "splitFactor": 1.0} for i in range(n)]


class FakeHttp:
    def __init__(self, meta=META, prices=None, status=200, raw=None):
        self.meta, self.prices, self.status, self.raw = meta, prices if prices is not None else rows(), status, raw
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        if self.raw is not None:
            return self.status, self.raw
        body = self.prices if "/prices" in url else self.meta
        return self.status, json.dumps(body).encode()


def provider(http):
    return TiingoProvider("secret-token", http_get=http, clock=lambda: datetime(2026, 11, 14, 23, 0, tzinfo=timezone.utc))


class Tiingo(unittest.TestCase):

    def test_maps_documented_fields(self):
        http = FakeHttp()
        f = provider(http).fetch("NEWCO", "2021-11-12", "2026-11-12")
        self.assertEqual((f.ticker, f.name, f.asset_class, f.market, f.currency, f.sector), ("NEWCO", "New Company Inc", "equity", "NASDAQ", "USD", None))
        self.assertEqual(f.rows[0]["date"], "2026-01-01")
        self.assertEqual(f.rows[0]["adj_close"], 9.8)  # adjusted close, never the raw close
        self.assertEqual(f.retrieved_at, "2026-11-14T23:00:00Z")
        self.assertIn("Internal Use Only", f.terms)
        urls = [u for u, _ in http.calls]
        self.assertEqual(urls[0], "https://api.tiingo.com/tiingo/daily/newco")
        self.assertEqual(urls[1], "https://api.tiingo.com/tiingo/daily/newco/prices?startDate=2021-11-12&endDate=2026-11-12")
        for url, headers in http.calls:
            self.assertNotIn("secret-token", url)  # token only in the header
            self.assertEqual(headers["Authorization"], "Token secret-token")

    def test_rejects_unsupported(self):
        cases = [
            (FakeHttp(meta={**META, "exchangeCode": "TSX"}), "unsupported"),
            (FakeHttp(meta={**META, "name": "Some Bond ETF"}), "unsupported"),
            (FakeHttp(meta={**META, "description": "The Fund seeks to track an index; an exchange-traded fund."}), "unsupported"),
            (FakeHttp(meta={**META, "name": "Some Holdings", "description": "Historical ETF prices for Some (SOME)."}), "unsupported"),
            (FakeHttp(status=404), "not_found"),
            (FakeHttp(status=429), "unavailable"),
            (FakeHttp(status=401), "unavailable"),
            (FakeHttp(raw=b"<html>"), "unavailable"),
            (FakeHttp(meta={}), "not_found"),
        ]
        for http, code in cases:
            with self.assertRaises(ProviderError) as ctx:
                provider(http).fetch("NEWCO", "2021-11-12", "2026-11-12")
            self.assertEqual(ctx.exception.code, code)
            self.assertTrue(ctx.exception.reason["fr"])

    def test_company_names_with_trust_are_not_funds(self):
        f = provider(FakeHttp(meta={**META, "ticker": "NTRS", "name": "Northern Trust Corp", "exchangeCode": "NYSE"})).fetch("NTRS", "2021-11-12", "2026-11-12")
        self.assertEqual((f.asset_class, f.market), ("equity", "NYSE"))

    def test_token_required(self):
        with self.assertRaises(ValueError):
            TiingoProvider("")


if __name__ == "__main__":
    unittest.main()
