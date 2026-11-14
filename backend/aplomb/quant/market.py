"""Gated, currency-converted price levels on the master calendar (quant SPEC §2–§4).

Built lazily per ticker from one ``TemporalGate``; nothing is read outside the gate and nothing
is filled: a master day without an observation (or without an earlier FX rate) is ``None``.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass

from aplomb.datastore import TemporalGate, UnknownTicker
from aplomb.datastore.constants import CASH_TICKERS, MIN_MASTER_OBS_FOR_RISK
from aplomb.datastore.types import DatasetRead


class Unavailable(Exception):
    """A figure cannot be computed; ``reason`` is a catalog NeeReason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


@dataclass(frozen=True)
class Series:
    ticker: str
    listing_currency: str
    levels: tuple[float | None, ...]       # reporting currency, aligned to MarketData.dates
    avail: tuple[str | None, ...]          # availability of the latest row used per date
    fx_used: tuple[str | None, ...]        # FX publication date used per date (None when no conversion)
    n_obs_master: int                      # visible master-calendar observations
    synthetic: bool                        # cash pseudo-asset


class MarketData:
    """Master-calendar levels in one reporting currency under one gate."""

    def __init__(self, gate: TemporalGate, currency: str) -> None:
        if currency not in ("CAD", "USD"):
            raise ValueError("currency must be CAD or USD")
        self.gate = gate
        self.currency = currency
        cal = gate.master_calendar()
        self.dates: tuple[str, ...] = cal.dates
        self.reads: list[DatasetRead] = list(cal.reads)
        fx = gate.fx(None, None)
        self.reads.append(fx.dataset_read())
        self._fx_dates = tuple(r["date"] for r in fx.rows)
        self._fx_rates = tuple(r["usdcad"] for r in fx.rows)
        self._fx_avail: dict[str, str] = {r["date"]: r["available_at"] for r in fx.rows}
        self._series: dict[str, Series] = {}
        self._index = {d: i for i, d in enumerate(self.dates)}

    def index_of(self, day: str) -> int | None:
        return self._index.get(day)

    def last_index_on_or_before(self, day: str) -> int | None:
        i = bisect.bisect_right(self.dates, day) - 1
        return i if i >= 0 else None

    def _fx_on_or_before(self, day: str) -> tuple[float, str] | None:
        i = bisect.bisect_right(self._fx_dates, day) - 1
        return (self._fx_rates[i], self._fx_dates[i]) if i >= 0 else None

    def series(self, ticker: str) -> Series:
        cached = self._series.get(ticker)
        if cached is not None:
            return cached
        if ticker in CASH_TICKERS:
            s = self._cash_series(ticker)
        else:
            try:
                sl = self.gate.prices([ticker], None, None)
            except UnknownTicker as exc:
                raise Unavailable("asset_unknown", str(exc)) from exc
            self.reads.append(sl.dataset_read())
            listing = self.gate.universe().get(ticker).currency
            by_date = {r["date"]: r for r in sl.rows}
            levels, avail, fx_used = [], [], []
            n_master = 0
            for d in self.dates:
                row = by_date.get(d)
                if row is None:
                    levels.append(None)
                    avail.append(None)
                    fx_used.append(None)
                    continue
                n_master += 1
                price = row["adj_close"]
                stamp = row["available_at"]
                if listing == self.currency:
                    levels.append(price)
                    avail.append(stamp)
                    fx_used.append(None)
                    continue
                fx = self._fx_on_or_before(d)
                if fx is None:  # no earlier published rate: missing, never a future rate
                    levels.append(None)
                    avail.append(None)
                    fx_used.append(None)
                    continue
                rate, fx_day = fx
                levels.append(price * rate if listing == "USD" else price / rate)
                avail.append(max(stamp, self._fx_avail[fx_day]))
                fx_used.append(fx_day)
            s = Series(ticker, listing, tuple(levels), tuple(avail), tuple(fx_used), n_master, False)
        self._series[ticker] = s
        return s

    def _cash_series(self, ticker: str) -> Series:
        own = CASH_TICKERS[ticker]
        levels, avail, fx_used = [], [], []
        for d in self.dates:
            if own == self.currency:
                levels.append(1.0)
                avail.append(None)
                fx_used.append(None)
                continue
            fx = self._fx_on_or_before(d)
            if fx is None:
                levels.append(None)
                avail.append(None)
                fx_used.append(None)
                continue
            rate, fx_day = fx
            levels.append(rate if own == "USD" else 1.0 / rate)  # USD cash in CAD / CAD cash in USD
            avail.append(self._fx_avail[fx_day])
            fx_used.append(fx_day)
        return Series(ticker, own, tuple(levels), tuple(avail), tuple(fx_used), len(self.dates), True)

    def window_levels(self, ticker: str, i0: int, i1: int) -> list[float]:
        """Levels on [i0, i1]; ``Unavailable`` when any is missing or history is too short (A-21)."""
        s = self.series(ticker)
        if not s.synthetic and s.n_obs_master < MIN_MASTER_OBS_FOR_RISK:
            raise Unavailable("short_history", f"{ticker} has {s.n_obs_master} master-calendar observations (< {MIN_MASTER_OBS_FOR_RISK})")
        out = s.levels[i0:i1 + 1]
        if any(v is None for v in out):
            raise Unavailable("short_history", f"{ticker} has no observation on some master days in the window")
        return list(out)

    def fx_rows_used(self, tickers, i0: int, i1: int) -> int:
        days = set()
        for t in tickers:
            for d in self.series(t).fx_used[i0:i1 + 1]:
                if d is not None:
                    days.add(d)
        return len(days)

    def latest_avail(self, tickers, i1: int) -> str | None:
        stamps = [self.series(t).avail[i1] for t in tickers]
        stamps = [s for s in stamps if s]
        return max(stamps) if stamps else None
