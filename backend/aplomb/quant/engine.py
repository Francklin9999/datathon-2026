"""Quant engine: portfolio views, metrics and facts (track T05, quant SPEC).

One ``QuantEngine`` = one gate (pinned version, as-of, mode), one reporting currency, one request
window and one ledger. ``view(weights, variant)`` returns a ``PortfolioView`` whose
``measure(metric, key)`` gives the rule engine a value plus the ID of the fact that holds it, or
a typed ``nee`` reason. Raw ``*_value`` methods compute the same numbers without registering facts
(for optimizer grid scans); only retained results should become facts.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from aplomb.contracts.models import PortfolioSnapshot
from aplomb.datastore import TemporalGate, UnknownTicker
from aplomb.datastore.constants import CASH_TICKERS

from . import metrics as mx
from .facts import FactContext, FactSink, fact_key, make_fact
from .market import MarketData, Unavailable

PORTFOLIO_LIMITATIONS = ("LIM_SAMPLE_WINDOW", "LIM_SURVIVORSHIP", "LIM_CONSTANT_WEIGHTS",
                         "LIM_YAHOO_NOT_CERTIFIED", "LIM_CALENDAR_INTERSECTION")
STRESS_2022 = ("2021-12-31", "2022-12-31")
RATE_CYCLE = ("2022-03-02", "2023-07-13")  # A-23; base is the day before the first increase (2022-03-03)
CNQ_FACTOR_DATE = "2022-08-22"
GROUP_ORDER = ("equity", "fixed_income", "commodity", "crypto", "cash")


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _years_before(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # 29 February
        return d.replace(year=d.year - years, day=28)


@dataclass(frozen=True)
class WindowRange:
    code: str              # fact-key token: full, 1y, 3y, 5y, ytd, custom:<start>..<end>
    spec: dict             # WindowSpec wire
    i0: int
    i1: int
    period: dict           # actual dates used


@dataclass(frozen=True)
class Measurement:
    """A value for the rule engine: number + fact, or null + nee reason."""

    value: float | None
    fact_id: str | None
    unit: str = "pct"
    worst: dict | None = None
    nee_reason: str | None = None
    detail: str | None = None


@dataclass
class PortfolioMetrics:
    """quant SPEC §1: volatility, positive drawdown, signed stress return, HHI/effective N."""

    volatility_pct: float | None
    max_drawdown_pct: float | None
    stress2022_pct: float | None          # signed return; the rule uses max(0, -value)
    hhi: float
    effective_n: float
    fact_ids: dict[str, str] = field(default_factory=dict)
    missing: dict[str, str] = field(default_factory=dict)   # metric -> NeeReason


class QuantEngine:
    def __init__(self, gate: TemporalGate, ledger: FactSink, *, currency: str, subject_id: str,
                 created_at: str, window: dict | None = None) -> None:
        self.gate = gate
        self.ledger = ledger
        self.currency = currency
        self.subject_id = subject_id
        self.market = MarketData(gate, currency)
        self.universe = gate.universe()
        self.ctx = FactContext(gate.as_of.isoformat(), created_at, gate.data_version)
        self.window_spec = dict(window or {"code": "full"})
        self._returns_cache: dict[tuple[str, int, int], list[float]] = {}
        p_passport = gate.describe("prices_daily")
        f_passport = gate.describe("fx_usdcad_daily")
        self._src = {"prices_daily": p_passport, "fx_usdcad_daily": f_passport}
        if "fx_boc_global" in gate._snap.loaded_datasets:
            self._src["fx_boc_global"] = gate.describe("fx_boc_global")
        self._universe_avail: dict[str, str] | None = None

    # Windows ----------------------------------------------------------------------------------

    def window(self, spec: dict | None = None) -> WindowRange:
        spec = dict(spec or self.window_spec)
        code = spec.get("code", "full")
        dates = self.market.dates
        if len(dates) < 2:
            raise Unavailable("not_visible_at_asof", "fewer than two master-calendar days are visible")
        i1 = len(dates) - 1
        if code == "full":
            i0 = 0
        elif code in ("1y", "3y", "5y"):
            target = _years_before(date.fromisoformat(dates[i1]), int(code[0])).isoformat()
            if target < dates[0]:
                raise Unavailable("short_history", f"history starts {dates[0]}, after the {code} window start {target}")
            i0 = self.market.last_index_on_or_before(target)
        elif code == "ytd":
            i0 = self.market.last_index_on_or_before(f"{int(dates[i1][:4]) - 1}-12-31")
            if i0 is None:
                raise Unavailable("short_history", "no master day before the start of the year")
        elif code == "custom":
            start, end = spec.get("start"), spec.get("end")
            if not start or not end or start > end:
                raise Unavailable("short_history", "custom window needs start <= end")
            i0 = self.market.last_index_on_or_before(start)
            i1c = self.market.last_index_on_or_before(end)
            if i0 is None or i1c is None:
                raise Unavailable("short_history", "custom window starts before the visible history")
            i1 = i1c
            code = f"custom:{start}..{end}"
        else:
            raise ValueError(f"unknown window code {code!r}")
        if i0 is None or i1 <= i0:
            raise Unavailable("short_history", "window holds fewer than two master-calendar days")
        return WindowRange(code, spec, i0, i1, {"start": dates[i0], "end": dates[i1]})

    def _named_range(self, start: str, end: str) -> tuple[int, int]:
        # The master calendar holds no weekend day: once only weekend days remain before ``end``
        # the window is complete. Calendar arithmetic only, no row after the cutoff is read.
        last = date.fromisoformat(end)
        while last.weekday() >= 5:
            last -= timedelta(days=1)
        if self.ctx.as_of < last.isoformat():
            raise Unavailable("not_visible_at_asof", f"the window ends {end}, after as_of {self.ctx.as_of}")
        i0 = self.market.last_index_on_or_before(start)
        i1 = self.market.last_index_on_or_before(end)
        if i0 is None or i1 is None or i1 <= i0:
            raise Unavailable("short_history", f"no master-calendar boundary on or before {start}")
        return i0, i1

    # Raw numbers (no facts) -------------------------------------------------------------------

    def asset_returns(self, ticker: str, i0: int, i1: int) -> list[float]:
        key = (ticker, i0, i1)
        r = self._returns_cache.get(key)
        if r is None:
            r = mx.simple_returns(self.market.window_levels(ticker, i0, i1))
            self._returns_cache[key] = r
        return r

    def portfolio_levels(self, weights: dict[str, float], i0: int, i1: int) -> list[float]:
        tickers = sorted(weights)
        rets = [self.asset_returns(t, i0, i1) for t in tickers]
        return mx.compound(mx.portfolio_returns([weights[t] for t in tickers], rets))

    def risk_values(self, weights: dict[str, float], wr: WindowRange | None = None) -> dict:
        """Volatility, drawdown and signed 2022 stress without facts; values None + reasons."""
        wr = wr or self.window()
        out: dict = {"missing": {}}
        try:
            levels = self.portfolio_levels(weights, wr.i0, wr.i1)
            out["vol"] = mx.annualized_vol_pct(mx.simple_returns(levels))
            out["mdd"] = mx.max_drawdown_pct(levels)
        except Unavailable as exc:
            out["vol"] = out["mdd"] = None
            out["missing"]["vol"] = out["missing"]["mdd"] = exc.reason
        try:
            i0, i1 = self._named_range(*STRESS_2022)
            out["stress2022"] = mx.period_return_pct(self.portfolio_levels(weights, i0, i1))
        except Unavailable as exc:
            out["stress2022"] = None
            out["missing"]["stress2022"] = exc.reason
        return out

    # Fact helpers -----------------------------------------------------------------------------

    def _sources(self, tickers, i0: int, i1: int) -> list[dict]:
        listed = [t for t in tickers if t not in CASH_TICKERS]
        out = []
        if listed:
            out.append(self._source("prices_daily", len(listed) * (i1 - i0 + 1)))
        for dataset, n_fx in sorted(self.market.fx_dataset_rows_used(tickers, i0, i1).items()):
            out.append(self._source(dataset, n_fx))
        return out

    def universe_provenance(self, tickers) -> tuple[list[dict], str | None]:
        """Source reference and latest availability of the universe rows of listed ``tickers``.

        ``([], None)`` when none is listed (cash only): nothing was read from the dataset."""
        if self._universe_avail is None:
            rows = self.gate.dataset("assets_universe", {}).rows
            self._universe_avail = {r["ticker"]: r["available_at"] for r in rows}
            self._src["assets_universe"] = self.gate.describe("assets_universe")
        stamps = [self._universe_avail[t] for t in tickers if self._universe_avail.get(t)]
        if not stamps:
            return [], None
        return [self._source("assets_universe", len(stamps))], max(stamps)

    def _source(self, dataset_id: str, rows: int) -> dict:
        p = self._src[dataset_id]
        return {"datasetId": dataset_id, "dataVersion": self.ctx.data_version, "sourceName": p["source"],
                "sourceUrl": p["sourceUrl"], "retrievedOn": p["retrievedOn"] or self.ctx.as_of,
                "licence": p["licence"], "rowsRead": rows}

    def _limitations(self, tickers, i0: int, i1: int, base=PORTFOLIO_LIMITATIONS) -> list[str]:
        lims = list(base)
        if self.market.fx_rows_used(tickers, i0, i1):
            lims.append("LIM_FX_FFILL")
        dates = self.market.dates
        if "CNQ.TO" in tickers and dates[i0] < CNQ_FACTOR_DATE <= dates[i1]:
            lims.append("LIM_CNQ_FACTOR")
        if any(t in CASH_TICKERS for t in tickers):
            lims.append("LIM_CASH_NO_INTEREST")
        return lims

    def _checks(self, i0: int, i1: int) -> list[dict]:
        return [{"code": "gated_inputs", "ok": True,
                 "detail": f"Rows read through the temporal gate ({self.gate.mode}, as of {self.ctx.as_of}, "
                           f"{self.ctx.data_version}); master days {self.market.dates[i0]}..{self.market.dates[i1]}."}]

    def add_series_fact(self, *, metric: str, value: float | None, subject: dict, variant_key: str, window_code: str,
                        tickers, i0: int, i1: int, method_id: str, label: dict, kind: str = "computed",
                        window_spec: dict | None = None, unit: str = "pct", currency: str | None = None,
                        params: dict | None = None, inputs: list[str] | None = None, base_lims=PORTFOLIO_LIMITATIONS,
                        extra_lims: tuple[str, ...] = (), created_by: str = "quant") -> str:
        key = fact_key(metric, subject["type"], subject["id"], variant_key, window_code)
        fact = make_fact(
            self.ctx, key=key, kind=kind, metric=metric, label=label, value=value, unit=unit, currency=currency,
            subject=subject, method_id=method_id, created_by=created_by,
            period={"start": self.market.dates[i0], "end": self.market.dates[i1]}, window=window_spec,
            available_at=self.market.latest_avail(tickers, i1), params=params,
            inputs=[*self.series_inputs(tickers, i0, i1), *(inputs or [])],
            n_obs=i1 - i0 + 1, sources=self._sources(tickers, i0, i1),
            limitations=self._limitations(tickers, i0, i1, base_lims) + list(extra_lims), checks=self._checks(i0, i1),
        )
        return self.ledger.add_fact(fact)

    def series_inputs(self, tickers, i0: int, i1: int) -> list[str]:
        """Receipt for the actual gated, currency-converted inputs, not model declarations.

        The immutable snapshot supplies source checksums; this receipt additionally pins
        the exact dates/levels consumed by a calculation. It is not a return forecast.
        """
        tickers = sorted(tickers)
        payload = {"dates": self.market.dates[i0:i1 + 1], "currency": self.currency,
                   "levels": {t: self.market.series(t).levels[i0:i1 + 1] for t in tickers}}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        sources = self._sources(tickers, i0, i1)
        fact = make_fact(
            self.ctx, key=fact_key("count.sources", "request", digest, "gated", "full"),
            kind="observed" if sources else "assumption", metric="count.sources",
            label={"en": "Source receipt for gated calculation inputs", "fr": "Reçu des sources des entrées filtrées"},
            value=len(sources), unit="count", currency=None,
            subject={"type": "request", "id": digest, "variant": "gated"},
            method_id="M_GATE_COUNT", created_by="quant",
            available_at=self.market.latest_avail(tickers, i1), sources=sources,
            n_obs=i1 - i0 + 1,
            params={"inputSha256": digest, "tickers": json.dumps(tickers), "currency": self.currency,
                    "dataVersion": self.ctx.data_version, "gateMode": self.gate.mode,
                    "start": self.market.dates[i0], "end": self.market.dates[i1]},
            checks=self._checks(i0, i1), limitations=["LIM_PAST_NOT_FUTURE"],
        )
        return [self.ledger.add_fact(fact)]

    # Public views -----------------------------------------------------------------------------

    def view(self, weights: dict[str, float], variant: str, total_value: float, *, after_move: bool | None = None,
             window: dict | None = None, record: bool = True) -> "PortfolioView":
        """``record=False`` computes the same values without registering facts (grid scans)."""
        return PortfolioView(self, weights, variant, total_value, after_move=variant != "before" if after_move is None else after_move,
                             window=window, record=record)

    def asset_metrics(self, ticker: str, window: dict | None = None) -> dict[str, Measurement]:
        """quant.asset_metrics: return.period, vol.annualized, drawdown.max, return.worst_12m (reporting currency)."""
        out: dict[str, Measurement] = {}
        try:
            wr = self.window(window)
            levels = self.market.window_levels(ticker, wr.i0, wr.i1)
        except Unavailable as exc:
            return {m: Measurement(None, None, nee_reason=exc.reason, detail=exc.detail)
                    for m in ("return.period", "vol.annualized", "drawdown.max", "return.worst_12m")}
        variant = f"na:currency:{self.currency}"
        subject = {"type": "asset", "id": ticker, "variant": variant}
        name = self._name(ticker)
        values = {
            "return.period": (mx.period_return_pct(levels), "M_RET_SIMPLE", "return"),
            "vol.annualized": (mx.annualized_vol_pct(mx.simple_returns(levels)), "M_VOL_STDEV_252", "volatility"),
            "drawdown.max": (mx.max_drawdown_pct(levels), "M_MDD_PEAK_TROUGH", "largest fall"),
            "return.worst_12m": (mx.worst_rolling_return_pct(levels), "M_WORST_ROLLING_252", "worst 12-month return"),
        }
        fr_names = {"return": "rendement", "volatility": "volatilité", "largest fall": "plus forte baisse",
                    "worst 12-month return": "pire rendement sur 12 mois"}
        for metric, (value, method, what) in values.items():
            if value is None:
                out[metric] = Measurement(None, None, nee_reason="short_history")
                continue
            fid = self.add_series_fact(
                metric=metric, value=value, subject=subject, variant_key=variant,
                window_code=wr.code, tickers=[ticker], i0=wr.i0, i1=wr.i1, method_id=method, window_spec=wr.spec,
                label={"en": f"{name} ({ticker}) {what}, {self.currency}", "fr": f"{name} ({ticker}), {fr_names[what]}, {self.currency}"},
                base_lims=("LIM_SAMPLE_WINDOW", "LIM_YAHOO_NOT_CERTIFIED", "LIM_CALENDAR_INTERSECTION", "LIM_PAST_NOT_FUTURE"),
            )
            out[metric] = Measurement(value, fid)
        return out

    def calendar_year_return(self, ticker: str, year: int) -> list[Measurement]:
        """quant.calendar_year_return on the asset's own calendar (``M_RET_CALENDAR_YEAR``):
        one fact in the listing currency and, if different, one in the reporting currency."""
        end_bound = f"{year}-12-31"
        if self.ctx.as_of < end_bound:
            return [Measurement(None, None, nee_reason="not_visible_at_asof")]
        try:
            rows = self.gate.prices([ticker], None, end_bound).rows
        except UnknownTicker:
            return [Measurement(None, None, nee_reason="asset_unknown")]
        base = [r for r in rows if r["date"] <= f"{year - 1}-12-31"]
        cur = [r for r in rows if r["date"] <= end_bound and r["date"] > f"{year - 1}-12-31"]
        if not base or not cur:
            return [Measurement(None, None, nee_reason="short_history")]
        a, b = base[-1], cur[-1]
        listing = self.universe.get(ticker).currency
        name = self._name(ticker)
        period = {"start": a["date"], "end": b["date"]}
        out = []
        currencies = [listing] + ([self.currency] if self.currency != listing else [])
        for ccy in currencies:
            pa, pb = a["adj_close"], b["adj_close"]
            sources = [self._source("prices_daily", 2)]
            lims = ["LIM_YAHOO_NOT_CERTIFIED", "LIM_PAST_NOT_FUTURE"]
            avail = max(a["available_at"], b["available_at"])
            if ccy != listing:
                ra = self.market.conversion_at(listing, ccy, a["date"])
                rb = self.market.conversion_at(listing, ccy, b["date"])
                if ra is None or rb is None:
                    out.append(Measurement(None, None, nee_reason="short_history", detail=f"no available {listing}/{ccy} FX rate"))
                    continue
                pa, pb = pa * ra[0], pb * rb[0]
                refs = {ref[:3] for ref in ra[1] + rb[1]}
                for dataset in sorted({ref[0] for ref in refs}):
                    sources.append(self._source(dataset, sum(1 for ref in refs if ref[0] == dataset)))
                avail = max([avail, *(ref[3] for ref in ra[1] + rb[1])])
                lims.append("LIM_FX_FFILL")
            if ticker == "CNQ.TO" and a["date"] < CNQ_FACTOR_DATE <= b["date"]:
                lims.append("LIM_CNQ_FACTOR")
            value = (pb / pa - 1.0) * 100.0
            variant = f"na:currency:{ccy}:year:{year}"
            key = fact_key("return.calendar_year", "asset", ticker, variant, str(year))
            fact = make_fact(
                self.ctx, key=key, kind="computed", metric="return.calendar_year",
                label={"en": f"{name} ({ticker}) return, calendar {year}, {ccy}",
                       "fr": f"{name} ({ticker}), rendement, année civile {year}, {ccy}"},
                value=value, unit="pct", currency=ccy, subject={"type": "asset", "id": ticker, "variant": variant},
                method_id="M_RET_CALENDAR_YEAR", created_by="quant", period=period, window=None, available_at=avail,
                params={"year": year, "baseDate": a["date"], "endDate": b["date"]}, n_obs=2, sources=sources,
                limitations=lims, checks=[{"code": "gated_inputs", "ok": True, "detail": f"Own-calendar rows read through the gate as of {self.ctx.as_of}."}],
            )
            out.append(Measurement(value, self.ledger.add_fact(fact)))
        return out

    def correlation(self, tickers: list[str], window: dict | None = None) -> dict[tuple[str, str], Measurement]:
        wr = self.window(window)
        variant = f"na:currency:{self.currency}"
        out = {}
        for i, a in enumerate(tickers):
            for b in tickers[i + 1:]:
                try:
                    ra, rb = self.asset_returns(a, wr.i0, wr.i1), self.asset_returns(b, wr.i0, wr.i1)
                except Unavailable as exc:
                    out[(a, b)] = Measurement(None, None, unit="ratio", nee_reason=exc.reason)
                    continue
                value = mx.pearson(ra, rb)
                if value is None:
                    out[(a, b)] = Measurement(None, None, unit="ratio", nee_reason="short_history", detail="zero variance")
                    continue
                fid = self.add_series_fact(
                    metric="corr.pair", value=value, subject={"type": "asset", "id": f"{a}~{b}", "variant": variant},
                    variant_key=variant, window_code=wr.code, tickers=[a, b], i0=wr.i0, i1=wr.i1,
                    method_id="M_CORR_PEARSON", window_spec=wr.spec, unit="ratio",
                    label={"en": f"Correlation of daily returns, {a} and {b}", "fr": f"Corrélation des rendements quotidiens, {a} et {b}"},
                    base_lims=("LIM_SAMPLE_WINDOW", "LIM_CALENDAR_INTERSECTION", "LIM_PAST_NOT_FUTURE"),
                )
                out[(a, b)] = Measurement(value, fid, unit="ratio")
        return out

    def price_move_after(self, ticker: str, event_date: str, n_days: int) -> Measurement:
        """``M_PRICE_MOVE_AFTER_EVENT``: N master days after the last master day on/before the event."""
        i0 = self.market.last_index_on_or_before(event_date)
        if i0 is None:
            return Measurement(None, None, nee_reason="short_history")
        i1 = i0 + n_days
        if n_days < 1 or i1 >= len(self.market.dates):
            return Measurement(None, None, nee_reason="not_visible_at_asof")
        try:
            levels = self.market.window_levels(ticker, i0, i1)
        except Unavailable as exc:
            return Measurement(None, None, nee_reason=exc.reason)
        value = mx.period_return_pct(levels)
        variant = f"event:{event_date}:n{n_days}:currency:{self.currency}"
        fid = self.add_series_fact(
            metric="return.period", value=value, subject={"type": "asset", "id": ticker, "variant": variant},
            variant_key=variant, window_code=f"after{n_days}",
            tickers=[ticker], i0=i0, i1=i1, method_id="M_PRICE_MOVE_AFTER_EVENT",
            params={"eventDate": event_date, "nDays": n_days},
            label={"en": f"{self._name(ticker)} ({ticker}) return over {n_days} trading days after {event_date}",
                   "fr": f"{self._name(ticker)} ({ticker}), rendement sur {n_days} jours de bourse après le {event_date}"},
            base_lims=("LIM_PRICE_MOVE_NOT_CAUSAL", "LIM_YAHOO_NOT_CERTIFIED", "LIM_CALENDAR_INTERSECTION"),
        )
        return Measurement(value, fid)

    def _name(self, ticker: str) -> str:
        try:
            return self.universe.get(ticker).name
        except UnknownTicker:
            return ticker


class _NoRecord(Exception):
    pass


class PortfolioView:
    """A portfolio variant (fractional weights) with lazily registered facts."""

    def __init__(self, engine: QuantEngine, weights: dict[str, float], variant: str, total_value: float, *,
                 after_move: bool, window: dict | None = None, record: bool = True) -> None:
        total = math.fsum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"weights sum to {total}, not 1")
        self.engine = engine
        self.weights = {k: v for k, v in weights.items() if v > 0}
        self.variant = variant
        self.total_value = total_value
        self.after_move = after_move
        self.wr_spec = window
        self.record = record
        self.assets = {t: engine.universe.get(t) for t in self.weights}  # raises UnknownTicker
        self._cache: dict[tuple, Measurement] = {}
        self._metrics: PortfolioMetrics | None = None
        self._composition: str | None = None

    # Weight measurements ----------------------------------------------------------------------

    @property
    def subject(self) -> dict:
        return {"type": "portfolio", "id": self.engine.subject_id, "variant": self.variant}

    def composition_fact(self) -> str | None:
        """The stipulated holdings every weight figure of this variant derives from.

        The fictional portfolio (or the hypothetical mix after a move) is an assumption, not an
        observation; registering it gives weight and concentration facts a verifiable input."""
        if not self.record:
            return None
        if self._composition is None:
            name = self.engine.subject_id
            unit = self.engine.currency.lower() if self.engine.currency in ("CAD", "USD") else "currency"
            ordered = sorted(self.weights, key=lambda t: (-self.weights[t], t))
            positions = "; ".join(f"{t} {self.weights[t] * 100:.4g}%" for t in ordered)
            what = ("Hypothetical portfolio after the move", "Portefeuille hypothétique après le mouvement") if self.after_move                 else ("Fictional portfolio holdings", "Titres du portefeuille fictif")
            self._composition = self.engine.ledger.add_fact(make_fact(
                self.engine.ctx, key=fact_key("value.portfolio", "portfolio", name, self.variant, "weights"), kind="assumption",
                metric="value.portfolio", label={"en": f"{what[0]}, {name} ({self.variant})", "fr": f"{what[1]}, {name} ({self.variant})"},
                value=float(self.total_value), unit=unit, currency=self.engine.currency, subject=self.subject,
                method_id="M_WEIGHTS_AFTER_MOVE" if self.after_move else "M_PROFILE_ASSUMPTION", created_by="quant",
                params={"profile": name, "positions": positions}, limitations=["LIM_SIMULATION_ONLY"],
                checks=[{"code": "weights_sum", "ok": True, "detail": "Position weights sum to 100%."}]))
        return self._composition

    def _weight_fact(self, metric: str, value: float, *, subject: dict | None = None, key_suffix: str = "",
                     label: dict, lims: tuple[str, ...] = ()) -> str | None:
        if not self.record:
            return None
        subject = subject or self.subject
        method = "M_WEIGHTS_AFTER_MOVE" if self.after_move else "M_PROFILE_ASSUMPTION"
        key = fact_key(metric, subject["type"], subject["id"] + key_suffix, self.variant, "weights")
        # A single position weight is arithmetic on the stipulated holdings. Every other weight
        # groups holdings by a universe label (class, group, sector, theme), which is dataset data.
        sources, available_at = ([], None) if metric == "weight.position" else self.engine.universe_provenance(self.weights)
        fact = make_fact(self.engine.ctx, key=key, kind="computed", metric=metric, label=label, value=value, unit="pct",
                         currency=None, subject=subject, method_id=method, created_by="quant",
                         sources=sources, available_at=available_at,
                         params={"profile": self.engine.subject_id}, limitations=list(lims), inputs=self._weight_inputs(),
                         checks=[{"code": "weights_sum", "ok": True, "detail": "Position weights sum to 100%."}])
        return self.engine.ledger.add_fact(fact)

    def _weight_inputs(self) -> list[str]:
        digest = hashlib.sha256(json.dumps(self.weights, sort_keys=True).encode()).hexdigest()
        return [self.engine.ledger.add_fact(make_fact(
            self.engine.ctx, key=fact_key("weight.position", "request", digest, "allocation", "full"),
            kind="assumption", metric="weight.position", value=100.0, unit="pct", currency=None,
            label={"en": "Hypothetical allocation used by code", "fr": "Allocation hypothétique utilisée par le code"},
            subject={"type": "request", "id": digest, "variant": "allocation"},
            method_id="M_PROFILE_ASSUMPTION", created_by="profile",
            params={"weights": json.dumps(self.weights, sort_keys=True), "weightsSha256": digest},
            limitations=["LIM_CONSTANT_WEIGHTS", "LIM_SIMULATION_ONLY"],
        ))]

    def group_weights(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for t, w in self.weights.items():
            g = self.assets[t].asset_group
            out[g] = out.get(g, 0.0) + w * 100
        return out

    def sector_weights(self) -> dict[str, float]:
        """Direct equities only, divided by total portfolio value (quant SPEC §6)."""
        out: dict[str, float] = {}
        for t, w in self.weights.items():
            a = self.assets[t]
            if a.asset_class == "equity" and a.sector != "unknown":
                out[a.sector] = out.get(a.sector, 0.0) + w * 100
        return out

    def theme_weight(self, theme: str) -> float:
        return math.fsum(w * 100 for t, w in self.weights.items() if theme in self.assets[t].themes)

    def measure(self, metric: str, key: str | None = None) -> Measurement:
        cache_key = (metric, key)
        if cache_key in self._cache:
            return self._cache[cache_key]
        m = self._measure(metric, key)
        self._cache[cache_key] = m
        return m

    def _measure(self, metric: str, key: str | None) -> Measurement:
        name = self.engine.subject_id
        if metric == "weight.position.max_single":
            single = {t: w * 100 for t, w in self.weights.items() if self.assets[t].is_single_name}
            if not single:
                value, worst = 0.0, None
            else:
                order = {t: i for i, t in enumerate(self.weights)}  # ties: first in portfolio order
                t = sorted(single, key=lambda x: (-single[x], order[x]))[0]
                value, worst = single[t], {"type": "asset", "id": t}
            fid = self._weight_fact(metric, value, label={"en": f"Largest single-name position, {name} ({self.variant})",
                                                          "fr": f"Plus grande position individuelle, {name} ({self.variant})"},
                                    lims=("LIM_ETF_NO_LOOKTHROUGH",) if self._holds_funds() else ())
            return Measurement(value, fid, worst=worst)
        if metric == "weight.sector.max":
            sectors = self.sector_weights()
            if not sectors:
                value, worst = 0.0, None
            else:
                s = sorted(sectors, key=lambda x: (-sectors[x], list(sectors).index(x)))[0]
                value, worst = sectors[s], {"type": "sector", "id": s}
            lims = ("LIM_SECTOR_LABELS",) + (("LIM_ETF_NO_LOOKTHROUGH",) if self._holds_funds() else ())
            fid = self._weight_fact(metric, value, label={"en": f"Largest sector among direct equities, {name} ({self.variant})",
                                                          "fr": f"Plus grand secteur parmi les actions détenues directement, {name} ({self.variant})"},
                                    lims=lims)
            return Measurement(value, fid, worst=worst)
        if metric in ("weight.country", "weight.currency"):
            dimension = metric.split(".")[1]
            values = [100 * w for t, w in self.weights.items() if getattr(self.assets[t], dimension) == key]
            value = math.fsum(values)
            fid = self._weight_fact(metric, value, subject={"type": dimension, "id": key or "unknown", "variant": self.variant},
                label={"en": f"{key}: {'listing-country proxy' if dimension == 'country' else 'quotation-currency'} weight",
                       "fr": f"{key} : poids par {'pays de cotation (approximation)' if dimension == 'country' else 'devise de cotation'}"},
                lims=("LIM_ETF_NO_LOOKTHROUGH",))
            return Measurement(value, fid)
        if metric == "weight.sector":
            sectors = self.sector_weights()
            label = next((s for s in sectors if slug(s) == slug(key or "")), None)
            value = sectors.get(label, 0.0) if label else 0.0
            offenders = sorted(((self.weights[t] * 100, t) for t in self.weights
                                if self.assets[t].asset_class == "equity" and slug(self.assets[t].sector) == slug(key or "")), reverse=True)
            worst = {"type": "asset", "id": offenders[0][1]} if offenders else None
            fid = self._weight_fact(metric, value, subject={"type": "sector", "id": key or "", "variant": self.variant},
                                    label={"en": f"Direct equities in sector {key}, {name} ({self.variant})",
                                           "fr": f"Actions détenues directement dans le secteur {key}, {name} ({self.variant})"},
                                    lims=("LIM_SECTOR_LABELS",))
            return Measurement(value, fid, worst=worst)
        if metric in ("weight.asset_group", "weight.asset_class"):
            attr = "asset_group" if metric == "weight.asset_group" else "asset_class"
            hits = sorted(((w * 100, t) for t, w in self.weights.items() if getattr(self.assets[t], attr) == key), reverse=True)
            value = math.fsum(v for v, _ in hits)
            worst = {"type": "asset", "id": hits[0][1]} if hits else None
            fid = self._weight_fact(metric, value, subject={"type": attr, "id": key or "", "variant": self.variant},
                                    label={"en": f"Weight of {key}, {name} ({self.variant})", "fr": f"Poids de {key}, {name} ({self.variant})"})
            return Measurement(value, fid, worst=worst)
        if metric in ("weight.growth_assets", "weight.fixed_income", "weight.diversifiers"):
            groups = self.group_weights()
            parts = {"weight.growth_assets": ("equity", "crypto"), "weight.fixed_income": ("fixed_income", "cash"),
                     "weight.diversifiers": ("fixed_income", "cash", "commodity")}[metric]
            value = math.fsum(groups.get(g, 0.0) for g in parts)
            what = {"weight.growth_assets": ("Stocks, equity funds and crypto", "Actions, fonds d'actions et crypto"),
                    "weight.fixed_income": ("Bonds and cash", "Obligations et encaisse"),
                    "weight.diversifiers": ("Bonds, cash and gold", "Obligations, encaisse et or")}[metric]
            fid = self._weight_fact(metric, value, label={"en": f"{what[0]}, {name} ({self.variant})", "fr": f"{what[1]}, {name} ({self.variant})"})
            return Measurement(value, fid)
        if metric == "weight.position":
            value = self.weights.get(key or "", 0.0) * 100
            fid = self._weight_fact(metric, value, subject={"type": "asset", "id": key or "", "variant": self.variant},
                                    label={"en": f"Weight of {key}, {name} ({self.variant})", "fr": f"Poids de {key}, {name} ({self.variant})"})
            return Measurement(value, fid, worst={"type": "asset", "id": key} if value > 0 else None)
        if metric == "weight.theme":
            if self.engine.gate.mode == "historical" and not any(a.themes for a in self.engine.universe.all()):
                return Measurement(None, None, nee_reason="not_visible_at_asof",
                                   detail="theme tags are not visible at this as-of date")
            value = self.theme_weight(key or "")
            fid = self._weight_fact(metric, value, subject={"type": "theme", "id": key or "", "variant": self.variant},
                                    label={"en": f"Positions tagged {key}, {name} ({self.variant})",
                                           "fr": f"Positions étiquetées {key}, {name} ({self.variant})"},
                                    lims=("LIM_THEME_TAGS",))
            return Measurement(value, fid, worst={"type": "theme", "id": key})
        if metric in ("vol.annualized", "drawdown.max", "stress.replay_2022"):
            pm = self.metrics()
            attr = {"vol.annualized": "volatility_pct", "drawdown.max": "max_drawdown_pct", "stress.replay_2022": "stress2022_pct"}[metric]
            value = getattr(pm, attr)
            if value is None:
                return Measurement(None, None, nee_reason=pm.missing.get(metric, "short_history"))
            return Measurement(value, pm.fact_ids.get(metric))
        if metric == "stress.rate_cycle":
            return self._replay("stress.rate_cycle", *RATE_CYCLE, label=("rate-hiking cycle", "cycle de hausse des taux"))
        if metric == "concentration.hhi" or metric == "concentration.effective_n":
            pm = self.metrics()
            return Measurement(pm.hhi if metric == "concentration.hhi" else pm.effective_n, pm.fact_ids.get(metric),
                               unit="ratio" if metric == "concentration.hhi" else "count")
        raise ValueError(f"metric {metric!r} is not measured by quant")

    def _holds_funds(self) -> bool:
        return any(a.asset_class.startswith("etf_") for a in self.assets.values())

    def _replay(self, metric: str, start: str, end: str, label: tuple[str, str], custom: bool = False) -> Measurement:
        """``custom`` marks a caller-chosen period: its dates enter the fact window, hence the key."""
        eng = self.engine
        try:
            i0, i1 = eng._named_range(start, end)
            value = mx.period_return_pct(eng.portfolio_levels(self.weights, i0, i1))
        except Unavailable as exc:
            return Measurement(None, None, nee_reason=exc.reason, detail=exc.detail)
        if not self.record:
            return Measurement(value, None)
        fid = eng.add_series_fact(
            metric=metric, value=value, subject=self.subject, variant_key=self.variant,
            window_code=f"custom:{start}..{end}" if custom else metric.split(".")[1],
            window_spec={"code": "custom", "start": start, "end": end} if custom else None,
            tickers=list(self.weights), i0=i0, i1=i1, method_id="M_STRESS_REPLAY", kind="scenario",
            params={"windowStart": start, "windowEnd": end}, inputs=self._weight_inputs(),
            label={"en": f"Portfolio return with these weights, {label[0]} ({eng.market.dates[i0]} to {eng.market.dates[i1]}), {eng.currency}",
                   "fr": f"Rendement du portefeuille avec ces pondérations, {label[1]} ({eng.market.dates[i0]} au {eng.market.dates[i1]}), {eng.currency}"},
            currency=None,
        )
        return Measurement(value, fid)

    # Metrics and snapshot ---------------------------------------------------------------------

    def metrics(self) -> PortfolioMetrics:
        if self._metrics is not None:
            return self._metrics
        eng = self.engine
        name = eng.subject_id
        weights = list(self.weights.values())
        h = mx.hhi(weights)
        pm = PortfolioMetrics(None, None, None, h, 1.0 / h)
        tickers = list(self.weights)
        try:
            wr = eng.window(self.wr_spec)
            levels = eng.portfolio_levels(self.weights, wr.i0, wr.i1)
            pm.volatility_pct = mx.annualized_vol_pct(mx.simple_returns(levels))
            pm.max_drawdown_pct = mx.max_drawdown_pct(levels)
            if not self.record:
                raise _NoRecord
            common = dict(subject=self.subject, variant_key=self.variant, window_code=wr.code, tickers=tickers,
                          inputs=self._weight_inputs(),
                          i0=wr.i0, i1=wr.i1, window_spec=wr.spec)
            pm.fact_ids["vol.annualized"] = eng.add_series_fact(
                metric="vol.annualized", value=pm.volatility_pct, method_id="M_VOL_STDEV_252",
                label={"en": f"Portfolio volatility, annualized, {name} ({self.variant}), {eng.currency}",
                       "fr": f"Volatilité annualisée du portefeuille, {name} ({self.variant}), {eng.currency}"}, **common)
            pm.fact_ids["drawdown.max"] = eng.add_series_fact(
                metric="drawdown.max", value=pm.max_drawdown_pct, method_id="M_MDD_PEAK_TROUGH",
                label={"en": f"Largest peak-to-trough fall, {name} ({self.variant}), {eng.currency}",
                       "fr": f"Plus forte baisse d'un sommet à un creux, {name} ({self.variant}), {eng.currency}"}, **common)
        except Unavailable as exc:
            pm.missing["vol.annualized"] = pm.missing["drawdown.max"] = exc.reason
        except _NoRecord:
            pass
        stress = self._replay("stress.replay_2022", *STRESS_2022, label=("calendar 2022", "année civile 2022"))
        pm.stress2022_pct = stress.value
        if stress.value is None:
            pm.missing["stress.replay_2022"] = stress.nee_reason or "short_history"
        else:
            pm.fact_ids["stress.replay_2022"] = stress.fact_id
        for metric, value, unit in (("concentration.hhi", h, "ratio"), ("concentration.effective_n", 1.0 / h, "count")):
            if not self.record:
                break
            key = fact_key(metric, "portfolio", name, self.variant, "weights")
            pm.fact_ids[metric] = eng.ledger.add_fact(make_fact(
                eng.ctx, key=key, kind="computed", metric=metric, value=value, unit=unit, currency=None,
                label={"en": f"{'Concentration (sum of squared weights)' if unit == 'ratio' else 'Effective number of positions'}, {name} ({self.variant})",
                       "fr": f"{'Concentration (somme des carrés des poids)' if unit == 'ratio' else 'Nombre effectif de positions'}, {name} ({self.variant})"},
                subject=self.subject, method_id="M_WEIGHTS_AFTER_MOVE" if self.after_move else "M_PROFILE_ASSUMPTION",
                created_by="quant", inputs=self._weight_inputs(),
                checks=[{"code": "weights_sum", "ok": True, "detail": "Position weights sum to 100%."}]))
        self._metrics = pm
        return pm

    def snapshot(self) -> PortfolioSnapshot:
        pm = self.metrics()
        positions = []
        for t in sorted(self.weights, key=lambda x: (-self.weights[x], x)):
            a = self.assets[t]
            w = self.weights[t] * 100
            positions.append({"ticker": t, "weightPct": min(w, 100.0), "name": a.name, "assetClass": a.asset_class,
                              "assetGroup": a.asset_group, "sector": a.sector, "marketValue": self.weights[t] * self.total_value})
        groups = self.group_weights()
        countries: dict[str, float] = {}
        for t, w in self.weights.items():
            c = self.assets[t].country
            if c:
                countries[c] = countries.get(c, 0.0) + w * 100
        sectors = self.sector_weights()
        fact_ids = {"volatility": pm.fact_ids.get("vol.annualized"), "maxDrawdown": pm.fact_ids.get("drawdown.max"),
                    "stress2022": pm.fact_ids.get("stress.replay_2022")}
        return PortfolioSnapshot.model_validate({
            "variant": self.variant, "totalValue": float(self.total_value), "currency": self.engine.currency,
            "positions": positions,
            "byAssetGroup": [{"key": g, "weightPct": min(groups[g], 100.0)} for g in GROUP_ORDER if g in groups],
            "bySector": [{"key": k, "weightPct": min(v, 100.0)} for k, v in sorted(sectors.items(), key=lambda kv: (-kv[1], kv[0]))],
            "byCountry": [{"key": k, "weightPct": min(v, 100.0)} for k, v in sorted(countries.items(), key=lambda kv: (-kv[1], kv[0]))],
            "metrics": {"volatilityPct": pm.volatility_pct, "maxDrawdownPct": pm.max_drawdown_pct,
                        "stress2022Pct": pm.stress2022_pct, "factIds": {k: v for k, v in fact_ids.items() if v}},
        })
