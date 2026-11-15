"""Live price providers for on-demand tickers (D-24, api.md §2.3).

``TiingoProvider`` uses the documented Tiingo End-of-Day REST API (checked 2026-11-14):
``GET https://api.tiingo.com/tiingo/daily/<ticker>`` (meta: ticker, name, exchangeCode,
description, startDate, endDate) and ``GET .../<ticker>/prices?startDate=&endDate=`` (date, open,
high, low, close, volume, adjClose; adjustments follow the CRSP split/dividend method). The token
travels in the ``Authorization: Token <key>`` header, never in a URL or a log line.

Licence: Tiingo's published plans state "Internal Use Only" (free tier: 50 requests per hour,
1,000 per day). Whether a public demo fits that licence is the project owner's decision; the
provider is only built when ``APLOMB_TIINGO_TOKEN`` is configured.

Classification is conservative: the meta endpoint carries no currency or asset type, so only
instruments on a U.S. exchange (priced in USD) whose description does not present them as a
fund are accepted as single-name equities; funds are rejected rather than guessed into a group.
Sector stays "unknown" (``sector_label_unsourced``).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote

from .ondemand import FetchedAsset

TIINGO_BASE = "https://api.tiingo.com/tiingo/daily"
US_EXCHANGES = {"NASDAQ": "NASDAQ", "NYSE": "NYSE", "NYSE ARCA": "NYSE Arca", "NYSE MKT": "NYSE American",
                "NYSE AMERICAN": "NYSE American", "BATS": "Cboe BZX", "CBOE BZX": "Cboe BZX"}
FUND_NAME_WORDS = (" etf", " fund", "ishares", "spdr")
FUND_DESCRIPTION_WORDS = ("exchange-traded fund", "exchange traded fund", "an etf", "the etf", "the fund ", "mutual fund")


class ProviderError(Exception):
    """``code``: not_found | unsupported | unavailable. ``reason`` is bilingual text."""

    def __init__(self, code: str, en: str, fr: str) -> None:
        super().__init__(en)
        self.code = code
        self.reason = {"en": en, "fr": fr}


HttpGet = Callable[[str, dict], tuple[int, bytes]]


def urllib_get(url: str, headers: dict, timeout: float = 15.0) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https host
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() if exc.fp else b""
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError("unavailable", f"Price provider unreachable: {type(exc).__name__}",
                            f"Fournisseur de prix injoignable : {type(exc).__name__}") from exc


class TiingoProvider:
    name = "Tiingo End-of-Day API"
    source_url = "https://www.tiingo.com/documentation/end-of-day"
    terms = "Tiingo plans: Internal Use Only (https://www.tiingo.com/about/pricing)"

    def __init__(self, token: str, *, http_get: HttpGet = urllib_get, clock: Callable[[], datetime] | None = None) -> None:
        if not token:
            raise ValueError("Tiingo token required")
        self._headers = {"Authorization": f"Token {token}", "Content-Type": "application/json",
                         "User-Agent": "aplomb-datastore"}
        self._get = http_get
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _json(self, url: str):
        status, body = self._get(url, dict(self._headers))
        if status == 404:
            raise ProviderError("not_found", "The provider does not cover this ticker.", "Le fournisseur ne couvre pas ce ticker.")
        if status in (401, 403):
            raise ProviderError("unavailable", "The provider rejected the configured token.", "Le fournisseur a refusé le jeton configuré.")
        if status == 429:
            raise ProviderError("unavailable", "Provider rate limit reached; retry later.", "Limite de requêtes du fournisseur atteinte; réessayez plus tard.")
        if status != 200:
            raise ProviderError("unavailable", f"Provider answered HTTP {status}.", f"Le fournisseur a répondu HTTP {status}.")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("unavailable", "Provider returned malformed JSON.", "Le fournisseur a renvoyé un JSON invalide.") from exc

    def fetch(self, ticker: str, start: str, end: str) -> FetchedAsset:
        retrieved = self._clock().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        symbol = quote(ticker.lower(), safe="-.")
        meta = self._json(f"{TIINGO_BASE}/{symbol}")
        if not isinstance(meta, dict) or not meta.get("ticker"):
            raise ProviderError("not_found", "The provider returned no metadata for this ticker.",
                                "Le fournisseur n'a renvoyé aucune métadonnée pour ce ticker.")
        exchange = str(meta.get("exchangeCode") or "").upper()
        market = US_EXCHANGES.get(exchange)
        if market is None:
            raise ProviderError("unsupported", f"Exchange {exchange or 'unknown'} is not a supported U.S. listing (CAD/USD only).",
                                f"La bourse {exchange or 'inconnue'} n'est pas une cotation américaine prise en charge (CAD/USD seulement).")
        name = str(meta.get("name") or ticker).strip()
        lowered_name = f" {name.lower()}"
        description = str(meta.get("description") or "").lower()
        if any(w in lowered_name for w in FUND_NAME_WORDS) or any(w in description for w in FUND_DESCRIPTION_WORDS):
            raise ProviderError("unsupported", "Funds are not accepted on demand: their asset group (equity or bond) cannot be verified.",
                                "Les fonds ne sont pas acceptés à la demande : leur groupe d'actifs (actions ou obligations) ne peut pas être vérifié.")
        rows = self._json(f"{TIINGO_BASE}/{symbol}/prices?startDate={start}&endDate={end}")
        if not isinstance(rows, list):
            raise ProviderError("unavailable", "Provider returned no price list.", "Le fournisseur n'a renvoyé aucune liste de prix.")
        prices = tuple({"date": str(r.get("date", ""))[:10], "open": r.get("open"), "high": r.get("high"), "low": r.get("low"),
                        "close": r.get("close"), "adj_close": r.get("adjClose"), "volume": r.get("volume")} for r in rows)
        return FetchedAsset(ticker=ticker.upper(), name=name, asset_class="equity", market=market, currency="USD", sector=None,
                            rows=prices, provider=self.name, retrieved_at=retrieved,
                            source_url=self.source_url, terms=self.terms)
