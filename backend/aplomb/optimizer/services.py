"""Adapters wiring the optimizer into the profile service (T06) and the agent workflow (T08)."""

from __future__ import annotations

from aplomb.api.errors import ServiceError
from aplomb.contracts import models as m
from aplomb.datastore import Snapshot
from aplomb.quant import LocalLedger, QuantEngine, Unavailable
from aplomb.rules.engine import RuleInputs, quick_statuses, verdict_of_statuses

from .check import assess, prepare
from .derive import derive_thresholds

PROPOSAL_VALUE = 100000.0  # fictional starting capital of a proposed portfolio (labelled hypothetical)


def _control_outcome_type():
    """T08's ``ControlOutcome``; a same-shaped dataclass where the agents package cannot load
    (its persistence layer needs POSIX ``fcntl``, absent on Windows development machines)."""
    try:
        from aplomb.agents.workflow import ControlOutcome

        return ControlOutcome
    except ModuleNotFoundError:
        from dataclasses import dataclass, field

        @dataclass
        class ControlOutcome:  # noqa: D401 - mirror of aplomb.agents.workflow.ControlOutcome
            check: object
            scenarios: list
            selected_scenario_id: str
            limitations: list = field(default_factory=list)

        return ControlOutcome


def _profile_engine(profile: m.Profile, snapshot: Snapshot, created_at: str, ledger=None) -> QuantEngine:
    gate = snapshot.gate(snapshot.data_as_of, "current")
    return QuantEngine(gate, ledger if ledger is not None else LocalLedger(), currency=profile.reporting_currency,
                       subject_id=profile.profile_id, created_at=created_at, custom_themes=profile.investor_context.custom_theme_definitions if profile.investor_context else ())


def deriver(*, profile: m.Profile, snapshot: Snapshot, window: dict | None, created_at: str):
    """``ProfileServiceImpl`` hook: derived rules (wire dicts) and the facts holding their inputs."""
    engine = _profile_engine(profile, snapshot, created_at)
    try:
        d = derive_thresholds(profile, engine, created_at=created_at, window=window)
    except Unavailable as exc:
        raise ServiceError("insufficient_data", exc.detail) from exc
    facts = {fid: engine.ledger.get_fact(fid) for fid in engine.ledger.facts()}
    return d.rules, facts


def proposer(*, request, snapshot: Snapshot, created_at: str) -> dict:
    """Hypothetical starting portfolio from broad reference funds (optimizer SPEC §5).

    Equity = XIU.TO / SPY (ESGV instead of SPY when the profile focuses on ESG), bonds = XBB.TO,
    5% gold when diversification is wanted, explicit same-currency cash only when needed. The
    largest equity share (5-point steps, starting at the derived growth cap) whose mix has no
    rule conflict is kept; no single names, no crypto, nothing inferred from free text.
    """
    body = {
        "profileId": "p_0000000000", "isDefault": False, "origin": "user", "name": request.name, "initial": request.name.strip()[0].upper(),
        "age": request.age, "occupation": None, "riskLevel": request.risk_level, "horizonYears": request.horizon_years.to_wire(),
        "objective": request.objective, "objectiveText": {"en": "-", "fr": "-"}, "experience": request.experience,
        "reportingCurrency": request.reporting_currency, "preferences": request.preferences.to_wire(),
        "blurb": {"en": "-", "fr": "-"}, "personaTest": None,
        "portfolio": {"isFictional": True, "totalValue": PROPOSAL_VALUE, "currency": request.reporting_currency,
                      "positions": [{"ticker": "XBB.TO", "weightPct": 100.0}], "updatedAt": created_at},
        "rules": [], "version": 1, "createdAt": created_at, "updatedAt": created_at,
    }
    profile = m.Profile.model_validate(body)
    engine = _profile_engine(profile, snapshot, created_at)
    try:
        derivation = derive_thresholds(profile, engine, created_at=created_at)
    except Unavailable as exc:
        raise ServiceError("insufficient_data", exc.detail) from exc
    rules = [m.PolicyRule.model_validate(r) for r in derivation.rules]
    growth = derivation.values["growthCapPct"]
    us_equity = "ESGV" if request.preferences.esg_focus else "SPY"
    gold = 5.0 if request.preferences.wants_diversification else 0.0
    cash = f"CASH.{request.reporting_currency}"
    start = int(growth) if growth is not None else 0
    for equity in range(start - start % 5, -1, -5):
        for cash_pct in range(0, 101 - equity - int(gold), 5):
            bonds = 100.0 - equity - gold - cash_pct
            weights = {"XIU.TO": equity / 200, us_equity: equity / 200, "XBB.TO": bonds / 100, "GLD": gold / 100, cash: cash_pct / 100}
            weights = {k: v for k, v in weights.items() if v > 0}
            view = engine.view(weights, f"proposal:{equity}:{cash_pct}", PROPOSAL_VALUE, record=False)
            statuses = quick_statuses(rules, RuleInputs(view, profile.profile_id))
            if verdict_of_statuses(statuses.values()) != "conflict":
                positions = [{"ticker": t, "weightPct": round(w * 100, 6)} for t, w in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))]
                return {"isFictional": True, "totalValue": PROPOSAL_VALUE, "currency": request.reporting_currency,
                        "positions": positions, "updatedAt": created_at}
    raise ServiceError("insufficient_data", "No reference-fund mix satisfies the derived rules; enter a starting portfolio instead.")


