"""Agent tools of tracks T04–T07 (contracts/tools.md §2–§4) for T08's ``ToolRegistry``.

    from aplomb.optimizer.tools import register_domain_tools
    register_domain_tools(services.registry)

Every read goes through ``ctx.gate``; every number returned to the model sits next to the ID of
the fact registered in ``ctx.ledger``. Portfolio variants created by ``quant.apply_move`` live
for the run (keyed by its run ID). Tools never raise to the model: the registry wraps errors.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Literal
from weakref import WeakKeyDictionary

from pydantic import BaseModel, ConfigDict, Field

from aplomb.contracts import models as m
from aplomb.quant import QuantEngine, Unavailable, apply_move
from aplomb.quant.facts import FactContext, fact_key, make_fact
from aplomb.rules.engine import RuleEngine, RuleInputs, verdict_of

from .derive import derive_thresholds
from .scenarios import alternatives, goal_candidates, rebalance, weights_of
from .search import compare_funding, funding_option_wire, max_compatible_size


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class UniverseSearchArgs(Args):
    q: str | None = None
    asset_class: str | None = None
    theme: str | None = None
    limit: int = Field(10, ge=1, le=50)


class TickerArgs(Args):
    ticker: str


class NoArgs(Args):
    pass


class DescribeArgs(Args):
    dataset_id: str


class MacroArgs(Args):
    series_id: str
    start: str | None = None
    end: str | None = None


class AssetMetricsArgs(Args):
    ticker: str
    window: dict | None = None
    currency: m.Currency | None = None


class CalendarYearArgs(Args):
    ticker: str
    year: int = Field(ge=1900, le=2100)
    variant: str = "before"
    currency: m.Currency | None = None


class VariantArgs(Args):
    variant: str = "before"


class VariantWindowArgs(Args):
    variant: str = "before"
    window: dict | None = None


class ApplyMoveArgs(Args):
    move: dict
    base_variant: str = "before"


class SizeArgs(Args):
    ticker: str
    size_pct: float = Field(gt=0, le=100)


class StressArgs(Args):
    variant: str = "before"
    window_id: Any = "2022"


class CorrelationArgs(Args):
    tickers: list[str] = Field(min_length=2, max_length=20)
    window: dict | None = None


class ExposureArgs(Args):
    variant: str = "before"
    theme: str


class PriceMoveArgs(Args):
    ticker: str
    date: str
    n_days: int = Field(ge=1, le=252)


class MaxSizeArgs(Args):
    ticker: str
    funding: dict


class GoalArgs(Args):
    goal: dict
    max_candidates: int = Field(3, ge=1, le=3)


class RebalanceArgs(Args):
    target: Literal["within_rules"] = "within_rules"


class DeriveArgs(Args):
    risk_level: str
    horizon: dict
    preferences: dict


# --- Run state ---------------------------------------------------------------------------------

# The workflow hands every tool call a copy of the run ledger, so variants are kept per run ID.
# An engine writes into the ledger it was built with and is therefore kept per ledger object.
_RUNS: "OrderedDict[str, dict]" = OrderedDict()
_MAX_RUNS = 256
_ENGINES: "WeakKeyDictionary[object, dict]" = WeakKeyDictionary()


def _state(ctx) -> dict:
    st = _RUNS.get(ctx.run_id)
    if st is None:
        st = _RUNS[ctx.run_id] = {"variants": {}, "counter": 0}
        while len(_RUNS) > _MAX_RUNS:
            _RUNS.popitem(last=False)
    else:
        _RUNS.move_to_end(ctx.run_id)
    return st


def _created_at(ctx) -> str:
    clock = getattr(ctx.ledger, "clock", None)
    return clock() if callable(clock) else f"{ctx.as_of}T00:00:00Z"


def _profile(ctx) -> m.Profile:
    if ctx.profile is None:
        raise ValueError("No profile in this run")
    return ctx.profile


def _engine(ctx, currency: str | None = None) -> QuantEngine:
    profile = _profile(ctx)
    ccy = currency or profile.reporting_currency
    engines = _ENGINES.setdefault(ctx.ledger, {})
    eng = engines.get(ccy)
    if eng is None or eng.gate is not ctx.gate:
        eng = QuantEngine(ctx.gate, ctx.ledger, currency=ccy, subject_id=profile.profile_id, created_at=_created_at(ctx))
        engines[ccy] = eng
    return eng


def _weights(ctx, variant: str) -> tuple[dict[str, float], float]:
    if variant == "before":
        profile = _profile(ctx)
        return weights_of(profile), 1.0
    found = _state(ctx)["variants"].get(variant)
    if found is None:
        raise ValueError(f"Unknown variant {variant!r}; create it with quant.apply_move")
    return found


def _num(meas, unit: str = "pct") -> dict:
    return {"value": meas.value, "unit": meas.unit or unit, "factId": meas.fact_id, "neeReason": meas.nee_reason}


def _reads(eng: QuantEngine, start: int) -> list[m.DatasetRead]:
    return [m.DatasetRead.model_validate(r.to_wire()) for r in eng.market.reads[start:]]


def _result(summary: str, data: dict, fact_ids=(), reads=()):
    from aplomb.agents.registry import ToolResult

    return ToolResult(True, summary, fact_ids=[f for f in dict.fromkeys(fact_ids) if f], data=data, datasets_read=list(reads))


def _ids(obj) -> list[str]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("factId", "valueFactId", "thresholdFactId") and isinstance(v, str):
                out.append(v)
            else:
                out += _ids(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _ids(v)
    return out


# --- Lookup tools (T04/T06) --------------------------------------------------------------------


def universe_search(ctx, q=None, asset_class=None, theme=None, limit=10):
    hits = ctx.gate.universe().search(q=q, asset_class=asset_class, theme=theme, limit=limit)
    assets = [{"ticker": a.ticker, "name": a.name, "assetClass": a.asset_class, "sector": a.sector, "themes": list(a.themes),
               "nObsMaster": a.history.n_obs_master} for a in hits]
    return _result(f"{len(assets)} asset(s) found", {"assets": assets})


def universe_get(ctx, ticker):
    return _result(f"Asset {ticker}", {"asset": ctx.gate.universe().get(ticker).to_wire()})


def profile_get(ctx):
    profile = _profile(ctx)
    ids, rules = [], []
    if ctx.gate is not None:
        eng = _engine(ctx)
        engine = RuleEngine(ctx.ledger, eng.ctx)
    else:
        engine = RuleEngine(ctx.ledger, FactContext(str(ctx.as_of), _created_at(ctx), "unpinned"))
    for r in profile.rules:
        fid = engine._threshold_fact(r, profile.profile_id) if r.threshold is not None else None
        ids.append(fid)
        rules.append({"ruleId": r.rule_id, "code": r.code, "type": r.type, "enabled": r.enabled, "label": r.label.en,
                      "threshold": {"value": r.threshold, "unit": r.unit, "factId": fid} if fid else None})
    positions = []
    if ctx.gate is not None:
        view = _engine(ctx).view(weights_of(profile), "before", profile.portfolio.total_value)
        for p in profile.portfolio.positions:
            meas = view.measure("weight.position", p.ticker)
            ids.append(meas.fact_id)
            positions.append({"ticker": p.ticker, "weight": _num(meas)})
    else:
        positions = [{"ticker": p.ticker} for p in profile.portfolio.positions]
    data = {"profileId": profile.profile_id, "riskLevel": profile.risk_level, "horizonYears": profile.horizon_years.to_wire(),
            "objective": profile.objective, "reportingCurrency": profile.reporting_currency,
            "preferences": profile.preferences.to_wire(), "rules": rules, "positions": positions}
    return _result("Profile summary; thresholds and weights are facts", data, ids)


def data_describe(ctx, dataset_id):
    p = ctx.gate.describe(dataset_id)
    data = {k: p[k] for k in ("datasetId", "name", "status", "coverage", "frequency", "limitations", "availabilityRule", "dataVersion")}
    return _result(f"Passport of {dataset_id}", data)


def macro_series(ctx, series_id, start=None, end=None):
    sl = ctx.gate.macro(series_id, start, end)
    if not sl.rows:
        return _result(f"No visible observation of {series_id} ({sl.rows_withheld} withheld)", {"seriesId": series_id, "rowsWithheld": sl.rows_withheld},
                       reads=[m.DatasetRead.model_validate(sl.dataset_read().to_wire())])
    passport = ctx.gate.describe("macro_rates")
    eng_ctx = FactContext(str(ctx.as_of), _created_at(ctx), ctx.gate.data_version)
    picks = {"first": sl.rows[0], "last": sl.rows[-1], "min": min(sl.rows, key=lambda r: (r["value"], r["date"])),
             "max": max(sl.rows, key=lambda r: (r["value"], r["date"]))}
    data, ids = {"seriesId": series_id, "label": sl.rows[0]["label"], "unit": sl.rows[0]["unit"]}, []
    for name, row in picks.items():
        # The Unit catalog has no index unit: a level that is not a percentage is registered as
        # text (its label states the base), never as a ratio, which would display as a multiple.
        percent = row["unit"] == "percent"
        unit = "pct" if percent else "text"
        fid = ctx.ledger.add_fact(make_fact(
            eng_ctx, key=fact_key("macro.level", "macro", series_id, row["date"], "na"), kind="observed", metric="macro.level",
            label={"en": f"{row['label']} ({series_id}), {row['date']}", "fr": f"{row['label']} ({series_id}), {row['date']}"},
            value=row["value"] if percent else str(row["value"]), unit=unit, currency=None,
            subject={"type": "macro", "id": series_id, "variant": row["date"]},
            method_id="M_OBSERVED_ROW", created_by="quant", period={"start": row["date"], "end": row["date"]},
            available_at=row["available_at"],
            params={"referenceDate": row["date"], "availabilityBasis": row["availability_basis"], "sourceUnit": row["unit"]},
            n_obs=1, sources=[{"datasetId": "macro_rates", "dataVersion": ctx.gate.data_version, "sourceName": passport["source"],
                               "sourceUrl": passport["sourceUrl"], "retrievedOn": passport["retrievedOn"] or str(ctx.as_of),
                               "licence": passport["licence"], "rowsRead": 1}],
            limitations=list(sl.limitations), checks=[{"code": "gated_row", "ok": True, "detail": "Row read through the temporal gate."}]))
        ids.append(fid)
        data[name] = {"date": row["date"], "value": row["value"], "unit": "pct" if percent else row["unit"], "factId": fid}
    return _result(f"{series_id}: first, last, min and max visible values", data, ids,
                   [m.DatasetRead.model_validate(sl.dataset_read().to_wire())])


# --- Quant tools (T05) -------------------------------------------------------------------------


def quant_asset_metrics(ctx, ticker, window=None, currency=None):
    eng = _engine(ctx, currency)
    n = len(eng.market.reads)
    out = eng.asset_metrics(ticker, window)
    data = {k: _num(v) for k, v in out.items()}
    return _result(f"Risk and return figures for {ticker}", {"ticker": ticker, "currency": eng.currency, **data},
                   [v.fact_id for v in out.values()], _reads(eng, n))


def quant_calendar_year_return(ctx, ticker, year, variant="before", currency=None):
    eng = _engine(ctx, currency)
    n = len(eng.market.reads)
    if ticker != "portfolio":
        out = eng.calendar_year_return(ticker, year)
        return _result(f"{ticker} calendar {year} return", {"ticker": ticker, "year": year, "values": [_num(v) for v in out]},
                       [v.fact_id for v in out], _reads(eng, n))
    weights, _ = _weights(ctx, variant)
    try:
        i0, i1 = eng._named_range(f"{year - 1}-12-31", f"{year}-12-31")
        value = (eng.portfolio_levels(weights, i0, i1)[-1] - 1.0) * 100.0
    except Unavailable as exc:
        return _result(f"Portfolio calendar {year} return unavailable", {"neeReason": exc.reason})
    qualified = variant if eng.currency == _profile(ctx).reporting_currency else f"{variant}:currency:{eng.currency}"
    qualified = f"{qualified}:year:{year}"
    fid = eng.add_series_fact(
        metric="return.calendar_year", value=value, subject={"type": "portfolio", "id": eng.subject_id, "variant": qualified},
        variant_key=qualified, window_code=str(year), tickers=list(weights), i0=i0, i1=i1, method_id="M_RET_CALENDAR_YEAR",
        label={"en": f"Portfolio return, calendar {year}, {eng.currency}", "fr": f"Rendement du portefeuille, année civile {year}, {eng.currency}"})
    return _result(f"Portfolio calendar {year} return", {"year": year, "value": {"value": value, "unit": "pct", "factId": fid}}, [fid], _reads(eng, n))


def quant_portfolio_snapshot(ctx, variant="before"):
    eng = _engine(ctx)
    n = len(eng.market.reads)
    weights, factor = _weights(ctx, variant)
    profile = _profile(ctx)
    view = eng.view(weights, variant, profile.portfolio.total_value * factor)
    snap = view.snapshot().to_wire()
    fid = view.composition_fact()  # the one value.portfolio fact of this variant
    return _result(f"Snapshot of {variant}", {"snapshot": snap, "value": {"value": snap["totalValue"], "factId": fid}},
                   _ids(snap) + [fid], _reads(eng, n))


def quant_portfolio_metrics(ctx, variant="before", window=None):
    eng = _engine(ctx)
    n = len(eng.market.reads)
    weights, factor = _weights(ctx, variant)
    view = eng.view(weights, variant, _profile(ctx).portfolio.total_value * factor, window=window)
    data = {k: _num(view.measure(k)) for k in ("vol.annualized", "drawdown.max", "stress.replay_2022", "concentration.hhi",
                                              "concentration.effective_n")}
    return _result(f"Risk figures of {variant}", data, [d["factId"] for d in data.values()], _reads(eng, n))


def quant_apply_move(ctx, move, base_variant="before"):
    eng = _engine(ctx)
    mv = m.ProposedMove.model_validate(move)
    if mv.funding.mode == "auto":
        raise ValueError("Resolve funding first (quant.compare_funding); quant never guesses")
    weights, factor = _weights(ctx, base_variant)
    res = apply_move(weights, mv.ticker, mv.size_pct, mv.funding.mode, mv.funding.from_tickers)
    st = _state(ctx)
    st["counter"] += 1
    variant = f"scenario:s{st['counter']}"
    st["variants"][variant] = (res.weights, factor * res.value_factor)
    total = _profile(ctx).portfolio.total_value
    before = eng.view(weights, base_variant, total * factor)
    after = eng.view(res.weights, variant, total * factor * res.value_factor)
    data = {"variant": variant, "weights": []}
    for t in dict.fromkeys([mv.ticker, *res.donors]):
        b, a = before.measure("weight.position", t), after.measure("weight.position", t)
        data["weights"].append({"ticker": t, "before": _num(b), "after": _num(a)})
    return _result(f"Registered {variant}", data, _ids(data))


def quant_compare_funding(ctx, ticker, size_pct):
    eng = _engine(ctx)
    profile = _profile(ctx)
    evals = compare_funding(eng, profile.rules, weights_of(profile), ticker, size_pct, profile_id=profile.profile_id)
    options, ids = [], []
    st = _state(ctx)
    for e in evals:
        opt = funding_option_wire(e)
        if e.feasible:
            variant = f"scenario:funding_{e.mode}"
            st["variants"][variant] = (e.result_weights, e.value_factor)
            meas = eng.view(e.result_weights, variant, profile.portfolio.total_value * e.value_factor).measure("weight.position", ticker)
            opt["variant"] = variant
            opt["targetWeight"] = _num(meas)
            ids.append(meas.fact_id)
        options.append(opt)
    return _result("Funding modes compared (hypothetical, not an instruction to sell)", {"options": options}, ids)


def quant_stress_replay(ctx, variant="before", window_id="2022"):
    eng = _engine(ctx)
    weights, factor = _weights(ctx, variant)
    view = eng.view(weights, variant, _profile(ctx).portfolio.total_value * factor)
    if window_id == "2022":
        meas = view.measure("stress.replay_2022")
    elif window_id == "rate_cycle":
        meas = view.measure("stress.rate_cycle")
    else:
        period = m.Period.model_validate(window_id)
        meas = view._replay("return.period", period.start, period.end, (f"{period.start} to {period.end}", f"{period.start} au {period.end}"),
                            custom=True)
    return _result(f"Replay {window_id if isinstance(window_id, str) else 'custom'} for {variant}", {"value": _num(meas)}, [meas.fact_id])


def quant_correlation(ctx, tickers, window=None):
    eng = _engine(ctx)
    out = eng.correlation(tickers, window)
    pairs = [{"a": a, "b": b, **_num(v, "ratio")} for (a, b), v in out.items()]
    return _result("Pairwise correlations of daily returns", {"pairs": pairs}, [p["factId"] for p in pairs])


def quant_exposure(ctx, variant="before", theme=""):
    eng = _engine(ctx)
    weights, factor = _weights(ctx, variant)
    meas = eng.view(weights, variant, _profile(ctx).portfolio.total_value * factor).measure("weight.theme", theme)
    return _result(f"Exposure to {theme} ({variant})", {"theme": theme, "value": _num(meas)}, [meas.fact_id])


def quant_price_move_after(ctx, ticker, date, n_days):
    meas = _engine(ctx).price_move_after(ticker, date, n_days)
    return _result(f"{ticker} return over {n_days} trading days after {date} (not causal)", {"value": _num(meas)}, [meas.fact_id])


# --- Rule and optimizer tools (T06/T07) --------------------------------------------------------


def rules_check(ctx, variant="before"):
    eng = _engine(ctx)
    profile = _profile(ctx)
    weights, factor = _weights(ctx, variant)
    base = weights_of(profile)
    moved = tuple(t for t, w in weights.items() if w / 1.0 > base.get(t, 0.0) / factor + 1e-12) if variant != "before" else ()
    view = eng.view(weights, variant, profile.portfolio.total_value * factor)
    checks = RuleEngine(ctx.ledger, eng.ctx).check_rules(profile.rules, RuleInputs(view, profile.profile_id, moved))
    verdict, counts = verdict_of(checks)
    data = {"verdict": verdict, "counts": counts.to_wire(), "checks": [c.to_wire() for c in checks]}
    return _result(f"{variant}: {verdict}", data, _ids(data))


def optimizer_max_compatible_size(ctx, ticker, funding):
    eng = _engine(ctx)
    profile = _profile(ctx)
    f = m.Funding.model_validate(funding)
    if f.mode == "auto":
        raise ValueError("Resolve funding first")
    search = max_compatible_size(eng, profile.rules, weights_of(profile), ticker, f.mode, f.from_tickers, profile_id=profile.profile_id)
    from .check import max_size_fact

    fid = max_size_fact(eng, profile, ticker, f.to_wire(), search, [])
    data = {"ticker": ticker, "funding": f.to_wire(), "maxCompatibleSizePct": {"value": search.max_size_pct, "unit": "pts", "factId": fid},
            "baselineConflict": search.baseline_conflict, "stoppedBy": search.stopped_by,
            "remainingAtBoundary": search.remaining_at_max, "grid": [[s, v] for s, v in search.grid]}
    return _result(f"Largest size before the first conflict for {ticker}", data, [fid])


def _scenario_result(name: str, result) -> Any:
    data = {"scenarios": result.scenarios, "screened": result.screened, "notes": result.notes}
    return _result(f"{name}: {len(result.scenarios)} scenario(s)", data, _ids(result.scenarios))


def optimizer_goal_candidates(ctx, goal, max_candidates=3):
    return _scenario_result("Goal candidates", goal_candidates(_engine(ctx), _profile(ctx), m.ExposureGoal.model_validate(goal), max_candidates))


def optimizer_alternatives(ctx, ticker, size_pct):
    return _scenario_result("Alternatives", alternatives(_engine(ctx), _profile(ctx), ticker, size_pct))


def optimizer_rebalance(ctx, target="within_rules"):
    return _scenario_result("Rebalance", rebalance(_engine(ctx), _profile(ctx)))


def optimizer_derive_thresholds(ctx, risk_level, horizon, preferences):
    base = _profile(ctx).to_wire()
    candidate = m.Profile.model_validate({**base, "riskLevel": risk_level, "horizonYears": horizon, "preferences": preferences})
    d = derive_thresholds(candidate, _engine(ctx), created_at=_created_at(ctx))
    data = {"rules": [{"ruleId": r["ruleId"], "code": r["code"], "threshold": r["threshold"], "unit": r["unit"]} for r in d.rules],
            "inputs": d.fact_ids, "issues": d.issues}
    return _result("Derived thresholds (assumptions, editable)", data, list(d.fact_ids.values()))


HANDLERS = {
    "universe.search": (UniverseSearchArgs, universe_search),
    "universe.get": (TickerArgs, universe_get),
    "profile.get": (NoArgs, profile_get),
    "data.describe": (DescribeArgs, data_describe),
    "macro.series": (MacroArgs, macro_series),
    "quant.asset_metrics": (AssetMetricsArgs, quant_asset_metrics),
    "quant.calendar_year_return": (CalendarYearArgs, quant_calendar_year_return),
    "quant.portfolio_snapshot": (VariantArgs, quant_portfolio_snapshot),
    "quant.portfolio_metrics": (VariantWindowArgs, quant_portfolio_metrics),
    "quant.apply_move": (ApplyMoveArgs, quant_apply_move),
    "quant.compare_funding": (SizeArgs, quant_compare_funding),
    "quant.stress_replay": (StressArgs, quant_stress_replay),
    "quant.correlation": (CorrelationArgs, quant_correlation),
    "quant.exposure": (ExposureArgs, quant_exposure),
    "quant.price_move_after": (PriceMoveArgs, quant_price_move_after),
    "rules.check": (VariantArgs, rules_check),
    "optimizer.max_compatible_size": (MaxSizeArgs, optimizer_max_compatible_size),
    "optimizer.goal_candidates": (GoalArgs, optimizer_goal_candidates),
    "optimizer.alternatives": (SizeArgs, optimizer_alternatives),
    "optimizer.rebalance": (RebalanceArgs, optimizer_rebalance),
    "optimizer.derive_thresholds": (DeriveArgs, optimizer_derive_thresholds),
}


def domain_tool_handlers() -> dict:
    return dict(HANDLERS)


def register_domain_tools(registry) -> None:
    """Register every T04–T07 tool of the shared catalog in T08's registry."""
    for name, (args, fn) in HANDLERS.items():
        registry.register(name, args, fn)

