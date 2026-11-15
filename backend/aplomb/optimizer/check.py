"""Deterministic move check (``POST /check``, api.md §4.2) and the T08 code-controls provider.

``prepare`` is the quant part (weights, snapshots, funding), ``assess`` the risk part (rules,
first-conflict boundary). ``CheckServiceImpl.check`` runs both in one ledger; the agent workflow
runs them as its ``quant`` and ``risk_check`` steps. No model call anywhere.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from aplomb.api.errors import NotFound, ServiceError
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.datastore import Snapshot, UnknownTicker
from aplomb.quant import FundingError, LocalLedger, QuantEngine, Unavailable, apply_move
from aplomb.quant.facts import fact_key, make_fact
from aplomb.rules.engine import (
    RuleEngine,
    RuleInputs,
    quick_statuses,
    verdict_of,
    verdict_of_statuses,
)

from .search import compare_funding, funding_option_wire, max_compatible_size


def _now(clock) -> str:
    return clock().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def apply_overrides(profile: m.Profile, overrides) -> list[m.PolicyRule]:
    """Request-scoped rule edits (never persisted)."""
    rules = [r.to_wire() for r in profile.rules]
    for ov in overrides or []:
        rule = next((r for r in rules if r["ruleId"] == ov.rule_id), None)
        if rule is None:
            raise ServiceError("validation_error", f"Profile {profile.profile_id} has no rule {ov.rule_id}", {"fields": ["ruleOverrides"]})
        fields = ov.model_fields_set
        if "threshold" in fields and ov.threshold is not None:
            b = rule["bounds"]
            if not rule["editable"] or b is None or rule["threshold"] is None:
                raise ServiceError("validation_error", f"Rule {ov.rule_id} has no editable threshold", {"fields": ["ruleOverrides"]})
            if not (b["min"] - 1e-9 <= ov.threshold <= b["max"] + 1e-9):
                raise ServiceError("validation_error", f"threshold for {ov.rule_id} must be between {b['min']:g} and {b['max']:g}",
                                   {"fields": ["ruleOverrides"]})
            rule.update({"threshold": float(ov.threshold), "origin": "user", "derivation": None})
        if "enabled" in fields and ov.enabled is not None:
            if not rule["editable"]:
                raise ServiceError("conflict", f"Rule {ov.rule_id} cannot be edited")
            rule.update({"enabled": bool(ov.enabled), "origin": "user", "derivation": None})
    return [m.PolicyRule.model_validate(r) for r in rules]


def weights_of(profile: m.Profile) -> dict[str, float]:
    return {p.ticker: p.weight_pct / 100.0 for p in profile.portfolio.positions if p.weight_pct > 0}


def prepare(engine: QuantEngine, profile: m.Profile, rules: list[m.PolicyRule], move: m.ProposedMove | None,
            compare: bool | None, evidence=()) -> dict:
    """Quant step: resolved funding, before/after weights, funding options (JSON-serializable)."""
    weights = weights_of(profile)
    out = {"profileId": profile.profile_id, "weightsBefore": weights, "weightsAfter": weights, "valueFactor": 1.0,
           "move": None, "funding": {"mode": "pro_rata"}, "fundingOptions": [], "fundingSearch": None}
    if move is None:
        return out
    ticker, size, mode = move.ticker, move.size_pct, move.funding.mode
    if mode != "new_money" and mode != "auto" and size > 100.0 * (1 - weights.get(ticker, 0.0)) + 1e-9:
        raise ServiceError("validation_error", f"sizePct must be at most {100 * (1 - weights.get(ticker, 0.0)):.2f} for {mode} funding",
                           {"fields": ["move.sizePct"]})
    if size > 100.0 + 1e-9:
        raise ServiceError("validation_error", "sizePct must be at most 100", {"fields": ["move.sizePct"]})
    options = []
    if mode == "auto" or compare:
        named = move.funding.from_tickers if mode == "from_holdings" else None
        options = compare_funding(engine, rules, weights, ticker, size, evidence, profile.profile_id, named)
        out["fundingOptions"] = [funding_option_wire(e) for e in options]
    if mode == "auto":
        best = next((e for e in options if e.rank == 1), None)
        if best is None:
            raise ServiceError("insufficient_data", "No funding mode can fund this move", {"reasons": [e.reason for e in options]})
        funding = best.funding
    else:
        funding = move.funding.to_wire()
    try:
        res = apply_move(weights, ticker, size, funding["mode"], funding.get("fromTickers"))
    except FundingError as exc:
        raise ServiceError("validation_error", exc.reason["en"], {"fields": ["move.funding"], "code": exc.code, "reason": exc.reason}) from exc
    out.update({"weightsAfter": res.weights, "valueFactor": res.value_factor, "funding": funding,
                "move": {"ticker": ticker, "sizePct": size, "funding": funding}})
    return out


def assess(engine: QuantEngine, profile: m.Profile, rules: list[m.PolicyRule], prepared: dict, *, window: dict, evidence=(),
           attention: dict | None = None, started: float | None = None) -> m.CheckResult:
    """Risk step: rule checks on the after-move portfolio and the first-conflict boundary."""
    started = started if started is not None else time.perf_counter()
    total = profile.portfolio.total_value
    before = engine.view(prepared["weightsBefore"], "before", total, window=window)
    move = prepared["move"]
    moved = (move["ticker"],) if move else ()
    after = engine.view(prepared["weightsAfter"], "after", total * prepared["valueFactor"], window=window) if move else before
    rule_engine = RuleEngine(engine.ledger, engine.ctx)
    checks = rule_engine.check_rules(rules, RuleInputs(after, profile.profile_id, moved, tuple(evidence), attention,
                                                       move["ticker"] if move else None))
    verdict, counts = verdict_of(checks)
    base_statuses = quick_statuses(rules, RuleInputs(engine.view(prepared["weightsBefore"], "before-scan", total, record=False,
                                                                 window=window), profile.profile_id, (), tuple(evidence)))
    baseline_conflict = verdict_of_statuses(base_statuses.values()) == "conflict"
    max_size = 0.0
    if move:
        f = prepared["funding"]
        search = max_compatible_size(engine, rules, prepared["weightsBefore"], move["ticker"], f["mode"], f.get("fromTickers"),
                                     evidence, profile.profile_id)
        max_size = search.max_size_pct
        _size_facts(engine, profile, move, search)
    return m.CheckResult.model_validate({
        "verdict": verdict, "counts": counts.to_wire(), "ruleChecks": [c.to_wire() for c in checks],
        "portfolioBefore": before.snapshot().to_wire(), "portfolioAfter": after.snapshot().to_wire(),
        "fundingUsed": prepared["funding"], "fundingOptions": prepared["fundingOptions"], "maxCompatibleSizePct": max_size,
        "baselineConflict": baseline_conflict, "facts": _facts(engine.ledger), "asOf": engine.ctx.as_of,
        "dataVersion": engine.ctx.data_version, "window": window, "computeMs": (time.perf_counter() - started) * 1000.0,
    })


def _facts(ledger) -> dict:
    if hasattr(ledger, "wire"):
        return ledger.wire()
    return {fid: f.to_wire() for fid, f in ledger.export().facts.items()}


def _size_facts(engine: QuantEngine, profile: m.Profile, move: dict, search) -> None:
    ctx = engine.ctx
    subject = {"type": "request", "id": move["ticker"], "variant": "after"}
    req_id = engine.ledger.add_fact(make_fact(
        ctx, key=fact_key("size.requested", "request", move["ticker"], "after", "na"), kind="input", metric="size.requested",
        label={"en": f"Requested size for {move['ticker']}", "fr": f"Taille demandée pour {move['ticker']}"},
        value=float(move["sizePct"]), unit="pts", currency=None, subject=subject, method_id="M_USER_INPUT", created_by="user",
        params={"fundingMode": move["funding"]["mode"]}, checks=[{"code": "schema", "ok": True, "detail": "Validated request field."}]))
    max_size_fact(engine, profile, move["ticker"], move["funding"], search, [req_id])


def max_size_fact(engine: QuantEngine, profile: m.Profile, ticker: str, funding: dict, search, inputs: list[str]) -> str:
    """``size.max_compatible`` fact for a grid search (inputs: the requested size, when there is one)."""
    ctx = engine.ctx
    move = {"ticker": ticker, "funding": funding}
    tickers = sorted({p.ticker for p in profile.portfolio.positions if p.weight_pct > 0} | {ticker})
    try:
        wr = engine.window()
        sources, available_at = engine._sources(tickers, wr.i0, wr.i1), engine.market.latest_avail(tickers, wr.i1)
    except Unavailable:
        sources, available_at = [], None
    if available_at is None:
        sources = []
    return engine.ledger.add_fact(make_fact(
        ctx, key=fact_key("size.max_compatible", "portfolio", profile.profile_id, f"after:{move['ticker']}:{move['funding']['mode']}", "na"),
        kind="scenario", metric="size.max_compatible",
        label={"en": f"Largest size before the first rule conflict, {move['ticker']} ({move['funding']['mode']})",
               "fr": f"Plus grande taille avant le premier conflit de règle, {move['ticker']} ({move['funding']['mode']})"},
        value=float(search.max_size_pct), unit="pts", currency=None,
        subject={"type": "portfolio", "id": profile.profile_id, "variant": "after"}, method_id="M_MAXSIZE_GRID", created_by="optimizer",
        params={"step": 0.5, "stoppedBy": search.stopped_by, "firstConflictPct": search.first_conflict_pct if search.first_conflict_pct is not None else "none",
                "remainingAtBoundary": "; ".join(search.remaining_at_max) or "none", "baselineConflict": search.baseline_conflict},
        inputs=inputs, sources=sources, available_at=available_at,
        limitations=["LIM_THRESHOLDS_ASSUMED", "LIM_PAST_NOT_FUTURE"],
        checks=[{"code": "grid_prefix", "ok": True, "detail": "Contiguous 0.5-point scan from zero, stopped at the first conflict; tension or missing evidence may remain."}]))


class CheckServiceImpl:
    """``CheckService`` for T03: profile (with session overlays) + request overrides."""

    def __init__(self, profiles, snapshot: Callable[[], Snapshot], *, clock: Callable[[], datetime] | None = None,
                 ledger_factory: Callable[[], object] = LocalLedger) -> None:
        self.profiles = profiles
        self.snapshot = snapshot
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.ledger_factory = ledger_factory

    def rebalance(self, session_id: str, request: a.RebalanceRequest) -> a.RebalanceResponse:
        from .rebalance import check_targets
        return check_targets(self.profiles, self.snapshot(), session_id, request, _now(self.clock))

    def check(self, session_id: str, request: a.CheckRequest) -> m.CheckResult:
        started = time.perf_counter()
        profile = self.profiles.get(session_id, request.profile_id)
        snap = self.snapshot()
        as_of = request.as_of or snap.data_as_of
        if as_of > snap.data_as_of:
            problem = f"asOf must be on or before the data date {snap.data_as_of}"
            raise ServiceError("validation_error", problem, {"fields": [{"path": "asOf", "problem": problem}]})
        mode = "historical" if as_of < snap.data_as_of else "current"
        window = request.window.to_wire() if request.window else {"code": "full"}
        gate = snap.gate(as_of, mode)
        if request.move is not None:
            ticker = request.move.ticker
            if ticker not in snap.gate(snap.data_as_of).universe():
                raise NotFound(f"Unknown ticker {ticker}")
            if ticker not in gate.universe():
                raise ServiceError("insufficient_data", f"{ticker} has no price on or before {as_of}", {"ticker": ticker})
        if mode == "historical":
            # Imported here: timemachine.service loads optimizer.derive, and with it this package.
            from aplomb.timemachine.service import rederive_at

            # Same rule set as a replay of that date; the stored one was derived from later data.
            profile = rederive_at(profile, snap, as_of, _now(self.clock))
        rules = apply_overrides(profile, request.rule_overrides)
        engine = QuantEngine(gate, self.ledger_factory(), currency=profile.reporting_currency, subject_id=profile.profile_id,
                             created_at=_now(self.clock), window=window)
        try:
            engine.window(window)
        except Unavailable as exc:
            raise ServiceError("insufficient_data", exc.detail, {"window": window}) from exc
        try:
            prepared = prepare(engine, profile, rules, request.move, request.compare_funding)
            return assess(engine, profile, rules, prepared, window=window, started=started)
        except UnknownTicker as exc:
            raise ServiceError("insufficient_data", str(exc)) from exc