class DecisionControls:
    """``CodeControls`` provider for the agent workflow (T08).

    ``quant`` registers snapshot/metrics/funding facts in the run ledger and returns a JSON state;
    ``risk`` evaluates every enabled rule and builds the scenarios. Move requests: the requested
    move, the largest size before the first conflict and, when the move conflicts, up to two
    alternatives sharing a theme tag. Goal requests: up to three goal candidates (best fit
    selected). A rebalance scenario is added when the current portfolio already conflicts
    (D-14). At most six scenarios. A goal with no candidate (target already met, or no eligible
    asset) yields one no-change scenario carrying the reason, with no move.
    """

    MAX_SCENARIOS = 6

    def _engine(self, ctx, window: dict) -> QuantEngine:
        clock = getattr(ctx.ledger, "clock", None)
        created_at = clock() if callable(clock) else f"{ctx.as_of}T00:00:00Z"
        profile = ctx.profile
        return QuantEngine(ctx.gate, ctx.ledger, currency=profile.reporting_currency, subject_id=profile.profile_id,
                           created_at=created_at, window=window, custom_themes=profile.investor_context.custom_theme_definitions if profile.investor_context else ())

    @staticmethod
    def _wire(obj):
        return obj.to_wire() if hasattr(obj, "to_wire") else dict(obj)

    def quant(self, ctx, request, window, tasks, scenarios) -> dict:
        win = self._wire(window) if window is not None else {"code": "full"}
        engine = self._engine(ctx, win)
        profile = ctx.profile
        if request is None:
            # Portfolio brief: the current portfolio against its rules, no move (agents SPEC §5).
            prepared = prepare(engine, profile, profile.rules, None, False)
            view = engine.view(prepared["weightsBefore"], "before", profile.portfolio.total_value, window=win)
            view.snapshot()
            view.measure("weight.asset_group", "fixed_income")
            funding = None
            if profile.investor_context and profile.investor_context.objectives and not ctx.historical:
                from aplomb.profiles.goals import register_goal_funding
                clock = getattr(ctx.ledger, "clock", None)
                now = clock() if callable(clock) else f"{ctx.as_of}T00:00:00Z"
                funding = register_goal_funding(ctx, now)
            return {"kind": "baseline", "window": win, "prepared": prepared, "goalFunding": funding}
        req = self._wire(request)
        if req.get("type") == "goal":
            goal = m.ExposureGoal.model_validate(req["goal"])
            engine.view(prepare(engine, profile, profile.rules, None, False)["weightsBefore"], "before",
                        profile.portfolio.total_value, window=win).snapshot()
            return {"kind": "goal", "window": win, "goal": goal.to_wire()}
        if req.get("type") != "move":
            raise RuntimeError(f"Unsupported decision request type {req.get('type')!r}")
        move = m.ProposedMove.model_validate(req["move"])
        prepared = prepare(engine, profile, profile.rules, move, compare=True)
        engine.view(prepared["weightsBefore"], "before", profile.portfolio.total_value, window=win).snapshot()
        engine.view(prepared["weightsAfter"], "after", profile.portfolio.total_value * prepared["valueFactor"], window=win).snapshot()
        return {"kind": "move", "window": win, "prepared": prepared}

    def risk(self, ctx, computed: dict):
        from .scenarios import alternatives, goal_candidates, no_change, rebalance

        ControlOutcome = _control_outcome_type()
        win = computed["window"]
        engine = self._engine(ctx, win)
        profile = ctx.profile
        # Evidence saved by the researcher in this run's ledger; the rule engine keeps only verified
        # tier 1-2 items about the assets the move adds or increases.
        export = getattr(ctx.ledger, "export", None)
        evidence = tuple(export().evidence.values()) if callable(export) else ()
        if computed["kind"] == "baseline":
            check = assess(engine, profile, profile.rules, computed["prepared"], window=win, evidence=evidence)
            facts = engine.ledger.export().facts if hasattr(engine.ledger, "export") else engine.ledger.facts()
            limitations = sorted({lim for f in facts.values() for lim in f.limitations} | {"LIM_SIMULATION_ONLY"})
            return ControlOutcome(check=check, scenarios=[], selected_scenario_id="", limitations=limitations)
        if computed["kind"] == "goal":
            goal = m.ExposureGoal.model_validate(computed["goal"])
            found = goal_candidates(engine, profile, goal)
            if found.scenarios:
                best = found.scenarios[0]
                prepared = prepare(engine, profile, profile.rules, m.ProposedMove.model_validate(best["moves"][0]), compare=True)
                scenarios = list(found.scenarios)
            else:
                # Target already met or no eligible asset: a normal outcome, never an invented trade.
                prepared = prepare(engine, profile, profile.rules, None, False)
                scenarios = [no_change(engine, profile, goal, found.notes)]
            check = assess(engine, profile, profile.rules, prepared, window=win, evidence=evidence)
            selected = scenarios[0]["scenarioId"]
        else:
            prepared = computed["prepared"]
            check = assess(engine, profile, profile.rules, prepared, window=win, evidence=evidence)
            scenarios = [self._scenario("sc_requested", "requested", prepared["move"], check.verdict, check.counts.to_wire(),
                                        [c.to_wire() for c in check.rule_checks], check.portfolio_after.to_wire(), 1, True)]
            size = check.max_compatible_size_pct
            if 0 < size < prepared["move"]["sizePct"]:
                from aplomb.quant import apply_move
                from aplomb.rules.engine import RuleEngine, verdict_of

                f = prepared["funding"]
                res = apply_move(prepared["weightsBefore"], prepared["move"]["ticker"], size, f["mode"], f.get("fromTickers"))
                view = engine.view(res.weights, "scenario:sc_max_compatible", profile.portfolio.total_value * res.value_factor, window=win)
                checks = RuleEngine(engine.ledger, engine.ctx).check_rules(
                    profile.rules, RuleInputs(view, profile.profile_id, (prepared["move"]["ticker"],)))
                verdict, counts = verdict_of(checks)
                move = {**prepared["move"], "sizePct": size}
                scenarios.append(self._scenario("sc_max_compatible", "max_compatible", move, verdict, counts.to_wire(),
                                                [c.to_wire() for c in checks], view.snapshot().to_wire(), 2, False))
            if check.verdict == "conflict":
                alts = alternatives(engine, profile, prepared["move"]["ticker"], prepared["move"]["sizePct"], max_candidates=2)
                for s in alts.scenarios:
                    scenarios.append({**s, "rank": len(scenarios) + 1})
            selected = "sc_requested"
        if check.baseline_conflict and len(scenarios) < self.MAX_SCENARIOS:
            for s in rebalance(engine, profile).scenarios:
                scenarios.append({**s, "rank": len(scenarios) + 1})
        scenarios = scenarios[: self.MAX_SCENARIOS]
        facts = engine.ledger.export().facts if hasattr(engine.ledger, "export") else engine.ledger.facts()
        limitations = sorted({lim for f in facts.values() for lim in f.limitations} | {"LIM_SIMULATION_ONLY"})
        return ControlOutcome(check=check, scenarios=[m.Scenario.model_validate(s) for s in scenarios],
                              selected_scenario_id=selected, limitations=limitations)

    @staticmethod
    def _scenario(sid, kind, move, verdict, counts, rule_checks, portfolio_after, rank, best) -> dict:
        refs = [c["valueFactId"] for c in rule_checks if c["status"] in ("conflict", "tension") and c["valueFactId"]]
        n_en = f"{move['sizePct']:g}"
        n_fr = n_en.replace(".", ",")
        label = {"requested": {"en": f"Requested: {n_en} points into {move['ticker']}",
                               "fr": f"Demandé : {n_fr} points dans {move['ticker']}"},
                 "max_compatible": {"en": f"Largest size before the first conflict: {n_en} points into {move['ticker']}",
                                    "fr": f"Plus grande taille avant le premier conflit : {n_fr} points dans {move['ticker']}"}}[kind]
        rationale = {"requested": {"en": "The move as confirmed by the user.", "fr": "Le mouvement tel que confirmé par l'utilisateur."},
                     "max_compatible": {"en": "Same move at the last 0.5-point size before the first rule conflict; tension or missing evidence may remain.",
                                        "fr": "Même mouvement à la dernière taille, par pas de 0,5 point, avant le premier conflit; une tension ou une preuve manquante peut subsister."}}[kind]
        return {"scenarioId": sid, "kind": kind, "label": label, "moves": [move], "verdict": verdict, "counts": counts,
                "ruleChecks": rule_checks, "portfolioAfter": portfolio_after, "exposure": [], "rationale": rationale,
                "isBestFit": best, "rank": rank, "keyFactIds": refs}


def build_domain_services(profile_repository, snapshot, clock=None):
    """Ready-to-inject ``ProfileService`` and ``CheckService`` for ``aplomb.api.services.Services``:

        profiles, checks = build_domain_services(profile_repo, lambda: store.open(version))
        services = Services(profiles=profiles, checks=checks, ...)
    """
    from aplomb.profiles.service import ProfileServiceImpl

    from .check import CheckServiceImpl

    profiles = ProfileServiceImpl(profile_repository, snapshot, clock=clock, deriver=deriver, proposer=proposer)
    return profiles, CheckServiceImpl(profiles, snapshot, clock=clock)
