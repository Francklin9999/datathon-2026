"""Profile service (track T06, profiles SPEC §2): defaults + per-session overlays, custom
profiles, rule edits, deterministic overview and performance.

Defaults are read-only; a session's edits to a default are an overlay item holding only the
changed rules/portfolio, merged on read. ``version`` = 1 + overlay revision for defaults and the
stored revision for custom profiles. Threshold derivation and starting-portfolio proposals are
injected (optimizer, T07); without them those operations report ``upstream_unavailable``.
"""

from __future__ import annotations

import copy
import math
import secrets
from datetime import datetime, timezone
from typing import Callable

from aplomb.api.errors import Conflict, NotFound, ServiceError, unavailable
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.datastore import Snapshot, UnknownTicker
from aplomb.quant import LocalLedger, QuantEngine, Unavailable
from aplomb.quant import metrics as mx
from aplomb.rules.engine import RuleEngine, RuleInputs, verdict_of

from .defaults import load_defaults
from .rulebuilder import renumber

VOL_BUDGET = {"low": 6.0, "low_moderate": 9.0, "moderate": 12.0, "moderate_high": 16.0, "high": 22.0}  # A-02
RISK_ORDER = ("low", "low_moderate", "moderate", "moderate_high", "high")
WINDOW_CODES = ("full", "1y", "3y", "5y", "ytd")
MAX_POSITIONS = 40
_B32 = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford base32, lower case (contracts ProfileId)

Deriver = Callable[..., tuple[list[dict], dict[str, m.Fact]]]
Proposer = Callable[..., dict]


def _now(clock: Callable[[], datetime]) -> str:
    return clock().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validation(message: str, details: dict | None = None) -> ServiceError:
    return ServiceError("validation_error", message, details)


