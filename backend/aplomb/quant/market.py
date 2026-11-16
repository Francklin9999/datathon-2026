"""Gated, currency-converted price levels on the master calendar (quant SPEC §2–§4).

Built lazily per ticker from one ``TemporalGate``; nothing is read outside the gate and nothing
is filled: a master day without an observation (or without an earlier FX rate) is ``None``.
"""

from __future__ import annotations

import bisect
import re
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
    levels: tuple[float | None, ...]       # reporting currency, aligned to MarketData.dates
    avail: tuple[str | None, ...]          # availability of the latest row used per date
    fx_used: tuple[tuple[tuple[str, str, str, str], ...], ...]  # dataset, currency, observation date, availability
    n_obs_master: int                      # visible master-calendar observations
    synthetic: bool                        # cash pseudo-asset


class MarketData:
    """Master-calendar levels in one reporting currency under one gate."""

    def __init__(self, gate: TemporalGate, currency: str) -> None:
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency must be an uppercase three-letter code")
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
        self._global: dict[str, tuple[tuple[str, ...], tuple[dict, ...]]] = {}
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

    def _cad_quote(self, currency: str, day: str):
        """CAD per one currency unit and the immutable gated source rows used."""
        if currency == "CAD":
            return 1.0, ()
        if currency == "USD":
            value = self._fx_on_or_before(day)
            if value is None:
                return None
            rate, observed = value
            return rate, (("fx_usdcad_daily", "USD", observed, self._fx_avail[observed]),)
        if currency not in self._global:
            sl = self.gate.global_fx(currency)
            self.reads.append(sl.dataset_read())
            self._global[currency] = (tuple(row["date"] for row in sl.rows), tuple(sl.rows))
        dates, rows = self._global[currency]
        i = bisect.bisect_right(dates, day) - 1
        if i < 0:
            return None
        row = rows[i]
        rate = row["cad_per_unit"]
        if not isinstance(rate, (int, float)) or not 0 < rate < float("inf"):
            return None
        return rate, (("fx_boc_global", currency, row["date"], row["available_at"]),)

    def conversion_at(self, source: str, target: str, day: str):
        """Target units per source unit via CAD. Missing rates remain unavailable."""
        if source == target:
            return 1.0, ()
        a, b = self._cad_quote(source, day), self._cad_quote(target, day)
        if a is None or b is None:
            return None
        return a[0] / b[0], a[1] + b[1]

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
                    fx_used.append(())
                    continue
                n_master += 1
                price = row["adj_close"]
                stamp = row["available_at"]
                if listing == self.currency:
                    levels.append(price)
                    avail.append(stamp)
                    fx_used.append(())
                    continue
                fx = self.conversion_at(listing, self.currency, d)
                if fx is None:
                    levels.append(None)
                    avail.append(None)
                    fx_used.append(())
                    continue
                rate, refs = fx
                levels.append(price * rate)
                avail.append(max([stamp, *(ref[3] for ref in refs)]))
                fx_used.append(refs)
            s = Series(ticker, tuple(levels), tuple(avail), tuple(fx_used), n_master, False)
        self._series[ticker] = s
        return s

    def _cash_series(self, ticker: str) -> Series:
        own = CASH_TICKERS[ticker]
        levels, avail, fx_used = [], [], []
        for d in self.dates:
            if own == self.currency:
                levels.append(1.0)
                avail.append(None)
                fx_used.append(())
                continue
            fx = self.conversion_at(own, self.currency, d)
            if fx is None:
                levels.append(None)
                avail.append(None)
                fx_used.append(())
                continue
            rate, refs = fx
            levels.append(rate)
            avail.append(max((ref[3] for ref in refs), default=None))
            fx_used.append(refs)
        return Series(ticker, tuple(levels), tuple(avail), tuple(fx_used), len(self.dates), True)

    def window_levels(self, ticker: str, i0: int, i1: int) -> list[float]:
        """Levels on [i0, i1]; ``Unavailable`` when any is missing or history is too short (A-21)."""
        s = self.series(ticker)
        if not s.synthetic and s.n_obs_master < MIN_MASTER_OBS_FOR_RISK:
            raise Unavailable("short_history", f"{ticker} has {s.n_obs_master} master-calendar observations (< {MIN_MASTER_OBS_FOR_RISK})")
        out = s.levels[i0:i1 + 1]
        if any(v is None for v in out):
            raise Unavailable("short_history", f"{ticker} has no observation on some master days in the window")
        return list(out)

    def fx_dataset_rows_used(self, tickers, i0: int, i1: int) -> dict[str, int]:
        refs = {ref[:3] for ticker in tickers for group in self.series(ticker).fx_used[i0:i1 + 1] for ref in group}
        return {dataset: sum(1 for ref in refs if ref[0] == dataset) for dataset in {ref[0] for ref in refs}}

    def fx_rows_used(self, tickers, i0: int, i1: int) -> int:
        return sum(self.fx_dataset_rows_used(tickers, i0, i1).values())

    def latest_avail(self, tickers, i1: int) -> str | None:
        stamps = [self.series(t).avail[i1] for t in tickers]
        stamps = [s for s in stamps if s]
        return max(stamps) if stamps else None
