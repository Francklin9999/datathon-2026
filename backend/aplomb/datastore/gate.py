"""Temporal gate: the only run-visible reader of a snapshot (datastore SPEC §4).

A row is visible iff its availability timestamp for the gate's mode is strictly before the
boundary (00:00:00.000Z of the day after ``as_of``) and its observation/reference date lies in
the requested interval. ``rows_withheld`` counts candidate rows (same keys and interval)
rejected by availability, before any other transformation (``M_GATE_COUNT``). Nothing is
forward-filled across the cutoff; FX reads may add the last *earlier* visible rate.
"""

from __future__ import annotations

import bisect
from datetime import date
from types import MappingProxyType

from .availability import BASIS_MONTHLY_LAG
from .constants import (
    CALENDAR_REF_CAD,
    CALENDAR_REF_USD,
    CASH_TICKERS,
    LIM_CALENDAR_INTERSECTION,
    LIM_CASH_NO_INTEREST,
    LIM_CNQ_FACTOR,
    LIM_FX_FFILL,
    LIM_MACRO_LAG_ASSUMED,
    LIM_MACRO_REVISED,
    LIM_SECTOR_LABELS,
    LIM_SURVIVORSHIP,
    LIM_THEME_TAGS,
    LIM_YAHOO_NOT_CERTIFIED,
)
from .errors import InvalidGateRequest, UnknownSeries, UnknownTicker
from .quality import is_split_anomaly
from .schemas import NORMALIZED
from .snapshot import AVAIL_KEYS, Snapshot, validate_gate_args
from .timeutil import boundary_for, parse_date
from .types import DatasetRead, DataSlice, FxSeries, MasterCalendar, PriceFrame

# Limitation codes attached to every read of a dataset (datastore-level; quant adds its own).
_READ_LIMITATIONS: dict[str, tuple[str, ...]] = {
    "assets_universe": (LIM_SURVIVORSHIP, LIM_SECTOR_LABELS),
    "prices_daily": (LIM_YAHOO_NOT_CERTIFIED,),
    "corporate_actions": (LIM_YAHOO_NOT_CERTIFIED,),
    "fx_usdcad_daily": (LIM_FX_FFILL,),
    "fx_boc_global": (LIM_FX_FFILL,),
    "macro_rates": (),
    "asset_themes": (LIM_THEME_TAGS,),
    "macro_release_dates": (),
}
# Split anomalies that have a catalog limitation code.
_ANOMALY_LIMITATION = {"CNQ.TO": LIM_CNQ_FACTOR}