class ProfileServiceImpl:
    def __init__(self, repository, snapshot: Callable[[], Snapshot], *, clock: Callable[[], datetime] | None = None,
                 deriver: Deriver | None = None, proposer: Proposer | None = None) -> None:
        self.repo = repository
        self.snapshot = snapshot
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.deriver = deriver
        self.proposer = proposer
        self._defaults = {p.profile_id: p for p in load_defaults()}

    # Reads ------------------------------------------------------------------------------------

    def list(self, session_id: str) -> list[m.Profile]:
        out = [self.get(session_id, pid) for pid in self._defaults]
        customs = [item for item in self.repo.list(session_id) if not item.get("overlay")]
        for item in sorted(customs, key=lambda i: i["value"]["createdAt"]):
            out.append(m.Profile.model_validate(item["value"]))
        return out

    def get(self, session_id: str, profile_id: str) -> m.Profile:
        return self._load(session_id, profile_id)[0]

    def _load(self, session_id: str, profile_id: str) -> tuple[m.Profile, dict | None]:
        if profile_id in self._defaults:
            overlay = self.repo.get(session_id, profile_id, overlay=True)
            return self._merge(self._defaults[profile_id], overlay), overlay
        item = self.repo.get(session_id, profile_id)
        if item is None:
            raise NotFound(f"Unknown profile {profile_id}")
        return m.Profile.model_validate(item["value"]), item

    def _merge(self, default: m.Profile, overlay: dict | None) -> m.Profile:
        if not overlay:
            return default
        data = default.to_wire()
        ov = overlay["value"]
        changed = ov.get("rules") or {}
        data["rules"] = [copy.deepcopy(changed.get(r["ruleId"], r)) for r in data["rules"]]
        if ov.get("portfolio") is not None:
            data["portfolio"] = copy.deepcopy(ov["portfolio"])
        data["version"] = 1 + overlay["revision"]
        data["updatedAt"] = ov.get("updatedAt", data["updatedAt"])
        return m.Profile.model_validate(data)

    # Writes -----------------------------------------------------------------------------------

    def _save(self, session_id: str, profile: m.Profile, stored: dict | None) -> m.Profile:
        data = profile.to_wire()
        if profile.is_default:
            # Overlay = only what differs from the shipped default (profiles SPEC §2 "Storage").
            base = self._defaults[profile.profile_id].to_wire()
            base_rules = {r["ruleId"]: r for r in base["rules"]}
            value = {"rules": {r["ruleId"]: r for r in data["rules"] if r != base_rules.get(r["ruleId"])},
                     "portfolio": data["portfolio"] if data["portfolio"] != base["portfolio"] else None,
                     "updatedAt": data["updatedAt"]}
            revision = stored["revision"] if stored else None
            saved = self.repo.save(session_id, profile.profile_id, value, revision, overlay=True)
            data["version"] = 1 + saved["revision"]
        else:
            revision = stored["revision"]
            data["version"] = revision + 1
            self.repo.save(session_id, profile.profile_id, data, revision)
        return m.Profile.model_validate(data)

    def patch_rule(self, session_id: str, profile_id: str, rule_id: str, threshold: float | None,
                   enabled: bool | None) -> m.Profile:
        profile, stored = self._load(session_id, profile_id)
        data = profile.to_wire()
        rule = next((r for r in data["rules"] if r["ruleId"] == rule_id), None)
        if rule is None:
            raise NotFound(f"Profile {profile_id} has no rule {rule_id}")
        if not rule["editable"]:
            raise Conflict(f"Rule {rule_id} cannot be edited")
        if threshold is None and enabled is None:
            raise validation("Supply threshold or enabled")
        if threshold is not None:
            b = rule["bounds"]
            if rule["threshold"] is None or b is None:
                raise validation(f"Rule {rule_id} has no editable threshold", {"fields": ["threshold"]})
            if not (b["min"] - 1e-9 <= threshold <= b["max"] + 1e-9):
                raise validation(f"threshold must be between {b['min']:g} and {b['max']:g}", {"fields": ["threshold"]})
            rule["threshold"] = float(threshold)
            rule["derivation"] = None
        if enabled is not None:
            rule["enabled"] = bool(enabled)
        now = _now(self.clock)
        rule["origin"] = "user"
        rule["updatedAt"] = now
        data["updatedAt"] = now
        return self._save(session_id, m.Profile.model_validate(data), stored)

    def set_portfolio(self, session_id: str, profile_id: str, portfolio: a.UpdatePortfolioRequest, version: int) -> m.Profile:
        profile, stored = self._load(session_id, profile_id)
        if profile.version != version:
            raise Conflict()
        positions = [p.to_wire() for p in portfolio.positions]
        self._validate_portfolio(portfolio.total_value, positions)
        now = _now(self.clock)
        data = profile.to_wire()
        data["portfolio"] = {"isFictional": True, "totalValue": float(portfolio.total_value), "currency": profile.reporting_currency,
                             "positions": positions, "updatedAt": now}
        data["updatedAt"] = now
        return self._save(session_id, m.Profile.model_validate(data), stored)

    def create(self, session_id: str, request: a.CreateProfileRequest) -> m.Profile:
        now = _now(self.clock)
        profile_id = "p_" + "".join(secrets.choice(_B32) for _ in range(10))
        data = self._custom_body(request, profile_id, now, created_at=now)
        data["version"] = 1
        self.repo.save(session_id, profile_id, data, None)
        return m.Profile.model_validate(data)

    def replace(self, session_id: str, profile_id: str, request: a.UpdateProfileRequest, version: int) -> m.Profile:
        if profile_id in self._defaults:
            raise Conflict("Default profiles cannot be replaced; edit rules or the portfolio instead")
        profile, stored = self._load(session_id, profile_id)
        if profile.version != version:
            raise Conflict()
        now = _now(self.clock)
        data = self._custom_body(request, profile_id, now, created_at=profile.created_at)
        data["version"] = stored["revision"] + 1
        self.repo.save(session_id, profile_id, data, stored["revision"])
        return m.Profile.model_validate(data)

    def delete(self, session_id: str, profile_id: str) -> None:
        if profile_id in self._defaults:
            raise Conflict("Default profiles cannot be deleted")
        _, stored = self._load(session_id, profile_id)
        self.repo.delete(session_id, profile_id, stored["revision"])

    def rederive_rules(self, session_id: str, profile_id: str, reset: bool, window: m.WindowSpec | None):
        if self.deriver is None:
            raise unavailable("Threshold derivation")
        profile, stored = self._load(session_id, profile_id)
        rules, facts = self.deriver(profile=profile, snapshot=self.snapshot(), window=window.to_wire() if window else None,
                                    created_at=_now(self.clock))
        derived = {r["ruleId"]: r for r in rules}
        merged = []
        for r in profile.to_wire()["rules"]:
            if r["ruleId"] in derived and (r["origin"] == "derived" or (reset and r["origin"] == "user")):
                merged.append({**derived[r["ruleId"]], "enabled": r["enabled"] if not reset else True})
            else:
                merged.append(r)
        data = profile.to_wire()
        data["rules"] = renumber(merged)
        data["updatedAt"] = _now(self.clock)
        return self._save(session_id, m.Profile.model_validate(data), stored), facts

    def _custom_body(self, request: a.CreateProfileRequest, profile_id: str, now: str, created_at: str) -> dict:
        req = request.to_wire()
        hz = request.horizon_years
        if hz.max is not None and hz.max < hz.min:
            raise validation("horizonYears.max must be at least horizonYears.min", {"fields": ["horizonYears"]})
        if request.portfolio is not None:
            positions = [p.to_wire() for p in request.portfolio.positions]
            self._validate_portfolio(request.portfolio.total_value, positions)
            portfolio = {"isFictional": True, "totalValue": float(request.portfolio.total_value),
                         "currency": request.reporting_currency, "positions": positions, "updatedAt": now}
        else:
            if self.proposer is None:
                raise unavailable("Starting-portfolio proposal")
            portfolio = self.proposer(request=request, snapshot=self.snapshot(), created_at=now)
        body = {
            "profileId": profile_id, "isDefault": False, "origin": "agent_draft" if req.get("fromDraftRunId") else "user",
            "name": request.name, "initial": request.name.strip()[0].upper(), "age": request.age, "occupation": None,
            "riskLevel": request.risk_level, "horizonYears": req["horizonYears"], "objective": request.objective,
            "objectiveText": _OBJECTIVE[request.objective], "experience": request.experience,
            "reportingCurrency": request.reporting_currency, "preferences": req["preferences"],
            "blurb": {"en": f"Custom fictional profile, {request.risk_level.replace('_', '-')} risk.",
                      "fr": f"Profil fictif personnalisé, risque {request.risk_level.replace('_', ' ')}."},
            "personaTest": None, "portfolio": portfolio, "rules": [], "version": 1, "createdAt": created_at, "updatedAt": now,
        }
        if request.rules is not None:
            body["rules"] = renumber([r.to_wire() for r in request.rules])
        else:
            if self.deriver is None:
                raise unavailable("Threshold derivation")
            rules, _ = self.deriver(profile=m.Profile.model_validate(body), snapshot=self.snapshot(), window=None, created_at=now)
            body["rules"] = renumber(rules)
        return m.Profile.model_validate(body).to_wire()

    def _validate_portfolio(self, total_value: float, positions: list[dict]) -> None:
        if not total_value > 0:
            raise validation("totalValue must be greater than 0", {"fields": ["totalValue"]})
        if len(positions) > MAX_POSITIONS:
            raise validation(f"At most {MAX_POSITIONS} positions", {"fields": ["positions"]})
        tickers = [p["ticker"] for p in positions]
        if len(set(tickers)) != len(tickers):
            raise validation("Each ticker may appear once", {"fields": ["positions"]})
        total = math.fsum(p["weightPct"] for p in positions)
        if abs(total - 100.0) > 0.01:
            raise validation(f"Position weights sum to {total:.2f}, not 100", {"fields": ["positions"], "sum": total})
        snap = self.snapshot()
        universe = snap.gate(snap.data_as_of).universe()
        unknown = [t for t in tickers if t not in universe]
        if unknown:
            raise NotFound(f"Unknown tickers: {', '.join(unknown)}")

    # Deterministic analytics ------------------------------------------------------------------

    def _engine(self, profile: m.Profile, query: dict, ledger: LocalLedger):
        code = (query or {}).get("window") or "full"
        if isinstance(code, dict):
            code = code.get("code", "full")
        if code not in WINDOW_CODES:
            raise validation(f"window must be one of {', '.join(WINDOW_CODES)}", {"fields": ["window"]})
        snap = self.snapshot()
        gate = snap.gate(snap.data_as_of, "current")
        eng = QuantEngine(gate, ledger, currency=profile.reporting_currency, subject_id=profile.profile_id,
                          created_at=_now(self.clock), window={"code": code})
        return eng, {"code": code}

    @staticmethod
    def _weights(profile: m.Profile) -> dict[str, float]:
        return {p.ticker: p.weight_pct / 100.0 for p in profile.portfolio.positions if p.weight_pct > 0}

    def overview(self, session_id: str, profile_id: str, query: dict) -> a.OverviewResponse:
        profile = self.get(session_id, profile_id)
        ledger = LocalLedger()
        eng, window = self._engine(profile, query, ledger)
        weights = self._weights(profile)
        try:
            view = eng.view(weights, "before", profile.portfolio.total_value)
        except UnknownTicker as exc:
            raise ServiceError("insufficient_data", str(exc)) from exc
        snapshot = view.snapshot()
        pm = view.metrics()

        returns, rids = {}, {}
        for field_name, code, metric in (("ytdPct", "ytd", "return.ytd"), ("y1Pct", "1y", "return.trailing"),
                                         ("y3Pct", "3y", "return.trailing"), ("y5Pct", "5y", "return.trailing")):
            try:
                wr = eng.window({"code": code})
                value = mx.period_return_pct(eng.portfolio_levels(weights, wr.i0, wr.i1))
            except Unavailable:
                returns[field_name] = None
                continue
            returns[field_name] = value
            rids[field_name] = eng.add_series_fact(
                metric=metric, value=value, subject=view.subject, variant_key="before", window_code=code, tickers=list(weights),
                i0=wr.i0, i1=wr.i1, method_id="M_PORT_CONST_WEIGHTS", window_spec={"code": code},
                label={"en": f"Portfolio return, {code}, {profile.name}, {profile.reporting_currency}",
                       "fr": f"Rendement du portefeuille, {code}, {profile.name}, {profile.reporting_currency}"})

        worst12, wid = None, None
        try:
            wr = eng.window(window)
            worst12 = mx.worst_rolling_return_pct(eng.portfolio_levels(weights, wr.i0, wr.i1))
            if worst12 is not None:
                wid = eng.add_series_fact(
                    metric="return.worst_12m", value=worst12, subject=view.subject, variant_key="before", window_code=wr.code,
                    tickers=list(weights), i0=wr.i0, i1=wr.i1, method_id="M_WORST_ROLLING_252", window_spec=window,
                    label={"en": f"Worst 12-month return, {profile.name}", "fr": f"Pire rendement sur 12 mois, {profile.name}"})
        except Unavailable:
            pass
        vol = pm.volatility_pct
        category = next((r for r in RISK_ORDER if vol is not None and VOL_BUDGET[r] >= vol - 1e-12), None)
        if category is None:
            category = "high" if vol is not None else profile.risk_level
        risk_ids = {k: v for k, v in {"volatility": pm.fact_ids.get("vol.annualized"), "maxDrawdown": pm.fact_ids.get("drawdown.max"),
                                      "worst12m": wid, "stress2022": pm.fact_ids.get("stress.replay_2022")}.items() if v}

        top = []
        for p in sorted(profile.portfolio.positions, key=lambda x: -x.weight_pct)[:5]:
            r1 = eng.asset_metrics(p.ticker, {"code": "1y"})["return.period"] if not p.ticker.startswith("CASH.") else None
            top.append({"ticker": p.ticker, "name": view.assets[p.ticker].name, "weightPct": p.weight_pct,
                        "marketValue": p.weight_pct / 100.0 * profile.portfolio.total_value,
                        "return1yPct": r1.value if r1 else None, "assetClass": view.assets[p.ticker].asset_class})

        correlation = None
        if len(weights) <= 20:
            pairs = eng.correlation(list(weights), window)
            usable = [t for t in weights if all(pairs.get((a_, b_), pairs.get((b_, a_))).value is not None
                                                for a_, b_ in [(t, u) for u in weights if u != t])]
            if len(usable) >= 2:
                matrix = [[1.0 if x == y else (pairs.get((x, y)) or pairs.get((y, x))).value for y in usable] for x in usable]
                correlation = {"tickers": usable, "matrix": matrix}

        rule_engine = RuleEngine(ledger, eng.ctx)
        checks = rule_engine.check_rules(profile.rules, RuleInputs(view, profile.profile_id))
        verdict, counts = verdict_of(checks)
        facts = ledger.wire()
        limitations = sorted({lim for f in ledger.facts().values() for lim in f.limitations} | {"LIM_SIMULATION_ONLY"})
        return a.OverviewResponse.model_validate({
            "profileId": profile.profile_id, "asOf": eng.ctx.as_of, "dataVersion": eng.ctx.data_version, "window": window,
            "snapshot": snapshot.to_wire(),
            "returns": {**returns, "factIds": rids},
            "risk": {"volatilityPct": vol, "maxDrawdownPct": pm.max_drawdown_pct, "worst12mPct": worst12,
                     "stress2022Pct": pm.stress2022_pct, "riskCategory": category, "factIds": risk_ids},
            "concentration": {"hhi": pm.hhi, "effectiveN": pm.effective_n, "topPositions": top},
            "correlation": correlation, "ruleChecks": [c.to_wire() for c in checks], "verdict": verdict,
            "counts": counts.to_wire(), "facts": facts, "limitations": limitations,
        })

    def performance(self, session_id: str, profile_id: str, query: dict) -> a.PerformanceResponse:
        profile = self.get(session_id, profile_id)
        eng, window = self._engine(profile, query, LocalLedger())
        weights = self._weights(profile)
        try:
            wr = eng.window(window)
            levels = eng.portfolio_levels(weights, wr.i0, wr.i1)
        except Unavailable as exc:
            raise ServiceError("insufficient_data", exc.detail) from exc
        dates = eng.market.dates[wr.i0:wr.i1 + 1]
        start = profile.portfolio.total_value
        series = [{"date": d, "value": start * v} for d, v in zip(dates, levels)]
        benchmark = None
        ticker = (query or {}).get("benchmark")
        if ticker:
            try:
                lv = eng.market.window_levels(ticker, wr.i0, wr.i1)
            except Unavailable as exc:
                if exc.reason == "asset_unknown":
                    raise NotFound(f"Unknown ticker {ticker}") from exc
                raise ServiceError("insufficient_data", exc.detail) from exc
            benchmark = {"ticker": ticker, "series": [{"date": d, "value": start * x / lv[0]} for d, x in zip(dates, lv)]}
        lims = ["LIM_CONSTANT_WEIGHTS", "LIM_SAMPLE_WINDOW", "LIM_PAST_NOT_FUTURE", "LIM_CALENDAR_INTERSECTION", "LIM_YAHOO_NOT_CERTIFIED"]
        if eng.market.fx_rows_used(list(weights) + ([ticker] if ticker else []), wr.i0, wr.i1):
            lims.append("LIM_FX_FFILL")
        return a.PerformanceResponse.model_validate({
            "window": window, "currency": profile.reporting_currency, "series": series, "benchmark": benchmark,
            "method": "M_PORT_CONST_WEIGHTS", "limitations": lims})

    def frontier(self, session_id: str, profile_id: str, query: dict) -> a.FrontierResponse:
        """Descriptive frontier (optimizer SPEC §6); never feeds a rule or a verdict."""
        from aplomb.optimizer.frontier import frontier

        profile = self.get(session_id, profile_id)
        eng, _ = self._engine(profile, {"window": (query or {}).get("window") or "full"}, LocalLedger())
        return a.FrontierResponse.model_validate(frontier(eng, profile, query or {}))

    def brief(self, session_id: str, profile_id: str, query: dict):
        raise unavailable("Portfolio brief lookup")


_OBJECTIVE = {
    "preserve": {"en": "Preserve capital while keeping some growth potential.", "fr": "Préserver le capital tout en gardant un potentiel de croissance."},
    "balanced": {"en": "Balanced capital growth over time.", "fr": "Croissance équilibrée du capital dans le temps."},
    "growth": {"en": "Grow capital over the long term.", "fr": "Faire croître le capital à long terme."},
}