class TemporalGate:
    """Gated reader bound to one snapshot version, one ``as_of`` date and one mode."""

    def __init__(self, snapshot: Snapshot, as_of: date | str, mode: str = "current") -> None:
        self._snap = snapshot
        self.as_of, self.mode = validate_gate_args(as_of, mode)
        self.boundary = boundary_for(self.as_of)
        self.data_version = snapshot.data_version
        self._key = AVAIL_KEYS[self.mode]
        self._universe = None
        ca = snapshot._table("corporate_actions") if "corporate_actions" in snapshot.loaded_datasets else None
        self._anomalies: dict[str, tuple[dict, ...]] = {}
        if ca is not None:
            for ticker, (_, rows) in ca.by["group"].items():
                hits = tuple(r for r in rows if r["action"] == "split" and is_split_anomaly(r["value"]))
                if hits:
                    self._anomalies[ticker] = hits

    def __repr__(self) -> str:
        return f"TemporalGate({self.data_version}, as_of={self.as_of.isoformat()}, mode={self.mode})"

    # Core helpers -----------------------------------------------------------------------------

    def _visible(self, row: dict) -> bool:
        stamp = row[self._key]
        return stamp != "" and stamp < self.boundary

    def _out(self, row: dict) -> dict:
        out = {k: v for k, v in row.items() if not k.startswith("available_at")}
        out["available_at"] = row[self._key] or None
        return out

    def _interval(self, start, end) -> tuple[str | None, str]:
        try:
            s = parse_date(start, "start").isoformat() if start is not None else None
            e = parse_date(end, "end").isoformat() if end is not None else self.as_of.isoformat()
        except ValueError as exc:
            raise InvalidGateRequest(str(exc)) from exc
        if s is not None and s > e:
            raise InvalidGateRequest(f"start {s} is after end {e}")
        return s, e

    @staticmethod
    def _range(dates: tuple[str, ...], start: str | None, end: str) -> tuple[int, int]:
        lo = bisect.bisect_left(dates, start) if start is not None else 0
        hi = bisect.bisect_right(dates, end)
        return lo, max(lo, hi)

    def _split(self, candidates) -> tuple[list[dict], int]:
        visible = [r for r in candidates if self._visible(r)]
        return visible, len(candidates) - len(visible)

    def _slice(self, dataset_id: str, visible: list[dict], withheld: int, extra_lims: tuple[str, ...] = ()) -> DataSlice:
        date_col = NORMALIZED[dataset_id].date_column
        last = max((r[date_col] for r in visible), default=None) if date_col else None
        lims = tuple(dict.fromkeys(_READ_LIMITATIONS.get(dataset_id, ()) + extra_lims))
        rows = tuple(self._out(r) for r in visible)
        return DataSlice(rows, dataset_id, self.data_version, len(rows), withheld, lims, last)

    def _price_rows(self, ticker: str, start: str | None, end: str) -> tuple[list[dict], int]:
        group = self._snap._table("prices_daily").by["group"].get(ticker)
        if group is None:
            return [], 0
        dates, rows = group
        lo, hi = self._range(dates, start, end)
        return self._split(rows[lo:hi])

    def _known(self, ticker: str) -> dict:
        """Universe row of a ticker known under this gate, else ``UnknownTicker``."""
        group = self._snap._table("assets_universe").by["group"].get(ticker)
        if group is None or not self._visible(group[1][0]):
            where = (f"at as_of {self.as_of.isoformat()}" if self.mode == "historical"
                     else f"in snapshot {self.data_version}")
            raise UnknownTicker(f"{ticker} is not known {where}")
        return group[1][0]

    def _anomaly_lims(self, ticker: str, visible: list[dict]) -> tuple[str, ...]:
        code = _ANOMALY_LIMITATION.get(ticker)
        if not code or not visible or ticker not in self._anomalies:
            return ()
        first, last = visible[0]["date"], visible[-1]["date"]
        if any(first < a["ex_date"] <= last and self._visible(a) for a in self._anomalies[ticker]):
            return (code,)
        return ()

    @staticmethod
    def _tickers(tickers) -> list[str]:
        if isinstance(tickers, str):
            tickers = [tickers]
        out = list(dict.fromkeys(tickers))
        if not out:
            raise InvalidGateRequest("at least one ticker is required")
        return out

    # Spec interface ---------------------------------------------------------------------------

    def prices(self, tickers: list[str], start: date | str | None, end: date | str | None) -> DataSlice:
        """Gated ``prices_daily`` rows for listed tickers, ordered by ticker (as requested) then date."""
        s, e = self._interval(start, end)
        visible_all: list[dict] = []
        withheld = 0
        lims: tuple[str, ...] = ()
        for t in self._tickers(tickers):
            if t in CASH_TICKERS:
                raise UnknownTicker(f"{t} is a cash pseudo-asset with no price rows; use price_frame()")
            self._known(t)
            visible, w = self._price_rows(t, s, e)
            visible_all.extend(visible)
            withheld += w
            lims += self._anomaly_lims(t, visible)
        return self._slice("prices_daily", visible_all, withheld, lims)

    def fx(self, start: date | str | None, end: date | str | None) -> DataSlice:
        """Gated USD/CAD rows in [start, end] plus the last visible rate before ``start``.

        The preceding row lets conversion carry the last previously available rate; with no
        visible earlier row the first in-window day simply has no prior rate. Never a later rate.
        """
        s, e = self._interval(start, end)
        dates, rows = self._snap._table("fx_usdcad_daily").by["all"]
        lo, hi = self._range(dates, s, e)
        visible, withheld = self._split(rows[lo:hi])
        if s is not None:
            for r in reversed(rows[:lo]):
                if self._visible(r):
                    visible.insert(0, r)
                    break
        return self._slice("fx_usdcad_daily", visible, withheld)

    def global_fx(self, currency: str, start: date | str | None = None, end: date | str | None = None) -> DataSlice:
        """Gated CAD-per-unit rates for one currency, with the latest earlier visible row.

        Absent optional data and unknown series yield an empty slice, never inferred rates.
        Historical visibility follows the captured vintage availability, not observation date.
        """
        s, e = self._interval(start, end)
        if "fx_boc_global" not in self._snap.loaded_datasets:
            return self._slice("fx_boc_global", [], 0)
        group = self._snap._table("fx_boc_global").by["group"].get(currency)
        if group is None:
            return self._slice("fx_boc_global", [], 0)
        dates, rows = group
        lo, hi = self._range(dates, s, e)
        visible, withheld = self._split(rows[lo:hi])
        if s is not None:
            for row in reversed(rows[:lo]):
                if self._visible(row):
                    visible.insert(0, row)
                    break
        return self._slice("fx_boc_global", visible, withheld)

    def macro(self, series_id: str, start: date | str | None, end: date | str | None) -> DataSlice:
        s, e = self._interval(start, end)
        group = self._snap._table("macro_rates").by["group"].get(series_id)
        if group is None:
            raise UnknownSeries(f"macro series {series_id!r} is not in snapshot {self.data_version}")
        dates, rows = group
        lo, hi = self._range(dates, s, e)
        visible, withheld = self._split(rows[lo:hi])
        lims: tuple[str, ...] = ()
        if rows and rows[0]["revised_latest_vintage"]:
            lims += (LIM_MACRO_REVISED,)
        if self.mode == "current" and any(r["availability_basis"] == BASIS_MONTHLY_LAG for r in visible):
            lims += (LIM_MACRO_LAG_ASSUMED,)
        return self._slice("macro_rates", visible, withheld, lims)

    def dataset(self, dataset_id: str, filters: dict | None = None) -> DataSlice:
        """Generic gated read with equality filters; ``start``/``end`` filter the date column."""
        table = self._snap._table(dataset_id)
        schema = table.schema
        filters = dict(filters or {})
        start, end = filters.pop("start", None), filters.pop("end", None)
        types = {c.name: c.type for c in schema.columns}
        for k in filters:
            if k not in types or k.startswith("available_at"):
                raise InvalidGateRequest(f"{dataset_id} has no filterable column {k!r}")
        if schema.date_column:
            s, e = self._interval(start, end)
            dates, rows = table.by["all"]
            lo, hi = self._range(dates, s, e)
            candidates = rows[lo:hi]
        else:
            if start is not None or end is not None:
                raise InvalidGateRequest(f"{dataset_id} has no date column for start/end")
            candidates = table.rows
        wanted = {k: self._coerce(types[k], v, k) for k, v in filters.items()}
        candidates = [r for r in candidates if all(r[k] == v for k, v in wanted.items())]
        visible, withheld = self._split(candidates)
        lims: tuple[str, ...] = ()
        if dataset_id == "prices_daily":
            by_t: dict[str, list[dict]] = {}
            for r in visible:
                by_t.setdefault(r["ticker"], []).append(r)
            for t, rs in by_t.items():
                lims += self._anomaly_lims(t, rs)
        if dataset_id == "macro_rates":
            if any(r["revised_latest_vintage"] for r in visible):
                lims += (LIM_MACRO_REVISED,)
            if self.mode == "current" and any(r["availability_basis"] == BASIS_MONTHLY_LAG for r in visible):
                lims += (LIM_MACRO_LAG_ASSUMED,)
        return self._slice(dataset_id, visible, withheld, lims)

    @staticmethod
    def _coerce(kind: str, value, name: str):
        if kind == "number":
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise InvalidGateRequest(f"filter {name}: expected a number") from exc
        if kind == "boolean":
            if isinstance(value, bool):
                return value
            raise InvalidGateRequest(f"filter {name}: expected a boolean")
        if kind == "date":
            try:
                return parse_date(value, name).isoformat()
            except ValueError as exc:
                raise InvalidGateRequest(str(exc)) from exc
        return value

    def describe(self, dataset_id: str) -> dict:
        """DatasetPassport (wire-shaped dict) of a catalog dataset in this snapshot."""
        return self._snap.passport(dataset_id)

    # Quant handoff (T05) ----------------------------------------------------------------------

    def master_calendar(self, start: date | str | None = None, end: date | str | None = None) -> MasterCalendar:
        """Visible XIU.TO dates ∩ visible SPY dates in [start, end] (A-15, ``M_CAL_INTERSECTION``)."""
        s, e = self._interval(start, end)
        cad, w1 = self._price_rows(CALENDAR_REF_CAD, s, e)
        usd, w2 = self._price_rows(CALENDAR_REF_USD, s, e)
        dates = tuple(sorted({r["date"] for r in cad} & {r["date"] for r in usd}))
        read = DatasetRead("prices_daily", self.data_version, len(cad) + len(usd), w1 + w2)
        return MasterCalendar(dates, self.data_version, (read,), (LIM_CALENDAR_INTERSECTION,))

    def price_frame(self, tickers: list[str], start: date | str | None = None, end: date | str | None = None,
                    calendar: str = "master") -> PriceFrame:
        """Adjusted closes aligned on the master calendar (default) or on the union of the
        requested assets' own dates. Missing observations are ``None``; nothing is filled.
        Cash pseudo-assets are constant 1.0 in their own currency."""
        if calendar not in ("master", "union"):
            raise InvalidGateRequest("calendar must be 'master' or 'union'")
        s, e = self._interval(start, end)
        wanted = self._tickers(tickers)
        listed = [t for t in wanted if t not in CASH_TICKERS]
        cash = [t for t in wanted if t in CASH_TICKERS]
        currencies = {t: self._known(t)["currency"] for t in listed}
        currencies.update({t: CASH_TICKERS[t] for t in cash})
        to_read = list(listed)
        if calendar == "master":
            to_read += [r for r in (CALENDAR_REF_CAD, CALENDAR_REF_USD) if r not in to_read]
        visible: dict[str, list[dict]] = {}
        n_rows = withheld = 0
        lims: tuple[str, ...] = (LIM_YAHOO_NOT_CERTIFIED,)
        for t in to_read:
            rows, w = self._price_rows(t, s, e)
            visible[t] = rows
            n_rows += len(rows)
            withheld += w
            if t in listed:
                lims += self._anomaly_lims(t, rows)
        if calendar == "master":
            dates = tuple(sorted({r["date"] for r in visible[CALENDAR_REF_CAD]} & {r["date"] for r in visible[CALENDAR_REF_USD]}))
            lims += (LIM_CALENDAR_INTERSECTION,)
        else:
            dates = tuple(sorted({r["date"] for t in listed for r in visible[t]}))
        columns: dict[str, tuple[float | None, ...]] = {}
        for t in listed:
            by_date = {r["date"]: r["adj_close"] for r in visible[t]}
            columns[t] = tuple(by_date.get(d) for d in dates)
        for t in cash:
            columns[t] = tuple(1.0 for _ in dates)
        if cash:
            lims += (LIM_CASH_NO_INTEREST,)
        return PriceFrame(
            dates=dates,
            tickers=tuple(wanted),
            adj_close=MappingProxyType({t: columns[t] for t in wanted}),
            currencies=MappingProxyType({t: currencies[t] for t in wanted}),
            synthetic=frozenset(cash),
            calendar=calendar,
            data_version=self.data_version,
            reads=(DatasetRead("prices_daily", self.data_version, n_rows, withheld),),
            limitations=tuple(dict.fromkeys(lims)),
        )

    def fx_series(self, start: date | str | None = None, end: date | str | None = None) -> FxSeries:
        sl = self.fx(start, end)
        return FxSeries(
            dates=tuple(r["date"] for r in sl.rows),
            usdcad=tuple(r["usdcad"] for r in sl.rows),
            data_version=self.data_version,
            reads=(sl.dataset_read(),),
            limitations=sl.limitations,
        )

    def universe(self):
        """Assets known under this gate (cached per gate)."""
        if self._universe is None:
            from .universe import Universe

            self._universe = Universe(self)
        return self._universe

    # Time Machine support (T12) ---------------------------------------------------------------

    def availability_summary(self) -> list[dict]:
        """Per loaded dataset: rows visible, rows withheld, last visible observation date.

        ``lastVisibleDate`` is null when nothing is visible or the dataset has no date column;
        it is never invented (timemachine SPEC §2)."""
        out = []
        for ds_id in self._snap.loaded_datasets:
            table = self._snap._table(ds_id)
            visible, withheld = self._split(table.rows)
            date_col = table.schema.date_column
            last = max((r[date_col] for r in visible), default=None) if date_col else None
            out.append({"datasetId": ds_id, "dataVersion": self.data_version, "rowsVisible": len(visible),
                        "rowsWithheld": withheld, "lastVisibleDate": last})
        return out
